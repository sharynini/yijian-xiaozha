<script setup>
/**
 * 批量添加衣物：/pages/item/batch
 *
 * 「先存后改」：一次选多张照片，每张自动走
 *   上传 POST /api/upload → 抠图 POST /api/ai/cutout → 识别 POST /api/ai/recognize-item
 *   → 保存 POST /api/items（needs_review: true，识别不出类别时存为「未分类」）
 * 全部处理完后到衣橱的「待确认」里逐件核对、补充备注。
 *
 * 容错：抠图失败用原图，识别失败存为「未分类」，都不算失败；
 *       上传 / 保存失败，或任何一步遇到断网，才标记失败，可单独重试，不影响其他照片。
 *       重试时从断开的那一步接着做，已完成的步骤不重复（不会重复上传、重复消耗 AI 次数）。
 * 并发：同时处理 CONCURRENCY 张，避免一下子打满后端的 AI 限流。
 */
import { ref, computed } from 'vue'
import { onUnload } from '@dcloudio/uni-app'
import { post, uploadFile } from '@/utils/request'

const UNCLASSIFIED = '未分类'
const CONCURRENCY = 2
const MAX_PER_BATCH = 30      // 一批最多处理的张数
const PICK_LIMIT = 9          // 小程序 chooseImage 单次最多 9 张

const STATUS_TEXT = {
  waiting: '排队中',
  uploading: '上传中',
  cutting: '去背景',
  recognizing: 'AI 识别',
  saving: '保存中',
  done: '已入库',
  failed: '失败'
}

const tasks = ref([])         // { key, localPath, preview, status, msg, imageUrl, type, cutDone, ai, dup }
const running = ref(0)        // 正在处理的数量
let seq = 0
let aiStopped = false         // 识别被限流（8004）后，本批剩下的不再调识别，直接存「未分类」
let leaving = false

const total = computed(() => tasks.value.length)
const doneCount = computed(() => tasks.value.filter((t) => t.status === 'done').length)
const failedCount = computed(() => tasks.value.filter((t) => t.status === 'failed').length)
const finishedCount = computed(() => doneCount.value + failedCount.value)
const busy = computed(() => finishedCount.value < total.value)
const percent = computed(() => (total.value ? Math.round((finishedCount.value / total.value) * 100) : 0))
const dupCount = computed(() => tasks.value.filter((t) => t.status === 'done' && t.dup).length)
const unclassifiedCount = computed(
  () => tasks.value.filter((t) => t.status === 'done' && t.type === UNCLASSIFIED).length
)

onUnload(() => { leaving = true })

/** 断网 / 超时：uni 的 fail 回调只带 errMsg，没有后端返回的业务 code */
function isNetworkError(e) {
  return !(e && typeof e.code !== 'undefined')
}

function choosePhotos() {
  const left = MAX_PER_BATCH - total.value
  if (left <= 0) {
    uni.showToast({ title: `一批最多 ${MAX_PER_BATCH} 张，先去核对这批吧`, icon: 'none' })
    return
  }
  uni.chooseImage({
    // 不按剩余张数限制 count：uni 在 H5 上会按 count 悄悄截断，用户不知道多选的去哪了。
    // 统一按单次上限选，超出剩余名额的部分在下面截掉并提示
    count: PICK_LIMIT,
    sizeType: ['compressed'],
    sourceType: ['album', 'camera'],
    success: (res) => {
      const picked = res.tempFilePaths || []
      const paths = picked.slice(0, left)
      if (picked.length > left) {
        uni.showToast({ title: `一批最多 ${MAX_PER_BATCH} 张，只加入了前 ${left} 张`, icon: 'none', duration: 2500 })
      }
      paths.forEach((p) => {
        tasks.value.push({
          key: ++seq, localPath: p, preview: p,
          status: 'waiting', msg: '', imageUrl: '', type: '', cutDone: false, ai: null
        })
      })
      pump()
    }
  })
}

/** 有空位就从队列里取下一张开始处理 */
function pump() {
  while (!leaving && running.value < CONCURRENCY) {
    const next = tasks.value.find((t) => t.status === 'waiting')
    if (!next) return
    running.value++
    processOne(next).finally(() => {
      running.value--
      pump()
    })
  }
}

