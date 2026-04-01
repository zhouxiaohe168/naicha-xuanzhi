// 项目配置常量
export const APP_NAME = '奶茶选址通'
export const APP_SLOGAN = '奶茶咖啡选址，AI帮你做决定'
export const APP_DESC = '不用实地考察，9.9元看清商圈竞品'

// 价格
export const PRICE_BASIC = 9.9
export const PRICE_AI = 59.9
export const PRICE_UPGRADE = 50 // 基础报告升级AI的补差价

// 范围选择选项（米）
export const RANGE_OPTIONS = [
  { label: '500m', value: 500 },
  { label: '1km', value: 1000 },
  { label: '2km', value: 2000 },
  { label: '3km', value: 3000 },
]
export const DEFAULT_RANGE = 1000

// MVP城市
export const MVP_CITY = '金华市'

// 品牌配色（标签用）
export const BRAND_COLORS = {
  '蜜雪冰城': { bg: '#FEE2E2', text: '#DC2626' },
  '瑞幸咖啡': { bg: '#DBEAFE', text: '#2563EB' },
  '喜茶': { bg: '#D1FAE5', text: '#059669' },
  '库迪咖啡': { bg: '#E0E7FF', text: '#4F46E5' },
  '沪上阿姨': { bg: '#FCE7F3', text: '#DB2777' },
  '书亦烧仙草': { bg: '#FEF3C7', text: '#D97706' },
  default: { bg: '#F3F4F6', text: '#6B7280' },
}
