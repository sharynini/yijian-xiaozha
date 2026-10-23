<script>
import { TOKEN_KEY } from '@/utils/config'

export default {
  onLaunch() {
    // 启动时校验登录态：未登录直接跳转登录页
    const token = uni.getStorageSync(TOKEN_KEY)
    if (!token) {
      uni.reLaunch({ url: '/pages/login/login' })
    }
  },
  onShow() {},
  onHide() {}
}
</script>

<style>
/* 全局基础样式：干净、有呼吸感的浅色风格 */
page {
  background-color: #f4f7fb;
  color: #2b3441;
  font-size: 28rpx;
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
}

/* 通用容器 */
.container {
  padding: 24rpx;
}

/* 卡片 */
.card {
  background: #ffffff;
  border-radius: 20rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 20rpx rgba(143, 179, 217, 0.12);
}

/* 主按钮 */
.btn-primary {
  background: #5b8def;
  color: #ffffff;
  border-radius: 16rpx;
  font-size: 30rpx;
  line-height: 88rpx;
  height: 88rpx;
  text-align: center;
  border: none;
}
.btn-primary::after {
  border: none;
}

/* 次要按钮 */
.btn-ghost {
  background: #eef3f9;
  color: #3d5a80;
  border-radius: 16rpx;
  font-size: 30rpx;
  line-height: 88rpx;
  height: 88rpx;
  text-align: center;
  border: none;
}
.btn-ghost::after {
  border: none;
}

/* 输入框 */
.input {
  background: #fbfcfe;
  border: 1rpx solid #d7e0ea;
  border-radius: 14rpx;
  height: 88rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
}

/* 标签文字 */
.label {
  font-size: 26rpx;
  color: #7b8794;
  margin-bottom: 12rpx;
}

/* 空状态 */
.empty {
  text-align: center;
  color: #a4b0be;
  font-size: 26rpx;
  padding: 120rpx 0;
}
</style>
