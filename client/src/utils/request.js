/**
 * 统一请求工具
 * 能力：
 *   1. 自动携带 Token（从本地缓存读取）
 *   2. 统一处理 HTTP 状态码与业务错误码
 *   3. 可选 loading 提示
 *   4. 401 自动清除登录态并跳转登录页（带防重入 flag，避免并发 401 触发多次 reLaunch）
 *   5. GET 请求去重（1 秒内相同 URL + body 的请求复用同一个 Promise，防狂刷）
 *   6. 开发期 console.* 输出错误细节，方便定位
 *   7. 微信小程序：没有 token 时先静默 wx.login 换 token；遇到 401 先静默重登并重试一次，仍失败才跳登录页
 *      （用户在「我的」里主动退出后不再静默登录，直到手动点「微信一键登录」或账号密码登录）
 *
 * 用法：
 *   import { get, post } from '@/utils/request'
 *   const data = await post('/api/auth/login', { account, password })   // 直接拿到 data
 */
import { BASE_URL, TOKEN_KEY, USER_KEY, MANUAL_LOGOUT_KEY, AUTH_EVENT, CODE } from './config'

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
// 1.5) 微信小程序静默登录：wx.login → POST /api/auth/wx-login → 写入 token
//      并发调用共享同一个 Promise，避免一次启动换多次 code
// ============================================================
let wxLoginPromise = null

/**
 * 微信静默登录（仅小程序端可用）
 * @param {Object} [opts]
 * @param {boolean} [opts.manual] 用户主动点按钮登录时为 true，会忽略「已主动退出」标记
 * @returns {Promise<{access_token, user, is_new}>}
 */
export function wxSilentLogin({ manual = false } = {}) {
  // #ifndef MP-WEIXIN
  return Promise.reject({ code: -1, msg: '仅微信小程序支持微信登录' })
  // #endif

  // #ifdef MP-WEIXIN
  if (!manual && uni.getStorageSync(MANUAL_LOGOUT_KEY)) {
    return Promise.reject({ code: -1, msg: '已主动退出登录' })
  }
  if (wxLoginPromise) return wxLoginPromise

  wxLoginPromise = new Promise((resolve, reject) => {
    uni.login({
      provider: 'weixin',
      success: ({ code }) => {
        uni.request({
          url: BASE_URL + '/api/auth/wx-login',
          method: 'POST',
          data: { code },
          header: { 'Content-Type': 'application/json' },
          success: ({ data: body }) => {
            if (body && body.code === CODE.SUCCESS && body.data && body.data.access_token) {
              uni.setStorageSync(TOKEN_KEY, body.data.access_token)
              uni.setStorageSync(USER_KEY, body.data.user)
              uni.removeStorageSync(MANUAL_LOGOUT_KEY)
              uni.$emit(AUTH_EVENT, body.data)   // App.vue 监听，同步到 Pinia
              resolve(body.data)
            } else {
              console.warn('[wxSilentLogin] business error', body)
              reject(body || { code: -1, msg: '微信登录失败' })
            }
          },
          fail: (err) => {
            console.error('[wxSilentLogin] network fail', err)
            reject(err)
          },
        })
      },
      fail: (err) => {
        console.error('[wxSilentLogin] wx.login fail', err)
        reject(err)
      },
    })
  })
  wxLoginPromise.then(
    () => { wxLoginPromise = null },
    () => { wxLoginPromise = null }
  )
  return wxLoginPromise
  // #endif
}

/**
 * 给一次请求加上「登录保障」：
 *   - 小程序端：没有 token 先静默登录；401 时清 token、静默重登、重试一次
 *   - 其它端 / 静默登录失败：走原来的 401 处理（清登录态并跳登录页）
 * @param {Function} attempt 发一次请求，返回 Promise；401 时 reject 的错误体带 __unauthorized
 * @param {boolean} auth     是否需要登录（登录、注册接口传 false）
 */
async function _withAuth(attempt, auth) {
  // #ifdef MP-WEIXIN
  if (auth && !uni.getStorageSync(TOKEN_KEY)) {
    await wxSilentLogin().catch(() => {})
  }
  // #endif

  try {
    return await attempt()
  } catch (e) {
    if (!(e && e.__unauthorized)) throw e

    // #ifdef MP-WEIXIN
    if (auth) {
      uni.removeStorageSync(TOKEN_KEY)
      const relogged = await wxSilentLogin().then(() => true, () => false)
      if (relogged) {
        try {
          return await attempt()
        } catch (e2) {
          if (!(e2 && e2.__unauthorized)) throw e2
        }
      }
    }
    // #endif

    handleUnauthorized()
    throw e
  }
}

function _unauthorizedError(body) {
  return { ...(body && typeof body === 'object' ? body : { code: 401, msg: '登录已过期，请重新登录' }), __unauthorized: true }
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
 * @param {boolean} [options.silent]      出错时不弹 toast（由调用方自行处理），默认 false
 * @param {boolean} [options.auth]        是否需要登录，默认 true；登录 / 注册接口传 false
 * @returns {Promise<any>} resolve 业务 data；reject 业务错误体
 */
export function request(options = {}) {
  const { url, method = 'GET', data = {}, skipDedup = false, auth = true } = options

  // GET 去重（写操作页面里已经有 submitting guard，不去重）
  if (method === 'GET' && !skipDedup) {
    const key = _dedupKey(method, url, data)
    const existing = IN_FLIGHT.get(key)
    if (existing) return existing
  }

  const promise = _withAuth(() => _send(options), auth)

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

/** 发一次请求（不含登录保障与去重） */
function _send(options) {
  const {
    url,
    method = 'GET',
    data = {},
    header = {},
    loading = false,
    loadingText = '加载中...',
    silent = false,
  } = options

  if (loading) {
    uni.showLoading({ title: loadingText, mask: true })
  }

  const token = uni.getStorageSync(TOKEN_KEY)

  return new Promise((resolve, reject) => {
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
          reject(_unauthorizedError(body))
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
        if (!silent) uni.showToast({ title: msg, icon: 'none' })
        reject(body || { code: statusCode, msg })
      },
      fail: (err) => {
        console.error('[request] network fail', { url, err })
        if (!silent) uni.showToast({ title: '网络异常，请检查网络', icon: 'none' })
        reject(err)
      },
      complete: () => {
        if (loading) uni.hideLoading()
      },
    })
  })
}

// ============================================================
// 4) 上传文件（图片）—— 独立实现，登录保障与 request 共用 _withAuth
// ============================================================

/**
 * 上传文件（图片）
 * @param {string} filePath  uni.chooseImage 返回的 tempFilePaths[0]
 * @param {string} [name]    后端接收的字段名，默认 'file'
 * @returns {Promise<{url: string}>}
 */
export function uploadFile(filePath, name = 'file') {
  return _withAuth(() => _sendUpload(filePath, name), true)
}

function _sendUpload(filePath, name) {
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
          reject(_unauthorizedError(body))
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
