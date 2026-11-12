<script setup>
/**
 * 我的搭配列表（嵌在「衣橱」页的「搭配」标签里）
 *   - GET /api/outfits 分页；下拉刷新 / 上拉加载由所在页面调用 reload() / loadMore()
 *   - 卡片：有画布布局显示拼贴图，没有则显示前 4 件衣物缩略图
 *   - 点卡片：今天穿这套 / 在画布中编辑 / 重命名 / 删除
 *
 * 注意：连续弹两个系统弹窗（动作面板 → 输入框/确认框）时要等前一个收起（约 350ms），
 * 否则 H5 端后一个会被吞掉。
 */
import { ref, computed } from 'vue'
import { get, put, del } from '@/utils/request'
import { useOutfitStore } from '@/store/outfit'
import { ensureHasItems } from '@/utils/wardrobe'
import OutfitCollage from '@/components/OutfitCollage.vue'
import SafeImage from '@/components/SafeImage.vue'
import TaotaoSprite from '@/components/TaotaoSprite.vue'

const PER_PAGE = 10
const NEXT_MODAL_DELAY = 350

const store = useOutfitStore()

const list = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const loaded = ref(false)
const loadError = ref(false)

const finished = computed(() => loaded.value && list.value.length >= total.value)

async function fetchList(reset) {
  if (loading.value) return
  loading.value = true
  loadError.value = false
  const target = reset ? 1 : page.value
  try {
    const data = await get('/api/outfits', { page: target, per_page: PER_PAGE }, { skipDedup: reset })
    list.value = reset ? data.list || [] : [...list.value, ...(data.list || [])]
    total.value = data.total || 0
    page.value = target
    loaded.value = true
  } catch (e) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function reload() {
  return fetchList(true)
}

/** 原地刷新：重新拉取已加载的前几页，列表长度不变，从画布编辑页返回时停在原位置 */
async function refreshInPlace() {
  if (!loaded.value || page.value <= 1 || !list.value.length) return reload()
  if (loading.value) return
  loading.value = true
  loadError.value = false
  try {
    const pages = await Promise.all(
      Array.from({ length: page.value }, (_, i) =>
        get('/api/outfits', { page: i + 1, per_page: PER_PAGE }, { skipDedup: true }))
    )
    const seen = new Set()
    const merged = []
    pages.forEach((d) => (d.list || []).forEach((o) => {
      if (!seen.has(o.outfit_id)) {
        seen.add(o.outfit_id)
        merged.push(o)
      }
    }))
    list.value = merged
    total.value = pages[0].total || 0
  } catch (e) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function loadMore() {
  if (finished.value || loading.value) return
  page.value += 1
  fetchList(false)
}

defineExpose({ reload, refreshInPlace, loadMore })

// ---------- 卡片操作 ----------
function onCardClick(outfit) {
  const usable = outfit.item_count > 0
  const actions = usable
    ? ['今天穿这套', '在画布中编辑', '重命名', '删除']
    : ['重命名', '删除']
  uni.showActionSheet({
    itemList: actions,
    success: ({ tapIndex }) => {
      const action = actions[tapIndex]
      if (action === '今天穿这套') wearToday(outfit)
      else if (action === '在画布中编辑') editInCanvas(outfit)
      else if (action === '重命名') setTimeout(() => rename(outfit), NEXT_MODAL_DELAY)
      else if (action === '删除') setTimeout(() => remove(outfit), NEXT_MODAL_DELAY)
    }
  })
}

function wearToday(outfit) {
  store.setOutfit(outfit.items, outfit.collage)
  uni.navigateTo({ url: '/pages/diary/create' })
}

function editInCanvas(outfit) {
  uni.navigateTo({ url: `/pages/outfit/canvas?outfit_id=${outfit.outfit_id}` })
}

function rename(outfit) {
  uni.showModal({
    title: '重命名搭配',
    editable: true,
    content: outfit.name,
    placeholderText: '新的名字',
    confirmColor: '#ff8fb1',
    success: async (res) => {
      if (!res.confirm) return
      const name = (res.content || '').trim()
      if (!name) {
        uni.showToast({ title: '名字不能为空', icon: 'none' })
        return
      }
      if (name.length > 30) {
        uni.showToast({ title: '名字最多 30 个字', icon: 'none' })
        return
      }
      if (name === outfit.name) return
      try {
        const data = await put(`/api/outfits/${outfit.outfit_id}`, { name })
        outfit.name = data.name
        uni.showToast({ title: '已重命名', icon: 'success' })
      } catch (e) {
        // request.js 已提示
      }
    }
  })
}

function remove(outfit) {
  uni.showModal({
    title: '删除搭配',
    content: `删除「${outfit.name}」吗？已经用它记录的日记不受影响。`,
    confirmColor: '#e5484d',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await del(`/api/outfits/${outfit.outfit_id}`)
        list.value = list.value.filter((o) => o.outfit_id !== outfit.outfit_id)
        total.value = Math.max(0, total.value - 1)
        uni.showToast({ title: '已删除', icon: 'success' })
      } catch (e) {
        // request.js 已提示
      }
    }
  })
}

