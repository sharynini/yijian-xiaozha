<script setup>
/**
 * 首页 —— 今日推荐 + 穿搭状态 + 快捷入口
 *
 * 区块从上到下：
 *   1. 头部问候 + 今日日期
 *   2. 今日穿搭状态（已记录 / 未记录）
 *   3. 温度输入 + "获取今日推荐"按钮 + 横向 swiper 推荐卡片
 *   4. 快捷入口（去衣橱 / 去记录）
 *
 * 数据来源：
 *   - GET /api/wear-logs?page=1&per_page=1 → 判断今日是否已记录
 *   - GET /api/recommend?temperature=xx → 3 套今日推荐
 */
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { get } from '@/utils/request'
import { useOutfitStore } from '@/store/outfit'

const outfitStore = useOutfitStore()

// ---------- 今日穿搭状态 ----------
const todayRecorded = ref(false)
const todayMood = ref('')
const loadingStatus = ref(true)

async function fetchTodayStatus() {
  loadingStatus.value = true
  try {
    const data = await get('/api/wear-logs', { page: 1, per_page: 1 })
    if (data.list && data.list.length) {
      const first = data.list[0]
      const today = new Date().toISOString().slice(0, 10)
      todayRecorded.value = first.wear_date === today
      todayMood.value = first.mood || ''
    } else {
      todayRecorded.value = false
    }
  } catch (e) {
    // request.js 已 toast
  } finally {
    loadingStatus.value = false
  }
}

// ---------- 今日推荐 ----------
const temperature = ref(20)          // 默认 20℃，推荐接口必填
const seasonLabel = ref('')
const recommendList = ref([])
const loadingRecommend = ref(false)

async function fetchRecommend() {
  loadingRecommend.value = true
  try {
    const data = await get('/api/recommend', { temperature: temperature.value })
    seasonLabel.value = data.season_label || ''
    recommendList.value = data.list || []
  } catch (e) {
    // request.js 已 toast
  } finally {
    loadingRecommend.value = false
  }
}

// ---------- 快捷入口 ----------

function goRecord() {
  uni.navigateTo({ url: '/pages/outfit/select' })
}

function goWardrobe() {
  uni.switchTab({ url: '/pages/item/list' })
}

function goTimeline() {
  uni.switchTab({ url: '/pages/timeline/index' })
}

/**
 * "用这套去记录" —— 把推荐搭配塞到 outfit store，直接跳日记创建页
 * 跳过 outfit/select 的手动选择，给用户一个"一键用这套"的快捷路径
 */
function useThisCombo(combo) {
  outfitStore.clearSelected()
  combo.items.forEach((it) => {
    outfitStore.selectedItems.push({
      item_id: it.item_id,
      image_url: it.image_url,
      type: it.type,
      color: it.color,
      season: it.season
    })
  })
  uni.navigateTo({ url: '/pages/diary/create' })
}

// ---------- 生命周期 ----------

onShow(() => {
  fetchTodayStatus()
  fetchRecommend()
})

// ---------- 计算属性 ----------
const today = computed(() => {
  const d = new Date()
  const w = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  return `${d.getMonth() + 1}月${d.getDate()}日 · 星期${w}`
})
</script>

