<script setup>
/**
 * IP 桃桃贴纸：圆滚滚、头顶小衣架、腮红。
 * mood: wave | peek | wink | book | closet | spin | fab
 */
const props = defineProps({
  mood: { type: String, default: 'wave' },
  size: { type: Number, default: 140 }
})

const SRC = {
  wave: '/static/taotao/wave.jpg',
  peek: '/static/taotao/peek.jpg',
  wink: '/static/taotao/peek.jpg',
  book: '/static/taotao/book.jpg',
  closet: '/static/taotao/closet.jpg',
  spin: '/static/taotao/wave.jpg',
  fab: '/static/taotao/wave.jpg'
}
</script>

<template>
  <image
    class="tt"
    :class="mood"
    :src="SRC[mood] || SRC.wave"
    mode="aspectFit"
    :style="{ width: size + 'rpx', height: size + 'rpx' }"
  />
</template>

<style scoped>
.tt {
  display: block;
  flex-shrink: 0;
  pointer-events: none;
}
.wave { animation: bob 1.8s ease-in-out infinite; }
.spin { animation: spin 0.9s linear infinite; }
.peek { transform: rotate(-8deg); }
@keyframes bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8rpx); }
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
