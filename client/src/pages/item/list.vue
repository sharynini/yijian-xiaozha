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

const PER_PAGE = 10

const items = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const loaded = ref(false)      // 是否已完成过一次请求（用于区分「空数据」与「还没加载」）

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
    // 统一错误提示
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
  await reload()
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
</script>

<template>
  <view class="container">
    <!-- 筛选栏 -->
    <view class="card filter">
      <view class="filter-row">
        <picker
          class="filter-item"
          :range="FILTER_SEASONS"
          :value="seasonIndex"
          @change="e => { seasonIndex = Number(e.detail.value); onFilterChange() }"
        >
          <view class="pill">{{ seasonIndex === 0 ? '季节' : FILTER_SEASONS[seasonIndex] }}</view>
        </picker>

        <picker
          class="filter-item"
          :range="FILTER_TYPES"
          :value="typeIndex"
          @change="e => { typeIndex = Number(e.detail.value); onFilterChange() }"
        >
          <view class="pill">{{ typeIndex === 0 ? '类型' : FILTER_TYPES[typeIndex] }}</view>
        </picker>

        <picker
          class="filter-item"
          :range="FILTER_COLORS"
          :value="colorIndex"
          @change="e => { colorIndex = Number(e.detail.value); onFilterChange() }"
        >
          <view class="pill">{{ colorIndex === 0 ? '颜色' : FILTER_COLORS[colorIndex] }}</view>
        </picker>
      </view>
      <view class="count">共 {{ total }} 件</view>
    </view>

    <!-- 网格列表 -->
    <view class="grid">
      <view v-for="item in items" :key="item.item_id" class="cell">
        <view class="cell-del" :style="{ width: DEL_WIDTH + 'px' }" @click="removeItem(item)">删除</view>
        <view
          class="cell-body"
          :style="{ transform: 'translateX(' + (item._offset || 0) + 'px)' }"
          @touchstart="onTouchStart($event, item)"
          @touchmove="onTouchMove($event, item)"
          @touchend="onTouchEnd(item)"
          @click="goEdit(item)"
        >
          <image class="thumb" :src="item.image_url" mode="aspectFill" />
          <view class="name">{{ item.type }}<text v-if="item.color"> · {{ item.color }}</text></view>
          <view class="meta">
            <text>{{ item.season || '未填季节' }}</text>
            <text class="dot">·</text>
            <text>穿{{ item.wear_count }}次</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 空状态 -->
    <view v-if="loaded && !items.length && !loading" class="empty">
      <view class="empty-text">还没有衣物，去添加第一件吧</view>
      <button class="btn-primary empty-btn" @click="goAdd">添加衣物</button>
    </view>

    <!-- 加载状态 -->
    <view v-else-if="loading && !items.length" class="loading-text">加载中…</view>
    <view v-else-if="items.length" class="loading-text">
      {{ finished ? '已经到底啦' : (loading ? '加载中…' : '上拉加载更多') }}
    </view>

    <!-- 悬浮添加按钮 -->
    <view class="fab" @click="goAdd">＋</view>
  </view>
</template>

<style scoped>
/* ---------- 筛选栏 ---------- */
.filter {
  padding: 24rpx 28rpx;
}
.filter-row {
  display: flex;
  gap: 16rpx;
}
.filter-item {
  flex: 1;
}
.pill {
  background: #eef3f9;
  color: #3d5a80;
  border-radius: 12rpx;
  padding: 14rpx 0;
  font-size: 26rpx;
  text-align: center;
  overflow: hidden;
  white-space: nowrap;
}
.count {
  margin-top: 18rpx;
  font-size: 24rpx;
  color: #7b8794;
}

/* ---------- 网格 ---------- */
.grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
}
.cell {
  position: relative;
  width: calc((100% - 20rpx) / 2);
  border-radius: 20rpx;
  overflow: hidden;
  background: #e05c5c;
  box-shadow: 0 4rpx 20rpx rgba(143, 179, 217, 0.12);
}
.cell-del {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 26rpx;
  z-index: 0;
}
.cell-body {
  position: relative;
  z-index: 1;
  background: #ffffff;
  border-radius: 20rpx;
  padding: 16rpx;
  transition: transform 0.2s ease;
  will-change: transform;
}
.thumb {
  width: 100%;
  height: 320rpx;
  border-radius: 14rpx;
  background: #eef3f9;
}
.name {
  margin-top: 14rpx;
  font-size: 26rpx;
  color: #2b3441;
  overflow: hidden;
  white-space: nowrap;
}
.meta {
  margin-top: 6rpx;
  font-size: 22rpx;
  color: #a4b0be;
}
.dot {
  margin: 0 8rpx;
}

/* ---------- 状态 ---------- */
.empty {
  padding: 140rpx 0 60rpx;
  text-align: center;
}
.empty-text {
  font-size: 28rpx;
  color: #a4b0be;
}
.empty-btn {
  margin-top: 40rpx;
  width: 360rpx;
}
.loading-text {
  text-align: center;
  font-size: 24rpx;
  color: #a4b0be;
  padding: 32rpx 0;
}

/* ---------- 悬浮按钮 ---------- */
.fab {
  position: fixed;
  right: 40rpx;
  bottom: 60rpx;
  width: 100rpx;
  height: 100rpx;
  border-radius: 50%;
  background: #5b8def;
  color: #ffffff;
  font-size: 56rpx;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(91, 141, 239, 0.35);
  z-index: 10;
}
</style>
