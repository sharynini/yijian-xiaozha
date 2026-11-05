<script setup>
/**
 * 穿搭日记详情
 * 入口：时间轴点卡片 → /pages/timeline/detail?log_id=12
 *
 * 展示：日期、当天天气与温度、拼贴图（或衣物缩略图）、心情、一句话、现场照片、当天衣物清单
 * 衣物清单来自日记的衣物快照；仍在衣橱里的可点进编辑页，已删除的标注出来
 * （逐件 GET /api/items/:id 静默检查，最多 12 件）
 *
 * 操作：编辑心情和日记（diary/edit）、删除这条记录（删除后返回时间轴，时间轴 onShow 会自动刷新）
 */
import { ref, computed } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { get, del } from '@/utils/request'
import { MOODS } from '@/utils/constants'
import OutfitCollage from '@/components/OutfitCollage.vue'
import SafeImage from '@/components/SafeImage.vue'
import TaotaoSprite from '@/components/TaotaoSprite.vue'

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

const logId = ref(null)
const log = ref(null)
const loading = ref(true)
const loadError = ref(false)
const missing = ref({})        // item_id → true：已从衣橱删除
const deleting = ref(false)

const dateText = computed(() => {
  if (!log.value || !log.value.wear_date) return ''
  const [y, m, d] = log.value.wear_date.split('-').map(Number)
  const week = WEEKDAYS[new Date(y, m - 1, d).getDay()]
  return `${y}年${m}月${d}日 · 周${week}`
})

const weatherText = computed(() => {
  const l = log.value
  if (!l) return ''
  const parts = []
  if (l.weather) parts.push(l.weather)
  if (l.temperature !== null && l.temperature !== undefined) parts.push(`${Math.round(l.temperature)}℃`)
  return parts.join(' · ')
})

const moodIcon = computed(() => {
  const label = log.value && log.value.mood
  const found = label && MOODS.find((m) => m.label === label)
  return found ? found.icon : ''
})

