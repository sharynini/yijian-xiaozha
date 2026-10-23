<template>
  <view class="app-empty">
    <view v-if="icon" class="empty-icon">{{ icon }}</view>
    <view class="empty-title">{{ title }}</view>
    <view v-if="desc" class="empty-desc">{{ desc }}</view>
    <button v-if="actionText" class="empty-action" @click="emit('action')">
      {{ actionText }}
    </button>
  </view>
</template>

<script setup>
/**
 * 通用空状态组件
 *
 * uni-app easycom 会自动扫描 components/ 目录，页面里直接用 <AppEmpty /> 就行，
 * 不需要 import。
 *
 * 用法：
 *   <AppEmpty icon="👕" title="还没有穿搭记录" desc="选两件今天穿的衣物吧"
 *             action-text="去记录" @action="goRecord" />
 *   <AppEmpty icon="🧥" title="暂无推荐" desc="先去衣橱添加衣物"
 *             action-text="去衣橱" @action="goWardrobe" />
 */
defineProps({
  icon:      { type: String, default: '📭' },
  title:     { type: String, default: '暂无数据' },
  desc:      { type: String, default: '' },
  actionText:{ type: String, default: '' },
})

const emit = defineEmits(['action'])
</script>

<style scoped>
.app-empty {
  padding: 120rpx 60rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.empty-icon {
  font-size: 120rpx;
  line-height: 1;
}

.empty-title {
  margin-top: 28rpx;
  font-size: 32rpx;
  font-weight: 600;
  color: #3d5a80;
}

.empty-desc {
  margin-top: 14rpx;
  font-size: 26rpx;
  color: #7b8794;
  text-align: center;
  line-height: 1.6;
}

.empty-action {
  margin-top: 40rpx;
  background: linear-gradient(135deg, #5b8def, #7aa2cc);
  color: #ffffff;
  font-size: 28rpx;
  font-weight: 500;
  border-radius: 999rpx;
  padding: 18rpx 60rpx;
  border: none;
}

.empty-action::after {
  border: none;
}
</style>
