<script setup>
/**
 * 用户协议
 * 【待填写】处需按注册小程序时的主体信息补全。
 */
const UPDATED_AT = '2026 年 11 月 5 日'

const sections = [
  {
    title: '一、协议说明',
    paras: [
      '欢迎使用「智能衣橱」（以下简称“本小程序”），本小程序由【待填写：运营者名称】运营。你在登录前勾选同意，即表示你已阅读并同意本协议和《隐私政策》。',
    ],
  },
  {
    title: '二、服务内容',
    paras: [
      '本小程序是个人衣物管理与穿搭记录工具，提供衣物拍照入库、智能识别与去背景、按天气推荐搭配、穿搭日记与时间轴等功能。你记录的内容仅本人可见。',
      '天气推荐、衣物识别等结果仅供参考，可能存在误差，请以你的实际判断为准。',
    ],
  },
  {
    title: '三、账号',
    paras: [
      '你可以使用微信一键登录或账号密码登录。请妥善保管你的账号和设备，因你自身原因导致的账号信息泄露，由你自行承担相应后果。',
      '你可以随时在「我的 → 注销账号」注销，注销后账号及全部数据会被彻底删除，无法恢复。',
    ],
  },
  {
    title: '四、你的内容与行为规范',
    paras: [
      '你上传的照片、文字等内容的权利归你所有。你授权我们为向你提供服务而存储、处理（如识别、去背景、生成缩略图）这些内容。',
      '请勿上传违反法律法规、侵犯他人权益或含有色情、暴力等不良信息的内容，请勿上传他人照片等未经授权的个人信息。违反的，我们有权删除相关内容或限制使用。',
      '请勿通过技术手段干扰本小程序正常运行，或批量、自动化调用相关接口。',
    ],
  },
  {
    title: '五、服务变更与中断',
    paras: [
      '我们会尽力保障服务稳定，但可能因系统维护、第三方服务异常、不可抗力等原因暂停或中断服务。如需停止运营，我们会提前在小程序内公告，并给你留出导出或删除数据的时间。',
    ],
  },
  {
    title: '六、责任限制',
    paras: [
      '在法律允许的范围内，本小程序按现状提供，对因使用推荐结果产生的穿着选择不承担责任。',
    ],
  },
  {
    title: '七、其他',
    paras: [
      '本协议的订立、执行和解释适用中华人民共和国法律。协议更新时会在小程序内提示，你继续使用即视为接受更新后的协议。',
      '联系我们：【待填写：联系邮箱】',
    ],
  },
]
</script>

<template>
  <scroll-view scroll-y class="legal">
    <view class="legal-title">用户协议</view>
    <view class="legal-date">更新日期：{{ UPDATED_AT }}</view>
    <view v-for="sec in sections" :key="sec.title" class="legal-section">
      <view class="legal-h">{{ sec.title }}</view>
      <view v-for="(p, i) in sec.paras" :key="i" class="legal-p">{{ p }}</view>
    </view>
  </scroll-view>
</template>

<style scoped>
.legal {
  height: 100vh;
  box-sizing: border-box;
  padding: 32rpx 36rpx 80rpx;
  background: #fffdfb;
}
.legal-title {
  font-size: 40rpx;
  font-weight: 600;
  color: #382e36;
}
.legal-date {
  margin: 12rpx 0 32rpx;
  font-size: 24rpx;
  color: #8a7f88;
}
.legal-section {
  margin-bottom: 32rpx;
}
.legal-h {
  font-size: 30rpx;
  font-weight: 600;
  color: #382e36;
  margin-bottom: 12rpx;
}
.legal-p {
  font-size: 27rpx;
  line-height: 1.8;
  color: #5a4f57;
  margin-bottom: 10rpx;
}
</style>
