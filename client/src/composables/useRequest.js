/**
 * 统一数据请求 composable
 *
 * 解决问题：每个页面都自己维护 loading / error / empty / retry 的模板分支，分散且不一致。
 * 这个 composable 把"请求 + 状态管理 + 重试"封装掉，页面只关心业务。
 *
 * @param {Function} fetcher   返回 Promise 的函数（会被调用时传 ...args 透传）
 * @param {Object}   [options]
 * @param {boolean}  [options.auto=true]  是否立即执行一次
 * @returns {{ data, loading, error, run }}
 *
 * 用法示例：
 *   // 时间轴页面（带分页）
 *   const page = ref(1)
 *   const { data, loading, run: fetchLogs } = useRequest(
 *     () => get('/api/wear-logs', { page: page.value, per_page: 10 }),
 *     { auto: true }
 *   )
 *
 *   // 首页推荐（不需要手动 run，auto=true 立即执行）
 *   const { data: recommend } = useRequest(
 *     () => get('/api/recommend', { temperature: temperature.value }),
 *     { auto: true }
 *   )
 *
 * 模板里统一判断：
 *   <template v-if="loading">加载中…</template>
 *   <template v-else-if="error">加载失败 <button @click="fetchLogs()">重试</button></template>
 *   <template v-else-if="!data?.list?.length">暂无记录</template>
 *   <template v-else>... 正常列表 ...</template>
 */
import { ref } from 'vue'

export function useRequest(fetcher, options = {}) {
  const { auto = false } = options

  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function run(...args) {
    loading.value = true
    error.value = null
    try {
      const res = await fetcher(...args)
      data.value = res
      return res
    } catch (e) {
      error.value = e
      // request.js 已经 toast 了具体错误，这里只记录以便模板判断
      return null
    } finally {
      loading.value = false
    }
  }

  if (auto) run()

  return { data, loading, error, run }
}
