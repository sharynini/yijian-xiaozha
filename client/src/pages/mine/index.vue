<script setup>
/**
 * 我的小窝
 * 组件：NestTitle / AvatarNoteCard / JellyStatCards / MenuGrid / LogoutNote / AppTabBar
 */
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useUserStore } from '@/store/user'
import { get } from '@/utils/request'
import TaotaoSprite from '@/components/TaotaoSprite.vue'
import AppTabBar from '@/components/AppTabBar.vue'

const userStore = useUserStore()
const statusPad = (uni.getSystemInfoSync().statusBarHeight || 12) + 8
const itemCount = ref(0)
const logCount = ref(0)
const loadError = ref(false)

const tag = computed(() => {
  if (logCount.value >= 8) return '穿搭达人'
  if (logCount.value >= 3) return '穿搭进阶'
  return '穿搭新手'
})

async function loadStat() {
  loadError.value = false
  try {
    const [items, logs] = await Promise.all([
      get('/api/items', { page: 1, per_page: 1 }),
      get('/api/wear-logs', { page: 1, per_page: 1 })
    ])
    itemCount.value = items.total
    logCount.value = logs.total
  } catch (e) {
    loadError.value = true
  }
}

function goCloset() {
  uni.switchTab({ url: '/pages/item/list' })
}
function goDiary() {
  uni.switchTab({ url: '/pages/timeline/index' })
}

function onLogout() {
  uni.showModal({
    title: '退出登录',
    content: '桃桃会在小窝等你回来～确定退出吗？',
    success: (res) => {
      if (res.confirm) userStore.logout()
    }
  })
}

function goProfile() {
  uni.navigateTo({ url: '/pages/mine/profile' })
}

function openLegal(name) {
  uni.navigateTo({ url: `/pages/legal/${name}` })
}

function onDeleteAccount() {
  uni.showModal({
    title: '注销账号',
    content: '注销后会立即彻底删除你的账号、全部衣物、搭配、日记和照片，无法恢复。确定继续吗？',
    confirmText: '继续',
    confirmColor: '#e5484d',
    success: (res) => {
      if (!res.confirm) return
      // 必须等第一个弹窗关闭动画结束再弹第二个：在回调里立即调用，H5 端的第二个弹窗会被吞掉
      setTimeout(confirmDeleteByTyping, 350)
    }
  })
}