async function loadDetail() {
  if (!logId.value) return
  loading.value = true
  loadError.value = false
  try {
    log.value = await get(`/api/wear-logs/${logId.value}`, {}, { skipDedup: true })
    checkItems(log.value.items || [])
  } catch (e) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

/** 静默检查快照里的衣物是否还在衣橱（不弹错误提示） */
async function checkItems(items) {
  const result = {}
  await Promise.all(items.map(async (it) => {
    try {
      await get(`/api/items/${it.item_id}`, {}, { silent: true })
    } catch (e) {
      if (e && e.code === 2001) result[it.item_id] = true
    }
  }))
  missing.value = result
}

function previewPhoto() {
  if (!log.value || !log.value.photo_url) return
  uni.previewImage({ urls: [log.value.photo_url], current: log.value.photo_url })
}

function openItem(it) {
  if (missing.value[it.item_id]) {
    uni.showToast({ title: '这件衣服已从衣橱删除', icon: 'none' })
    return
  }
  uni.navigateTo({ url: `/pages/item/add?id=${it.item_id}` })
}

function goEdit() {
  uni.navigateTo({ url: `/pages/diary/edit?log_id=${logId.value}` })
}

function onDelete() {
  if (deleting.value) return
  uni.showModal({
    title: '删除这条记录',
    content: '删除后时间轴里就看不到这天的穿搭了，衣橱里的衣服不受影响。确定删除吗？',
    confirmColor: '#e5484d',
    success: async (res) => {
      if (!res.confirm) return
      deleting.value = true
      try {
        await del(`/api/wear-logs/${logId.value}`)
        uni.showToast({ title: '已删除', icon: 'success' })
        setTimeout(() => uni.navigateBack(), 600)
      } catch (e) {
        // request.js 已提示
      } finally {
        deleting.value = false
      }
    }
  })
}

let firstShow = true
onLoad((query = {}) => {
  logId.value = query.log_id
  loadDetail()
})

// 从编辑页返回时刷新心情和文字
onShow(() => {
  if (firstShow) {
    firstShow = false
    return
  }
  loadDetail()
})
</script>

<template>
  <view class="page">
    <view v-if="loading && !log" class="state">加载中…</view>

    <view v-else-if="loadError && !log" class="state">
      <TaotaoSprite mood="book" :size="150" />
      <view class="state-t">这条日记加载失败，可能已被删除</view>
      <button class="btn-primary state-btn" @click="loadDetail">重试</button>
    </view>

    <template v-else-if="log">
      <view class="head">
        <view class="date">{{ dateText }}</view>
        <view v-if="weatherText" class="weather">🌤 {{ weatherText }}</view>
      </view>

      <!-- 拼贴图 / 衣物缩略图 -->
      <view class="cover-card">
        <view class="cover">
          <OutfitCollage v-if="log.collage" :collage="log.collage" :items="log.items" />
          <view v-else class="thumbs">
            <view v-for="it in (log.items || []).slice(0, 4)" :key="it.item_id" class="thumb">
              <SafeImage :src="it.image_url" mode="aspectFit" />
            </view>
          </view>
        </view>
      </view>

      <!-- 心情与一句话 -->
      <view class="note-card">
        <view class="mood-row">
          <text class="mood-ico">{{ moodIcon || '📝' }}</text>
          <text class="mood-txt">{{ log.mood || '没有记录心情' }}</text>
        </view>
        <view class="content" :class="{ empty: !log.content }">{{ log.content || '这天没有写一句话' }}</view>
      </view>

      <!-- 现场照片 -->
      <view v-if="log.photo_url" class="section">
        <view class="sec-title">现场照片</view>
        <view class="photo" @click="previewPhoto"><SafeImage :src="log.photo_url" mode="aspectFill" /></view>
      </view>

      <!-- 当天衣物 -->
      <view class="section">
        <view class="sec-title">这天穿了 {{ (log.items || []).length }} 件</view>
        <view class="items">
          <view
            v-for="it in log.items || []"
            :key="it.item_id"
            class="item press-bounce"
            :class="{ gone: missing[it.item_id] }"
            @click="openItem(it)"
          >
            <view class="item-img"><SafeImage :src="it.image_url" mode="aspectFit" /></view>
            <view class="item-name">{{ it.type }}{{ it.color ? '·' + it.color : '' }}</view>
            <view v-if="missing[it.item_id]" class="item-gone">已从衣橱删除</view>
          </view>
        </view>
      </view>

      <view class="actions">
        <view class="act ghost press-bounce" @click="onDelete">{{ deleting ? '删除中…' : '删除这条记录' }}</view>
        <view class="act primary press-bounce" @click="goEdit">编辑心情和日记</view>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 24rpx 28rpx calc(160rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
  background: #fff8f5;
}
.state {
  padding: 160rpx 0;
  text-align: center;
  color: #8a7f88;
  font-size: 26rpx;
}
.state-t {
  margin-top: 16rpx;
}
.state-btn {
  margin-top: 28rpx;
  width: 260rpx;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20rpx;
}
.date {
  font-size: 34rpx;
  font-weight: 800;
  color: #382e36;
}
.weather {
  font-size: 24rpx;
  color: #8a7f88;
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  background: #fffdfb;
  border: 2rpx dashed #f3d5dc;
}
.cover-card {
  padding: 16rpx;
  background: #fffdfb;
  border-radius: 32rpx;
  box-shadow: 0 10rpx 30rpx rgba(255, 150, 175, 0.12);
}
.cover {
  width: 100%;
  height: 620rpx;
  border-radius: 24rpx;
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
  padding: 10rpx;
}
.note-card {
  margin-top: 24rpx;
  padding: 24rpx 28rpx;
  background: #fffdfb;
  border-radius: 28rpx;
  border: 2rpx dashed #f3b8c8;
}
.mood-row {
  display: flex;
  align-items: center;
}
.mood-ico {
  font-size: 40rpx;
  margin-right: 12rpx;
}
.mood-txt {
  font-size: 28rpx;
  font-weight: 700;
  color: #382e36;
}
.content {
  margin-top: 14rpx;
  font-size: 28rpx;
  line-height: 1.7;
  color: #382e36;
}
.content.empty {
  color: #b5aab0;
}
.section {
  margin-top: 28rpx;
}
.sec-title {
  font-size: 26rpx;
  font-weight: 700;
  color: #8a7f88;
  margin-bottom: 14rpx;
}
.photo {
  width: 100%;
  height: 420rpx;
  border-radius: 24rpx;
  overflow: hidden;
}
.items {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}
.item {
  width: calc((100% - 32rpx) / 3);
  padding: 10rpx;
  box-sizing: border-box;
  background: #fffdfb;
  border-radius: 20rpx;
  box-shadow: 0 6rpx 16rpx rgba(255, 150, 175, 0.1);
  position: relative;
}
.item.gone {
  opacity: 0.55;
}
.item-img {
  width: 100%;
  height: 180rpx;
  border-radius: 14rpx;
  background: #fff0f4;
}
.item-name {
  margin-top: 8rpx;
  font-size: 22rpx;
  color: #382e36;
  text-align: center;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.item-gone {
  font-size: 20rpx;
  color: #c45a6a;
  text-align: center;
}
.actions {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 30;
  display: flex;
  gap: 20rpx;
  padding: 18rpx 28rpx calc(18rpx + env(safe-area-inset-bottom));
  background: #fffdfb;
  box-shadow: 0 -8rpx 24rpx rgba(255, 150, 175, 0.1);
}
.act {
  height: 84rpx;
  line-height: 84rpx;
  text-align: center;
  border-radius: 999rpx;
  font-size: 28rpx;
  font-weight: 700;
}
.act.ghost {
  padding: 0 32rpx;
  color: #c45a6a;
  background: #fff8f5;
  border: 2rpx dashed #f3c2cc;
}
.act.primary {
  flex: 1;
  color: #fff;
  background: linear-gradient(180deg, #ffb3c9 0%, #ff8fb1 72%);
  box-shadow: 0 10rpx 22rpx rgba(255, 143, 177, 0.35);
}
</style>