async function goCanvas() {
  if (!(await ensureHasItems())) return
  uni.navigateTo({ url: '/pages/outfit/canvas' })
}
</script>

<template>
  <view class="outfit-list">
    <view class="grid">
      <view
        v-for="outfit in list"
        :key="outfit.outfit_id"
        class="card press-bounce"
        @click="onCardClick(outfit)"
      >
        <view class="cover">
          <OutfitCollage v-if="outfit.collage" :collage="outfit.collage" :items="outfit.items" />
          <view v-else-if="outfit.items.length" class="thumbs">
            <view v-for="it in outfit.items.slice(0, 4)" :key="it.item_id" class="thumb">
              <SafeImage :src="it.image_url" mode="aspectFit" />
            </view>
          </view>
          <view v-else class="gone">衣服都被删除啦</view>
        </view>
        <view class="name">{{ outfit.name }}</view>
        <view class="meta">{{ outfit.item_count }} 件</view>
      </view>
    </view>

    <view v-if="loadError && !list.length" class="empty">
      <TaotaoSprite mood="closet" :size="140" />
      <view class="empty-text">搭配加载失败</view>
      <button class="btn-primary empty-btn" @click="reload">重试</button>
    </view>
    <view v-else-if="loaded && !list.length && !loading" class="empty">
      <TaotaoSprite mood="closet" :size="150" />
      <view class="empty-text">还没有保存的搭配，去画布拼一套，点「保存」就会出现在这里</view>
      <button class="btn-primary empty-btn" @click="goCanvas">去搭一套</button>
    </view>
    <view v-else-if="loading && !list.length" class="loading-text">加载中…</view>
    <view v-else-if="list.length" class="loading-text">
      {{ finished ? '已经到底啦' : (loading ? '加载中…' : '上拉加载更多') }}
    </view>
  </view>
</template>

<style scoped>
.outfit-list {
  padding: 0 20rpx 0 20rpx;
}
.grid {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
}
.card {
  width: calc(50% - 10rpx);
  margin-bottom: 20rpx;
  padding: 14rpx;
  box-sizing: border-box;
  background: #fffdfb;
  border-radius: 28rpx;
  box-shadow: 0 10rpx 28rpx rgba(255, 150, 175, 0.12);
}
.cover {
  width: 100%;
  height: 300rpx;
  border-radius: 20rpx;
  overflow: hidden;
  background: #fffaf7;
}
.thumbs {
  display: flex;
  flex-wrap: wrap;
  width: 100%;
  height: 100%;
}
.thumb {
  width: 50%;
  height: 50%;
  box-sizing: border-box;
  padding: 6rpx;
}
.gone {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b5aab0;
  font-size: 24rpx;
}
.name {
  margin-top: 12rpx;
  font-size: 28rpx;
  font-weight: 700;
  color: #382e36;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.meta {
  margin-top: 4rpx;
  font-size: 22rpx;
  color: #8a7f88;
}
.empty { padding: 60rpx 0; text-align: center; }
.empty-text { margin-top: 12rpx; color: #8a7f88; font-size: 24rpx; padding: 0 40rpx; }
.empty-btn { margin-top: 24rpx; width: 300rpx; }
.loading-text { text-align: center; color: #8a7f88; font-size: 22rpx; padding: 24rpx 0; }
</style>
