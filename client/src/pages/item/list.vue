<script setup>
/**
 * 衣物列表页（衣橱 tab）
 *   - 顶部筛选：季节 / 类型 / 颜色
 *   - 网格展示 + 下拉刷新 + 上拉加载更多
 *   - 左滑出现「删除」按钮（软删除 DELETE /api/items/<id>）
 *   - 点击卡片进入编辑页
 *   - 空状态引导去添加
 */
import { ref, computed } from 'vue'
import { onShow, onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
import { get, del } from '@/utils/request'
import { FILTER_TYPES, FILTER_SEASONS, FILTER_COLORS } from '@/utils/constants'
import TaotaoSprite from '@/components/TaotaoSprite.vue'
import AppTabBar from '@/components/AppTabBar.vue'
import SafeImage from '@/components/SafeImage.vue'

const CAT_TABS = [
  { label: '全部', typeIndex: 0, color: '#FF8FB1' },
  { label: '上装', typeIndex: 1, color: '#93C5FD' },
  { label: '下装', typeIndex: 2, color: '#8EE4AF' },
  { label: '鞋包', typeIndex: 4, color: '#FFD56B' },
  { label: '配饰', typeIndex: 5, color: '#C4B5FD' }
]

const TIPS = ['这件很适合搭配浅色上衣哦！', '桃桃觉得今天穿它刚刚好～', '低调又好搭，通勤也可以！']

const statusPad = (uni.getSystemInfoSync().statusBarHeight || 12) + 8
const spinning = ref(false)
const tipId = ref(null)
const tipText = ref('')

const PER_PAGE = 10

const items = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const loaded = ref(false)      // 是否已完成过一次请求（用于区分「空数据」与「还没加载」）
const loadError = ref(false)

const typeIndex = ref(0)
const seasonIndex = ref(0)
const colorIndex = ref(0)

const finished = computed(() => loaded.value && items.value.length >= total.value)

// 左滑露出宽度：120rpx 换算成 px，保证 H5 与小程序下 transform 单位都安全
const DEL_WIDTH = Math.round((120 * uni.getSystemInfoSync().windowWidth) / 750)

let startX = 0
let startY = 0
let dragged = false            // 本次触摸是否发生了横向拖动（用于抑制误触跳转）

// ---------- 数据加载 ----------
async function fetchItems(reset = false) {
  if (loading.value) return
  // 上拉加载时若已到底则不再请求
  if (!reset && loaded.value && items.value.length >= total.value) return

  loading.value = true
  loadError.value = false
  try {
    const params = { page: page.value, per_page: PER_PAGE }
    if (typeIndex.value > 0) params.type = FILTER_TYPES[typeIndex.value]
    if (seasonIndex.value > 0) params.season = FILTER_SEASONS[seasonIndex.value]
    if (colorIndex.value > 0) params.color = FILTER_COLORS[colorIndex.value]

    const data = await get('/api/items', params)
    total.value = data.total || 0
    const list = data.list || []
    items.value = reset ? list : items.value.concat(list)
    loaded.value = true
  } catch (e) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  return fetchItems(true)
}

function onFilterChange() {
  reload()
}

// ---------- 生命周期 ----------
onShow(() => {
  // 从添加/编辑页返回或切回衣橱 tab 时刷新
  reload()
})

onPullDownRefresh(async () => {
  spinning.value = true
  await reload()
  spinning.value = false
  uni.stopPullDownRefresh()
})

onReachBottom(() => {
  if (finished.value || loading.value) return
  page.value += 1
  fetchItems(false)
})

// ---------- 左滑删除 ----------
function closeItem(item) {
  item._offset = 0
}

function closeOthers(except) {
  items.value.forEach((i) => {
    if (i !== except && i._offset) i._offset = 0
  })
}

function onTouchStart(e, item) {
  closeOthers(item)
  startX = e.touches[0].clientX
  startY = e.touches[0].clientY
  item._start = item._offset || 0
  dragged = false
}

function onTouchMove(e, item) {
  const dx = e.touches[0].clientX - startX
  const dy = e.touches[0].clientY - startY
  // 纵向意图优先，交给页面滚动处理
  if (Math.abs(dy) > Math.abs(dx)) return

  dragged = true
  let offset = (item._start || 0) + dx
  offset = Math.min(0, Math.max(-DEL_WIDTH, offset))
  item._offset = offset
}

function onTouchEnd(item) {
  if (item._offset === undefined) return
  // 划过一半就吸附展开，否则回弹
  item._offset = item._offset < -DEL_WIDTH / 2 ? -DEL_WIDTH : 0
}

function removeItem(item) {
  uni.showModal({
    title: '删除衣物',
    content: `确定删除「${item.type}${item.color ? ' · ' + item.color : ''}」吗？删除后不可在此列表中看到。`,
    confirmColor: '#e05c5c',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await del(`/api/items/${item.item_id}`)
        items.value = items.value.filter((i) => i.item_id !== item.item_id)
        total.value = Math.max(0, total.value - 1)
        uni.showToast({ title: '已删除', icon: 'success' })
      } catch (e) {
        closeItem(item)
      }
    }
  })
}

