<script setup>
/**
 * 编辑资料：头像 + 昵称
 * 入口：「我的」页点头像卡片；新用户微信登录后由登录页带 ?first=1 进入（可跳过）
 *
 * 小程序：微信官方「头像昵称填写」能力
 *   - <button open-type="chooseAvatar">：可选微信头像、相册或拍照，回调给本地临时路径
 *   - <input type="nickname">：键盘上方提示「使用微信昵称」；微信会对昵称做安全检测，
 *     选用微信昵称时 v-model 不一定更新，所以在 blur / change 里再取一次值
 * H5：普通选图 + 普通输入框
 * 头像先走 POST /api/upload，再把返回的地址交给 PUT /api/auth/profile
 * 这两个都是隐私接口，页面里放了 PrivacyPopup
 */
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { uploadFile } from '@/utils/request'
import { useUserStore } from '@/store/user'
import PrivacyPopup from '@/components/PrivacyPopup.vue'
import TaotaoSprite from '@/components/TaotaoSprite.vue'

const NICKNAME_MAX = 20

const userStore = useUserStore()
const first = ref(false)              // 新用户首次进入：显示「跳过」，保存后回首页
const avatarPreview = ref('')         // 正在显示的头像（本地临时图或服务器地址）
const avatarUrl = ref('')             // 本次新上传的头像地址，未换头像为空
const nickname = ref('')
const uploading = ref(false)
const saving = ref(false)

const original = computed(() => userStore.userInfo || {})
const nicknameLen = computed(() => nickname.value.trim().length)
const changed = computed(() => !!avatarUrl.value || nickname.value.trim() !== (original.value.nickname || ''))

onLoad((query = {}) => {
  first.value = query.first === '1'
  avatarPreview.value = original.value.avatar || ''
  nickname.value = original.value.nickname || ''
  if (first.value) uni.setNavigationBarTitle({ title: '设置头像和昵称' })
})

async function useAvatar(localPath) {
  if (!localPath || uploading.value) return
  avatarPreview.value = localPath
  uploading.value = true
  uni.showLoading({ title: '上传中...', mask: true })
  try {
    const data = await uploadFile(localPath)
    avatarUrl.value = data.url
  } catch (e) {
    avatarPreview.value = original.value.avatar || ''
    avatarUrl.value = ''
  } finally {
    uploading.value = false
    uni.hideLoading()
  }
}

// 小程序：官方头像选择按钮的回调
function onChooseAvatar(e) {
  useAvatar(e && e.detail && e.detail.avatarUrl)
}

// H5：普通选图
function pickAvatarH5() {
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    success: (res) => useAvatar(res.tempFilePaths && res.tempFilePaths[0])
  })
}

function onNicknameDone(e) {
  const value = e && e.detail && typeof e.detail.value === 'string' ? e.detail.value : null
  if (value !== null) nickname.value = value
}

function finish() {
  if (first.value) uni.switchTab({ url: '/pages/index/index' })
  else uni.navigateBack()
}

