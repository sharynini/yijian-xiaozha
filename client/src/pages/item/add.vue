<script setup>
/**
 * 衣物入库 / 编辑页
 *   新增：/pages/item/add
 *   编辑：/pages/item/add?id=123（复用同一套表单，提交时走 PUT）
 *
 * 图片流程：uni.chooseImage 拿到本地临时路径 → 立即上传 POST /api/upload 换取服务器 URL
 *          → 提交时只把 image_url 传给 /api/items
 */
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { get, post, put, del, uploadFile } from '@/utils/request'
import { ITEM_TYPES, SEASONS, OCCASIONS, COLORS } from '@/utils/constants'

const editId = ref(null)      // 非空即编辑模式
const imageUrl = ref('')      // 上传成功后的服务器地址（提交用）
const previewPath = ref('')   // 本地预览路径（选图后立即显示）
const uploading = ref(false)
const submitting = ref(false)
const deleting = ref(false)

const form = ref({
  type: '',
  color: '',
  season: '全季',
  occasion: '',
  material: '',
  brand: '',
  price: '',
  remark: ''
})

// ---------- 编辑模式：回填数据 ----------
onLoad(async (query = {}) => {
  if (!query.id) return
  editId.value = Number(query.id)
  uni.setNavigationBarTitle({ title: '编辑衣物' })

  uni.showLoading({ title: '加载中...', mask: true })
  try {
    const data = await get(`/api/items/${editId.value}`)
    imageUrl.value = data.image_url || ''
    previewPath.value = data.image_url || ''
    form.value.type = data.type || ''
    form.value.color = data.color || ''
    form.value.season = data.season || ''
    form.value.occasion = data.occasion || ''
    form.value.material = data.material || ''
    form.value.brand = data.brand || ''
    form.value.price = data.price === null || data.price === undefined ? '' : String(data.price)
    form.value.remark = data.remark || ''
  } catch (e) {
    // 统一错误提示
  } finally {
    uni.hideLoading()
  }
})

// ---------- 选图 + 立即上传 ----------
function chooseImage() {
  if (uploading.value) return
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],          // 压缩后再上传，避免大图
    sourceType: ['album', 'camera'],   // 相册 or 拍照
    success: async (res) => {
      const path = res.tempFilePaths[0]
      previewPath.value = path
      imageUrl.value = ''
      uploading.value = true
      uni.showLoading({ title: '上传中...', mask: true })
      try {
        const data = await uploadFile(path)
        imageUrl.value = data.url
      } catch (e) {
        // 上传失败：保留 previewPath 让用户看到"选了但没传上去"，
        // 给三个选择：换一张 / 不带图提交 / 等网络好再试
        uni.showModal({
          title: '图片上传失败',
          content: '可以换一张，或者先不带图提交，稍后再补',
          confirmText: '重新选择',
          cancelText: '先不带图',
          success: (r) => {
            if (r.confirm) {
              previewPath.value = ''
              imageUrl.value = ''
            } else {
              // 用户选择不带图：清空状态让 validate 失败时提示
              previewPath.value = ''
              imageUrl.value = ''
            }
          },
        })
      } finally {
        uploading.value = false
        uni.hideLoading()
      }
    }
  })
}

function previewImage() {
  if (!previewPath.value) return
  uni.previewImage({ urls: [previewPath.value], current: previewPath.value })
}

function toggle(field, value) {
  // 单选标签：再次点击可取消选择
  form.value[field] = form.value[field] === value ? '' : value
}

// ---------- 删除（仅编辑模式） ----------
function removeItem() {
  if (!editId.value || deleting.value) return
  uni.showModal({
    title: '删除衣物',
    content: '确定删除这件衣物吗？删除后衣橱里不再显示，已有的穿搭日记不受影响。',
    confirmText: '删除',
    confirmColor: '#e05c5c',
    success: async (res) => {
      if (!res.confirm) return
      deleting.value = true
      try {
        await del(`/api/items/${editId.value}`)
        uni.showToast({ title: '已删除', icon: 'success' })
        // 返回衣橱（列表页 onShow 会自动刷新）
        setTimeout(() => uni.navigateBack(), 600)
      } catch (e) {
        // 统一错误提示
      } finally {
        deleting.value = false
      }
    }
  })
}

// ---------- 提交 ----------
function validate() {
  if (uploading.value) {
    uni.showToast({ title: '图片上传中，请稍候', icon: 'none' })
    return false
  }
  if (!imageUrl.value) {
    uni.showToast({ title: '请先选择衣物照片', icon: 'none' })
    return false
  }
  if (!form.value.type) {
    uni.showToast({ title: '请选择衣物类型', icon: 'none' })
    return false
  }
  if (!form.value.season) {
    uni.showToast({ title: '请选择适用季节', icon: 'none' })
    return false
  }
  const price = String(form.value.price).trim()
  if (price !== '' && !/^\d+(\.\d{1,2})?$/.test(price)) {
    uni.showToast({ title: '价格需为数字，最多两位小数', icon: 'none' })
    return false
  }
  return true
}

