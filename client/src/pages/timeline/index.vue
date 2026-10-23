<script setup>
/**
 * 穿搭时间轴页面
 * 功能：
 *   1. 按日期倒序分页展示所有 wear_log
 *   2. 下拉刷新（onPullDownRefresh）、上拉加载更多（onReachBottom）
 *   3. 点击卡片 → action sheet（编辑 / 删除）
 *   4. 空状态精致引导
 */
import { ref, computed } from 'vue'
import { onShow, onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
import { get, del } from '@/utils/request'
import { MOODS } from '@/utils/constants'

const logs = ref([])
const page = ref(1)
const perPage = 10
const total = ref(0)
const loadingMore = ref(false)

// ---------- 工具函数 ----------

/** 心情 label → emoji（没匹配上就原样返回） */
function moodEmoji(label) {
  if (!label) return ''
  const found = MOODS.find((m) => m.label === label)
  return found ? found.icon : label
}

/**
 * 日期格式化：今天 → "今天"，昨天 → "昨天"，同年 → "MM月DD日"，跨年 → "YYYY年MM月DD日"
 * @param {string} s YYYY-MM-DD
 */
function friendlyDate(s) {
  if (!s) return ''
  const [y, m, d] = s.split('-').map(Number)
  const today = new Date()
  const ty = today.getFullYear()
  const tm = today.getMonth() + 1
  const td = today.getDate()

  if (y === ty && m === tm && d === td) return '今天'
  // 昨天（跨月跨年也算）
  const yest = new Date(today.getTime() - 86400000)
  if (y === yest.getFullYear() && m === yest.getMonth() + 1 && d === yest.getDate()) return '昨天'
  if (y === ty) return `${m}月${d}日`
  return `${y}年${m}月${d}日`
}

// ---------- 数据加载 ----------

async function fetchLogs(reset = true) {
  if (reset) {
    page.value = 1
  } else if (loadingMore.value) {
    return
  }
  loadingMore.value = !reset
  try {
    const data = await get('/api/wear-logs', {
      page: page.value,
      per_page: perPage
    })
    total.value = data.total
    logs.value = reset ? data.list : logs.value.concat(data.list)
  } catch (e) {
    // request.js 里已经 toast 过了
  } finally {
    loadingMore.value = false
  }
}

function loadMore() {
  if (logs.value.length >= total.value) return
  page.value += 1
  fetchLogs(false)
}

function refresh() {
  fetchLogs(true).finally(() => {
    uni.stopPullDownRefresh()
  })
}

// ---------- 卡片操作 ----------

function onCardTap(log) {
  uni.showActionSheet({
    itemList: ['编辑心情和日记', '删除这条记录'],
    success: (res) => {
      if (res.tapIndex === 0) editLog(log)
      if (res.tapIndex === 1) deleteLog(log)
    }
  })
}

function editLog(log) {
  uni.navigateTo({ url: `/pages/diary/edit?log_id=${log.log_id}` })
}

function deleteLog(log) {
  uni.showModal({
    title: '确认删除',
    content: `删除「${friendlyDate(log.wear_date)}」的穿搭日记？`,
    confirmColor: '#ff6b6b',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await del(`/api/wear-logs/${log.log_id}`)
        uni.showToast({ title: '已删除', icon: 'success' })
        fetchLogs(true)
      } catch (e) {
        // request.js 已 toast
      }
    }
  })
}

function goRecord() {
  uni.navigateTo({ url: '/pages/outfit/select' })
}

// ---------- 生命周期 ----------

onShow(() => {
  fetchLogs(true)
})

onPullDownRefresh(() => {
  refresh()
})

onReachBottom(() => {
  loadMore()
})

const hasMore = computed(() => logs.value.length < total.value)
</script>

