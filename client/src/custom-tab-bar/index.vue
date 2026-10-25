<script>
/**
 * uni-app 自定义 tabBar 入口（pages.json tabBar.custom = true）
 * 各 tab 页仍会再放 AppTabBar，这里留空高度避免原生条挡住。
 */
export default {
  data() {
    return { hide: true }
  }
}
</script>
<template>
  <view />
</template>
<style>
/* 原生占位隐藏，实际导航由页面内 AppTabBar 绘制 */
</style>
