/**
 * 用户登录状态管理（Pinia）
 * 维护 token 与用户信息，并同步到本地缓存
 */
import { defineStore } from 'pinia'
import { post, get, put, del, wxSilentLogin } from '@/utils/request'
import { TOKEN_KEY, USER_KEY, MANUAL_LOGOUT_KEY } from '@/utils/config'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: uni.getStorageSync(TOKEN_KEY) || '',
    userInfo: uni.getStorageSync(USER_KEY) || null
  }),

  getters: {
    isLogin: (state) => !!state.token,
    nickname: (state) => (state.userInfo && state.userInfo.nickname) || '未登录',
    /** 还没设置过头像：「我的」页提示去完善资料 */
    needsProfile: (state) => !!state.userInfo && !state.userInfo.avatar
  },

  actions: {
    /**
     * 保存登录态
     */
    setAuth(token, userInfo) {
      this.token = token || ''
      this.userInfo = userInfo || null
      uni.setStorageSync(TOKEN_KEY, this.token)
      uni.setStorageSync(USER_KEY, this.userInfo)
      if (this.token) uni.removeStorageSync(MANUAL_LOGOUT_KEY)
    },

    /**
     * 微信一键登录（小程序端，用户主动点击；首次登录会自动创建账号）
     * @returns {Promise<{user, isNew}>} isNew 为 true 时登录页引导去设置头像昵称
     */
    async wxLogin() {
      uni.showLoading({ title: '登录中...', mask: true })
      try {
        const data = await wxSilentLogin({ manual: true })
        this.setAuth(data.access_token, data.user)
        return { user: data.user, isNew: !!data.is_new }
      } finally {
        uni.hideLoading()
      }
    },

    /**
     * 登录（用户名或邮箱 + 密码）
     */
    async login(account, password) {
      const data = await post('/api/auth/login', { account, password }, { loading: true, loadingText: '登录中...', auth: false })
      this.setAuth(data.access_token, data.user)
      return data.user
    },

    /**
     * 注册
     */
    async register(username, email, password) {
      return post('/api/auth/register', { username, email, password }, { loading: true, loadingText: '注册中...', auth: false })
    },

    /**
     * 修改头像 / 昵称（PUT /api/auth/profile），成功后同步本地用户信息
     * @param {{nickname?: string, avatar?: string}} payload 只传要改的字段
     */
    async updateProfile(payload) {
      const user = await put('/api/auth/profile', payload, { loading: true, loadingText: '保存中...' })
      this.userInfo = user
      uni.setStorageSync(USER_KEY, user)
      return user
    },

    /**
     * 拉取当前用户信息（校验 token 有效性）
     */
    async fetchProfile() {
      const user = await get('/api/auth/profile', {}, { loading: true })
      this.userInfo = user
      uni.setStorageSync(USER_KEY, user)
      return user
    },

    /**
     * 注销账号：后端彻底删除账号与全部数据；成功后清空本机所有缓存并回到登录页
     * 小程序端同样记下「主动退出」，避免回到登录页后又被静默登录建出新账号
     */
    async deleteAccount() {
      await del('/api/auth/account', {}, { loading: true, loadingText: '注销中...' })
      this.token = ''
      this.userInfo = null
      uni.clearStorageSync()
      uni.setStorageSync(MANUAL_LOGOUT_KEY, 1)
      uni.reLaunch({ url: '/pages/login/login' })
    },

    /**
     * 退出登录
     * 小程序端记下「主动退出」，之后不再自动静默登录，直到用户在登录页手动登录
     */
    logout() {
      this.token = ''
      this.userInfo = null
      uni.removeStorageSync(TOKEN_KEY)
      uni.removeStorageSync(USER_KEY)
      uni.setStorageSync(MANUAL_LOGOUT_KEY, 1)
      uni.reLaunch({ url: '/pages/login/login' })
    }
  }
})
