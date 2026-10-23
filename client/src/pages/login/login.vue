<script setup>
import { ref } from 'vue'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()

const account = ref('')
const password = ref('')
const loading = ref(false)

async function handleLogin() {
  if (!account.value.trim() || !password.value) {
    uni.showToast({ title: '请输入账号和密码', icon: 'none' })
    return
  }
  loading.value = true
  try {
    await userStore.login(account.value.trim(), password.value)
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => {
      uni.switchTab({ url: '/pages/index/index' })
    }, 400)
  } catch (e) {
    // 错误提示已由 request 统一处理
  } finally {
    loading.value = false
  }
}

function goRegister() {
  uni.navigateTo({ url: '/pages/register/register' })
}
</script>

<template>
  <view class="container">
    <view class="header">
      <view class="logo">衣</view>
      <view class="title">智能衣橱</view>
      <view class="subtitle">管理你的衣物，记录每天的穿搭</view>
    </view>

    <view class="card">
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
  </view>
</template>

<style scoped>
.header {
  text-align: center;
  padding: 60rpx 0 40rpx;
}
.logo {
  width: 120rpx;
  height: 120rpx;
  line-height: 120rpx;
  margin: 0 auto 24rpx;
  border-radius: 32rpx;
  background: linear-gradient(135deg, #8fb3d9, #5b8def);
  color: #fff;
  font-size: 52rpx;
  font-weight: 600;
  text-align: center;
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