// ---------- 跳转 ----------
function goEdit(item) {
  if (dragged) {
    dragged = false
    return
  }
  if (item._offset) {
    // 已展开时点击先收起
    closeItem(item)
    return
  }
  uni.navigateTo({ url: `/pages/item/add?id=${item.item_id}` })
}

function goAdd() {
  uni.navigateTo({ url: '/pages/item/add' })
}

function selectCat(tab) {
  typeIndex.value = tab.typeIndex
  onFilterChange()
}

function openFilter() {
  uni.showActionSheet({
    itemList: FILTER_SEASONS.map((s, i) => (i === 0 ? '季节·全部' : '季节·' + s)),
    success: (res) => {
      seasonIndex.value = res.tapIndex
      onFilterChange()
    }
  })
}

function showTip(item) {
  tipId.value = item.item_id
  tipText.value = TIPS[(item.item_id || 0) % TIPS.length]
  setTimeout(() => {
    if (tipId.value === item.item_id) tipId.value = null
  }, 1800)
}

function onCardClick(item) {
  if (dragged) {
    dragged = false
    return
  }
  if (item._offset) {
    closeItem(item)
    return
  }
  if (tipId.value === item.item_id) {
    uni.navigateTo({ url: `/pages/item/add?id=${item.item_id}` })
    return
  }
  showTip(item)
}
</script>

