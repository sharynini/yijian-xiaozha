<template>
  <!-- 骨架屏：列表 / 卡片加载中 -->
  <view v-if="type === 'skeleton'" class="loading-skeleton">
    <view v-for="n in count" :key="n" class="skeleton-card">
      <view class="sk sk-thumb" />
      <view class="sk-body">
        <view class="sk sk-line sk-line--lg" />
        <view class="sk sk-line sk-line--sm" />
      </view>
    </view>
  </view>

  <!-- 文字 / 三点：局部或轻量加载 -->
  <view v-else class="loading-inline">
    <view class="dots">
      <view class="dot" />
      <view class="dot" />
      <view class="dot" />
    </view>
    <text v-if="text" class="loading-label">{{ text }}</text>
  </view>
</template>

<script setup>
/**
 * 通用加载状态组件（与 AppEmpty 配对的「加载中」呈现）
 *
 * 提供两种统一风格：
 *   1. skeleton —— 列表/卡片骨架屏，适合首屏与分页加载
 *   2. text     —— 三点呼吸 + 文案，适合按钮旁、区块内的轻量加载
 *
 * 样式全部写在组件内部并基于设计系统 token，不依赖全局类，
 * 在微信小程序等「组件样式隔离」环境下同样生效。
 *
 * uni-app easycom 自动扫描 components/ 目录，直接用 <AppLoading /> 即可，无需 import。
 *
 * 用法：
 *   <AppLoading v-if="loading" type="skeleton" :count="3" />
 *   <AppLoading v-if="loading" text="加载中…" />
 */
defineProps({
  // 'skeleton' | 'text'
  type:  { type: String, default: 'text' },
  text:  { type: String, default: '加载中…' },
  // 骨架屏卡片数量
  count: { type: Number, default: 3 },
})
</script>

<style lang="scss" scoped>
/* ---------- 骨架屏 ---------- */
.loading-skeleton {
  display: flex;
  flex-direction: column;
  gap: $list-gap;
}

.skeleton-card {
  display: flex;
  gap: $space-md;
  align-items: center;
  background: $color-bg-card;
  border-radius: $radius-lg;
  padding: $card-padding;
  box-shadow: $shadow-xs;
}

/* 骨架元素：轻盈的呼吸动画，避免刺眼 */
.sk {
  background: linear-gradient(
    90deg,
    $color-bg-muted 25%,
    $color-bg-soft 37%,
    $color-bg-muted 63%
  );
  background-size: 400% 100%;
  border-radius: $radius-sm;
  animation: sk-loading 1.4s ease infinite;
}

.sk-thumb {
  width: 120rpx;
  height: 120rpx;
  border-radius: $radius-md;
  flex: 0 0 auto;
}

.sk-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: $space-sm;
}

.sk-line {
  height: 24rpx;
  &--lg {
    width: 60%;
  }
  &--sm {
    width: 35%;
  }
}

@keyframes sk-loading {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0 50%;
  }
}

/* ---------- 三点呼吸 ---------- */
.loading-inline {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: $space-sm;
  padding: $space-xl 0;
}

.dots {
  display: flex;
  gap: 10rpx;
}

.dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: $radius-circle;
  background: $color-primary-light;
  animation: dot-breathe 1.2s ease-in-out infinite;

  &:nth-child(2) {
    animation-delay: 0.2s;
  }
  &:nth-child(3) {
    animation-delay: 0.4s;
  }
}

@keyframes dot-breathe {
  0%,
  100% {
    opacity: 0.3;
    transform: scale(0.8);
  }
  50% {
    opacity: 1;
    transform: scale(1);
  }
}

.loading-label {
  font-size: $font-sm;
  color: $color-text-placeholder;
}
</style>
