<script setup>
/**
 * 手动搭配画布
 *   上：正方形画布（movable-area），衣服可拖动；选中后可放大 / 缩小 / 置顶 / 移除
 *   下：衣橱抽屉，按分类横向滑动，点一下把衣服放到画布上（再点一下从画布拿走）
 *   底部「用这套去打卡」→ 带着衣物和画布布局进入日记页，记录后出现在时间轴
 *
 * 入口：
 *   - /pages/outfit/canvas                 空白画布，自己搭
 *   - /pages/outfit/canvas?from=recommend  首页智能推荐进入：按衣物类型自动摆好，
 *                                          顶部多一个「换一套推荐」按钮
 *
 * 用 movable-area / movable-view 实现拖动：H5 与微信小程序都原生支持，不引入新依赖。
 * 布局以「相对画布边长的比例」保存（x / y / w 都是 0~1），换屏幕尺寸也能还原。
 */
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { get } from '@/utils/request'
import { useOutfitStore } from '@/store/outfit'
import { ITEM_TYPES } from '@/utils/constants'
import SafeImage from '@/components/SafeImage.vue'

const MAX_PIECES = 12          // 与后端一次记录最多 12 件保持一致
const MIN_RATIO = 0.18         // 单件最小 / 最大占画布边长的比例
const MAX_RATIO = 0.9
const DEFAULT_RATIO = 0.42

const store = useOutfitStore()

// ---------- 画布尺寸（px） ----------
const sys = uni.getSystemInfoSync()
const rpx = sys.windowWidth / 750
const side = Math.round(sys.windowWidth - 48 * rpx)

// ---------- 画布上的衣服 ----------
// 每件：{ item_id, image_url, type, color, season, x, y, size, z }（x / y / size 单位 px）
const pieces = ref([])
const selectedId = ref(null)

// ---------- 来自智能推荐 ----------
const fromRecommend = ref(false)
const touched = ref(false)       // 推荐摆好后，用户是否手动调整过

/**
 * 按衣物类型给出默认摆放位置（相对画布边长的比例）
 * 上装 / 外套在上方，下装 / 连衣裙在中下方，鞋包帽配饰放四周
 */
const SLOT = {
  外套: { x: 0.08, y: 0.03, w: 0.5, z: 1 },
  上装: { x: 0.3, y: 0.06, w: 0.46, z: 2 },
  连衣裙: { x: 0.28, y: 0.1, w: 0.56, z: 2 },
  下装: { x: 0.3, y: 0.45, w: 0.46, z: 3 },
  鞋子: { x: 0.66, y: 0.7, w: 0.3, z: 4 },
  包包: { x: 0.04, y: 0.6, w: 0.32, z: 4 },
  帽子: { x: 0.66, y: 0.02, w: 0.28, z: 5 },
  配饰: { x: 0.04, y: 0.36, w: 0.26, z: 5 }
}

function layoutCombo(items) {
  const used = {}
  pieces.value = items.slice(0, MAX_PIECES).map((item, i) => {
    const base = SLOT[item.type] || { x: 0.3, y: 0.3, w: 0.4, z: 1 }
    const n = used[item.type] || 0          // 同类型多件时依次错开
    used[item.type] = n + 1
    const p = {
      item_id: item.item_id,
      image_url: item.image_url,
      type: item.type,
      color: item.color,
      season: item.season,
      size: Math.round(side * base.w),
      x: side * base.x + n * 30,
      y: side * base.y + n * 30,
      z: base.z * 10 + i
    }
    clampPos(p)
    return p
  })
  selectedId.value = null
  touched.value = false
}

function showRecommend(index) {
  const list = store.recommendList
  if (!list.length) return
  const i = ((index % list.length) + list.length) % list.length
  store.recommendIndex = i
  layoutCombo(list[i].items || [])
}

function nextRecommend() {
  const list = store.recommendList
  if (list.length <= 1) {
    uni.showToast({ title: '目前只有这一套推荐哦', icon: 'none' })
    return
  }
  const doSwitch = () => {
    const next = store.recommendIndex + 1
    if (next >= list.length) uni.showToast({ title: '已经是全部推荐啦，从第一套重新看', icon: 'none' })
    showRecommend(next)
  }
  if (!touched.value) {
    doSwitch()
    return
  }
  uni.showModal({
    title: '换一套推荐',
    content: '换一套会丢掉你刚才的调整，确定吗？',
    confirmColor: '#ff8fb1',
    success: (res) => { if (res.confirm) doSwitch() }
  })
}

