<script setup>
/**
 * 底部导航：首页 / 衣橱 / 时间轴 / 我的
 * 手绘风图标，选中项带小星星
 */
import { computed } from 'vue'

const props = defineProps({
  current: { type: String, default: 'index' }
})

const tabs = [
  { id: 'index', text: '首页', url: '/pages/index/index' },
  { id: 'closet', text: '衣橱', url: '/pages/item/list' },
  { id: 'diary', text: '时间轴', url: '/pages/timeline/index' },
  { id: 'mine', text: '我的', url: '/pages/mine/index' }
]

const active = computed(() => props.current)

function go(tab) {
  if (tab.id === active.value) return
  uni.switchTab({ url: tab.url })
}
</script>

<template>
  <view class="tabbar-placeholder" />
  <view class="tabbar">
    <view
      v-for="tab in tabs"
      :key="tab.id"
      class="tab"
      :class="{ on: active === tab.id }"
      @click="go(tab)"
    >
      <view class="ico-wrap">
        <view class="star" v-if="active === tab.id">✦</view>
        <view class="ico" :class="tab.id" />
      </view>
      <text class="txt">{{ tab.text }}</text>
    </view>
  </view>
</template>

<style scoped>
.tabbar-placeholder {
  height: 140rpx;
  padding-bottom: env(safe-area-inset-bottom);
}
.tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 50;
  height: 120rpx;
  padding-bottom: env(safe-area-inset-bottom);
  background: #fffdfb;
  border-top: 3rpx dashed #ffd0de;
  display: flex;
  box-shadow: 0 -8rpx 24rpx rgba(255, 150, 175, 0.08);
}
.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6rpx;
}
.ico-wrap {
  position: relative;
  width: 48rpx;
  height: 44rpx;
}
.star {
  position: absolute;
  top: -16rpx;
  right: -14rpx;
  font-size: 18rpx;
  color: #ffd56b;
  animation: pop 0.35s ease;
}
.txt {
  font-size: 20rpx;
  color: #8a7f88;
}
.tab.on .txt {
  color: #ff8fb1;
  font-weight: 700;
}

/* 手绘图标：不均匀描边 */
.ico {
  position: absolute;
  inset: 4rpx;
  border: 5rpx solid #8a7f88;
  border-radius: 10rpx 14rpx 8rpx 12rpx;
}
.ico.index {
  border-radius: 8rpx 8rpx 4rpx 4rpx;
  clip-path: polygon(50% 0, 100% 42%, 82% 42%, 82% 100%, 18% 100%, 18% 42%, 0 42%);
  background: transparent;
  border: none;
  box-shadow:
    0 0 0 5rpx #8a7f88;
}
.tab.on .ico.index { box-shadow: 0 0 0 5rpx #ff8fb1; background: #ffe4ed; }

.ico.closet {
  border: none;
  background: transparent;
}
.ico.closet::before,
.ico.closet::after {
  content: '';
  position: absolute;
  border: 4rpx solid #8a7f88;
}
.ico.closet::before {
  left: 20%;
  right: 20%;
  top: 0;
  height: 28%;
  border-radius: 20rpx 20rpx 0 0;
  border-bottom: none;
}
.ico.closet::after {
  left: 8%;
  right: 8%;
  top: 28%;
  bottom: 8%;
  border-radius: 6rpx;
}
.tab.on .ico.closet::before,
.tab.on .ico.closet::after { border-color: #ff8fb1; }

.ico.diary {
  border-radius: 6rpx 16rpx 6rpx 6rpx;
  background: #fff;
}
.ico.diary::after {
  content: '';
  position: absolute;
  left: 18%;
  right: 18%;
  top: 28%;
  height: 4rpx;
  background: #8a7f88;
  box-shadow: 0 10rpx 0 #8a7f88, 0 20rpx 0 #8a7f88;
}
.tab.on .ico.diary { border-color: #ff8fb1; background: #fff4c8; }
.tab.on .ico.diary::after { background: #ff8fb1; box-shadow: 0 10rpx 0 #ff8fb1, 0 20rpx 0 #ff8fb1; }

.ico.mine {
  border-radius: 50% 50% 40% 40%;
  width: 28rpx;
  height: 28rpx;
  left: 10rpx;
  top: 0;
}
.ico.mine::after {
  content: '';
  position: absolute;
  left: -8rpx;
  top: 26rpx;
  width: 44rpx;
  height: 16rpx;
  border: 4rpx solid #8a7f88;
  border-radius: 20rpx 20rpx 8rpx 8rpx;
  border-top: none;
}
.tab.on .ico.mine { border-color: #ff8fb1; background: #ffe4ed; }
.tab.on .ico.mine::after { border-color: #ff8fb1; }

@keyframes pop {
  from { transform: scale(0.4) rotate(-20deg); opacity: 0; }
  to { transform: scale(1) rotate(12deg); opacity: 1; }
}
</style>
