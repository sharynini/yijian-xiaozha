/**
 * 用户登录状态管理（Pinia）
 * 维护 token 与用户信息，并同步到本地缓存
 */
import { defineStore } from 'pinia'
import { post, get } from '@/utils/request'
import { TOKEN_KEY, USER_KEY } from '@/utils/config'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: uni.getStorageSync(TOKEN_KEY) || '',
    userInfo: uni.getStorageSync(USER_KEY) || null
  }),

  getters: {
    isLogin: (state) => !!state.token,
    nickname: (state) => (state.userInfo && state.userInfo.nickname) || '未登录'
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
    },

    /**
     * 登录（用户名或邮箱 + 密码）
     */
    async login(account, password) {
      const data = await post('/api/auth/login', { account, password }, { loading: true, loadingText: '登录中...' })
      this.setAuth(data.access_token, data.user)
      return data.user
    },

    /**
     * 注册
     */
    async register(username, email, password) {
      return post('/api/auth/register', { username, email, password }, { loading: true, loadingText: '注册中...' })
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
     * 退出登录
     */
    logout() {
      this.token = ''
      this.userInfo = null
      uni.removeStorageSync(TOKEN_KEY)
      uni.removeStorageSync(USER_KEY)
      uni.reLaunch({ url: '/pages/login/login' })
    }
  }
})