const recommendLabel = computed(() => {
  const n = store.recommendList.length
  return n ? `推荐 ${store.recommendIndex + 1}/${n}` : ''
})

const selected = computed(() => pieces.value.find((p) => p.item_id === selectedId.value) || null)
const onCanvasIds = computed(() => new Set(pieces.value.map((p) => p.item_id)))

function clampPos(p) {
  const max = Math.max(0, side - p.size)
  p.x = Math.min(Math.max(p.x, 0), max)
  p.y = Math.min(Math.max(p.y, 0), max)
}

function addPiece(item) {
  if (onCanvasIds.value.has(item.item_id)) {
    removePiece(item.item_id)
    return
  }
  if (pieces.value.length >= MAX_PIECES) {
    uni.showToast({ title: `最多放 ${MAX_PIECES} 件哦`, icon: 'none' })
    return
  }
  const size = Math.round(side * DEFAULT_RATIO)
  const n = pieces.value.length
  // 新衣服从中间偏上开始，依次错开一点，避免完全叠在一起
  const piece = {
    item_id: item.item_id,
    image_url: item.image_url,
    type: item.type,
    color: item.color,
    season: item.season,
    size,
    x: (side - size) / 2 + ((n % 4) - 1.5) * 24,
    y: (side - size) / 2 + (Math.floor(n / 4) - 1) * 24,
    z: nextZ()
  }
  clampPos(piece)
  pieces.value.push(piece)
  selectedId.value = item.item_id
  touched.value = true
}

function removePiece(itemId) {
  touched.value = true
  pieces.value = pieces.value.filter((p) => p.item_id !== itemId)
  if (selectedId.value === itemId) selectedId.value = null
}

function nextZ() {
  return pieces.value.reduce((m, p) => Math.max(m, p.z), 0) + 1
}

function onMove(e, p) {
  // 只记录手指拖动产生的位置；程序设置 x/y 时也会触发 change，忽略即可
  if (e.detail.source !== 'touch' && e.detail.source !== 'touch-out-of-bounds') return
  p.x = e.detail.x
  p.y = e.detail.y
  touched.value = true
}

function select(p) {
  selectedId.value = p.item_id
}

function resize(delta) {
  const p = selected.value
  if (!p) return
  const next = Math.round(p.size + side * delta)
  p.size = Math.min(Math.max(next, side * MIN_RATIO), side * MAX_RATIO)
  clampPos(p)
  touched.value = true
}

function bringToFront() {
  const p = selected.value
  if (p) {
    p.z = nextZ()
    touched.value = true
  }
}

function clearCanvas() {
  if (!pieces.value.length) return
  uni.showModal({
    title: '清空画布',
    content: '把画布上的衣服都拿下来吗？',
    confirmColor: '#ff8fb1',
    success: (res) => {
      if (res.confirm) {
        pieces.value = []
        selectedId.value = null
        touched.value = true
      }
    }
  })
}

// ---------- 衣橱抽屉 ----------
const CATEGORIES = [{ label: '全部', value: '' }, ...ITEM_TYPES.map((t) => ({ label: t, value: t }))]
const currentType = ref('')
const shelf = ref([])
const shelfLoading = ref(false)
const cache = {}               // 分类 → 衣物列表，切换分类时不重复请求

async function loadShelf(type) {
  currentType.value = type
  if (cache[type]) {
    shelf.value = cache[type]
    return
  }
  shelfLoading.value = true
  try {
    const params = { page: 1, per_page: 50 }
    if (type) params.type = type
    const data = await get('/api/items', params)
    cache[type] = data.list || []
    if (currentType.value === type) shelf.value = cache[type]
  } catch (e) {
    shelf.value = []
  } finally {
    shelfLoading.value = false
  }
}

onLoad((query = {}) => {
  loadShelf('')
  if (query.from === 'recommend' && store.recommendList.length) {
    fromRecommend.value = true
    uni.setNavigationBarTitle({ title: '推荐搭配' })
    showRecommend(store.recommendIndex)
  }
})

