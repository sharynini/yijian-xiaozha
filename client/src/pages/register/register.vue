<script setup>
import { ref } from 'vue'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()

const username = ref('')
const email = ref('')
const password = ref('')
const confirm = ref('')
const loading = ref(false)

async function handleRegister() {
  if (!username.value.trim()) {
    return uni.showToast({ title: '请输入用户名', icon: 'none' })
  }
  if (!email.value.trim()) {
    return uni.showToast({ title: '请输入邮箱', icon: 'none' })
  }
  if (password.value.length < 6) {
    return uni.showToast({ title: '密码长度至少为 6 位', icon: 'none' })
  }
  if (password.value !== confirm.value) {
    return uni.showToast({ title: '两次输入的密码不一致', icon: 'none' })
  }

  loading.value = true
  try {
    await userStore.register(username.value.trim(), email.value.trim(), password.value)
    uni.showToast({ title: '注册成功，请登录', icon: 'success' })
    setTimeout(() => {
      uni.navigateBack() // 返回登录页
    }, 800)
  } catch (e) {
    // 错误提示已由 request 统一处理
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <view class="container">
    <view class="card">
      <view class="label">用户名</view>
      <input class="input" v-model="username" placeholder="2-20 个字符" placeholder-class="ph" />

      <view class="label mt">邮箱</view>
      <input class="input" v-model="email" placeholder="用于登录与找回" placeholder-class="ph" />

      <view class="label mt">密码</view>
      <input class="input" v-model="password" password placeholder="至少 6 位" placeholder-class="ph" />

      <view class="label mt">确认密码</view>
      <input class="input" v-model="confirm" password placeholder="再次输入密码" placeholder-class="ph" />

      <button class="btn-primary mt-lg" :disabled="loading" @click="handleRegister">
        {{ loading ? '提交中...' : '注 册' }}
      </button>
    </view>
  </view>
</template>

<style scoped>
.mt {
  margin-top: 24rpx;
}
.mt-lg {
  margin-top: 44rpx;
}
.ph {
  color: #a4b0be;
}
</style>
