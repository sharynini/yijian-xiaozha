/**
 * 统一请求工具
 * 能力：
 *   1. 自动携带 Token（从本地缓存读取）
 *   2. 统一处理 HTTP 状态码与业务错误码
 *   3. 可选 loading 提示
 *   4. 401 自动清除登录态并跳转登录页（带防重入 flag，避免并发 401 触发多次 reLaunch）
 *   5. GET 请求去重（1 秒内相同 URL + body 的请求复用同一个 Promise，防狂刷）
 *   6. 开发期 console.* 输出错误细节，方便定位
 *
 * 用法：
 *   import { get, post } from '@/utils/request'
 *   const data = await post('/api/auth/login', { account, password })   // 直接拿到 data
 */
import { BASE_URL, TOKEN_KEY, USER_KEY, CODE } from './config'

// ============================================================
// 1) 401 重定向防重入：避免并发请求多次触发 reLaunch
// ============================================================
let isRedirecting = false

function handleUnauthorized() {
  if (isRedirecting) return
  isRedirecting = true
  try {
    uni.removeStorageSync(TOKEN_KEY)
    uni.removeStorageSync(USER_KEY)
  } catch (e) {
    // uni.removeStorageSync 在某些平台不抛异常，这里只是防御
  }
  console.warn('[request] 401 Unauthorized → redirect login')
  uni.showToast({ title: '登录已过期，请重新登录', icon: 'none', duration: 1200 })
  // 等 toast 显示一下再跳
  setTimeout(() => {
    uni.reLaunch({
      url: '/pages/login/login',
      complete: () => { isRedirecting = false }
    })
  }, 800)
}

// ============================================================
// 2) GET 请求去重：1 秒内相同 method+url+body 只发一次
// ============================================================
const IN_FLIGHT = new Map()   // dedupKey → Promise
const DEDUP_TTL_MS = 1000

function _dedupKey(method, url, data) {
  return `${method}:${url}:${JSON.stringify(data || {})}`
}

// ============================================================
// 3) 核心请求
// ============================================================

/**
 * @param {Object} options
 * @param {string} options.url      接口路径（以 / 开头，不含 BASE_URL）
 * @param {string} [options.method] 请求方法，默认 GET
 * @param {Object} [options.data]   请求数据
 * @param {Object} [options.header] 额外请求头
 * @param {boolean} [options.loading]     是否显示 loading，默认 false
 * @param {string} [options.loadingText]  loading 文案
 * @param {boolean} [options.skipDedup]   跳过 GET 去重（比如强刷），默认 false
 * @returns {Promise<any>} resolve 业务 data；reject 业务错误体
 */
export function request(options = {}) {
  const {
    url,
    method = 'GET',
    data = {},
    header = {},
    loading = false,
    loadingText = '加载中...',
    skipDedup = false,
  } = options

  if (loading) {
    uni.showLoading({ title: loadingText, mask: true })
  }

  const token = uni.getStorageSync(TOKEN_KEY)

  // GET 去重（写操作页面里已经有 submitting guard，不去重）
  if (method === 'GET' && !skipDedup) {
    const key = _dedupKey(method, url, data)
    const existing = IN_FLIGHT.get(key)
    if (existing) return existing
  }

  const promise = new Promise((resolve, reject) => {
    uni.request({
      url: BASE_URL + url,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: 'Bearer ' + token } : {}),
        ...header,
      },
      success: (res) => {
        const { statusCode, data: body } = res
        const bizCode = body && typeof body.code !== 'undefined' ? body.code : null

        // ① 未授权：HTTP 401 或业务码 401
        if (statusCode === 401 || bizCode === CODE.UNAUTHORIZED) {
          handleUnauthorized()
          reject(body || { code: 401, msg: '登录已过期，请重新登录' })
          return
        }

        // ② 业务成功
        if (statusCode >= 200 && statusCode < 300 && bizCode === CODE.SUCCESS) {
          resolve(body.data)
          return
        }

        // ③ 其他错误（HTTP 非 2xx 或业务码非 0）
        const msg = (body && body.msg) || `请求失败(${statusCode})`
        console.warn('[request] business error', { url, statusCode, bizCode, body })
        uni.showToast({ title: msg, icon: 'none' })
        reject(body || { code: statusCode, msg })
      },
      fail: (err) => {
        console.error('[request] network fail', { url, err })
        uni.showToast({ title: '网络异常，请检查网络', icon: 'none' })
        reject(err)
      },
      complete: () => {
        if (loading) uni.hideLoading()
      },
    })
  })

  // 只对 GET 去重：TTL 后释放
  if (method === 'GET' && !skipDedup) {
    const key = _dedupKey(method, url, data)
    IN_FLIGHT.set(key, promise)
    promise.finally(() => {
      setTimeout(() => {
        // 只有当 Map 里还是这同一个 Promise 才清（避免 A 请求先完成、B 请求后完成时的竞态）
        if (IN_FLIGHT.get(key) === promise) {
          IN_FLIGHT.delete(key)
        }
      }, DEDUP_TTL_MS)
    })
  }

  return promise
}

// ============================================================
// 4) 上传文件（图片）—— 独立实现但复用 handleUnauthorized
// ============================================================

/**
 * 上传文件（图片）
 * @param {string} filePath  uni.chooseImage 返回的 tempFilePaths[0]
 * @param {string} [name]    后端接收的字段名，默认 'file'
 * @returns {Promise<{url: string}>}
 */
export function uploadFile(filePath, name = 'file') {
  const token = uni.getStorageSync(TOKEN_KEY)

  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: BASE_URL + '/api/upload',
      filePath,
      name,
      header: token ? { Authorization: 'Bearer ' + token } : {},
      success: (res) => {
        let body = res.data
        try { body = JSON.parse(res.data) } catch (e) { /* 非 JSON（如 413） */ }
        const bizCode = body && typeof body.code !== 'undefined' ? body.code : null

        if (res.statusCode === 401 || bizCode === CODE.UNAUTHORIZED) {
          handleUnauthorized()
          reject(body || { code: 401, msg: '登录已过期' })
          return
        }

        if (res.statusCode >= 200 && res.statusCode < 300 && bizCode === CODE.SUCCESS) {
          resolve(body.data)
          return
        }

        const msg = (body && body.msg) || `上传失败(${res.statusCode})`
        console.warn('[uploadFile] error', { status: res.statusCode, body })
        uni.showToast({ title: msg, icon: 'none' })
        reject(body || { code: res.statusCode, msg })
      },
      fail: (err) => {
        console.error('[uploadFile] network fail', err)
        uni.showToast({ title: '网络异常，请检查网络', icon: 'none' })
        reject(err)
      },
    })
  })
}

// ============================================================
// 5) 便捷方法
// ============================================================
export function get(url, data, options = {}) {
  return request({ url, method: 'GET', data, ...options })
}
export function post(url, data, options = {}) {
  return request({ url, method: 'POST', data, ...options })
}
export function put(url, data, options = {}) {
  return request({ url, method: 'PUT', data, ...options })
}
export function del(url, data, options = {}) {
  return request({ url, method: 'DELETE', data, ...options })
}

export default request