<template>
  <view class="page">
    <!-- 1. 头部 -->
    <view class="header">
      <view class="hello">你好 👋</view>
      <view class="today">{{ today }}</view>
    </view>

    <!-- 2. 今日穿搭状态 -->
    <view v-if="!loadingStatus" class="status-card" :class="{ done: todayRecorded }">
      <view class="status-left">
        <view class="status-icon">{{ todayRecorded ? '✅' : '📝' }}</view>
        <view class="status-text">
          <view class="status-title">
            {{ todayRecorded ? '今日穿搭已记录' : '今日穿搭还没记录' }}
            <text v-if="todayRecorded && todayMood" class="status-mood">· {{ todayMood }}</text>
          </view>
          <view class="status-desc">
            {{ todayRecorded ? '去时间轴回顾一下吧' : '选两件今天穿的衣物，花 10 秒写一条' }}
          </view>
        </view>
      </view>
      <view class="status-btn" @click="todayRecorded ? goTimeline() : goRecord()">
        {{ todayRecorded ? '查看时间轴' : '去记录 →' }}
      </view>
    </view>

    <!-- 3. 今日推荐 -->
    <view class="section">
      <view class="section-head">
        <view class="section-title">
          今日推荐
          <text v-if="seasonLabel" class="season-tag">{{ seasonLabel }}</text>
        </view>
        <view class="temp-row">
          <text class="temp-label">温度</text>
          <input
            class="temp-input"
            type="digit"
            v-model="temperature"
            placeholder="20"
            placeholder-class="ph"
          />
          <text class="temp-unit">℃</text>
          <view class="refresh-btn" :class="{ disabled: loadingRecommend }" @click="fetchRecommend">
            {{ loadingRecommend ? '推荐中' : '换一批' }}
          </view>
        </view>
      </view>

      <!-- 有推荐：swiper 横向滑动 -->
      <view v-if="recommendList.length" class="swiper-wrap">
        <swiper
          class="swiper"
          :indicator-dots="recommendList.length > 1"
          :autoplay="false"
          :circular="recommendList.length > 1"
          indicator-color="rgba(143,179,217,0.4)"
          indicator-active-color="#5b8def"
        >
          <swiper-item v-for="(combo, i) in recommendList" :key="i">
            <view class="recommend-card">
              <view class="recommend-head">
                <text class="combo-label">推荐 {{ i + 1 }}</text>
                <text class="combo-temp">{{ temperature }}℃</text>
              </view>

              <view class="combo-items">
                <view v-for="item in combo.items" :key="item.item_id" class="combo-item">
                  <image :src="item.image_url" mode="aspectFill" class="combo-thumb" />
                  <view class="combo-meta">
                    <text class="combo-type">{{ item.type }}</text>
                    <text class="combo-color">{{ item.color || '—' }}</text>
                  </view>
                </view>
              </view>

              <view class="reason">{{ combo.reason }}</view>

              <view class="use-btn" @click="useThisCombo(combo)">用这套去记录</view>
            </view>
          </swiper-item>
        </swiper>
      </view>

      <!-- 无推荐：空状态引导 -->
      <view v-else class="recommend-empty">
        <view class="recommend-empty-icon">🧥</view>
        <view class="recommend-empty-title">暂时生成不了推荐</view>
        <view class="recommend-empty-desc">
          衣橱里需要同时有「上装」和「下装」才能自动搭配
        </view>
        <button class="btn-primary" @click="goWardrobe">去衣橱添加衣物</button>
      </view>
    </view>

    <!-- 4. 快捷入口 -->
    <view class="quick-row">
      <view class="quick-card" @click="goRecord">
        <view class="quick-icon">📝</view>
        <view class="quick-text">
          <view class="quick-title">记录今日穿搭</view>
          <view class="quick-desc">选衣物 + 一句话 + 心情</view>
        </view>
      </view>

      <view class="quick-card" @click="goWardrobe">
        <view class="quick-icon">👔</view>
        <view class="quick-text">
          <view class="quick-title">管理衣橱</view>
          <view class="quick-desc">添衣物、看搭配</view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 32rpx 24rpx 120rpx;
  background: linear-gradient(180deg, #e8f0ff 0%, #f4f7fb 30%);
  box-sizing: border-box;
}

/* ---------- 头部 ---------- */
.header {
  padding: 16rpx 8rpx 32rpx;
}

.hello {
  font-size: 44rpx;
  font-weight: 700;
  color: #3d5a80;
}

.today {
  font-size: 26rpx;
  color: #7b8794;
  margin-top: 8rpx;
}

/* ---------- 今日穿搭状态卡 ---------- */
.status-card {
  background: #ffffff;
  border-radius: 28rpx;
  padding: 28rpx;
  display: flex;
  align-items: center;
  gap: 24rpx;
  box-shadow: 0 8rpx 32rpx rgba(91, 141, 239, 0.1);
  margin-bottom: 32rpx;
}

.status-card.done {
  background: linear-gradient(135deg, #e8f7ed, #f4fff6);
  box-shadow: 0 8rpx 32rpx rgba(78, 170, 110, 0.15);
}

.status-left {
  flex: 1;
  display: flex;
  gap: 20rpx;
  align-items: center;
}

.status-icon {
  font-size: 56rpx;
  line-height: 1;
}

.status-text {
  flex: 1;
}

.status-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #3d5a80;
}

.status-mood {
  font-size: 24rpx;
  color: #5baa6e;
  margin-left: 8rpx;
}

.status-desc {
  font-size: 24rpx;
  color: #7b8794;
  margin-top: 8rpx;
}