async function save() {
  if (saving.value || uploading.value) return
  const name = nickname.value.trim()
  if (!name) {
    uni.showToast({ title: '昵称不能为空', icon: 'none' })
    return
  }
  if (name.length > NICKNAME_MAX) {
    uni.showToast({ title: `昵称最多 ${NICKNAME_MAX} 个字`, icon: 'none' })
    return
  }
  if (!changed.value) {
    finish()
    return
  }
  const payload = {}
  if (name !== (original.value.nickname || '')) payload.nickname = name
  if (avatarUrl.value) payload.avatar = avatarUrl.value
  saving.value = true
  try {
    await userStore.updateProfile(payload)
    uni.showToast({ title: '已保存', icon: 'success' })
    setTimeout(finish, 600)
  } catch (e) {
    // request.js 已提示具体原因
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <view class="page">
    <view v-if="first" class="welcome">
      <TaotaoSprite mood="wave" :size="140" />
      <view class="welcome-t">欢迎来到衣笺小札</view>
      <view class="welcome-d">给自己选个头像和昵称吧，之后也可以在「我的」里修改</view>
    </view>

    <view class="card">
      <!-- #ifdef MP-WEIXIN -->
      <button class="avatar-btn" open-type="chooseAvatar" @chooseavatar="onChooseAvatar">
        <image v-if="avatarPreview" class="avatar" :src="avatarPreview" mode="aspectFill" />
        <view v-else class="avatar empty">🙂</view>
        <view class="avatar-tip">点击更换头像</view>
      </button>
      <!-- #endif -->
      <!-- #ifndef MP-WEIXIN -->
      <view class="avatar-btn" @click="pickAvatarH5">
        <image v-if="avatarPreview" class="avatar" :src="avatarPreview" mode="aspectFill" />
        <view v-else class="avatar empty">🙂</view>
        <view class="avatar-tip">点击更换头像</view>
      </view>
      <!-- #endif -->

      <view class="label">昵称 <text class="counter">{{ nicknameLen }}/{{ NICKNAME_MAX }}</text></view>
      <input
        class="input"
        type="nickname"
        v-model="nickname"
        :maxlength="NICKNAME_MAX"
        placeholder="给自己起个名字"
        placeholder-class="ph"
        @blur="onNicknameDone"
        @change="onNicknameDone"
      />
    </view>

    <view class="actions">
      <view v-if="first" class="act ghost press-bounce" @click="finish">跳过</view>
      <view class="act primary press-bounce" :class="{ off: saving || uploading }" @click="save">
        {{ saving ? '保存中…' : '保存' }}
      </view>
    </view>

    <PrivacyPopup />
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 32rpx 32rpx calc(160rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
  background: #fff8f5;
}
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 24rpx;
}
.welcome-t {
  margin-top: 8rpx;
  font-size: 34rpx;
  font-weight: 700;
  color: #382e36;
}
.welcome-d {
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #8a7f88;
  text-align: center;
}
.card {
  padding: 40rpx 32rpx;
  background: #fffdfb;
  border-radius: 32rpx;
  box-shadow: 0 10rpx 30rpx rgba(255, 150, 175, 0.12);
}
.avatar-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 0 auto 36rpx;
  padding: 0;
  background: transparent;
  border: none;
  line-height: normal;
}
.avatar-btn::after {
  border: none;
}
.avatar {
  width: 168rpx;
  height: 168rpx;
  border-radius: 50%;
  border: 6rpx solid #ffc9d9;
  background: #fdf5e8;
}
.avatar.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 72rpx;
}
.avatar-tip {
  margin-top: 12rpx;
  font-size: 24rpx;
  color: #ff8fb1;
}
.label {
  display: flex;
  justify-content: space-between;
  font-size: 26rpx;
  color: #8a7f88;
  margin-bottom: 12rpx;
}
.counter {
  font-size: 22rpx;
  color: #b5aab0;
}
.input {
  height: 88rpx;
  padding: 0 24rpx;
  border-radius: 20rpx;
  border: 2rpx dashed #f3d5dc;
  background: #fffdfb;
  font-size: 30rpx;
  color: #382e36;
}
.ph {
  color: #b5aab0;
}
.actions {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  gap: 20rpx;
  padding: 18rpx 32rpx calc(18rpx + env(safe-area-inset-bottom));
  background: #fffdfb;
  box-shadow: 0 -8rpx 24rpx rgba(255, 150, 175, 0.1);
}
.act {
  height: 84rpx;
  line-height: 84rpx;
  text-align: center;
  border-radius: 999rpx;
  font-size: 30rpx;
  font-weight: 700;
}
.act.ghost {
  padding: 0 48rpx;
  color: #8a7f88;
  background: #fff8f5;
  border: 2rpx dashed #e5d7dc;
}
.act.primary {
  flex: 1;
  color: #fff;
  background: linear-gradient(180deg, #ffb3c9 0%, #ff8fb1 72%);
  box-shadow: 0 10rpx 22rpx rgba(255, 143, 177, 0.35);
}
.act.primary.off {
  opacity: 0.6;
}
</style>
