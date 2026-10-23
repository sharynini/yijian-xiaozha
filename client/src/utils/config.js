/**
 * 全局配置
 */

// 后端接口基地址
// - H5 / 浏览器调试：http://127.0.0.1:5001
// - 微信小程序真机预览：需改为电脑局域网 IP，例如 http://172.20.10.8:5001
export const BASE_URL = 'http://127.0.0.1:5001'

// 本地缓存 key
export const TOKEN_KEY = 'sw_token'
export const USER_KEY = 'sw_user'

// 业务错误码（与后端约定一致）
export const CODE = {
  SUCCESS: 0,
  UNAUTHORIZED: 401
}
