/**
 * 衣橱数量相关的小工具
 *
 *   getItemCount()      查询当前用户未删除衣物总数（GET /api/items?per_page=1 取 total）
 *   ensureHasItems()    衣橱为空时弹框引导去添加，并返回 false 拦住后续跳转；有衣服返回 true
 *
 * 规则（4d）：0 件 → 拦住进画布并引导添加；1 件 → 可以进画布（单件也能记录）；首页推荐卡片分档提示由首页自己处理
 * 查询失败（网络问题等）时不拦截，交给后续页面自己处理，避免误伤正常使用
 */
import { get } from './request'

export async function getItemCount() {
  const data = await get('/api/items', { page: 1, per_page: 1 }, { silent: true, skipDedup: true })
  return Number(data && data.total) || 0
}

export async function ensureHasItems() {
  let count
  try {
    count = await getItemCount()
  } catch (e) {
    return true
  }
  if (count > 0) return true

  uni.showModal({
    title: '衣橱还是空的',
    content: '先拍几件衣服放进衣橱，再来搭配和记录吧～',
    confirmText: '去添加',
    confirmColor: '#ff8fb1',
    success: (res) => {
      if (res.confirm) uni.navigateTo({ url: '/pages/item/add' })
    }
  })
  return false
}