// ---------- 去打卡 ----------
function goDiary() {
  if (!pieces.value.length) {
    uni.showToast({ title: '先往画布上放几件衣服吧', icon: 'none' })
    return
  }
  const ordered = [...pieces.value].sort((a, b) => a.z - b.z)
  const collage = ordered.map((p, i) => ({
    item_id: p.item_id,
    x: +(p.x / side).toFixed(4),
    y: +(p.y / side).toFixed(4),
    w: +(p.size / side).toFixed(4),
    z: i + 1
  }))
  store.setOutfit(ordered, collage)
  uni.navigateTo({ url: '/pages/diary/create' })
}

function goAdd() {
  // 衣橱为空时引导去添加
  uni.navigateTo({ url: '/pages/item/add' })
}
</script>

<template>
  <view class="page">
    <view v-if="fromRecommend" class="rec-bar">
      <text class="rec-label">✨ 桃桃{{ recommendLabel }}</text>
      <view class="rec-btn" @click="nextRecommend">🔄 换一套推荐</view>
    </view>

    <view class="tip-line">
      <text>拖动摆位置 · 点衣服可放大缩小</text>
      <text class="clear" :class="{ off: !pieces.length }" @click="clearCanvas">清空</text>
    </view>

    <!-- 画布 -->
    <movable-area
      class="canvas"
      :style="{ width: side + 'px', height: side + 'px' }"
      @click="selectedId = null"
    >
      <movable-view
        v-for="p in pieces"
        :key="p.item_id"
        class="piece"
        :class="{ sel: selectedId === p.item_id }"
        direction="all"
        :x="p.x"
        :y="p.y"
        :style="{ width: p.size + 'px', height: p.size + 'px', zIndex: p.z }"
        @change="onMove($event, p)"
        @touchstart="select(p)"
        @click.stop="select(p)"
      >
        <image class="piece-img" :src="p.image_url" mode="aspectFit" />
      </movable-view>

      <view v-if="!pieces.length" class="canvas-empty">
        <view class="ce-ico">🧺</view>
        <view>点下面的衣服，放到画布上搭一搭～</view>
      </view>
    </movable-area>

    <!-- 选中衣服的工具条 -->
    <view class="tools" :class="{ off: !selected }">
      <view class="tool" @click="resize(-0.08)">－ 缩小</view>
      <view class="tool" @click="resize(0.08)">＋ 放大</view>
      <view class="tool" @click="bringToFront">⇧ 置顶</view>
      <view class="tool danger" @click="selected && removePiece(selected.item_id)">✕ 拿走</view>
    </view>

    <!-- 衣橱抽屉 -->
    <view class="drawer">
      <scroll-view scroll-x class="cats" :show-scrollbar="false">
        <view
          v-for="cat in CATEGORIES"
          :key="cat.label"
          class="cat"
          :class="{ on: currentType === cat.value }"
          @click="loadShelf(cat.value)"
        >{{ cat.label }}</view>
      </scroll-view>

      <scroll-view scroll-x class="shelf" :show-scrollbar="false">
        <view
          v-for="item in shelf"
          :key="item.item_id"
          class="shelf-item"
          :class="{ on: onCanvasIds.has(item.item_id) }"
          @click="addPiece(item)"
        >
          <view class="shelf-img"><SafeImage :src="item.image_url" mode="aspectFit" /></view>
          <view v-if="onCanvasIds.has(item.item_id)" class="check">✓</view>
          <view class="shelf-name">{{ item.type }}{{ item.color ? '·' + item.color : '' }}</view>
        </view>
        <view v-if="!shelfLoading && !shelf.length" class="shelf-empty" @click="goAdd">
          这里还没有衣服，点我去添加 ›
        </view>
        <view v-if="shelfLoading && !shelf.length" class="shelf-empty">加载中…</view>
      </scroll-view>
    </view>

    <view class="footer">
      <view class="count">已放 {{ pieces.length }} 件</view>
      <view class="go" :class="{ off: !pieces.length }" @click="goDiary">用这套去打卡 ✎</view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 16rpx 24rpx calc(150rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
  background: #fff8f5;
}
.rec-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14rpx;
  padding: 14rpx 18rpx;
  border-radius: 20rpx;
  background: linear-gradient(90deg, #ffe4ed, #fff4c8);
}
.rec-label {
  font-size: 26rpx;
  font-weight: 800;
  color: #382e36;
}
.rec-btn {
  padding: 10rpx 24rpx;
  border-radius: 999rpx;
  background: #ff8fb1;
  color: #fff;
  font-size: 24rpx;
  font-weight: 700;
  box-shadow: 0 6rpx 14rpx rgba(255, 143, 177, 0.35);
}
.tip-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 22rpx;
  color: #8a7f88;
  margin-bottom: 12rpx;
}
.clear {
  color: #ff8fb1;
  font-weight: 700;
}
.clear.off { color: #d9cfd5; }

/* ---------- 画布 ---------- */
.canvas {
  position: relative;
  border-radius: 28rpx;
  border: 3rpx dashed #f3b8c8;
  overflow: hidden;
  background:
    radial-gradient(circle, rgba(255, 143, 177, 0.22) 2rpx, transparent 2.5rpx) 0 0 / 32rpx 32rpx,
    #fffdfb;
  box-shadow: 0 10rpx 30rpx rgba(255, 150, 175, 0.12);
}
.piece {
  box-sizing: border-box;
  border: 3rpx solid transparent;
  border-radius: 16rpx;
}
.piece.sel {
  border: 3rpx dashed #ff8fb1;
  background: rgba(255, 240, 245, 0.35);
}
.piece-img {
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.canvas-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #b3a7b0;
  font-size: 24rpx;
  gap: 12rpx;
}
.ce-ico { font-size: 72rpx; }

/* ---------- 工具条 ---------- */
.tools {
  display: flex;
  gap: 12rpx;
  margin: 18rpx 0;
  transition: opacity 0.2s;
}
.tools.off {
  opacity: 0.35;
  pointer-events: none;
}
.tool {
  flex: 1;
  height: 64rpx;
  line-height: 64rpx;
  text-align: center;
  border-radius: 999rpx;
  background: #fffdfb;
  border: 2rpx solid #fbe3ea;
  font-size: 24rpx;
  color: #382e36;
}
.tool.danger { color: #e05c5c; }

/* ---------- 衣橱抽屉 ---------- */
.drawer {
  background: #fffdfb;
  border-radius: 28rpx;
  padding: 16rpx 0 20rpx;
  box-shadow: 0 10rpx 30rpx rgba(255, 150, 175, 0.1);
}
.cats {
  white-space: nowrap;
  padding: 0 16rpx;
  box-sizing: border-box;
}
.cat {
  display: inline-block;
  padding: 8rpx 22rpx;
  margin-right: 10rpx;
  border-radius: 999rpx;
  font-size: 24rpx;
  color: #8a7f88;
  background: #fff5f8;
}
.cat.on {
  background: #ff8fb1;
  color: #fff;
  font-weight: 700;
}
.shelf {
  white-space: nowrap;
  margin-top: 16rpx;
  padding: 0 16rpx;
  box-sizing: border-box;
}
.shelf-item {
  position: relative;
  display: inline-block;
  width: 160rpx;
  margin-right: 14rpx;
  vertical-align: top;
}
.shelf-img {
  width: 160rpx;
  height: 160rpx;
  border-radius: 18rpx;
  overflow: hidden;
  border: 3rpx solid #fbe3ea;
  box-sizing: border-box;
  background: #fff0f4;
}
.shelf-item.on .shelf-img { border-color: #ff8fb1; }
.check {
  position: absolute;
  top: 8rpx;
  right: 8rpx;
  width: 36rpx;
  height: 36rpx;
  line-height: 36rpx;
  text-align: center;
  border-radius: 50%;
  background: #ff8fb1;
  color: #fff;
  font-size: 22rpx;
}
.shelf-name {
  margin-top: 6rpx;
  font-size: 20rpx;
  color: #8a7f88;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.shelf-empty {
  display: inline-block;
  padding: 50rpx 20rpx;
  font-size: 24rpx;
  color: #b3a7b0;
}

/* ---------- 底部 ---------- */
.footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 18rpx 24rpx calc(18rpx + env(safe-area-inset-bottom));
  background: #fffdfb;
  box-shadow: 0 -8rpx 24rpx rgba(255, 150, 175, 0.1);
}
.count {
  font-size: 24rpx;
  color: #8a7f88;
}
.go {
  flex: 1;
  height: 84rpx;
  line-height: 84rpx;
  text-align: center;
  border-radius: 999rpx;
  color: #fff;
  font-size: 30rpx;
  font-weight: 700;
  background: linear-gradient(180deg, #ffb3c9 0%, #ff8fb1 72%);
  box-shadow: 0 10rpx 22rpx rgba(255, 143, 177, 0.35);
}
.go.off {
  background: #f3dde4;
  box-shadow: none;
}
</style>
