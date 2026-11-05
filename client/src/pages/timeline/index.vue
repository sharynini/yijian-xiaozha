<script setup>
/**
 * 穿搭日记时间轴
 * 组件：DiaryTitle / ClipDateTab / TiltLogCard / TaotaoFab / EmptyBook / AppTabBar
 *
 * 排列：按「月 → 日 → 小卡」三层分组，最新的在最前；每换一个月插入一个月份分段标题
 * 筛选：标题左侧「📅 选日期」，选中后只请求这一天（GET /api/wear-logs?date=），点筛选标签的 ✕ 恢复全部
 * 小卡交互在筛选前后一致：点卡片进详情，💬 进编辑，⭐ 收藏（仅页面内存）
 */
import { ref, computed } from 'vue'
import { onShow, onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
import { get } from '@/utils/request'
import { MOODS } from '@/utils/constants'
import TaotaoSprite from '@/components/TaotaoSprite.vue'
import AppTabBar from '@/components/AppTabBar.vue'
import SafeImage from '@/components/SafeImage.vue'
import OutfitCollage from '@/components/OutfitCollage.vue'

const STYLE_CHIPS = [
  { t: '通勤', bg: '#dbeafe', c: '#2563eb' },
  { t: '甜妹', bg: '#ffe4ed', c: '#e05690' },
  { t: '休闲', bg: '#d8fbe6', c: '#2f9e63' }
]

const logs = ref([])
const page = ref(1)
const perPage = 10
const total = ref(0)
const loadingMore = ref(false)
const loadError = ref(false)
const booting = ref(true)
const spinning = ref(false)
const starred = ref({})
const statusPad = (uni.getSystemInfoSync().statusBarHeight || 12) + 8

function moodEmoji(label) {
  if (!label) return '😊'
  const found = MOODS.find((m) => m.label === label)
  return found ? found.icon : '😊'
}

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

/** 本地日期 YYYY-MM-DD（不能用 toISOString，那是 UTC） */
function localDateStr(d = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** 日分组标题：「5日 周四 · 今天」 */
function dayLabel(s) {
  const [y, m, d] = s.split('-').map(Number)
  const week = WEEKDAYS[new Date(y, m - 1, d).getDay()]
  const today = localDateStr()
  const yesterday = localDateStr(new Date(Date.now() - 86400000))
  const suffix = s === today ? ' · 今天' : (s === yesterday ? ' · 昨天' : '')
  return `${d}日 周${week}${suffix}`
}

/** 筛选标签：同年显示「11月5日」，跨年带年份 */
function shortDate(s) {
  const [y, m, d] = s.split('-').map(Number)
  return y === new Date().getFullYear() ? `${m}月${d}日` : `${y}年${m}月${d}日`
}

function chipsFor(id) {
  const n = Number(id) || 0
  const a = STYLE_CHIPS[n % 3]
  const b = STYLE_CHIPS[(n + 1) % 3]
  return n % 2 === 0 ? [a, b] : [a, b, STYLE_CHIPS[(n + 2) % 3]]
}

function decoFor(id) {
  return Number(id) % 2 === 0 ? '🎀' : '✦'
}

function tiltFor(id) {
  return Number(id) % 2 === 0 ? -1.2 : 1.1
}

// 月 → 日 → 小卡；列表本身已按日期倒序，换月 / 换日时插入分段标题
const grouped = computed(() => {
  const out = []
  let lastMonth = ''
  let lastDay = ''
  logs.value.forEach((log) => {
    const day = log.wear_date || ''
    const month = day.slice(0, 7)
    if (month !== lastMonth) {
      const [y, m] = month.split('-').map(Number)
      out.push({ kind: 'month', label: `${y}年${m}月`, key: 'm-' + month })
      lastMonth = month
    }
    if (day !== lastDay) {
      out.push({ kind: 'date', label: dayLabel(day), key: 'd-' + day })
      lastDay = day
    }
    out.push({ kind: 'log', log, key: log.log_id })
  })
  return out
})

// ---------- 日期筛选 ----------
const today = localDateStr()
const filterDate = ref('')     // '' 表示不筛选

function onPickDate(e) {
  const value = e.detail.value
  if (!value || value === filterDate.value) return
  filterDate.value = value
  fetchLogs(true)
}

function clearFilter() {
  if (!filterDate.value) return
  filterDate.value = ''
  fetchLogs(true)
}

// 切换筛选时可能有旧请求还没回来：只采用最后一次请求的结果
let requestSeq = 0

async function fetchLogs(reset = true) {
  if (reset) page.value = 1
  else if (loadingMore.value) return
  loadingMore.value = !reset
  loadError.value = false
  const seq = ++requestSeq
  const params = { page: page.value, per_page: perPage }
  if (filterDate.value) params.date = filterDate.value
  try {
    const data = await get('/api/wear-logs', params, { skipDedup: reset })
    if (seq !== requestSeq) return
    total.value = data.total
    logs.value = reset ? data.list : logs.value.concat(data.list)
  } catch (e) {
    if (seq === requestSeq) loadError.value = true
  } finally {
    if (seq === requestSeq) {
      loadingMore.value = false
      booting.value = false
    }
  }
}

function loadMore() {
  if (logs.value.length >= total.value) return
  page.value += 1
  fetchLogs(false)
}

onShow(() => { fetchLogs(true) })

onPullDownRefresh(() => {
  spinning.value = true
  fetchLogs(true).finally(() => {
    spinning.value = false
    uni.stopPullDownRefresh()
  })
})

onReachBottom(() => { loadMore() })

// 点卡片进入详情页；编辑、删除都在详情页里做（返回时 onShow 会刷新列表）
function onCardTap(log) {
  uni.navigateTo({ url: `/pages/timeline/detail?log_id=${log.log_id}` })
}

function editLog(log) {
  uni.navigateTo({ url: `/pages/diary/edit?log_id=${log.log_id}` })
}

function toggleStar(e, id) {
  e.stopPropagation()
  starred.value = { ...starred.value, [id]: !starred.value[id] }
}

function goRecord() {
  uni.navigateTo({ url: '/pages/outfit/canvas' })
}

const hasMore = computed(() => logs.value.length < total.value)
const coverOf = (log) => (log.photo_url) || (log.items && log.items[0] && log.items[0].image_url) || ''
</script>

<template>
  <view class="page" :style="{ paddingTop: statusPad + 'px' }">
    <view v-if="spinning" class="spin-mask">
      <TaotaoSprite mood="spin" :size="140" />
      <view class="spin-txt">桃桃转圈刷新中…</view>
    </view>

    <view class="head">
      <picker mode="date" :value="filterDate || today" :end="today" class="date-picker" @change="onPickDate">
        <view class="sticker left press-bounce">📅 选日期</view>
      </picker>
      <view class="title">穿搭日记📒</view>
      <view class="sticker press-bounce" @click="fetchLogs(true)">✦ 刷新</view>
    </view>

    <view v-if="filterDate" class="filter-bar">
      <view class="filter-chip press-bounce" @click="clearFilter">只看 {{ shortDate(filterDate) }} ✕</view>
    </view>

    <view v-if="booting" class="empty"><view class="empty-d">加载中…</view></view>
    <view v-else-if="logs.length" class="album">
      <template v-for="row in grouped" :key="row.key">
        <view v-if="row.kind === 'month'" class="month-head">
          <text class="month-label">{{ row.label }}</text>
          <view class="month-line" />
        </view>
        <view v-else-if="row.kind === 'date'" class="date-tab">
          <view class="clip">📎</view>
          <text>{{ row.label }}</text>
        </view>
        <view
          v-else
          class="polaroid press-bounce"
          :style="{ transform: 'rotate(' + tiltFor(row.log.log_id) + 'deg)' }"
          @click="onCardTap(row.log)"
        >
          <view class="corner">{{ decoFor(row.log.log_id) }}</view>
          <view class="preview">
            <!-- 手动搭配的记录显示拼贴图；有现场照时贴在右上角 -->
            <template v-if="row.log.collage">
              <view class="cover collage-cover">
                <OutfitCollage :collage="row.log.collage" :items="row.log.items" />
              </view>
              <view v-if="row.log.photo_url" class="photo-inset"><SafeImage :src="row.log.photo_url" /></view>
            </template>
            <view v-else class="cover"><SafeImage :src="coverOf(row.log)" /></view>
            <view class="emo">{{ moodEmoji(row.log.mood) }}</view>
          </view>
          <view class="body">
            <view class="chips">
              <text
                v-for="ch in chipsFor(row.log.log_id)"
                :key="ch.t"
                class="chip"
                :style="{ background: ch.bg, color: ch.c }"
              >{{ ch.t }}</text>
            </view>
            <view class="note">{{ row.log.content || '还没写一句话' }}</view>
            <view class="ops">
              <text class="op" :class="{ on: starred[row.log.log_id] }" @click.stop="toggleStar($event, row.log.log_id)">⭐</text>
              <text class="op" @click.stop="editLog(row.log)">💬</text>
            </view>
          </view>
        </view>
      </template>
      <view v-if="hasMore" class="more" @click="loadMore">{{ loadingMore ? '加载中...' : '加载更多' }}</view>
      <view v-else class="more">—— 到底啦 ——</view>
    </view>

    <view v-else-if="loadError" class="empty">
      <TaotaoSprite mood="book" :size="160" />
      <view class="empty-t">日记加载失败</view>
      <view class="empty-d">点下面让桃桃再试一次</view>
      <button class="btn-primary" style="margin-top:24rpx;width:280rpx" @click="fetchLogs(true)">重试</button>
    </view>
    <view v-else-if="filterDate" class="empty">
      <TaotaoSprite mood="book" :size="160" />
      <view class="empty-t">{{ shortDate(filterDate) }} 没有穿搭记录</view>
      <view class="empty-d">换个日期看看，或者现在补记一套</view>
      <view class="empty-actions">
        <view class="empty-btn ghost press-bounce" @click="clearFilter">看全部</view>
        <view class="empty-btn press-bounce" @click="goRecord">去记录</view>
      </view>
    </view>
    <view v-else class="empty">
      <TaotaoSprite mood="book" :size="180" />
      <view class="empty-t">快来写下你的第一套穿搭日记吧！</view>
      <view class="empty-d">桃桃举着空白手账本等你～</view>
    </view>

    <view class="fab press-bounce" @click="goRecord">
      <TaotaoSprite mood="fab" :size="108" />
    </view>

    <AppTabBar current="diary" />
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 12rpx 24rpx 40rpx;
  box-sizing: border-box;
  position: relative;
}
.spin-mask {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(255, 248, 245, 0.72);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.spin-txt { margin-top: 12rpx; color: #ff8fb1; font-weight: 700; }
.head {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  margin-bottom: 16rpx;
}
.title { font-size: 40rpx; font-weight: 800; }
.date-picker {
  position: absolute;
  left: 0;
  top: 0;
  z-index: 2;
}
.sticker.left {
  position: static;
  transform: rotate(-6deg);
  background: #e7f3ff;
  border-color: #93c5fd;
}
.filter-bar {
  display: flex;
  justify-content: center;
  margin: 4rpx 0 12rpx;
}
.filter-chip {
  padding: 8rpx 24rpx;
  border-radius: 999rpx;
  font-size: 24rpx;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(180deg, #ffb3c9 0%, #ff8fb1 72%);
}
.month-head {
  width: 100%;
  display: flex;
  align-items: center;
  margin: 28rpx 0 4rpx;
}
.month-head:first-child {
  margin-top: 4rpx;
}
.month-label {
  flex-shrink: 0;
  font-size: 32rpx;
  font-weight: 800;
  color: #382e36;
  margin-right: 16rpx;
}
.month-line {
  flex: 1;
  height: 0;
  border-top: 3rpx dashed #f3b8c8;
}
.empty-actions {
  display: flex;
  gap: 20rpx;
  margin-top: 28rpx;
}
.empty-btn {
  padding: 0 40rpx;
  height: 76rpx;
  line-height: 76rpx;
  border-radius: 999rpx;
  font-size: 28rpx;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(180deg, #ffb3c9 0%, #ff8fb1 72%);
}
.empty-btn.ghost {
  color: #ff8fb1;
  background: #fff8f5;
  border: 2rpx dashed #ffb3c9;
}
.sticker {
  position: absolute;
  right: 0;
  top: 0;
  background: #fff4c8;
  border: 2rpx dashed #ffd56b;
  border-radius: 16rpx;
  padding: 8rpx 16rpx;
  font-size: 20rpx;
  transform: rotate(6deg);
}

.date-tab {
  position: relative;
  width: 100%;
  align-self: flex-start;
  background: #fffdfb;
  border: 2rpx dashed #f3b8c8;
  border-radius: 12rpx;
  padding: 8rpx 28rpx 8rpx 36rpx;
  font-size: 24rpx;
  font-weight: 700;
  margin: 12rpx 0 8rpx 8rpx;
  box-shadow: 0 6rpx 12rpx rgba(255,150,175,0.08);
}
.clip {
  position: absolute;
  left: -6rpx;
  top: -10rpx;
  font-size: 28rpx;
  transform: rotate(-25deg);
}

.album {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx 16rpx;
  align-items: flex-start;
}
.polaroid {
  width: calc(50% - 10rpx);
  background: #fffdfb;
  border: 3rpx dashed #f3b8c8;
  border-radius: 20rpx;
  overflow: hidden;
  margin: 8rpx 0 12rpx;
  box-shadow: 0 10rpx 28rpx rgba(255, 150, 175, 0.1);
  position: relative;
  box-sizing: border-box;
}
.corner {
  position: absolute;
  right: 12rpx;
  top: 12rpx;
  z-index: 2;
  font-size: 28rpx;
}
.preview { position: relative; height: 280rpx; background: #fff0f4; }
.cover { width: 100%; height: 280rpx; }
.collage-cover {
  /* 拼贴图是正方形：居中显示，两侧留出底色 */
  width: 280rpx;
  margin: 0 auto;
}
.photo-inset {
  position: absolute;
  top: 16rpx;
  right: 16rpx;
  width: 120rpx;
  height: 120rpx;
  padding: 6rpx 6rpx 14rpx;
  background: #fff;
  border-radius: 8rpx;
  transform: rotate(4deg);
  box-shadow: 0 6rpx 14rpx rgba(56, 46, 54, 0.12);
}
.cover.ph {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 64rpx;
  height: 280rpx;
}
.emo {
  position: absolute;
  right: 16rpx;
  bottom: 16rpx;
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  background: #fffdfb;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36rpx;
  box-shadow: 0 6rpx 12rpx rgba(56,46,54,0.08);
}
.body { padding: 16rpx 20rpx 18rpx; }
.chips { display: flex; flex-wrap: wrap; gap: 8rpx; }
.chip {
  font-size: 20rpx;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  font-weight: 700;
}
.note {
  margin-top: 10rpx;
  font-size: 26rpx;
  color: #382e36;
}
.ops {
  margin-top: 8rpx;
  display: flex;
  gap: 20rpx;
  font-size: 28rpx;
}
.op.on { filter: none; }
.op { opacity: 0.7; }

.empty {
  padding-top: 160rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.empty-t { margin-top: 16rpx; font-weight: 800; font-size: 30rpx; }
.empty-d { margin-top: 8rpx; color: #8a7f88; font-size: 24rpx; }

.fab {
  position: fixed;
  right: 28rpx;
  bottom: 180rpx;
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: linear-gradient(180deg, #ffb3c9, #ff8fb1);
  box-shadow: 0 12rpx 24rpx rgba(255, 143, 177, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 40;
}
.more { text-align: center; color: #8a7f88; font-size: 22rpx; padding: 12rpx 0 24rpx; }
</style>
