<script setup>
/**
 * 图片加载失败时显示占位，避免裂图。
 */
import { ref, watch } from 'vue'

const props = defineProps({
  src: { type: String, default: '' },
  mode: { type: String, default: 'aspectFill' },
  icon: { type: String, default: '👕' }
})

const broken = ref(false)
watch(() => props.src, () => { broken.value = false })
</script>

<template>
  <view class="safe-img">
    <image
      v-if="src && !broken"
      :src="src"
      :mode="mode"
      class="img"
      @error="broken = true"
    />
    <view v-else class="ph">{{ icon }}</view>
  </view>
</template>

<style scoped>
.safe-img, .img, .ph {
  width: 100%;
  height: 100%;
}
.ph {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff0f4;
  color: #ff8fb1;
  font-size: 48rpx;
}
</style>
