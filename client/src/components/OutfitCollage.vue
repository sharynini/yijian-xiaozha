<script setup>
/**
 * 手动搭配拼贴图（只读展示）
 * 按 collage 里每件衣物的相对坐标还原画布效果，用于日记页预览和时间轴卡片。
 *
 * props.collage: [{ item_id, x, y, w, z }]，x/y/w 为相对画布边长的 0~1 比例（画布是正方形）
 * props.items:   含 item_id 与 image_url 的衣物数组（时间轴里用日记的 items 快照）
 */
import { computed } from 'vue'

const props = defineProps({
  collage: { type: Array, default: () => [] },
  items: { type: Array, default: () => [] }
})

const pieces = computed(() => {
  const urlOf = {}
  props.items.forEach((it) => { urlOf[it.item_id] = it.image_url })
  return props.collage
    .filter((p) => urlOf[p.item_id])
    .map((p) => ({ ...p, src: urlOf[p.item_id] }))
    .sort((a, b) => (a.z || 0) - (b.z || 0))
})
</script>

<template>
  <view class="collage">
    <view
      v-for="p in pieces"
      :key="p.item_id"
      class="piece"
      :style="{
        left: p.x * 100 + '%',
        top: p.y * 100 + '%',
        width: p.w * 100 + '%',
        height: p.w * 100 + '%',
        zIndex: p.z || 0
      }"
    >
      <image class="img" :src="p.src" mode="aspectFit" />
    </view>
  </view>
</template>

<style scoped>
.collage {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background:
    radial-gradient(circle, rgba(255, 143, 177, 0.18) 2rpx, transparent 2.5rpx) 0 0 / 28rpx 28rpx,
    #fffaf7;
}
.piece {
  position: absolute;
}
.img {
  width: 100%;
  height: 100%;
}
</style>
