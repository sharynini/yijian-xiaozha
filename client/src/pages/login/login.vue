<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useUserStore } from '@/store/user'
import TaotaoSprite from '@/components/TaotaoSprite.vue'

const userStore = useUserStore()

const account = ref('')
const password = ref('')
const loading = ref(false)
// 必须勾选同意《用户协议》《隐私政策》才能登录
const agreed = ref(false)

function ensureAgreed() {
  if (agreed.value) return true
  uni.showToast({ title: '请先阅读并同意用户协议和隐私政策', icon: 'none' })
  return false
}

function clearForm() {
  account.value = ''
  password.value = ''
}

// 从注册页返回时清空之前输入的账号密码（勾选状态保留）；
// 从《用户协议》《隐私政策》返回时不清空，避免刚输入的内容丢失
let clearOnReturn = false
onShow(() => {
  if (!clearOnReturn) return
  clearOnReturn = false
  clearForm()
})

function openLegal(name) {
  uni.navigateTo({ url: `/pages/legal/${name}` })
}
// 小程序端只用「微信一键登录」；账号密码登录只在 H5 保留（开发测试用）
const showPasswordForm = ref(true)
// #ifdef MP-WEIXIN
showPasswordForm.value = false
// #endif

function goHome() {
  uni.showToast({ title: '登录成功', icon: 'success' })
  setTimeout(() => {
    uni.switchTab({ url: '/pages/index/index' })
  }, 400)
}

async function handleWxLogin() {
  if (loading.value || !ensureAgreed()) return
  loading.value = true
  try {
    const { isNew } = await userStore.wxLogin()
    if (isNew) {
      // 新用户：先去设置头像和昵称（可跳过）
      uni.redirectTo({ url: '/pages/mine/profile?first=1' })
    } else {
      goHome()
    }
  } catch (e) {
    uni.showToast({ title: (e && e.msg) || '微信登录失败，请稍后再试', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function handleLogin() {
  if (!ensureAgreed()) return
  if (!account.value.trim() || !password.value) {
    uni.showToast({ title: '请输入账号和密码', icon: 'none' })
    return
  }
  loading.value = true
  try {
    await userStore.login(account.value.trim(), password.value)
    goHome()
  } catch (e) {
    // 错误提示已由 request 统一处理。账号或密码错误等业务错误时清空输入框；
    // 网络异常（没有业务 code）时保留，方便用户直接重试
    if (e && typeof e.code === 'number') clearForm()
  } finally {
    loading.value = false
  }
}

function goRegister() {
  clearOnReturn = true
  uni.navigateTo({ url: '/pages/register/register' })
}
</script>

<template>
  <view class="container">
    <view class="header">
      <!-- 桃桃挥手：组件自带上下浮动，外层圆框再加左右轻摆 -->
      <view class="logo">
        <TaotaoSprite mood="wave" :size="320" />
      </view>
      <view class="title">衣笺小札</view>
      <view class="subtitle">管理你的衣物，记录每天的穿搭</view>
    </view>

    <!-- #ifdef MP-WEIXIN -->
    <view class="card">
      <button class="btn-primary" :disabled="loading" @click="handleWxLogin">
        {{ loading ? '登录中...' : '微信一键登录' }}
      </button>
    </view>
    <!-- #endif -->

    <view v-if="showPasswordForm" class="card">
      <view class="label">用户名 / 邮箱</view>
      <input class="input" v-model="account" placeholder="请输入用户名或邮箱" placeholder-class="ph" />

      <view class="label mt">密码</view>
      <input class="input" v-model="password" password placeholder="请输入密码" placeholder-class="ph" />

      <button class="btn-primary mt-lg" :disabled="loading" @click="handleLogin">
        {{ loading ? '登录中...' : '登 录' }}
      </button>

      <view class="footer">
        <text>还没有账号？</text>
        <text class="link" @click="goRegister">立即注册</text>
      </view>
    </view>

    <view class="agree" @click="agreed = !agreed">
      <view class="agree-box" :class="{ on: agreed }">{{ agreed ? '✓' : '' }}</view>
      <view class="agree-text">
        我已阅读并同意
        <text class="link" @click.stop="openLegal('agreement')">《用户协议》</text>
        和
        <text class="link" @click.stop="openLegal('privacy')">《隐私政策》</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.header {
  text-align: center;
  padding: 60rpx 0 40rpx;
}
.logo {
  width: 220rpx;
  height: 220rpx;
  margin: 0 auto 24rpx;
  border-radius: 50%;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fdf5e8;            /* 与桃桃插画的底色一致，看不出图片边界 */
  border: 6rpx solid #ffc9d9;
  box-shadow: 0 12rpx 32rpx rgba(255, 143, 177, 0.25);
  animation: sway 3.2s ease-in-out infinite;
}
@keyframes sway {
  0%, 100% { transform: rotate(-4deg); }
  50% { transform: rotate(4deg); }
}
.title {
  font-size: 40rpx;
  font-weight: 600;
  color: #3d5a80;
}
.subtitle {
  margin-top: 12rpx;
  font-size: 26rpx;
  color: #7b8794;
}
.agree {
  display: flex;
  align-items: flex-start;
  margin-top: 36rpx;
  padding: 0 8rpx;
  font-size: 24rpx;
  color: #7b8794;
  line-height: 1.6;
}
.agree-box {
  flex-shrink: 0;
  width: 30rpx;
  height: 30rpx;
  line-height: 30rpx;
  margin: 4rpx 12rpx 0 0;
  border-radius: 50%;
  border: 2rpx solid #c5ccd6;
  text-align: center;
  font-size: 20rpx;
  color: #fff;
}
.agree-box.on {
  background: #5b8def;
  border-color: #5b8def;
}
.agree-text {
  flex: 1;
}
.card + .card {
  margin-top: 32rpx;
}
.mt {
  margin-top: 24rpx;
}
.mt-lg {
  margin-top: 44rpx;
}
.ph {
  color: #a4b0be;
}
.footer {
  margin-top: 28rpx;
  text-align: center;
  font-size: 26rpx;
  color: #7b8794;
}
.link {
  color: #5b8def;
  margin-left: 8rpx;
}
</style>
