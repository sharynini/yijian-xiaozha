<script setup>
/**
 * 衣物列表页（衣橱 tab）
 *   - 左侧导航：筛选（颜色/季节/场合组合筛选面板）+ 全部 + 各分类
 *   - 右侧两列网格，卡片展示类型 / 颜色 / 季节 / 场合
 *   - 下拉刷新 + 上拉加载更多
 *   - 左滑出现「删除」按钮（软删除 DELETE /api/items/<id>）
 *   - 点击卡片进入编辑页
 *   - 顶部「衣物 | 搭配」切换：搭配标签显示 OutfitList（我的搭配），下拉刷新 / 上拉加载转交给它
 */
import { ref, computed } from 'vue'
import { onShow, onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
import { get, del } from '@/utils/request'
import { ITEM_TYPES, SEASONS, OCCASIONS, COLORS } from '@/utils/constants'
import TaotaoSprite from '@/components/TaotaoSprite.vue'
import AppTabBar from '@/components/AppTabBar.vue'
import SafeImage from '@/components/SafeImage.vue'
import OutfitList from '@/components/OutfitList.vue'

// 顶部标签：items 衣物 / outfits 搭配
const tab = ref('items')
const outfitListRef = ref(null)

function switchTab(next) {
  if (tab.value === next) return
  tab.value = next
  if (next === 'outfits') outfitListRef.value && outfitListRef.value.reload()
}

// 左侧分类：value 为空表示「全部」
const CATEGORIES = [{ label: '全部', value: '' }, ...ITEM_TYPES.map((t) => ({ label: t, value: t }))]

const statusPad = (uni.getSystemInfoSync().statusBarHeight || 12) + 8
const spinning = ref(false)

const PER_PAGE = 10

const items = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const loaded = ref(false)      // 是否已完成过一次请求（用于区分「空数据」与「还没加载」）
const loadError = ref(false)

// ---------- 分类与筛选 ----------
const currentType = ref('')
// 已生效的筛选条件；空串表示不限
const filters = ref({ color: '', season: '', occasion: '' })
// 面板里正在编辑、还没点「确定」的筛选条件
const draft = ref({ color: '', season: '', occasion: '' })
const showFilter = ref(false)

const FILTER_GROUPS = [
  { key: 'season', title: '季节', options: SEASONS },
  { key: 'occasion', title: '场合', options: OCCASIONS },
  { key: 'color', title: '颜色', options: COLORS }
]

const activeFilterChips = computed(() =>
  FILTER_GROUPS
    .filter((g) => filters.value[g.key])
    .map((g) => ({ key: g.key, text: `${g.title}·${filters.value[g.key]}` }))
)

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
    if (currentType.value) params.type = currentType.value
    Object.entries(filters.value).forEach(([k, v]) => {
      if (v) params[k] = v
    })

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

function selectType(cat) {
  if (currentType.value === cat.value) return
  currentType.value = cat.value
  reload()
}

function openFilter() {
  draft.value = { ...filters.value }
  showFilter.value = true
}

function toggleDraft(key, value) {
  draft.value[key] = draft.value[key] === value ? '' : value
}

function resetDraft() {
  draft.value = { color: '', season: '', occasion: '' }
}

function applyFilter() {
  filters.value = { ...draft.value }
  showFilter.value = false
  reload()
}

function clearChip(key) {
  filters.value[key] = ''
  reload()
}

// ---------- 生命周期 ----------
onShow(() => {
  // 从添加/编辑页、画布页返回或切回衣橱 tab 时刷新当前标签
  if (tab.value === 'outfits') outfitListRef.value && outfitListRef.value.reload()
  else reload()
})

onPullDownRefresh(async () => {
  spinning.value = true
  if (tab.value === 'outfits') await (outfitListRef.value && outfitListRef.value.reload())
  else await reload()
  spinning.value = false
  uni.stopPullDownRefresh()
})

onReachBottom(() => {
  if (tab.value === 'outfits') {
    outfitListRef.value && outfitListRef.value.loadMore()
    return
  }
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
function onCardClick(item) {
  if (dragged) {
    dragged = false
    return
  }
  if (item._offset) {
    // 已展开删除按钮时，点击先收起
    closeItem(item)
    return
  }
  uni.navigateTo({ url: `/pages/item/add?id=${item.item_id}` })
}

function goAdd() {
  uni.navigateTo({ url: '/pages/item/add' })
}

/** 卡片上展示的标签：类型 / 颜色 / 季节 / 场合，四个都显示；没填的显示灰色「未填」 */
function cardTags(item) {
  return [
    { key: 'type', text: item.type, empty: '类型未填' },
    { key: 'color', text: item.color, empty: '颜色未填' },
    { key: 'season', text: item.season, empty: '季节未填' },
    { key: 'occasion', text: item.occasion, empty: '场合未填' }
  ].map((t) => ({ key: t.key, text: t.text || t.empty, cls: t.text ? t.key : 'none' }))
}
</script>

<template>
  <view class="page" :style="{ paddingTop: statusPad + 'px' }">
    <view v-if="spinning" class="spin-mask">
      <TaotaoSprite mood="spin" :size="140" />
    </view>

    <view class="title">我的衣橱👗</view>

    <view class="tabs">
      <view class="tab" :class="{ on: tab === 'items' }" @click="switchTab('items')">衣物</view>
      <view class="tab" :class="{ on: tab === 'outfits' }" @click="switchTab('outfits')">搭配</view>
    </view>

    <!-- 小程序里自定义组件不支持直接 v-show，外面包一层 view -->
    <view v-show="tab === 'outfits'">
      <OutfitList ref="outfitListRef" />
    </view>

    <view v-show="tab === 'items'" class="body">
      <!-- 左侧导航 -->
      <view class="side" :style="{ top: statusPad + 'px' }">
        <view
          class="side-item filter press-bounce"
          :class="{ active: activeFilterChips.length }"
          @click="openFilter"
        >
          <text class="filter-ico">☰</text>
          <text>筛选</text>
          <view v-if="activeFilterChips.length" class="dot">{{ activeFilterChips.length }}</view>
        </view>
        <view
          v-for="cat in CATEGORIES"
          :key="cat.label"
          class="side-item"
          :class="{ on: currentType === cat.value }"
          @click="selectType(cat)"
        >{{ cat.label }}</view>
      </view>

      <!-- 右侧内容 -->
      <view class="main">
        <view v-if="activeFilterChips.length" class="chips">
          <view
            v-for="chip in activeFilterChips"
            :key="chip.key"
            class="chip"
            @click="clearChip(chip.key)"
          >{{ chip.text }} ✕</view>
        </view>

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
              <view class="thumb"><SafeImage :src="item.image_url" /></view>
              <view class="tags">
                <text v-for="tag in cardTags(item)" :key="tag.key" class="tag" :class="tag.cls">{{ tag.text }}</text>
              </view>
              <view class="meta">已穿 {{ item.wear_count || 0 }} 次</view>
            </view>
          </view>
        </view>

        <view v-if="loadError && !items.length" class="empty">
          <TaotaoSprite mood="closet" :size="140" />
          <view class="empty-text">衣橱加载失败</view>
          <button class="btn-primary empty-btn" @click="reload">重试</button>
        </view>
        <view v-else-if="loaded && !items.length && !loading" class="empty">
          <TaotaoSprite mood="closet" :size="150" />
          <view class="empty-text">
            {{ currentType || activeFilterChips.length ? '这里还没有符合条件的衣服' : '衣橱空空，快去上传你的漂亮衣服✨' }}
          </view>
          <button class="btn-primary empty-btn" @click="goAdd">添加衣物</button>
        </view>
        <view v-else-if="loading && !items.length" class="loading-text">加载中…</view>
        <view v-else-if="items.length" class="loading-text">
          {{ finished ? '已经到底啦' : (loading ? '加载中…' : '上拉加载更多') }}
        </view>
      </view>
    </view>

    <view v-if="tab === 'items'" class="fab press-bounce" @click="goAdd">
      <text class="tee">👕</text>
    </view>

    <!-- 筛选面板（从底部弹出） -->
    <view v-if="showFilter" class="mask" @click="showFilter = false">
      <view class="panel" @click.stop>
        <view class="panel-title">筛选衣物</view>
        <scroll-view scroll-y class="panel-body">
          <view v-for="group in FILTER_GROUPS" :key="group.key" class="group">
            <view class="group-title">{{ group.title }}</view>
            <view class="opts">
              <view
                v-for="opt in group.options"
                :key="opt"
                class="opt"
                :class="{ on: draft[group.key] === opt }"
                @click="toggleDraft(group.key, opt)"
              >{{ opt }}</view>
            </view>
          </view>
        </scroll-view>
        <view class="panel-actions">
          <view class="btn-ghost" @click="resetDraft">重置</view>
          <view class="btn-ok" @click="applyFilter">确定</view>
        </view>
      </view>
    </view>

    <AppTabBar current="closet" />
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 8rpx 20rpx 40rpx 0;
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
  padding-left: 20rpx;
}

.tabs {
  display: flex;
  justify-content: center;
  margin: 0 0 20rpx 20rpx;
}
.tab {
  padding: 10rpx 44rpx;
  margin: 0 8rpx;
  border-radius: 999rpx;
  font-size: 28rpx;
  color: #8a7f88;
  background: #fffdfb;
  border: 2rpx dashed #f3d5dc;
}
.tab.on {
  color: #fff;
  font-weight: 700;
  background: linear-gradient(180deg, #ffb3c9 0%, #ff8fb1 72%);
  border-color: transparent;
}
.body {
  display: flex;
  align-items: flex-start;
}

/* ---------- 左侧导航 ---------- */
.side {
  position: sticky;
  flex-shrink: 0;
  width: 148rpx;
  margin-right: 16rpx;
  background: #fffdfb;
  border-radius: 0 28rpx 28rpx 0;
  box-shadow: 0 10rpx 30rpx rgba(255, 150, 175, 0.12);
  padding: 12rpx 0;
  z-index: 5;
}
.side-item {
  position: relative;
  height: 84rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26rpx;
  color: #8a7f88;
}
.side-item.on {
  color: #ff8fb1;
  font-weight: 800;
  background: #fff0f5;
}
.side-item.on::before {
  content: '';
  position: absolute;
  left: 0;
  top: 22rpx;
  bottom: 22rpx;
  width: 8rpx;
  border-radius: 0 8rpx 8rpx 0;
  background: #ff8fb1;
}
.side-item.filter {
  margin: 0 14rpx 10rpx;
  border: 2rpx dashed #f3b8c8;
  border-radius: 20rpx;
  gap: 6rpx;
  font-size: 24rpx;
}
.side-item.filter.active {
  background: #ff8fb1;
  border-color: #ff8fb1;
  color: #fff;
  font-weight: 700;
}
.filter-ico { font-size: 22rpx; }
.dot {
  position: absolute;
  top: -10rpx;
  right: -8rpx;
  min-width: 30rpx;
  height: 30rpx;
  line-height: 30rpx;
  padding: 0 6rpx;
  border-radius: 999rpx;
  background: #ffd56b;
  color: #382e36;
  font-size: 18rpx;
  text-align: center;
  box-sizing: border-box;
}

/* ---------- 右侧内容 ---------- */
.main {
  flex: 1;
  min-width: 0;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-bottom: 16rpx;
}
.chip {
  font-size: 22rpx;
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  background: #ffe4ed;
  color: #e05690;
}
.grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}
.cell {
  position: relative;
  width: calc((100% - 16rpx) / 2);
  border-radius: 22rpx;
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
  border-radius: 22rpx;
  overflow: hidden;
  box-shadow: 0 10rpx 30rpx rgba(255, 150, 175, 0.12);
  transition: transform 0.12s ease;
  border: 2rpx solid #fbe3ea;
}
.thumb {
  width: 100%;
  height: 260rpx;
  background: #fff0f4;
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6rpx;
  padding: 12rpx 12rpx 0;
}
.tag {
  font-size: 18rpx;
  line-height: 1.6;
  padding: 0 10rpx;
  border-radius: 999rpx;
}
.tag.type { background: #ffe4ed; color: #e05690; font-weight: 700; }
.tag.color { background: #f3eefe; color: #7c5cd6; }
.tag.season { background: #e3f7ec; color: #2f9e63; }
.tag.occasion { background: #e3efff; color: #2563eb; }
.tag.none { background: #f4f1f3; color: #b3a7b0; }
.meta {
  padding: 8rpx 12rpx 14rpx;
  font-size: 20rpx;
  color: #a79ca5;
}

.empty { padding: 60rpx 0; text-align: center; }
.empty-text { margin-top: 12rpx; color: #8a7f88; font-size: 24rpx; padding: 0 12rpx; }
.empty-btn { margin-top: 24rpx; width: 300rpx; }
.loading-text { text-align: center; color: #8a7f88; font-size: 22rpx; padding: 24rpx 0; }

.fab {
  position: fixed;
  right: 28rpx;
  bottom: 180rpx;
  width: 110rpx;
  height: 110rpx;
  border-radius: 50%;
  background: linear-gradient(180deg, #ffb3c9, #ff8fb1);
  box-shadow: 0 12rpx 24rpx rgba(255, 143, 177, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.tee { font-size: 44rpx; }

/* ---------- 筛选面板 ---------- */
.mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(56, 46, 54, 0.35);
  display: flex;
  align-items: flex-end;
}
.panel {
  width: 100%;
  background: #fffdfb;
  border-radius: 32rpx 32rpx 0 0;
  padding: 28rpx 28rpx calc(28rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
  animation: slide-up 0.22s ease;
}
.panel-title {
  text-align: center;
  font-size: 30rpx;
  font-weight: 800;
  margin-bottom: 12rpx;
}
.panel-body { max-height: 60vh; }
.group { margin-top: 20rpx; }
.group-title {
  font-size: 24rpx;
  font-weight: 700;
  color: #382e36;
  margin-bottom: 12rpx;
}
.opts {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
}
.opt {
  padding: 10rpx 24rpx;
  border-radius: 999rpx;
  background: #fff5f8;
  border: 2rpx solid #fbe3ea;
  font-size: 24rpx;
  color: #8a7f88;
}
.opt.on {
  background: #ff8fb1;
  border-color: #ff8fb1;
  color: #fff;
  font-weight: 700;
}
.panel-actions {
  display: flex;
  gap: 20rpx;
  margin-top: 28rpx;
}
.btn-ghost,
.btn-ok {
  flex: 1;
  height: 84rpx;
  line-height: 84rpx;
  text-align: center;
  border-radius: 999rpx;
  font-size: 28rpx;
  font-weight: 700;
}
.btn-ghost { background: #fff5f8; color: #ff8fb1; border: 2rpx dashed #ffb3c9; }
.btn-ok { background: linear-gradient(180deg, #ffb3c9, #ff8fb1); color: #fff; }

@keyframes slide-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
</style>