async function processOne(task) {
  task.msg = ''
  try {
    // 1. 上传（重试时如果已经上传过就跳过）
    if (!task.imageUrl) {
      task.status = 'uploading'
      const up = await uploadFile(task.localPath)
      task.imageUrl = up.url
    }

    // 2. 抠图：后端处理失败就用原图；断网则整张标记失败，重试时再抠
    if (!task.cutDone) {
      task.status = 'cutting'
      try {
        const cut = await post('/api/ai/cutout', { image_url: task.imageUrl }, { silent: true })
        task.imageUrl = cut.url
        task.preview = cut.url
      } catch (e) {
        if (isNetworkError(e)) throw e
        task.cutMsg = '未去背景'
      }
      task.cutDone = true
    }

    // 3. 识别：后端识别失败或被限流就存「未分类」；断网同上
    if (!task.ai) {
      if (aiStopped) {
        task.ai = {}
        task.aiMsg = 'AI 次数用完，待手动分类'
      } else {
        task.status = 'recognizing'
        try {
          task.ai = (await post('/api/ai/recognize-item', { image_url: task.imageUrl }, { silent: true })) || {}
        } catch (e) {
          if (isNetworkError(e)) throw e
          if (e.code === 8004) aiStopped = true
          task.ai = {}
          task.aiMsg = e.code === 8004 ? 'AI 次数用完，待手动分类' : '未识别，待手动分类'
        }
      }
    }
    const ai = task.ai

    // 4. 保存为待确认
    task.status = 'saving'
    const payload = { image_url: task.imageUrl, type: ai.type || UNCLASSIFIED, needs_review: true }
    ;['color', 'season', 'occasion'].forEach((k) => { if (ai[k]) payload[k] = ai[k] })
    const saved = await post('/api/items', payload, { silent: true })
    // 后端按图片指纹比对，和衣橱里已有的照片很像时返回 duplicates
    task.dup = !!(saved && saved.duplicates && saved.duplicates.length)
    task.type = payload.type
    task.status = 'done'
    task.msg = task.aiMsg || task.cutMsg || ''
  } catch (e) {
    task.status = 'failed'
    task.msg = isNetworkError(e) ? '网络断开' : (e.msg || '保存失败')
  }
}

function retry(task) {
  if (task.status !== 'failed') return
  task.status = 'waiting'
  task.msg = ''
  pump()
}

function retryAll() {
  tasks.value.forEach((t) => { if (t.status === 'failed') { t.status = 'waiting'; t.msg = '' } })
  pump()
}

/** 衣橱是 tab 页，不能带参数跳转：先在本地存个标记，衣橱 onShow 读到后自动切到「待确认」 */
function goReview() {
  try { uni.setStorageSync('wardrobe_open_review', 1) } catch (e) { /* 存不了就停在全部 */ }
  uni.switchTab({ url: '/pages/item/list' })
}

function goSingle() {
  uni.navigateTo({ url: '/pages/item/add' })
}

function startNewBatch() {
  tasks.value = []
  aiStopped = false
  choosePhotos()
}
</script>

<template>
  <view class="page">
    <view class="intro">
      <view class="intro-title">一次拍多件，AI 帮你入库</view>
      <view class="intro-text">
        选好照片后会自动去背景、识别类别和颜色，先存进衣橱；
        识别不准或想加备注，稍后在「待确认」里改就行。
      </view>
    </view>

    <view v-if="!total" class="picker" @click="choosePhotos">
      <text class="picker-plus">＋</text>
      <text class="picker-tip">选择照片（每次最多 {{ PICK_LIMIT }} 张，可分几次添加）</text>
    </view>

    <template v-else>
      <view class="progress-card">
        <view class="progress-head">
          <text class="progress-title">{{ busy ? '正在处理…' : '处理完成' }}</text>
          <text class="progress-num">{{ finishedCount }} / {{ total }}</text>
        </view>
        <view class="bar"><view class="bar-inner" :style="{ width: percent + '%' }" /></view>
        <view v-if="!busy" class="summary">
          已入库 {{ doneCount }} 件<text v-if="failedCount">，失败 {{ failedCount }} 件</text>
          <text v-if="unclassifiedCount">，其中 {{ unclassifiedCount }} 件需要手动选类别</text>
        </view>
        <view v-if="!busy && dupCount" class="summary dup">
          有 {{ dupCount }} 张和衣橱里已有的照片很像，核对时可以顺手删掉重复的
        </view>
        <view v-else class="summary muted">处理时请不要离开本页面</view>
      </view>

      <view class="grid">
        <view v-for="t in tasks" :key="t.key" class="cell" @click="retry(t)">
          <image class="thumb" :src="t.preview" mode="aspectFit" />
          <view class="badge" :class="t.status">{{ STATUS_TEXT[t.status] }}</view>
          <view v-if="t.status === 'done'" class="cell-type">{{ t.type }}</view>
          <view v-if="t.dup" class="cell-dup">可能重复</view>
          <view v-if="t.msg" class="cell-msg">{{ t.status === 'failed' ? t.msg + '，点击重试' : t.msg }}</view>
        </view>
        <view v-if="total < MAX_PER_BATCH" class="cell add-cell" @click="choosePhotos">
          <text class="picker-plus">＋</text>
          <text class="add-tip">继续添加（{{ total }}/{{ MAX_PER_BATCH }}）</text>
        </view>
      </view>

      <view v-if="!busy" class="actions">
        <view v-if="failedCount" class="btn ghost" @click="retryAll">重试失败的 {{ failedCount }} 张</view>
        <view v-if="doneCount" class="btn primary" @click="goReview">去核对 {{ doneCount }} 件</view>
        <view v-else class="btn primary" @click="startNewBatch">重新选择</view>
      </view>
    </template>

    <view class="single" @click="goSingle">只添加一件，想手动填写？</view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 28rpx 28rpx 60rpx; background: #fff8f5; box-sizing: border-box; }
