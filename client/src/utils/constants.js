/**
 * 衣物枚举常量
 * 取值必须与后端保持一致（server/app/modules/item/services.py 中的 ALLOWED_*）
 * 后端校验严格等值匹配，前端不要自造新值
 */

// 衣物类型（顺序即衣橱左侧导航顺序）
export const ITEM_TYPES = ['上装', '下装', '连衣裙', '外套', '鞋子', '包包', '帽子', '配饰']

// 适用季节
export const SEASONS = ['春', '夏', '秋', '冬', '全季']

// 适用场合
export const OCCASIONS = ['日常', '工作', '运动', '正式']

// 颜色（列表筛选与表单共用，后端按等值筛选，建议从预设里选）
export const COLORS = [
  '黑色', '白色', '灰色', '米色', '卡其', '棕色', '蓝色', '牛仔蓝',
  '绿色', '红色', '粉色', '紫色', '黄色', '橙色', '花色'
]

// 列表页筛选专用：下标 0 表示「全部」（对应不传该参数）
export const FILTER_TYPES = ['全部', ...ITEM_TYPES]
export const FILTER_SEASONS = ['全部', ...SEASONS]
export const FILTER_COLORS = ['全部', ...COLORS]

// ---------- 穿搭日记心情 ----------
// 取值必须与后端 ALLOWED_MOODS 严格一致（server/app/models/wear_log.py）
// icon 用 emoji，H5 和小程序都原生支持，不引入额外图标库
export const MOODS = [
  { label: '开心', icon: '😄' },
  { label: '平静', icon: '😌' },
  { label: '专注', icon: '🧐' },
  { label: '疲惫', icon: '😵‍💫' },
  { label: '期待', icon: '🤩' },
  { label: '低落', icon: '😔' },
  { label: '自信', icon: '🦾' },
  { label: '随性', icon: '🌿' }
]
