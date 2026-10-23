<script setup>
/**
 * 搭配选择页：从衣橱多选衣物，底部「已选 X 件 | 今天穿这套」
 *
 * 数据来源：GET /api/items（无筛选时默认 page=1 per_page=50，一次拉齐够选）
 * 选中状态：Pinia store/outfit.js，跨页不丢、完成后显式 clear
 */
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { get } from '@/utils/request'
import { useOutfitStore } from '@/store/outfit'

const store = useOutfitStore()

const items = ref([])
const loading = ref(false)
const perPage = 50

async function fetchItems() {
  loading.value = true
  try {
    const data = await get('/api/items', { page: 1, per_page: perPage })
    items.value = data.list || []
  } catch (e) {
    // 统一错误提示
  } finally {
    loading.value = false
  }
}

function isSelected(item) {
  return store.selectedItems.some((it) => it.item_id === item.item_id)
}

function toggle(item) {
  store.toggle(item)
}

const selectedCount = computed(() => store.selectedItems.length)

function confirm() {
  if (selectedCount.value === 0) {
    uni.showToast({ title: '请至少选一件衣物', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/pages/diary/create' })
}

function goAdd() {
  uni.navigateTo({ url: '/pages/item/add' })
}

onShow(() => {
  fetchItems()
})
</script>

<template>
  <view class="container">
    <!-- 头部已选摘要 -->
    <view v-if="store.selectedItems.length" class="card summary">
      <view class="summary-title">已选 {{ selectedCount }} 件</view>
      <scroll-view scroll-x class="summary-list">
        <view v-for="it in store.selectedItems" :key="it.item_id" class="summary-chip">
          <image :src="it.image_url" mode="aspectFill" class="chip-thumb" />
          <view class="chip-label">{{ it.type }}</view>
        </view>
      </scroll-view>
    </view>

    <!-- 衣橱网格 -->
    <view v-if="!items.length && !loading" class="empty">
      还没有衣物
      <button class="btn-ghost empty-btn" @click="goAdd">去添加</button>
    </view>

    <view class="grid">
      <view
        v-for="item in items"
        :key="item.item_id"
        class="cell"
        :class="{ selected: isSelected(item) }"
        @click="toggle(item)"
      >
        <image :src="item.image_url" mode="aspectFill" class="thumb" />
        <view class="name">{{ item.type }}<text v-if="item.color"> · {{ item.color }}</text></view>
        <view class="meta">{{ item.season || '—' }}</view>
        <view v-if="isSelected(item)" class="check">✓</view>
      </view>
    </view>

    <view v-if="loading" class="loading">加载中…</view>

    <!-- 底部固定操作栏 -->
    <view class="bottom-bar">
      <view class="bottom-left">
        已选 <text class="num">{{ selectedCount }}</text> 件
      </view>
      <button class="btn-primary confirm" :disabled="!selectedCount" @click="confirm">
        今天穿这套
      </button>
    </view>
    <view class="bottom-spacer" />
  </view>
</template>

<style scoped>
/* ---------- 已选摘要 ---------- */
.summary {
  padding: 20rpx 24rpx 14rpx;
}
.summary-title {
  font-size: 26rpx;
  color: #7b8794;
  margin-bottom: 14rpx;
}
.summary-list {
  white-space: nowrap;
}
.summary-chip {
  display: inline-flex;
  align-items: center;
  background: #eef3f9;
  border-radius: 999rpx;
  padding: 6rpx 16rpx 6rpx 6rpx;
  margin-right: 14rpx;
}
.chip-thumb {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  background: #fff;
  margin-right: 10rpx;
}
.chip-label {
  font-size: 24rpx;
  color: #3d5a80;
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
  background: #ffffff;
  border-radius: 20rpx;
  padding: 16rpx;
  box-shadow: 0 4rpx 20rpx rgba(143, 179, 217, 0.12);
  transition: border-color 0.15s ease;
  border: 2rpx solid transparent;
}
.cell.selected {
  border-color: #5b8def;
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
}
.meta {
  margin-top: 6rpx;
  font-size: 22rpx;
  color: #a4b0be;
}
.check {
  position: absolute;
  top: 16rpx;
  right: 16rpx;
  width: 44rpx;
  height: 44rpx;
  border-radius: 50%;
  background: #5b8def;
  color: #fff;
  font-size: 26rpx;
  line-height: 44rpx;
  text-align: center;
  box-shadow: 0 2rpx 8rpx rgba(91, 141, 239, 0.3);
}

/* ---------- 底部栏 ---------- */
.bottom-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: 116rpx;
  background: #ffffff;
  border-top: 1rpx solid #eef3f9;
  padding: 0 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  z-index: 20;
}
.bottom-left {
  font-size: 26rpx;
  color: #3d5a80;
}
.num {
  font-weight: 600;
  color: #5b8def;
  font-size: 34rpx;
}
.confirm {
  width: 340rpx;
  height: 80rpx;
  line-height: 80rpx;
  font-size: 28rpx;
}
.bottom-spacer {
  height: 140rpx;
}

/* ---------- 状态 ---------- */
.empty-btn {
  margin-top: 32rpx;
  width: 280rpx;
}
.loading {
  text-align: center;
  font-size: 24rpx;
  color: #a4b0be;
  padding: 32rpx 0;
}
</style>