.intro { padding: 24rpx 28rpx; border-radius: 20rpx; background: #fff5f8; border: 2rpx dashed #ffc4d6; margin-bottom: 28rpx; }
.intro-title { font-size: 30rpx; font-weight: 700; color: #c0607f; }
.intro-text { margin-top: 10rpx; font-size: 24rpx; color: #8a7a80; line-height: 1.6; }
.picker { height: 360rpx; background: #fff; border: 2rpx dashed #ffc4d6; border-radius: 20rpx; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.picker-plus { font-size: 64rpx; color: #ff8fb1; line-height: 1; }
.picker-tip { margin-top: 14rpx; font-size: 24rpx; color: #a4949a; }
.progress-card { padding: 24rpx 28rpx; border-radius: 20rpx; background: #fff; margin-bottom: 24rpx; }
.progress-head { display: flex; justify-content: space-between; align-items: baseline; }
.progress-title { font-size: 28rpx; font-weight: 700; color: #4a3f44; }
.progress-num { font-size: 26rpx; color: #ff8fb1; font-weight: 700; }
.bar { margin-top: 16rpx; height: 14rpx; border-radius: 999rpx; background: #f6e6ec; overflow: hidden; }
.bar-inner { height: 100%; border-radius: 999rpx; background: #ff8fb1; transition: width 0.3s; }
.summary { margin-top: 14rpx; font-size: 24rpx; color: #4a3f44; }
.summary.muted { color: #a4949a; }
.summary.dup { color: #d9822b; }
.cell-dup { position: absolute; left: 10rpx; top: 48rpx; padding: 2rpx 12rpx; border-radius: 999rpx; font-size: 20rpx; color: #fff; background: #f0a04b; }
.grid { display: flex; flex-wrap: wrap; gap: 18rpx; }
.cell { position: relative; width: calc((100% - 36rpx) / 3); height: 260rpx; border-radius: 16rpx; background: #fff; overflow: hidden; box-sizing: border-box; }
.thumb { width: 100%; height: 100%; }
.badge { position: absolute; left: 10rpx; top: 10rpx; padding: 2rpx 12rpx; border-radius: 999rpx; font-size: 20rpx; color: #fff; background: rgba(74, 63, 68, 0.6); }
.badge.done { background: #7cc49a; }
.badge.failed { background: #e05c5c; }
.badge.uploading, .badge.cutting, .badge.recognizing, .badge.saving { background: #ff8fb1; }
.cell-type { position: absolute; right: 10rpx; top: 10rpx; padding: 2rpx 12rpx; border-radius: 999rpx; font-size: 20rpx; color: #c0607f; background: #fff0f5; }
.cell-msg { position: absolute; left: 0; right: 0; bottom: 0; padding: 6rpx 10rpx; font-size: 20rpx; color: #fff; background: rgba(74, 63, 68, 0.55); text-align: center; }
.add-cell { display: flex; flex-direction: column; align-items: center; justify-content: center; border: 2rpx dashed #ffc4d6; }
.add-tip { margin-top: 8rpx; font-size: 22rpx; color: #a4949a; }
.actions { display: flex; gap: 20rpx; margin-top: 36rpx; }
.btn { flex: 1; height: 84rpx; line-height: 84rpx; text-align: center; border-radius: 999rpx; font-size: 28rpx; font-weight: 700; }
.btn.primary { background: #ff8fb1; color: #fff; }
.btn.ghost { background: #fff; color: #ff8fb1; border: 2rpx solid #ffc4d6; }
.single { margin-top: 40rpx; text-align: center; font-size: 24rpx; color: #a4949a; text-decoration: underline; }
</style>
