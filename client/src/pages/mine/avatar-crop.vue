<script setup>
/**
 * 裁剪头像
 * 入口：编辑资料页选图后 uni.navigateTo 到这里，通过事件通道传入 { src }，
 *       裁好后 emit('cropped', 本地临时路径) 并返回
 *
 * 交互：圆形取景框（框外变暗）；拖动图片调整位置；下方滑杆放大缩小
 * 实现：movable-area 就是取景正方形（边长 BOX），movable-view 是图片，
 *       图片尺寸始终不小于取景框，movable-view 会自动限制拖动范围，保证框内没有空白
 *       缩放通过改变图片显示宽高实现（不用 movable-view 自带的 scale，便于换算坐标）
 * 导出：按框内区域对应到原图的矩形，用 canvas 画成 OUT×OUT，再 canvasToTempFilePath
 */
import { ref, computed, getCurrentInstance } from 'vue'
import { onLoad } from '@dcloudio/uni-app'

const OUT = 512            // 导出头像边长（px）
const MAX_ZOOM = 4

const instance = getCurrentInstance()
// 取景框边长（px），两侧各留 32；页面加载时再量一次窗口宽度（个别环境创建页面时宽度会读成 0）
const BOX = ref(280)
function measureBox() {
  const w = uni.getSystemInfoSync().windowWidth || 0
  BOX.value = w > 120 ? Math.round(Math.min(w, 480) - 64) : 280
}
measureBox()

const src = ref('')
const imgW = ref(0)        // 原图宽高
const imgH = ref(0)
const zoom = ref(1)        // 1 = 刚好铺满取景框
const x = ref(0)           // 图片左上角相对取景框的位置（px，≤ 0）
const y = ref(0)
const ready = ref(false)
const exporting = ref(false)
let channel = null

// 缩放为 1 时图片铺满取景框的尺寸（短边 = BOX）
const baseW = computed(() => (imgW.value >= imgH.value ? BOX.value * imgW.value / imgH.value : BOX.value))
const baseH = computed(() => (imgW.value >= imgH.value ? BOX.value : BOX.value * imgH.value / imgW.value))
const viewW = computed(() => baseW.value * zoom.value)
const viewH = computed(() => baseH.value * zoom.value)

function clamp(v, min, max) {
  return Math.min(Math.max(v, min), max)
}

function center() {
  x.value = (BOX.value - viewW.value) / 2
  y.value = (BOX.value - viewH.value) / 2
}

onLoad(() => {
  measureBox()
  channel = instance.proxy.getOpenerEventChannel && instance.proxy.getOpenerEventChannel()
  if (!channel) return
  channel.on('init', ({ src: path }) => {
    src.value = path
    uni.getImageInfo({
      src: path,
      success: (info) => {
        imgW.value = info.width
        imgH.value = info.height
        zoom.value = 1
        center()
        ready.value = true
      },
      fail: () => {
        uni.showToast({ title: '图片读取失败，请换一张', icon: 'none' })
        setTimeout(() => uni.navigateBack(), 800)
      }
    })
  })
})

// 拖动：只记录手指拖出来的位置，程序设置 x/y 时也会触发 change，忽略
function onMove(e) {
  const d = e.detail || {}
  if (d.source !== 'touch' && d.source !== 'touch-out-of-bounds') return
  x.value = d.x
  y.value = d.y
}

// 缩放：以取景框中心为基准，保持中心不动，再夹到合法范围
function onZoom(e) {
  const next = Number(e.detail.value) / 100
  const box = BOX.value
  const cx = (box / 2 - x.value) / viewW.value      // 取景框中心落在图片上的相对位置
  const cy = (box / 2 - y.value) / viewH.value
  zoom.value = clamp(next, 1, MAX_ZOOM)
  x.value = clamp(box / 2 - cx * viewW.value, box - viewW.value, 0)
  y.value = clamp(box / 2 - cy * viewH.value, box - viewH.value, 0)
}

function toBlobUrl(path) {
  // H5 的 canvasToTempFilePath 可能给 base64，转成 blob 地址后 uploadFile 才能用
  // #ifdef H5
  if (path.startsWith('data:')) {
    return fetch(path).then((r) => r.blob()).then((b) => URL.createObjectURL(b))
  }
  // #endif
  return Promise.resolve(path)
}

