<script setup>
/**
 * 轻量穿搭日记页
 *
 * 两步提交（无论「跳过」还是「完成」）：
 *   1. POST /api/outfits           临时搭配，拿 outfit_id
 *   2. POST /api/wear-logs          记录今日穿搭（increase_wear_count: true）
 *
 * 后端模型允许 outfit_id = NULL（临时组合），但当前 WearLogService.create 强制要求
 * outfit_id，所以必须先建 outfit 再建 wear_log。临时搭配不命名，name 传 null。
 */
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { post, uploadFile } from '@/utils/request'
import { useOutfitStore } from '@/store/outfit'
import { MOODS } from '@/utils/constants'

const store = useOutfitStore()

const selectedMood = ref('')
const content = ref('')
const previewPath = ref('')   // 现场照片本地预览
const photoUrl = ref('')      // 上传后的服务器 URL
const uploading = ref(false)
const submitting = ref(false)

onLoad(() => {
  // 理论上 store 在搭配选择页已经填好，这里兜底；空了就提示返回
  if (store.isEmpty) {
    uni.showToast({ title: '请先选衣物', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 600)
  }
})

// ---------- 现场照片 ----------
function choosePhoto() {
  if (uploading.value) return
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    sourceType: ['album', 'camera'],
    success: async (res) => {
      const path = res.tempFilePaths[0]
      previewPath.value = path
      photoUrl.value = ''
      uploading.value = true
      uni.showLoading({ title: '上传中...', mask: true })
      try {
        const data = await uploadFile(path)
        photoUrl.value = data.url
      } catch (e) {
        previewPath.value = ''
      } finally {
        uploading.value = false
        uni.hideLoading()
      }
    }
  })
}

function previewPhoto() {
  if (previewPath.value) {
    uni.previewImage({ urls: [previewPath.value], current: previewPath.value })
  }
}

// ---------- 提交 ----------
async function submit(hasContent) {
  if (store.isEmpty) {
    uni.showToast({ title: '请先选衣物', icon: 'none' })
    return
  }
  if (submitting.value) return

  // 照片还在上传：让用户决定等不等
  if (uploading.value) {
    uni.showModal({
      title: '现场照片还在上传',
      content: '等一下再提交，还是不带照片先记？',
      confirmText: '等一下',
      cancelText: '不带照片',
      success: (r) => {
        if (r.cancel) {
          // 用户选择不带照片：清空照片状态，后续流程照常
          photoUrl.value = ''
          previewPath.value = ''
          _doSubmit(hasContent)
        }
      },
    })
    return
  }

  _doSubmit(hasContent)
}

/** 真正执行提交（submit 做前置校验，这里做两步 API 串联） */
async function _doSubmit(hasContent) {
  submitting.value = true
  uni.showLoading({ title: '记录中...', mask: true })
  try {
    // Step 1: 先建临时搭配
    const outfit = await post('/api/outfits', {
      item_ids: store.selectedItemIds,
      name: null,
    })

    // Step 2: 再建穿搭日记
    const payload = {
      outfit_id: outfit.outfit_id,
      increase_wear_count: true,
    }
    if (hasContent) {
      // 「完成」模式：只把用户实际填了的字段传给后端
      payload.mood = selectedMood.value || null
      payload.content = content.value.trim() || null
      payload.photo_url = photoUrl.value || null
    }

    await post('/api/wear-logs', payload)

    // 成功后清空 store 并跳到时间轴
    store.clearSelected()
    uni.hideLoading()
    uni.showToast({ title: '已记录今日穿搭', icon: 'success' })
    // switchTab 用于 tabBar 页；延时保证 toast 可显
    setTimeout(() => uni.switchTab({ url: '/pages/timeline/index' }), 700)
  } catch (e) {
    // request.js 已经 toast 了具体原因，这里只需收尾
  } finally {
    submitting.value = false
    uni.hideLoading()
  }
}

function skip() {
  submit(false)
}

function finish() {
  // 完成模式：允许 mood 留空，content 和 photo_url 都可以空串（后端统一转 null）
  if (content.value.length > 100) {
    uni.showToast({ title: '一句话最多 100 字', icon: 'none' })
    return
  }
  submit(true)
}
</script>