async function submit() {
  if (submitting.value) return
  if (!validate()) return

  submitting.value = true
  try {
    const payload = {
      image_url: imageUrl.value,
      type: form.value.type,
      color: form.value.color,
      season: form.value.season,
      occasion: form.value.occasion,
      material: form.value.material,
      brand: form.value.brand,
      price: String(form.value.price).trim() === '' ? null : Number(form.value.price),
      remark: form.value.remark
    }

    if (editId.value) {
      await put(`/api/items/${editId.value}`, payload)
    } else {
      await post('/api/items', payload)
    }

    uni.showToast({ title: editId.value ? '保存成功' : '添加成功', icon: 'success' })
    // 等 toast 显示一下再返回上一页（列表页 onShow 会自动刷新）
    setTimeout(() => uni.navigateBack(), 600)
  } catch (e) {
    // 统一错误提示
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <view class="container">
    <!-- 图片 -->
    <view class="card">
      <view class="label">衣物照片 <text class="required">*</text></view>

      <view v-if="!previewPath" class="picker" @click="chooseImage">
        <view class="picker-plus">＋</view>
        <view class="picker-tip">从相册选择 / 拍照</view>
      </view>

      <view v-else class="preview">
        <image class="preview-img" :src="previewPath" mode="aspectFill" @click="previewImage" />
        <view v-if="uploading" class="preview-mask">
          <text>上传中…</text>
        </view>
        <view class="preview-ops">
          <text class="op" @click="chooseImage">重新选择</text>
          <text class="op" @click="previewImage">预览大图</text>
        </view>
      </view>
    </view>

    <!-- 类型（必填）+ 颜色 + 季节 + 场合 -->
    <view class="card">
      <view class="label">类型 <text class="required">*</text></view>
      <view class="tags">
        <view
          v-for="t in ITEM_TYPES"
          :key="t"
          class="tag"
          :class="{ active: form.type === t }"
          @click="toggle('type', t)"
        >{{ t }}</view>
      </view>

      <view class="label mt">颜色</view>
      <view class="tags">
        <view
          v-for="c in COLORS"
          :key="c"
          class="tag"
          :class="{ active: form.color === c }"
          @click="toggle('color', c)"
        >{{ c }}</view>
      </view>

      <view class="label mt">季节 <text class="required">*</text></view>
      <view class="tags">
        <view
          v-for="s in SEASONS"
          :key="s"
          class="tag"
          :class="{ active: form.season === s }"
          @click="form.season = s"
        >{{ s }}</view>
      </view>

      <view class="label mt">场合</view>
      <view class="tags">
        <view
          v-for="o in OCCASIONS"
          :key="o"
          class="tag"
          :class="{ active: form.occasion === o }"
          @click="toggle('occasion', o)"
        >{{ o }}</view>
      </view>
    </view>

    <!-- 文本字段 -->
    <view class="card">
      <view class="label">材质</view>
      <input class="input" v-model="form.material" placeholder="如 纯棉、羊毛（选填）" placeholder-class="ph" maxlength="50" />

      <view class="label mt">品牌</view>
      <input class="input" v-model="form.brand" placeholder="选填" placeholder-class="ph" maxlength="50" />

      <view class="label mt">价格（元）</view>
      <input class="input" type="digit" v-model="form.price" placeholder="选填，如 199" placeholder-class="ph" />

      <view class="label mt">备注</view>
      <textarea
        class="textarea"
        v-model="form.remark"
        placeholder="选填，记录搭配心得、洗护注意等"
        placeholder-class="ph"
        maxlength="200"
      />
    </view>

    <button class="btn-primary" :disabled="submitting || uploading || deleting" @click="submit">
      {{ submitting ? '提交中...' : (editId ? '保存修改' : '确认入库') }}
    </button>
    <button
      v-if="editId"
      class="btn-danger"
      :disabled="submitting || deleting"
      @click="removeItem"
    >{{ deleting ? '删除中...' : '删除衣物' }}</button>
    <view v-if="!editId" class="bottom-tip">照片会先上传到服务器，再提交衣物信息</view>
  </view>
</template>

<style scoped>
.required {
  color: #e05c5c;
  font-size: 26rpx;
}
.mt {
  margin-top: 28rpx;
}

/* ---------- 图片选择 ---------- */
.picker {
  height: 320rpx;
  background: #fbfcfe;
  border: 2rpx dashed #cfdbe7;
  border-radius: 16rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.picker-plus {
  font-size: 64rpx;
  color: #a9c1dd;
  line-height: 1;
}
.picker-tip {
  margin-top: 14rpx;
  font-size: 26rpx;
  color: #a4b0be;
}

.preview {
  position: relative;
}
.preview-img {
  width: 100%;
  height: 420rpx;
  border-radius: 16rpx;
  background: #eef3f9;
}
.preview-mask {
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  height: 420rpx;
  border-radius: 16rpx;
  background: rgba(43, 52, 65, 0.45);
  color: #fff;
  font-size: 26rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.preview-ops {
  display: flex;
  gap: 32rpx;
  margin-top: 18rpx;
}
.op {
  font-size: 26rpx;
  color: #5b8def;
}

/* ---------- 标签选择 ---------- */
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}
.tag {
  padding: 12rpx 26rpx;
  border-radius: 999rpx;
  background: #eef3f9;
  color: #3d5a80;
  font-size: 26rpx;
  border: 1rpx solid transparent;
}
.tag.active {
  background: #e8f0ff;
  border-color: #5b8def;
  color: #5b8def;
  font-weight: 600;
}

/* ---------- 文本输入 ---------- */
.textarea {
  width: 100%;
  box-sizing: border-box;
  height: 180rpx;
  background: #fbfcfe;
  border: 1rpx solid #d7e0ea;
  border-radius: 14rpx;
  padding: 20rpx 24rpx;
  font-size: 28rpx;
}
.ph {
  color: #a4b0be;
}

.btn-danger {
  margin-top: 24rpx;
  height: 88rpx;
  line-height: 88rpx;
  border-radius: 999rpx;
  background: #fffdfb;
  color: #e05c5c;
  font-size: 30rpx;
  border: 2rpx solid #f5c2c2;
}
.btn-danger::after {
  border: none;
}

.bottom-tip {
  margin-top: 20rpx;
  text-align: center;
  font-size: 22rpx;
  color: #a4b0be;
}
</style>