function confirmDeleteByTyping() {
  uni.showModal({
    title: '最后确认',
    editable: true,
    placeholderText: '请输入「注销」两个字',
    confirmText: '确认注销',
    confirmColor: '#e5484d',
    success: async (r) => {
      if (!r.confirm) return
      if ((r.content || '').trim() !== '注销') {
        uni.showToast({ title: '输入不正确，已取消', icon: 'none' })
        return
      }
      try {
        await userStore.deleteAccount()
        uni.showToast({ title: '账号已注销', icon: 'none' })
      } catch (e) {
        // request.js 已提示具体原因
      }
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
  <view class="page" :style="{ paddingTop: statusPad + 'px' }">
    <view class="deco star">✦</view>
    <view class="deco hang">♡</view>

    <view class="title">我的小窝🥰</view>

    <!-- AvatarNoteCard -->
    <view class="avatar-card press-bounce" @click="goProfile">
      <view class="avatar-ring">
        <image
          v-if="userStore.userInfo?.avatar"
          :src="userStore.userInfo.avatar"
          class="avatar"
          mode="aspectFill"
        />
        <view v-else class="avatar fallback">{{ (userStore.userInfo?.nickname || '衣').slice(0, 1) }}</view>
      </view>
      <view class="who">
        <view class="name">{{ userStore.userInfo?.nickname || '衣笺用户' }}</view>
        <view class="tag">💛 {{ tag }}</view>
        <view class="sub">桃桃陪你搭了 {{ logCount }} 套穿搭啦</view>
        <view class="edit-hint" :class="{ todo: userStore.needsProfile }">
          {{ userStore.needsProfile ? '完善头像和昵称 ›' : '编辑资料 ›' }}
        </view>
      </view>
      <view class="peek">
        <TaotaoSprite mood="peek" :size="120" />
      </view>
    </view>

    <!-- JellyStatCards -->
    <view v-if="loadError" class="logout press-bounce" @click="loadStat">统计加载失败，点此重试</view>

    <view class="stats">
      <view class="stat mint press-bounce" @click="goCloset">
        <view class="num">{{ itemCount }}</view>
        <view class="lab">件宝贝衣服</view>
        <view class="cap">我的衣物</view>
      </view>
      <view class="stat cheese press-bounce" @click="goDiary">
        <view class="num">{{ logCount }}</view>
        <view class="lab">套搭配日记</view>
        <view class="cap">穿搭记录</view>
      </view>
    </view>

    <view class="logout press-bounce" @click="onLogout">退出登录</view>

    <view class="legal-links">
      <text class="legal-link" @click="openLegal('agreement')">用户协议</text>
      <text class="legal-sep">·</text>
      <text class="legal-link" @click="openLegal('privacy')">隐私政策</text>
      <text class="legal-sep">·</text>
      <text class="legal-link danger" @click="onDeleteAccount">注销账号</text>
    </view>

    <view class="floor-tt">
      <TaotaoSprite mood="wink" :size="96" />
    </view>

    <AppTabBar current="mine" />
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 16rpx 28rpx 40rpx;
  box-sizing: border-box;
  position: relative;
}
.deco.star {
  position: absolute;
  right: 48rpx;
  top: 80rpx;
  color: #ffd56b;
  opacity: 0.7;
}
.deco.hang {
  position: absolute;
  left: 32rpx;
  top: 88rpx;
  color: #ff8fb1;
  opacity: 0.5;
}
.title {
  text-align: center;
  font-size: 40rpx;
  font-weight: 800;
  color: #382e36;
  margin-bottom: 24rpx;
}

.avatar-card {
  position: relative;
  background: #fffdfb;
  border: 3rpx dashed #f3b8c8;
  border-radius: 32rpx;
  padding: 32rpx 28rpx 28rpx;
  display: flex;
  align-items: center;
  gap: 24rpx;
  box-shadow: 0 10rpx 36rpx rgba(255, 150, 175, 0.12);
  overflow: hidden;
}
.avatar-ring {
  width: 128rpx;
  height: 128rpx;
  border-radius: 50%;
  padding: 8rpx;
  background:
    radial-gradient(circle at 30% 20%, #fff, transparent 40%),
    repeating-conic-gradient(#ff8fb1 0 12deg, #ffd56b 12deg 18deg, #93c5fd 18deg 24deg, #8ee4af 24deg 30deg);
  box-sizing: border-box;
}
.avatar, .fallback {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: #ffe4ed;
}
.fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48rpx;
  font-weight: 800;
  color: #ff8fb1;
}
.name { font-size: 36rpx; font-weight: 800; }
.tag {
  display: inline-flex;
  margin-top: 8rpx;
  background: #fff4c8;
  border-radius: 999rpx;
  padding: 4rpx 16rpx;
  font-size: 20rpx;
  color: #382e36;
}
.sub { margin-top: 8rpx; font-size: 22rpx; color: #8a7f88; }
.peek {
  position: absolute;
  right: -8rpx;
  bottom: -18rpx;
}

.stats {
  margin-top: 28rpx;
  display: flex;
  gap: 20rpx;
}
.stat {
  flex: 1;
  border-radius: 48rpx;
  padding: 28rpx 24rpx 22rpx;
  box-shadow: 0 10rpx 36rpx rgba(255, 150, 175, 0.14);
  color: #382e36;
}
.stat.mint { background: linear-gradient(160deg, #d8fbe6, #8ee4af); }
.stat.cheese { background: linear-gradient(160deg, #ffeeb0, #ffd56b); }
.num { font-size: 56rpx; font-weight: 800; line-height: 1; }
.lab { margin-top: 8rpx; font-size: 22rpx; }
.cap { margin-top: 12rpx; font-size: 20rpx; opacity: 0.7; }

.grid {
  margin-top: 32rpx;
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
}
.cell {
  width: calc(50% - 10rpx);
  background: #fffdfb;
  border: 2rpx dashed #f3b8c8;
  border-radius: 24rpx;
  padding: 36rpx 20rpx;
  box-sizing: border-box;
  box-shadow: 0 8rpx 20rpx rgba(255, 150, 175, 0.08);
}
.cell.c1 { transform: rotate(-1.4deg); background: linear-gradient(180deg, #e8fff3, #fffdfb); }
.cell.c2 { transform: rotate(1.2deg); background: linear-gradient(180deg, #fff6d4, #fffdfb); }
.cell.c3 { transform: rotate(1.1deg); background: linear-gradient(180deg, #efe8ff, #fffdfb); }
.cell.c4 { transform: rotate(-1.3deg); background: linear-gradient(180deg, #ffe8f0, #fffdfb); }
.ico { font-size: 40rpx; }
.ct { margin-top: 12rpx; font-size: 26rpx; font-weight: 700; }

.edit-hint {
  margin-top: 8rpx;
  font-size: 22rpx;
  color: #b5aab0;
}
.edit-hint.todo {
  display: inline-block;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  color: #fff;
  background: #ff8fb1;
}
.legal-links {
  margin-top: 28rpx;
  text-align: center;
  font-size: 24rpx;
  color: #8a7f88;
  position: relative;
  z-index: 1;
}
.legal-link {
  padding: 8rpx 4rpx;
}
.legal-link.danger {
  color: #c45a6a;
}
.legal-sep {
  margin: 0 12rpx;
  color: #c9bec5;
}
.logout {
  margin: 40rpx 40rpx 0;
  height: 84rpx;
  line-height: 84rpx;
  text-align: center;
  border: 2rpx dashed #ffb3c9;
  border-radius: 20rpx;
  color: #ff8fb1;
  background: #fff8f5;
  font-size: 28rpx;
}
.floor-tt {
  display: flex;
  justify-content: flex-end;
  padding-right: 24rpx;
  margin-top: -20rpx;
}
</style>
