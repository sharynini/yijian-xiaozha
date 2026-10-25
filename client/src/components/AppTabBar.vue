<script setup>
/**
 * 底部导航：首页 / 衣橱 / 时间轴 / 我的
 * 图标为 static/tabbar 下的 SVG（未选中 + 选中各一套），H5 与小程序 <image> 均支持
 */
import { computed } from 'vue'

const props = defineProps({
  current: { type: String, default: 'index' }
})

const tabs = [
  { id: 'index', text: '首页', url: '/pages/index/index', icon: 'home' },
  { id: 'closet', text: '衣橱', url: '/pages/item/list', icon: 'closet' },
  { id: 'diary', text: '时间轴', url: '/pages/timeline/index', icon: 'diary' },
  { id: 'mine', text: '我的', url: '/pages/mine/index', icon: 'mine' }
]

const active = computed(() => props.current)

function iconSrc(tab) {
  const suffix = active.value === tab.id ? '-on' : ''
  return `/static/tabbar/${tab.icon}${suffix}.svg`
}

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
        <view v-if="active === tab.id" class="bubble" />
        <image class="ico" :src="iconSrc(tab)" mode="aspectFit" />
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
  border-top: 2rpx solid #ffe1ea;
  display: flex;
  box-shadow: 0 -8rpx 24rpx rgba(255, 150, 175, 0.08);
}
.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4rpx;
}
.ico-wrap {
  position: relative;
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* 选中时图标背后的淡粉色圆形 */
.bubble {
  position: absolute;
  width: 68rpx;
  height: 68rpx;
  border-radius: 50%;
  background: #fff0f5;
  animation: pop 0.3s ease;
}
.ico {
  position: relative;
  width: 52rpx;
  height: 52rpx;
}
.tab.on .ico {
  animation: bounce 0.35s ease;
}
.txt {
  font-size: 20rpx;
  color: #8a7f88;
}
.tab.on .txt {
  color: #ff8fb1;
  font-weight: 700;
}

@keyframes pop {
  from { transform: scale(0.4); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
@keyframes bounce {
  0% { transform: translateY(0); }
  40% { transform: translateY(-6rpx); }
  100% { transform: translateY(0); }
}
</style>
