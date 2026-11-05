<script>
/**
 * 微信小程序隐私授权弹窗
 *
 * 机制：小程序调用定位、选图、拍照等隐私接口时，如果用户还没同意《隐私保护指引》，
 * 微信会触发 wx.onNeedPrivacyAuthorization，接口调用先挂起，等开发者回调 resolve 后：
 *   - 同意：接口继续执行
 *   - 拒绝：接口失败（各页面已有失败兜底，例如定位失败改为手动调温度）
 *
 * 用法：在会调用隐私接口的页面 import 本组件，并在模板里放一个 <PrivacyPopup />
 *      （easycom 只自动扫描 components/名称/名称.vue 结构，这里需要手动 import）。
 * 监听在模块加载时注册一次（全局只有一个），弹窗状态在各页面的组件实例间共享，
 * 只有当前显示的页面能看到并点击按钮。
 *
 * 「同意」按钮必须是 open-type="agreePrivacyAuthorization" 的 button，id 要与 resolve 的 buttonId 一致。
 * 《隐私保护指引》的内容在小程序后台填写，wx.openPrivacyContract 打开的就是那一份。
 * H5 等其它端不渲染任何内容。
 */
import { reactive } from 'vue'

const AGREE_BUTTON_ID = 'privacy-agree-btn'

const privacyState = reactive({
  visible: false,
  contractName: '《隐私保护指引》',
})
let pendingResolve = null

// #ifdef MP-WEIXIN
if (typeof wx !== 'undefined' && wx.onNeedPrivacyAuthorization) {
  wx.onNeedPrivacyAuthorization((resolve) => {
    pendingResolve = resolve
    privacyState.visible = true
  })
  if (wx.getPrivacySetting) {
    wx.getPrivacySetting({
      success: (res) => {
        if (res && res.privacyContractName) privacyState.contractName = res.privacyContractName
      },
    })
  }
}
// #endif

function finish(event) {
  privacyState.visible = false
  if (pendingResolve) {
    pendingResolve(event === 'agree' ? { buttonId: AGREE_BUTTON_ID, event: 'agree' } : { event: 'disagree' })
    pendingResolve = null
  }
}
</script>

<script setup>
const state = privacyState
const agreeButtonId = AGREE_BUTTON_ID

function onAgree() {
  finish('agree')
}

function onDisagree() {
  finish('disagree')
}

function openContract() {
  // #ifdef MP-WEIXIN
  if (wx.openPrivacyContract) wx.openPrivacyContract({})
  // #endif
}
</script>

<template>
  <!-- #ifdef MP-WEIXIN -->
  <view v-if="state.visible" class="privacy-mask" @touchmove.stop.prevent>
    <view class="privacy-card">
      <view class="privacy-title">用户隐私保护提示</view>
      <view class="privacy-desc">
        为了帮你记录衣物、获取当地天气，需要使用相册、相机和位置信息。使用前请阅读
        <text class="privacy-link" @click="openContract">{{ state.contractName }}</text>
        ，同意后才能继续。拒绝也不影响浏览，相关功能可以手动操作。
      </view>
      <view class="privacy-actions">
        <button class="privacy-btn ghost" @click="onDisagree">拒绝</button>
        <button
          :id="agreeButtonId"
          class="privacy-btn primary"
          open-type="agreePrivacyAuthorization"
          @agreeprivacyauthorization="onAgree"
        >同意</button>
      </view>
    </view>
  </view>
  <!-- #endif -->
</template>

<style scoped>
.privacy-mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 9999;
  background: rgba(56, 46, 54, 0.45);
  display: flex;
  align-items: flex-end;
}
.privacy-card {
  width: 100%;
  box-sizing: border-box;
  background: #fffdfb;
  border-radius: 40rpx 40rpx 0 0;
  padding: 48rpx 40rpx calc(40rpx + env(safe-area-inset-bottom));
}
.privacy-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #382e36;
  margin-bottom: 24rpx;
}
.privacy-desc {
  font-size: 28rpx;
  line-height: 1.7;
  color: #8a7f88;
}
.privacy-link {
  color: #ff8fb1;
}
.privacy-actions {
  display: flex;
  margin-top: 40rpx;
}
.privacy-btn {
  flex: 1;
  height: 84rpx;
  line-height: 84rpx;
  border-radius: 999rpx;
  font-size: 30rpx;
  border: none;
}
.privacy-btn::after {
  border: none;
}
.privacy-btn + .privacy-btn {
  margin-left: 24rpx;
}
.privacy-btn.ghost {
  background: #fff8f5;
  color: #8a7f88;
}
.privacy-btn.primary {
  background: linear-gradient(180deg, #ffb3c9 0%, #ff8fb1 70%);
  color: #ffffff;
}
</style>
