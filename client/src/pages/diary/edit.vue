<script setup>
/**
 * 穿搭日记编辑页
 * 仅允许修改 mood 和 content（后端 WearLogService.update_log 也只改这两个字段）
 */
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { get, put } from '@/utils/request'
import { MOODS } from '@/utils/constants'

const logId = ref(null)
const loading = ref(true)
const loadError = ref(false)
const saving = ref(false)

// 表单字段
const detail = ref(null)   // 原始详情（含衣物缩略图等只读信息）
const selectedMood = ref('')
const content = ref('')

async function loadDetail(id) {
  loading.value = true
  loadError.value = false
  try {
    const data = await get(`/api/wear-logs/${id}`)
    detail.value = data
    selectedMood.value = data.mood || ''
    content.value = data.content || ''
  } catch (e) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function toggleMood(label) {
  selectedMood.value = selectedMood.value === label ? '' : label
}

const contentLen = computed(() => content.value.length)

async function save() {
  if (saving.value) return
  if (content.value.length > 100) {
    uni.showToast({ title: '一句话最多 100 字', icon: 'none' })
    return
  }
  saving.value = true
  try {
    await put(`/api/wear-logs/${logId.value}`, {
      mood: selectedMood.value || null,
      content: content.value.trim() || null
    })
    uni.showToast({ title: '已保存', icon: 'success' })
    setTimeout(() => uni.navigateBack({ delta: 1 }), 600)
  } catch (e) {
    // request.js 已 toast
  } finally {
    saving.value = false
  }
}

onLoad((options) => {
  const id = Number(options?.log_id)
  if (!id) {
    uni.showToast({ title: '参数错误', icon: 'none' })
    setTimeout(() => uni.navigateBack({ delta: 1 }), 500)
    return
  }
  logId.value = id
  loadDetail(id)
})
</script>

<template>
  <view class="page">
    <!-- 加载中 -->
    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="loadError" class="loading">
      加载失败
      <button class="btn-primary" style="margin-top:24rpx;width:280rpx" @click="loadDetail(logId)">重试</button>
    </view>

    <template v-else-if="detail">
      <!-- 顶部：搭配概览 -->
      <view class="card">
        <view class="section-title">今日穿搭</view>
        <view v-if="detail.items && detail.items.length" class="items-grid">
          <view v-for="item in detail.items" :key="item.item_id" class="item-box">
            <view class="thumb"><SafeImage :src="item.image_url" /></view>
            <view class="item-meta">
              <text class="item-type">{{ item.type }}</text>
              <text class="item-color">{{ item.color || '—' }}</text>
            </view>
          </view>
        </view>
        <view class="hint">照片和衣物不能在这里改。若要换一套，请在时间轴删除后重新打卡。</view>
        <view class="date-row">
          <text class="date-label">穿搭日期</text>
          <text class="date-val">{{ detail.wear_date }}</text>
          <text v-if="detail.weather || detail.temperature != null" class="weather-val">
            · {{ detail.weather || '' }}{{ detail.temperature != null ? ' ' + detail.temperature + '℃' : '' }}
          </text>
        </view>
      </view>

      <!-- 心情 -->
      <view class="card">
        <view class="section-title">心情</view>
        <view class="mood-grid">
          <view
            v-for="m in MOODS"
            :key="m.label"
            class="mood-cell"
            :class="{ active: selectedMood === m.label }"
            @click="toggleMood(m.label)"
          >
            <text class="mood-icon">{{ m.icon }}</text>
            <text class="mood-label">{{ m.label }}</text>
          </view>
        </view>
      </view>

      <!-- 一句话日记 -->
      <view class="card">
        <view class="section-title">
          一句话日记（选填）
          <text class="counter">{{ contentLen }}/100</text>
        </view>
        <textarea
          class="textarea"
          v-model="content"
          :maxlength="100"
          placeholder="今天穿这套是什么感觉？"
          placeholder-class="ph"
          auto-height
        />
      </view>

      <!-- 保存 -->
      <view class="footer">
        <button class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 24rpx 24rpx 200rpx;
  background: #f4f7fb;
  box-sizing: border-box;
}

.loading {
  text-align: center;
  padding: 200rpx 0;
  color: #a4b0be;
  font-size: 28rpx;
}

.card {
  background: #ffffff;
  border-radius: 24rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 24rpx rgba(61, 90, 128, 0.06);
}

.section-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #3d5a80;
  margin-bottom: 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.hint {
  font-size: 22rpx;
  color: #8a7f88;
  line-height: 1.5;
  margin-bottom: 16rpx;
}

.counter {
  font-size: 22rpx;
  font-weight: 400;
  color: #a4b0be;
}

/* ---------- 搭配概览 ---------- */
.items-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  margin-bottom: 24rpx;
}

.item-box {
  width: 150rpx;
}

.thumb {
  width: 150rpx;
  height: 150rpx;
  border-radius: 16rpx;
  background: #eef3f9;
}

.item-meta {
  margin-top: 8rpx;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.item-type {
  font-size: 24rpx;
  color: #2b3441;
}

.item-color {
  font-size: 20rpx;
  color: #a4b0be;
}

.date-row {
  padding-top: 20rpx;
  border-top: 1rpx solid #eef3f9;
  font-size: 24rpx;
  color: #7b8794;
  display: flex;
  align-items: baseline;
  gap: 8rpx;
  flex-wrap: wrap;
}

.date-label {
  color: #a4b0be;
}

.date-val {
  color: #2b3441;
  font-weight: 500;
}

.weather-val {
  color: #5b8def;
}

/* ---------- 心情网格 ---------- */
.mood-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16rpx;
}

.mood-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24rpx 0;
  border-radius: 20rpx;
  background: #f4f7fb;
  transition: all 0.2s;
  border: 2rpx solid transparent;
}

.mood-cell.active {
  background: linear-gradient(135deg, #e8f0ff, #f4f7fb);
  border-color: #5b8def;
}

.mood-icon {
  font-size: 48rpx;
  line-height: 1;
}

.mood-label {
  font-size: 22rpx;
  color: #2b3441;
  margin-top: 8rpx;
}

.mood-cell.active .mood-label {
  color: #5b8def;
  font-weight: 500;
}

/* ---------- 输入框 ---------- */
.textarea {
  width: 100%;
  min-height: 160rpx;
  font-size: 28rpx;
  color: #2b3441;
  line-height: 1.6;
  padding: 20rpx;
  background: #f8fafd;
  border-radius: 16rpx;
  box-sizing: border-box;
}

.ph {
  color: #a4b0be;
}

/* ---------- 保存按钮 ---------- */
.footer {
  position: fixed;
  left: 24rpx;
  right: 24rpx;
  bottom: 60rpx;
}

.btn-primary {
  background: linear-gradient(135deg, #5b8def, #7aa2cc);
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 600;
  border-radius: 999rpx;
  padding: 24rpx 0;
  border: none;
  width: 100%;
  box-shadow: 0 8rpx 32rpx rgba(91, 141, 239, 0.3);
}

.btn-primary::after {
  border: none;
}

.btn-primary[disabled] {
  opacity: 0.6;
}
</style>
