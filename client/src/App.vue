<script>
import { TOKEN_KEY } from '@/utils/config'

export default {
  onLaunch() {
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
page {
  background-color: #fff8f5;
  background-image: repeating-linear-gradient(
    to bottom,
    rgba(255, 143, 177, 0.045) 0,
    rgba(255, 143, 177, 0.045) 1px,
    transparent 1px,
    transparent 28px
  );
  color: #382e36;
  font-size: 28rpx;
  font-family: -apple-system, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
}

.container {
  padding: 24rpx;
}

.jelly-card {
  background: #fffdfb;
  border-radius: 48rpx;
  box-shadow: 0 10rpx 36rpx rgba(255, 150, 175, 0.14);
}

.note-card {
  background: #fffdfb;
  border-radius: 28rpx;
  border: 2rpx dashed #f3b8c8;
  box-shadow: 0 10rpx 28rpx rgba(255, 150, 175, 0.08);
}

.btn-primary {
  background: linear-gradient(180deg, #ffb3c9 0%, #ff8fb1 70%);
  color: #ffffff;
  border-radius: 999rpx;
  font-size: 30rpx;
  font-weight: 600;
  line-height: 88rpx;
  height: 88rpx;
  text-align: center;
  border: none;
  box-shadow: 0 10rpx 22rpx rgba(255, 143, 177, 0.35);
}
.btn-primary::after {
  border: none;
}

.btn-ghost {
  background: #fff8f5;
  color: #ff8fb1;
  border-radius: 20rpx;
  font-size: 28rpx;
  line-height: 84rpx;
  height: 84rpx;
  text-align: center;
  border: 2rpx dashed #ffb3c9;
}
.btn-ghost::after {
  border: none;
}

.input {
  background: #fffdfb;
  border: 2rpx dashed #f3d5dc;
  border-radius: 20rpx;
  height: 88rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
}

.label {
  font-size: 26rpx;
  color: #8a7f88;
  margin-bottom: 12rpx;
}

.empty {
  text-align: center;
  color: #8a7f88;
  font-size: 26rpx;
  padding: 120rpx 0;
}

.press-bounce {
  position: relative;
  transition: transform 0.12s ease;
}
.press-bounce:active {
  transform: scale(0.96);
}
@media (hover: hover) {
  .press-bounce:hover::after {
    content: '✦';
    position: absolute;
    top: -8rpx;
    right: 8rpx;
    color: #ffd56b;
    font-size: 22rpx;
    pointer-events: none;
    animation: star-pop 0.35s ease;
  }
}
@keyframes star-pop {
  from { transform: scale(0.3) rotate(-20deg); opacity: 0; }
  to { transform: scale(1) rotate(12deg); opacity: 1; }
}

.style-chip {
  display: inline-flex;
  align-items: center;
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  font-size: 20rpx;
  font-weight: 600;
  color: #382e36;
}

.deco-star,
.deco-dot,
.deco-bow,
.deco-heart {
  position: absolute;
  pointer-events: none;
  opacity: 0.85;
  z-index: 0;
}
</style>