.status-btn {
  flex: 0 0 auto;
  background: linear-gradient(135deg, #5b8def, #7aa2cc);
  color: #ffffff;
  font-size: 24rpx;
  font-weight: 500;
  padding: 14rpx 24rpx;
  border-radius: 999rpx;
}

.status-card.done .status-btn {
  background: linear-gradient(135deg, #5baa6e, #7cc48f);
}

/* ---------- 推荐区块 ---------- */
.section {
  margin-bottom: 32rpx;
}

.section-head {
  padding: 0 8rpx 20rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: 700;
  color: #3d5a80;
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.season-tag {
  font-size: 22rpx;
  font-weight: 400;
  background: #5b8def;
  color: #ffffff;
  padding: 4rpx 16rpx;
  border-radius: 999rpx;
}

.temp-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 16rpx;
}

.temp-label {
  font-size: 24rpx;
  color: #7b8794;
}

.temp-input {
  width: 120rpx;
  height: 56rpx;
  background: #ffffff;
  border: 1rpx solid #d7e0ea;
  border-radius: 12rpx;
  text-align: center;
  font-size: 28rpx;
  color: #2b3441;
}

.ph {
  color: #a4b0be;
}

.temp-unit {
  font-size: 24rpx;
  color: #7b8794;
}

.refresh-btn {
  background: #ffffff;
  border: 1rpx solid #d7e0ea;
  border-radius: 999rpx;
  padding: 10rpx 24rpx;
  font-size: 24rpx;
  color: #5b8def;
}

.refresh-btn.disabled {
  opacity: 0.6;
}

/* ---------- swiper ---------- */
.swiper-wrap {
  width: 100%;
}

.swiper {
  width: 100%;
  height: 620rpx;
}

.recommend-card {
  height: 580rpx;
  background: #ffffff;
  border-radius: 28rpx;
  padding: 28rpx;
  box-sizing: border-box;
  box-shadow: 0 8rpx 32rpx rgba(61, 90, 128, 0.08);
  margin: 4rpx;
  display: flex;
  flex-direction: column;
}

.recommend-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.combo-label {
  font-size: 28rpx;
  font-weight: 600;
  color: #3d5a80;
}

.combo-temp {
  font-size: 24rpx;
  color: #5b8def;
  background: #eef3f9;
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
}

.combo-items {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.combo-item {
  width: 140rpx;
}

.combo-thumb {
  width: 140rpx;
  height: 140rpx;
  border-radius: 16rpx;
  background: #eef3f9;
}

.combo-meta {
  margin-top: 6rpx;
  display: flex;
  flex-direction: column;
}

.combo-type {
  font-size: 22rpx;
  color: #2b3441;
}

.combo-color {
  font-size: 20rpx;
  color: #a4b0be;
}

.reason {
  flex: 1;
  margin-top: 20rpx;
  padding: 16rpx 20rpx;
  background: #f8fafd;
  border-radius: 16rpx;
  font-size: 24rpx;
  color: #7b8794;
  line-height: 1.6;
}

.use-btn {
  margin-top: 20rpx;
  text-align: center;
  background: linear-gradient(135deg, #5b8def, #7aa2cc);
  color: #ffffff;
  font-size: 28rpx;
  font-weight: 500;
  padding: 22rpx 0;
  border-radius: 999rpx;
}

/* ---------- 推荐空状态 ---------- */
.recommend-empty {
  background: #ffffff;
  border-radius: 28rpx;
  padding: 48rpx 32rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  box-shadow: 0 8rpx 32rpx rgba(61, 90, 128, 0.06);
}

.recommend-empty-icon {
  font-size: 80rpx;
  line-height: 1;
}

.recommend-empty-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #3d5a80;
  margin-top: 20rpx;
}

.recommend-empty-desc {
  font-size: 24rpx;
  color: #7b8794;
  text-align: center;
  margin-top: 12rpx;
  line-height: 1.6;
  padding: 0 20rpx;
}

.btn-primary {
  margin-top: 28rpx;
  background: linear-gradient(135deg, #5b8def, #7aa2cc);
  color: #ffffff;
  font-size: 26rpx;
  font-weight: 500;
  border-radius: 999rpx;
  padding: 18rpx 60rpx;
  border: none;
}

.btn-primary::after {
  border: none;
}

/* ---------- 快捷入口 ---------- */
.quick-row {
  display: flex;
  gap: 20rpx;
}

.quick-card {
  flex: 1;
  background: #ffffff;
  border-radius: 24rpx;
  padding: 28rpx;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  box-shadow: 0 4rpx 20rpx rgba(61, 90, 128, 0.05);
}

.quick-icon {
  font-size: 48rpx;
  line-height: 1;
}

.quick-title {
  font-size: 28rpx;
  font-weight: 600;
  color: #3d5a80;
  margin-top: 16rpx;
}

.quick-desc {
  font-size: 22rpx;
  color: #a4b0be;
  margin-top: 6rpx;
}
</style>