<template>
  <view class="container">
    <!-- 当前搭配缩略图 -->
    <view class="card">
      <view class="label">今日搭配 · {{ store.selectedItems.length }} 件</view>
      <view class="outfit-thumbs">
        <image
          v-for="it in store.selectedItems"
          :key="it.item_id"
          :src="it.image_url"
          mode="aspectFill"
          class="outfit-thumb"
        />
      </view>
    </view>

    <!-- 心情 -->
    <view class="card">
      <view class="label">今日心情 <text class="hint">（可跳过）</text></view>
      <view class="mood-grid">
        <view
          v-for="m in MOODS"
          :key="m.label"
          class="mood-cell"
          :class="{ active: selectedMood === m.label }"
          @click="selectedMood = selectedMood === m.label ? '' : m.label"
        >
          <view class="mood-icon">{{ m.icon }}</view>
          <view class="mood-label">{{ m.label }}</view>
        </view>
      </view>
    </view>

    <!-- 一句话 + 现场照片 -->
    <view class="card">
      <view class="label">一句话日记 <text class="hint">（选填，最多 100 字）</text></view>
      <textarea
        class="textarea"
        v-model="content"
        placeholder="今天穿得舒服/有点冷/被夸好看…"
        placeholder-class="ph"
        maxlength="100"
      />
      <view class="count">{{ content.length }}/100</view>

      <view class="label mt">现场照片 <text class="hint">（选填，最多 1 张）</text></view>
      <view v-if="!previewPath" class="photo-picker" @click="choosePhoto">
        <text class="plus">＋</text>
        <text class="picker-tip">拍照 / 相册</text>
      </view>
      <view v-else class="photo-preview">
        <image class="photo-img" :src="previewPath" mode="aspectFill" @click="previewPhoto" />
        <view v-if="uploading" class="photo-mask">上传中…</view>
        <view class="photo-ops">
          <text class="op" @click="choosePhoto">重新选</text>
          <text class="op" @click="previewPhoto">预览</text>
        </view>
      </view>
    </view>

    <!-- 底部操作 -->
    <view class="actions">
      <button class="btn-ghost action-btn" :disabled="submitting" @click="skip">跳过</button>
      <button class="btn-primary action-btn" :disabled="submitting" @click="finish">完成</button>
    </view>
    <view class="actions-tip">跳过也会记录今日穿搭，稍后可在时间轴补充心情</view>
  </view>
</template>

<style scoped>
.hint {
  font-size: 24rpx;
  color: #a4b0be;
  font-weight: normal;
}
.mt {
  margin-top: 28rpx;
}

/* ---------- 搭配缩略图 ---------- */
.outfit-thumbs {
  display: flex;
  gap: 16rpx;
  margin-top: 16rpx;
  flex-wrap: wrap;
}
.outfit-thumb {
  width: 120rpx;
  height: 120rpx;
  border-radius: 14rpx;
  background: #eef3f9;
}

/* ---------- 心情 ---------- */
.mood-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  margin-top: 12rpx;
}
.mood-cell {
  width: calc((100% - 48rpx) / 4);
  background: #fbfcfe;
  border: 1rpx solid #d7e0ea;
  border-radius: 14rpx;
  padding: 20rpx 0;
  text-align: center;
  transition: all 0.15s ease;
}
.mood-cell.active {
  border-color: #5b8def;
  background: #e8f0ff;
}
.mood-icon {
  font-size: 48rpx;
  line-height: 1;
}
.mood-label {
  font-size: 24rpx;
  color: #2b3441;
  margin-top: 8rpx;
}
.mood-cell.active .mood-label {
  color: #5b8def;
  font-weight: 600;
}

/* ---------- 一句话 + 照片 ---------- */
.textarea {
  width: 100%;
  box-sizing: border-box;
  height: 160rpx;
  background: #fbfcfe;
  border: 1rpx solid #d7e0ea;
  border-radius: 14rpx;
  padding: 20rpx 24rpx;
  font-size: 28rpx;
}
.count {
  text-align: right;
  font-size: 22rpx;
  color: #a4b0be;
  margin-top: 8rpx;
}
.ph {
  color: #a4b0be;
}

.photo-picker {
  height: 240rpx;
  background: #fbfcfe;
  border: 2rpx dashed #cfdbe7;
  border-radius: 16rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.plus {
  font-size: 56rpx;
  color: #a9c1dd;
  line-height: 1;
}
.picker-tip {
  margin-top: 12rpx;
  font-size: 24rpx;
  color: #a4b0be;
}

.photo-preview {
  position: relative;
}
.photo-img {
  width: 100%;
  height: 360rpx;
  border-radius: 16rpx;
  background: #eef3f9;
}
.photo-mask {
  position: absolute;
  inset: 0;
  background: rgba(43, 52, 65, 0.45);
  color: #fff;
  font-size: 26rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16rpx;
}
.photo-ops {
  display: flex;
  gap: 32rpx;
  margin-top: 14rpx;
}
.op {
  font-size: 26rpx;
  color: #5b8def;
}

/* ---------- 底部 ---------- */
.actions {
  display: flex;
  gap: 20rpx;
  margin-top: 40rpx;
}
.action-btn {
  flex: 1;
  height: 88rpx;
  line-height: 88rpx;
  font-size: 30rpx;
}
.actions-tip {
  margin-top: 20rpx;
  text-align: center;
  font-size: 22rpx;
  color: #a4b0be;
}
</style>
