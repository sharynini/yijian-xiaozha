/**
 * 搭配选择 / 轻量日记 跨页状态
 *
 * 为什么用 Pinia store 而不是 URL 参数：
 *   1. 已选衣物数组可能很大，序列化后 URL 太长
 *   2. 日记页完成后需要清空，store 有显式 action
 *   3. 用户从日记页返回选择页时需要保留已选态（store 持续存活，不必重新加载）
 *
 * 传哪些字段：只传 item_id/image_url/type/color/season 这些渲染和后端必需字段
 * （后端 wear_log 按 item_ids 从库取最新值写 items_snapshot；选择页 UI 靠这些精简字段）
 */
import { defineStore } from 'pinia'

export const useOutfitStore = defineStore('outfit', {
  state: () => ({
    /** 已选中的衣物对象数组，元素形如：{ item_id, image_url, type, color, season } */
    selectedItems: []
  }),

  getters: {
    /** 仅 item_id 数组，直接喂给 POST /api/wear-logs 的 item_ids 字段 */
    selectedItemIds: (state) => state.selectedItems.map((it) => it.item_id),
    isEmpty: (state) => state.selectedItems.length === 0
  },

  actions: {
    /**
     * 切换选中态
     * @param {Object} item 完整 item 对象（至少含 item_id）
     */
    toggle(item) {
      const idx = this.selectedItems.findIndex((it) => it.item_id === item.item_id)
      if (idx >= 0) {
        this.selectedItems.splice(idx, 1)
      } else {
        // 仅保留跨页渲染必需字段，减少 store 体积
        this.selectedItems.push({
          item_id: item.item_id,
          image_url: item.image_url,
          type: item.type,
          color: item.color,
          season: item.season
        })
      }
    },

    clearSelected() {
      this.selectedItems = []
    }
  }
})
