<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useUserStore } from '@/store/user'
import { get } from '@/utils/request'

const userStore = useUserStore()

const itemCount = ref(0)
const logCount = ref(0)

async function loadStat() {
  try {
    const [items, logs] = await Promise.all([
      get('/api/items', { page: 1, per_page: 1 }),
      get('/api/wear-logs', { page: 1, per_page: 1 })
    ])
    itemCount.value = items.total
    logCount.value = logs.total
  } catch (e) {
    // 统一错误提示
  }
}

function onLogout() {
  uni.showModal({
    title: '提示',
    content: '确定要退出登录吗？',
    success: (res) => {
      if (res.confirm) userStore.logout()
    }
  })
}

onShow(() => {
  if (userStore.isLogin) {
    userStore.fetchProfile().catch(() => {})
    loadStat()
  }
})
</script>

<template>
  <view class="container">
    <view class="card profile">
      <image
        :src="userStore.userInfo?.avatar || 'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=avatar%20placeholder&image_size=square'"
        mode="aspectFill"
        class="avatar"
      />
      <view class="info">
        <view class="nickname">{{ userStore.userInfo?.nickname || '未登录' }}</view>
        <view class="account">{{ userStore.userInfo?.username || '' }}</view>
      </view>
    </view>

    <view class="card stat">
      <view class="stat-item">
        <view class="num">{{ itemCount }}</view>
        <view class="stat-label">衣物</view>
      </view>
      <view class="divider"></view>
      <view class="stat-item">
        <view class="num">{{ logCount }}</view>
        <view class="stat-label">穿搭记录</view>
      </view>
    </view>

    <button class="btn-ghost" @click="onLogout">退出登录</button>
  </view>
</template>

<style scoped>
.profile {
  display: flex;
  align-items: center;
  gap: 24rpx;
}
.avatar {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: #eef3f9;
}
.nickname {
  font-size: 34rpx;
  font-weight: 600;
  color: #3d5a80;
}
.account {
  margin-top: 8rpx;
  font-size: 26rpx;
  color: #a4b0be;
}
.stat {
  display: flex;
  align-items: center;
  justify-content: space-around;
  text-align: center;
}
.stat-item {
  flex: 1;
}
.num {
  font-size: 44rpx;
  font-weight: 600;
  color: #5b8def;
}
.stat-label {
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #7b8794;
}
.divider {
  width: 1rpx;
  height: 60rpx;
  background: #eef3f9;
}
</style>