<template>
  <view class="page" :style="{ paddingTop: statusPad + 'px' }">
    <view v-if="spinning" class="spin-mask">
      <TaotaoSprite mood="spin" :size="140" />
    </view>

    <view class="title">我的衣橱👗</view>

    <scroll-view scroll-x class="cats" :show-scrollbar="false">
      <view
        v-for="tab in CAT_TABS"
        :key="tab.label"
        class="cat press-bounce"
        :class="{ on: typeIndex === tab.typeIndex }"
        :style="{ '--c': tab.color }"
        @click="selectCat(tab)"
      >{{ tab.label }}</view>
      <view class="filter-btn press-bounce" @click="openFilter">☰</view>
    </scroll-view>

    <view class="grid">
      <view v-for="item in items" :key="item.item_id" class="cell">
        <view class="cell-del" :style="{ width: DEL_WIDTH + 'px' }" @click="removeItem(item)">删除</view>
        <view
          class="cell-body press-bounce"
          :style="{ transform: 'translateX(' + (item._offset || 0) + 'px)' }"
          @touchstart="onTouchStart($event, item)"
          @touchmove="onTouchMove($event, item)"
          @touchend="onTouchEnd(item)"
          @click="onCardClick(item)"
        >
          <view class="thumb-wrap">
            <view class="thumb"><SafeImage :src="item.image_url" /></view>
            <view class="season-tag">{{ item.season || '未填' }}</view>
            <view v-if="item.season === '夏' || item.season === '春'" class="sun">☀</view>
          </view>
          <view v-if="tipId === item.item_id" class="bubble">
            <TaotaoSprite mood="wink" :size="52" />
            <text>{{ tipText }}</text>
          </view>
          <view class="bar">{{ item.type }} ｜ {{ item.color || '未填色' }}</view>
          <view class="meta">已穿{{ item.wear_count || 0 }}次
            <text class="style">{{ item.occasion || '日常' }}款</text>
          </view>
        </view>
      </view>
    </view>

    <view v-if="loadError && !items.length" class="empty">
      <TaotaoSprite mood="closet" :size="160" />
      <view class="empty-text">衣橱加载失败</view>
      <button class="btn-primary empty-btn" @click="reload">重试</button>
    </view>
    <view v-else-if="loaded && !items.length && !loading" class="empty">
      <TaotaoSprite mood="closet" :size="180" />
      <view class="empty-text">衣橱空空，快去上传你的漂亮衣服✨</view>
      <button class="btn-primary empty-btn" @click="goAdd">添加衣物</button>
    </view>
    <view v-else-if="loading && !items.length" class="loading-text">加载中…</view>
    <view v-else-if="items.length" class="loading-text">
      {{ finished ? '已经到底啦' : (loading ? '加载中…' : '上拉加载更多') }}
    </view>

    <view class="fab press-bounce" @click="goAdd">
      <text class="tee">👕</text>
    </view>

    <AppTabBar current="closet" />
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 8rpx 24rpx 40rpx;
  box-sizing: border-box;
}
.spin-mask {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(255,248,245,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
}
.title {
  text-align: center;
  font-size: 40rpx;
  font-weight: 800;
  margin-bottom: 16rpx;
}
.cats {
  white-space: nowrap;
  margin-bottom: 20rpx;
  width: 100%;
}
.cat {
  display: inline-flex;
  padding: 12rpx 28rpx;
  margin-right: 12rpx;
  border-radius: 999rpx;
  background: #fffdfb;
  border: 2rpx solid #f3d5dc;
  font-size: 24rpx;
  color: #8a7f88;
}
.cat.on {
  background: var(--c, #ff8fb1);
  color: #fff;
  border-color: transparent;
  font-weight: 700;
}
.filter-btn {
  display: inline-flex;
  width: 64rpx;
  height: 64rpx;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #fffdfb;
  border: 2rpx dashed #f3b8c8;
  vertical-align: middle;
}

.grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
}
.cell {
  position: relative;
  width: calc((100% - 20rpx) / 2);
  border-radius: 24rpx;
  overflow: hidden;
  background: #ff8fb1;
}
.cell-del {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 26rpx;
  z-index: 0;
}
.cell-body {
  position: relative;
  z-index: 1;
  background: #fffdfb;
  border-radius: 24rpx;
  overflow: hidden;
  box-shadow: 0 10rpx 36rpx rgba(255, 150, 175, 0.14);
  transition: transform 0.12s ease;
  border: 2rpx dashed #f3d5dc;
}
.thumb-wrap { position: relative; }
.thumb {
  width: 100%;
  height: 340rpx;
  background: #fff0f4;
}
.season-tag {
  position: absolute;
  left: 12rpx;
  top: 12rpx;
  background: #ffe4ed;
  color: #e05690;
  font-size: 20rpx;
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
  font-weight: 700;
}
.sun {
  position: absolute;
  right: 12rpx;
  top: 12rpx;
  font-size: 28rpx;
}
.bubble {
  position: absolute;
  left: 12rpx;
  right: 12rpx;
  top: 200rpx;
  background: #fffdfb;
  border: 2rpx dashed #ffb3c9;
  border-radius: 20rpx;
  padding: 8rpx 12rpx;
  display: flex;
  align-items: center;
  gap: 8rpx;
  font-size: 20rpx;
  color: #382e36;
  z-index: 3;
}
.bar {
  background: linear-gradient(90deg, #ffe4ed, #fff4c8);
  padding: 10rpx 16rpx;
  font-size: 24rpx;
  font-weight: 700;
}
.meta {
  padding: 8rpx 16rpx 16rpx;
  font-size: 20rpx;
  color: #8a7f88;
}
.style {
  margin-left: 8rpx;
  background: #dbeafe;
  color: #2563eb;
  padding: 2rpx 10rpx;
  border-radius: 999rpx;
  font-size: 18rpx;
}

.empty { padding: 80rpx 0; text-align: center; }
.empty-text { margin-top: 12rpx; color: #8a7f88; }
.empty-btn { margin-top: 28rpx; width: 360rpx; }
.loading-text { text-align: center; color: #8a7f88; font-size: 22rpx; padding: 24rpx 0; }

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
  z-index: 20;
}
.tee { font-size: 44rpx; }
</style>
