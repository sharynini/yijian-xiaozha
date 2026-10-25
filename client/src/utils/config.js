/**
 * 全局配置
 *
 * BASE_URL 按 Vite 模式读取：
 *   开发：client/.env.development 的 VITE_API_BASE
 *   生产：client/.env.production 的 VITE_API_BASE
 *   真机调试：复制为 .env.development.local（已 gitignore），写成电脑局域网 IP
 */

export const BASE_URL = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:5001'

// 本地缓存 key
export const TOKEN_KEY = 'sw_token'
export const USER_KEY = 'sw_user'

// 业务错误码（与后端约定一致）
export const CODE = {
  SUCCESS: 0,
  UNAUTHORIZED: 401
}