function confirmCrop() {
  if (!ready.value || exporting.value) return
  exporting.value = true
  uni.showLoading({ title: '裁剪中...', mask: true })
  // 取景框对应到原图上的矩形
  const ratio = imgW.value / viewW.value
  const sx = clamp(-x.value * ratio, 0, imgW.value)
  const sy = clamp(-y.value * ratio, 0, imgH.value)
  const sw = Math.min(BOX.value * ratio, imgW.value - sx)
  const sh = Math.min(BOX.value * ratio, imgH.value - sy)

  const ctx = uni.createCanvasContext('avatarCanvas', instance.proxy)
  ctx.setFillStyle('#ffffff')
  ctx.fillRect(0, 0, OUT, OUT)
  ctx.drawImage(src.value, sx, sy, sw, sh, 0, 0, OUT, OUT)
  ctx.draw(false, () => {
    uni.canvasToTempFilePath({
      canvasId: 'avatarCanvas',
      x: 0,
      y: 0,
      width: OUT,
      height: OUT,
      destWidth: OUT,
      destHeight: OUT,
      fileType: 'jpg',
      quality: 0.92,
      success: async (res) => {
        const path = await toBlobUrl(res.tempFilePath)
        uni.hideLoading()
        exporting.value = false
        if (channel) channel.emit('cropped', path)
        uni.navigateBack()
      },
      fail: () => {
        uni.hideLoading()
        exporting.value = false
        uni.showToast({ title: '裁剪失败，请重试', icon: 'none' })
      }
    }, instance.proxy)
  })
}

function rechoose() {
  if (channel) channel.emit('rechoose')
  uni.navigateBack()
}
</script>

<template>
  <view class="page">
    <view class="tip">拖动图片调整位置，拖动下方滑杆放大缩小</view>

    <view class="stage" :style="{ width: BOX + 'px', height: BOX + 'px' }">
      <movable-area class="area" :style="{ width: BOX + 'px', height: BOX + 'px' }">
        <movable-view
          v-if="ready"
          class="view"
          direction="all"
          :x="x"
          :y="y"
          :style="{ width: viewW + 'px', height: viewH + 'px' }"
          @change="onMove"
        >
          <image class="img" :src="src" mode="scaleToFill" />
        </movable-view>
      </movable-area>
      <!-- 圆形取景：框外用超大阴影压暗，不挡拖动 -->
      <view class="mask" />
    </view>

    <view class="zoom">
      <text class="zoom-ico">－</text>
      <slider
        class="slider"
        :min="100"
        :max="MAX_ZOOM * 100"
        :value="Math.round(zoom * 100)"
        activeColor="#ff8fb1"
        block-color="#ff8fb1"
        :block-size="22"
        @changing="onZoom"
        @change="onZoom"
      />
      <text class="zoom-ico">＋</text>
    </view>

    <view class="actions">
      <view class="act ghost press-bounce" @click="rechoose">重新选择</view>
      <view class="act primary press-bounce" :class="{ off: !ready || exporting }" @click="confirmCrop">使用这张</view>
    </view>

    <!-- 导出用的画布，放在屏幕外 -->
    <canvas canvas-id="avatarCanvas" class="canvas" :style="{ width: OUT + 'px', height: OUT + 'px' }" />
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 32rpx 0 calc(160rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
  background: #2b2427;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow: hidden;
}
.tip {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 48rpx;
}
.stage {
  position: relative;
}
.area {
  overflow: visible;
}
.view {
  will-change: transform;
}
.img {
  width: 100%;
  height: 100%;
  display: block;
}
.mask {
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  border-radius: 50%;
  border: 4rpx solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 0 0 2000px rgba(20, 14, 16, 0.6);
  pointer-events: none;
}
.zoom {
  width: 80%;
  display: flex;
  align-items: center;
  margin-top: 64rpx;
}
.zoom-ico {
  color: rgba(255, 255, 255, 0.8);
  font-size: 32rpx;
  padding: 0 12rpx;
}
.slider {
  flex: 1;
}
.actions {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  gap: 20rpx;
  padding: 18rpx 32rpx calc(18rpx + env(safe-area-inset-bottom));
  background: #2b2427;
}
.act {
  height: 84rpx;
  line-height: 84rpx;
  text-align: center;
  border-radius: 999rpx;
  font-size: 30rpx;
  font-weight: 700;
}
.act.ghost {
  padding: 0 40rpx;
  color: #fff;
  border: 2rpx solid rgba(255, 255, 255, 0.5);
}
.act.primary {
  flex: 1;
  color: #fff;
  background: linear-gradient(180deg, #ffb3c9 0%, #ff8fb1 72%);
}
.act.primary.off {
  opacity: 0.5;
}
.canvas {
  position: fixed;
  left: -9999px;
  top: 0;
}
</style>
