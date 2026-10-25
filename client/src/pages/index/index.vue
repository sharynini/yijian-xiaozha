<script setup>
/**
 * 首页｜今日推荐
 * 组件：HeroGreet / CheckinNote / HeroRecommendCard / AppTabBar
 */
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { get } from '@/utils/request'
import { useOutfitStore } from '@/store/outfit'
import { useUserStore } from '@/store/user'
import TaotaoSprite from '@/components/TaotaoSprite.vue'
import AppTabBar from '@/components/AppTabBar.vue'
import SafeImage from '@/components/SafeImage.vue'

const outfitStore = useOutfitStore()
const userStore = useUserStore()

// 问候语里的名字：优先昵称，其次用户名
const greetName = computed(() => {
  const u = userStore.userInfo || {}
  return u.nickname || u.username || ''
})

/** 本地日期 YYYY-MM-DD（不能用 toISOString，那是 UTC，北京时间 0~8 点会差一天） */
function localDateStr(d = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
const statusPad = (uni.getSystemInfoSync().statusBarHeight || 12) + 8

const todayRecorded = ref(false)
const todayMood = ref('')
const loadingStatus = ref(true)
const statusError = ref(false)

async function fetchTodayStatus() {
  loadingStatus.value = true
  statusError.value = false
  try {
    const data = await get('/api/wear-logs', { page: 1, per_page: 1 })
    if (data.list && data.list.length) {
      const first = data.list[0]
      const today = localDateStr()
      todayRecorded.value = first.wear_date === today
      todayMood.value = first.mood || ''
    } else {
      todayRecorded.value = false
    }
  } catch (e) {
    statusError.value = true
  } finally {
    loadingStatus.value = false
  }
}

const temperature = ref(20)
const seasonLabel = ref('')

// ---------- 定位 → 天气 ----------
// 成功拿到当地气温后自动推荐；定位或天气失败时，显示 +/- 让用户手动调温度兜底
const WEATHER_CACHE_KEY = 'sw_weather'
const WEATHER_CACHE_MS = 30 * 60 * 1000
const weather = ref(null)          // { temperature, text, city }
const locating = ref(false)
const manualTemp = ref(false)      // true = 走手动调温度
const weatherTip = ref('')

function readWeatherCache() {
  try {
    const c = uni.getStorageSync(WEATHER_CACHE_KEY)
    if (c && Date.now() - c.ts < WEATHER_CACHE_MS) return c.data
  } catch (e) { /* 忽略 */ }
  return null
}

function getLocation() {
  return new Promise((resolve, reject) => {
    uni.getLocation({
      type: 'wgs84',
      success: (res) => resolve(res),
      fail: (err) => reject(err)
    })
  })
}

async function loadWeather(force = false) {
  const cached = force ? null : readWeatherCache()
  if (cached) {
    applyWeather(cached)
    return
  }
  locating.value = true
  weatherTip.value = ''
  try {
    const loc = await getLocation()
    const data = await get('/api/weather', { lat: loc.latitude, lon: loc.longitude }, { silent: true })
    uni.setStorageSync(WEATHER_CACHE_KEY, { ts: Date.now(), data })
    applyWeather(data)
  } catch (e) {
    manualTemp.value = true
    weather.value = null
    if (e && e.code === 7001) weatherTip.value = '天气服务还没配置，先手动调温度吧'
    else if (e && e.code) weatherTip.value = '天气获取失败，先手动调温度吧'
    else weatherTip.value = '没拿到定位，先手动调温度吧'
  } finally {
    locating.value = false
  }
}

function applyWeather(data) {
  weather.value = data
  manualTemp.value = false
  temperature.value = Math.round(data.temperature)
}

async function refreshWeather() {
  if (locating.value) return
  await loadWeather(true)
  fetchRecommend()
}
const recommendList = ref([])
const loadingRecommend = ref(false)
const recError = ref(false)
const comboIndex = ref(0)

const currentCombo = computed(() => recommendList.value[comboIndex.value] || null)

const matchScore = computed(() => {
  const combo = currentCombo.value
  if (!combo) return 0
  const wears = (combo.items || []).reduce((s, it) => s + (it.wear_count || 0), 0)
  return Math.min(98, Math.max(78, 94 - wears * 2 - comboIndex.value))
})

const taotaoCopy = computed(() => {
  const combo = currentCombo.value
  if (!combo) return ''
  const types = (combo.items || []).map((it) => it.type).join('、')
  const band = seasonLabel.value || '今天'
  return `今天${temperature.value}℃很舒服，桃桃帮你挑了这套${band}轻薄通勤搭配，优先选了你穿得比较少的单品，不容易腻哦~（含：${types}）`
})

async function fetchRecommend() {
  loadingRecommend.value = true
  recError.value = false
  try {
    const data = await get('/api/recommend', { temperature: temperature.value })
    seasonLabel.value = data.season_label || ''
    recommendList.value = data.list || []
    comboIndex.value = 0
  } catch (e) {
    recError.value = true
    recommendList.value = []
  } finally {
    loadingRecommend.value = false
  }
}

function bumpTemp(delta) {
  const n = Number(temperature.value)
  const next = Math.min(60, Math.max(-50, (Number.isFinite(n) ? n : 20) + delta))
  temperature.value = next
  fetchRecommend()
}

function shuffleCombo() {
  if (loadingRecommend.value) return
  if (recommendList.value.length > 1) {
    comboIndex.value = (comboIndex.value + 1) % recommendList.value.length
    return
  }
  fetchRecommend()
}

function goRecord() {
  goCanvas()
}
function goCanvas() {
  uni.navigateTo({ url: '/pages/outfit/canvas' })
}
function goWardrobe() {
  uni.switchTab({ url: '/pages/item/list' })
}
function goTimeline() {
  uni.switchTab({ url: '/pages/timeline/index' })
}

function useThisCombo(combo) {
  if (!combo) return
  // 先到画布看效果（可换一套、可微调），再去打卡
  outfitStore.setRecommend(recommendList.value, comboIndex.value)
  uni.navigateTo({ url: '/pages/outfit/canvas?from=recommend' })
}

let weatherLoaded = false
onShow(async () => {
  fetchTodayStatus()
  // 第一次进入先定位拿气温再推荐；之后切回首页沿用已有温度（30 分钟内有缓存）
  if (!weatherLoaded) {
    weatherLoaded = true
    await loadWeather()
  }
  fetchRecommend()
})

const todayLine = computed(() => {
  const d = new Date()
  return `今天是 ${d.getMonth() + 1}月${d.getDate()}日`
})
</script>

<template>
  <view class="page">
    <!-- 装饰：星光云朵 -->
    <view class="deco cloud a">☁</view>
    <view class="deco star a">✦</view>
    <view class="deco star b">✧</view>
    <view class="deco heart">♡</view>
    <view class="deco bow">🎀</view>

    <!-- HeroGreet：奶桃转浅橙问候 -->
    <view class="hero" :style="{ paddingTop: statusPad + 'px' }">
      <view class="hero-row">
        <TaotaoSprite mood="wave" :size="168" />
        <view class="greet">
          <view class="hi">哈喽～<text v-if="greetName" class="hi-name">{{ greetName }}</text></view>
          <view class="meta">{{ todayLine }}</view>
          <view v-if="locating" class="temp-row">📍 正在获取当地天气…</view>
          <view v-else-if="!manualTemp && weather" class="temp-row" @click="refreshWeather">
            <text>📍 {{ weather.city || '当前位置' }} · {{ weather.text }}</text>
            <text class="temp-now">{{ temperature }}℃</text>
            <text class="refresh">↻</text>
          </view>
          <view v-else class="temp-row">
            <text>室外</text>
            <text class="temp-btn" @click="bumpTemp(-1)">−</text>
            <input class="temp" type="digit" v-model="temperature" @blur="fetchRecommend" />
            <text class="temp-btn" @click="bumpTemp(1)">+</text>
            <text>℃</text>
            <text class="refresh" @click="refreshWeather">📍重试</text>
          </view>
          <view v-if="weatherTip && manualTemp" class="weather-tip">{{ weatherTip }}</view>
        </view>
        <view v-if="seasonLabel" class="season-sticker">适合{{ seasonLabel }}穿搭</view>
      </view>
    </view>

    <!-- CheckinNote：薄荷绿打卡条 -->
    <view v-if="statusError" class="checkin press-bounce" @click="fetchTodayStatus">
      <text class="check-ico">!</text>
      <text class="check-txt">打卡状态加载失败，点这里重试</text>
    </view>
    <view
      v-else-if="!loadingStatus"
      class="checkin press-bounce"
      @click="todayRecorded ? goTimeline() : goRecord()"
    >
      <text class="check-ico">{{ todayRecorded ? '✔' : '✎' }}</text>
      <text class="check-txt">
        {{ todayRecorded ? `今日穿搭打卡成功！${todayMood ? ' · ' + todayMood : ''}` : '今天还没打卡，桃桃等你来记一套～' }}
      </text>
      <text class="check-arrow">›</text>
    </view>

    <!-- HeroRecommendCard -->
    <view v-if="currentCombo" class="hero-card">
      <view class="tape" />
      <view class="badge">✨ 桃桃智能推荐</view>
      <view class="shuffle press-bounce" @click="shuffleCombo">
        <TaotaoSprite mood="wink" :size="44" />
        <text>{{ loadingRecommend ? '想…' : '换一批' }}</text>
      </view>

      <view class="pair">
        <view
          v-for="it in (currentCombo.items || []).slice(0, 2)"
          :key="it.item_id"
          class="polaroid"
        >
          <view class="pair-img">
            <SafeImage :src="it.image_url" />
          </view>
        </view>
      </view>

      <view class="match">
        <view class="bar">
          <view class="fill" :style="{ width: matchScore + '%' }" />
          <view class="star-end">★</view>
        </view>
        <view class="match-label">匹配度 {{ matchScore }}%</view>
      </view>

      <view class="copy">{{ taotaoCopy }}</view>

      <view class="cta press-bounce" @click="useThisCombo(currentCombo)">用这套去打卡</view>
      <view class="manual-link press-bounce" @click="goCanvas">不太满意？自己动手搭一套 ›</view>
    </view>

    <view v-else class="hero-card empty-rec">
      <TaotaoSprite :mood="loadingRecommend ? 'spin' : 'closet'" :size="140" />
      <view class="empty-title">{{ recError ? '推荐加载失败' : (loadingRecommend ? '桃桃转圈想搭配中…' : '暂时生成不了推荐') }}</view>
      <view class="empty-desc">
        {{ recError
          ? '网络不稳定，点重试让桃桃再想一次。'
          : '需要「上装 + 下装」或「连衣裙」，且季节匹配当前温度（或标成全季）。没填季节的衣服不会出现在推荐里。' }}
      </view>
      <view v-if="recError" class="cta ghost press-bounce" @click="fetchRecommend">重试</view>
      <view v-else class="cta ghost press-bounce" @click="goWardrobe">去衣橱补季节</view>
      <view class="manual-link press-bounce" @click="goCanvas">或者自己动手搭一套 ›</view>
    </view>

    <AppTabBar current="index" />
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 0 28rpx 40rpx;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
}
.deco {
  position: absolute;
  pointer-events: none;
  opacity: 0.55;
  z-index: 0;
}
.deco.cloud.a { top: 120rpx; right: 40rpx; font-size: 40rpx; color: #ffd0de; }
.deco.star.a { top: 40rpx; right: 80rpx; color: #ffd56b; font-size: 28rpx; }
.deco.star.b { top: 220rpx; left: 24rpx; color: #c4b5fd; font-size: 22rpx; }
.deco.heart { top: 88rpx; right: 200rpx; color: #ff8fb1; }
.deco.bow { bottom: 280rpx; right: 16rpx; font-size: 36rpx; transform: rotate(18deg); }

.hero {
  margin: 0 -28rpx;
  padding: 16rpx 28rpx 48rpx;
  background: linear-gradient(180deg, #ffd6e4 0%, #ffe3c8 55%, #fff8f5 100%);
  position: relative;
  z-index: 1;
}
.hero-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  position: relative;
}
.greet { flex: 1; }
.hi {
  font-size: 52rpx;
  font-weight: 800;
  color: #382e36;
  letter-spacing: 2rpx;
  /* 名字太长时省略，避免挤到右侧季节贴纸 */
  max-width: 400rpx;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.hi-name {
  color: #ff8fb1;
  margin-left: 4rpx;
}
.meta {
  margin-top: 8rpx;
  font-size: 22rpx;
  color: #8a7f88;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}
.temp-row {
  margin-top: 8rpx;
  display: flex;
  align-items: center;
  gap: 8rpx;
  font-size: 22rpx;
  color: #8a7f88;
}
.temp-btn {
  width: 40rpx;
  height: 40rpx;
  line-height: 40rpx;
  text-align: center;
  border-radius: 50%;
  background: #fffdfb;
  border: 2rpx dashed #ffb3c9;
  color: #ff8fb1;
  font-size: 28rpx;
}
.temp {
  width: 64rpx;
  display: inline-block;
  text-align: center;
  border-bottom: 2rpx dashed #ff8fb1;
  margin: 0 4rpx;
  font-size: 22rpx;
  color: #382e36;
}
.temp-now {
  font-size: 30rpx;
  font-weight: 800;
  color: #382e36;
}
.refresh {
  color: #ff8fb1;
  font-size: 22rpx;
}
.weather-tip {
  margin-top: 6rpx;
  font-size: 20rpx;
  color: #c28a9d;
}
.season-sticker {
  position: absolute;
  top: 0;
  right: 0;
  background: #fffdfb;
  border: 2rpx dashed #ffb3c9;
  border-radius: 999rpx;
  padding: 8rpx 18rpx;
  font-size: 20rpx;
  color: #ff8fb1;
  transform: rotate(4deg);
  box-shadow: 0 8rpx 16rpx rgba(255, 150, 175, 0.12);
}

.checkin {
  position: relative;
  z-index: 1;
  margin-top: -12rpx;
  background: linear-gradient(90deg, #d8fbe6, #c5f6d8);
  border: 2rpx dashed #8ee4af;
  border-radius: 999rpx;
  padding: 16rpx 24rpx;
  display: flex;
  align-items: center;
  gap: 12rpx;
  transform: rotate(-0.8deg);
}
.check-ico { color: #2f9e63; font-weight: 700; }
.check-txt { flex: 1; font-size: 24rpx; color: #382e36; font-weight: 600; }
.check-arrow { color: #8a7f88; }

.hero-card {
  position: relative;
  z-index: 1;
  margin-top: 28rpx;
  background:
    repeating-linear-gradient(
      to bottom,
      transparent 0 36rpx,
      rgba(255, 180, 196, 0.18) 36rpx 37rpx
    ),
    #fffdfb;
  border: 3rpx dashed #f3b8c8;
  border-radius: 28rpx;
  padding: 48rpx 28rpx 32rpx;
  transform: rotate(-1.2deg);
  box-shadow: 0 10rpx 36rpx rgba(255, 150, 175, 0.14);
}
.tape {
  position: absolute;
  top: -14rpx;
  left: 50%;
  width: 120rpx;
  height: 28rpx;
  margin-left: -60rpx;
  background: rgba(147, 197, 253, 0.45);
  transform: rotate(-2deg);
  border-radius: 4rpx;
}
.badge {
  position: absolute;
  top: -18rpx;
  left: 24rpx;
  background: linear-gradient(180deg, #ffe08a, #ffd56b);
  color: #382e36;
  font-size: 22rpx;
  font-weight: 800;
  padding: 8rpx 20rpx;
  border-radius: 999rpx;
  transform: rotate(-3deg);
  box-shadow: 0 6rpx 12rpx rgba(255, 213, 107, 0.4);
}
.shuffle {
  position: absolute;
  top: 16rpx;
  right: 16rpx;
  background: #fffdfb;
  border: 2rpx dashed #ffb3c9;
  border-radius: 999rpx;
  padding: 4rpx 16rpx 4rpx 6rpx;
  display: flex;
  align-items: center;
  gap: 4rpx;
  font-size: 20rpx;
  color: #ff8fb1;
  transform: rotate(3deg);
}
.pair {
  display: flex;
  gap: 20rpx;
  margin-top: 36rpx;
  justify-content: center;
}
.polaroid {
  padding: 10rpx 10rpx 22rpx;
  background: #fff;
  border-radius: 16rpx;
  box-shadow: 0 8rpx 18rpx rgba(56, 46, 54, 0.08);
  transform: rotate(-1.5deg);
}
.polaroid:nth-child(2) { transform: rotate(1.6deg); }
.pair-img {
  width: 220rpx;
  height: 220rpx;
  border-radius: 10rpx;
  background: #fff0f4;
}
.match { margin-top: 28rpx; }
.bar {
  height: 22rpx;
  border-radius: 999rpx;
  background: #ffe4ed;
  position: relative;
  overflow: visible;
}
.fill {
  height: 100%;
  border-radius: 999rpx;
  background: linear-gradient(90deg, #93c5fd, #c4b5fd 55%, #ff8fb1);
  box-shadow: inset 0 -4rpx 0 rgba(255,255,255,0.4);
}
.star-end {
  position: absolute;
  right: 8rpx;
  top: -8rpx;
  color: #ffd56b;
  font-size: 28rpx;
}
.match-label {
  text-align: center;
  margin-top: 10rpx;
  font-size: 22rpx;
  color: #8a7f88;
  font-weight: 600;
}
.copy {
  margin-top: 16rpx;
  font-size: 24rpx;
  color: #382e36;
  line-height: 1.7;
  text-align: center;
  padding: 0 8rpx;
}
.cta {
  margin-top: 24rpx;
  height: 88rpx;
  line-height: 88rpx;
  text-align: center;
  color: #fff;
  font-size: 32rpx;
  font-weight: 700;
  border-radius: 999rpx;
  background: linear-gradient(180deg, #ffb3c9 0%, #ff8fb1 72%);
  box-shadow: 0 10rpx 22rpx rgba(255, 143, 177, 0.38);
}
.manual-link {
  margin-top: 20rpx;
  text-align: center;
  font-size: 26rpx;
  color: #ff8fb1;
  font-weight: 700;
}
.cta.ghost {
  background: #fff8f5;
  color: #ff8fb1;
  border: 2rpx dashed #ffb3c9;
  box-shadow: none;
}
.empty-rec {
  display: flex;
  flex-direction: column;
  align-items: center;
  transform: rotate(0.8deg);
}
.empty-title { margin-top: 12rpx; font-weight: 700; font-size: 30rpx; }
.empty-desc {
  margin-top: 8rpx;
  font-size: 22rpx;
  color: #8a7f88;
  text-align: center;
  line-height: 1.6;
}

</style>