<template>
  <view class="page">
    <!-- 有数据：时间轴列表 -->
    <view v-if="logs.length" class="list">
      <view
        v-for="log in logs"
        :key="log.log_id"
        class="card"
        @click="onCardTap(log)"
      >
        <!-- 顶部：日期 + 天气温度 + 心情 -->
        <view class="card-head">
          <view class="date-block">
            <view class="date-main">{{ friendlyDate(log.wear_date) }}</view>
            <view class="date-sub" v-if="log.wear_date !== friendlyDate(log.wear_date)">
              {{ log.wear_date }}
            </view>
          </view>

          <view class="weather" v-if="log.weather || log.temperature != null">
            <text v-if="log.weather" class="weather-item">{{ log.weather }}</text>
            <text v-if="log.temperature != null" class="weather-item">{{ log.temperature }}℃</text>
          </view>

          <view v-if="log.mood" class="mood-chip">
            <text class="mood-icon">{{ moodEmoji(log.mood) }}</text>
            <text class="mood-label">{{ log.mood }}</text>
          </view>
        </view>

        <!-- 衣物缩略图 -->
        <view v-if="log.items && log.items.length" class="items-grid">
          <image
            v-for="item in log.items"
            :key="item.item_id"
            :src="item.image_url"
            mode="aspectFill"
            class="thumb"
          />
        </view>

        <!-- 一句话日记 -->
        <view v-if="log.content" class="content">{{ log.content }}</view>

        <!-- 现场照片 -->
        <view v-if="log.photo_url" class="photo-wrap">
          <image :src="log.photo_url" mode="widthFix" class="photo" />
        </view>
      </view>

      <!-- 加载更多 -->
      <view v-if="hasMore" class="load-more" @click="loadMore">
        {{ loadingMore ? '加载中...' : '加载更多' }}
      </view>
      <view v-else-if="logs.length" class="no-more">—— 到底啦 ——</view>
    </view>

    <!-- 空状态 -->
    <view v-else class="empty">
      <view class="empty-icon">👕</view>
      <view class="empty-title">还没有穿搭记录</view>
      <view class="empty-desc">选两件今天穿的衣物，留下第一条穿搭日记吧</view>
      <button class="btn-primary empty-btn" @click="goRecord">去记录今日穿搭</button>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 24rpx 24rpx 120rpx;
  box-sizing: border-box;
  background: #f4f7fb;
}

/* ---------- 卡片 ---------- */
.list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.card {
  background: #ffffff;
  border-radius: 24rpx;
  padding: 28rpx;
  box-shadow: 0 4rpx 24rpx rgba(61, 90, 128, 0.06);
}

.card-head {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  margin-bottom: 20rpx;
}

.date-block {
  flex: 0 0 auto;
}

.date-main {
  font-size: 32rpx;
  font-weight: 700;
  color: #3d5a80;
  line-height: 1.2;
}

.date-sub {
  font-size: 20rpx;
  color: #a4b0be;
  margin-top: 4rpx;
}

.weather {
  flex: 1;
  display: flex;
  gap: 10rpx;
  flex-wrap: wrap;
  padding-top: 6rpx;
}

.weather-item {
  font-size: 22rpx;
  color: #7b8794;
  background: #f1f5fa;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
}

.mood-chip {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 6rpx;
  background: linear-gradient(135deg, #e8f0ff, #f4f7fb);
  padding: 8rpx 18rpx;
  border-radius: 999rpx;
}

.mood-icon {
  font-size: 28rpx;
  line-height: 1;
}

.mood-label {
  font-size: 22rpx;
  color: #5b8def;
  font-weight: 500;
}

/* ---------- 衣物缩略图 ---------- */
.items-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.thumb {
  width: 128rpx;
  height: 128rpx;
  border-radius: 16rpx;
  background: #eef3f9;
}

/* ---------- 一句话日记 ---------- */
.content {
  margin-top: 20rpx;
  font-size: 28rpx;
  color: #2b3441;
  line-height: 1.7;
  padding: 16rpx 20rpx;
  background: #f8fafd;
  border-radius: 16rpx;
}

/* ---------- 现场照片 ---------- */
.photo-wrap {
  margin-top: 20rpx;
  border-radius: 16rpx;
  overflow: hidden;
  background: #eef3f9;
}

.photo {
  width: 100%;
  display: block;
}

/* ---------- 加载状态 ---------- */
.load-more,
.no-more {
  text-align: center;
  padding: 32rpx 0;
  font-size: 24rpx;
  color: #a4b0be;
}

/* ---------- 空状态 ---------- */
.empty {
  padding-top: 200rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
}

.empty-icon {
  font-size: 120rpx;
  line-height: 1;
}

.empty-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #3d5a80;
  margin-top: 24rpx;
}

.empty-desc {
  font-size: 26rpx;
  color: #7b8794;
  text-align: center;
  padding: 0 60rpx;
  line-height: 1.6;
}

.empty-btn {
  margin-top: 40rpx;
}

.btn-primary {
  background: linear-gradient(135deg, #5b8def, #7aa2cc);
  color: #ffffff;
  font-size: 28rpx;
  font-weight: 500;
  border-radius: 999rpx;
  padding: 20rpx 0;
  width: 520rpx;
  border: none;
}

.btn-primary::after {
  border: none;
}
</style>
