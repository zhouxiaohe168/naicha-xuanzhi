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

// ── 加盟商选址：目标品牌 ──────────────────────────────
export const TARGET_BRANDS = [
  { name: '蜜雪冰城', icon: '🧋', category: 'tea',  desc: '低价高频，学生工人首选' },
  { name: '古茗',    icon: '🍵', category: 'tea',  desc: '中价奶茶，年轻白领客群' },
  { name: '正新鸡排', icon: '🍗', category: 'food', desc: '平价炸鸡，人流密集区' },
  { name: '华莱士',  icon: '🍔', category: 'food', desc: '平价快餐，下沉市场强' },
  { name: '瑞幸咖啡', icon: '☕', category: 'coffee', desc: '平价咖啡，白领上班族' },
  { name: '其他品牌', icon: '🏪', category: 'other', desc: '自定义品牌，通用选址' },
]

// 锚点品牌（选定目标品牌后，系统默认推荐的参考锚点）
export const ANCHOR_BRANDS = [
  { name: '古茗',    icon: '🍵' },
  { name: '瑞幸咖啡', icon: '☕' },
  { name: '麦当劳',  icon: '🍟' },
  { name: '肯德基',  icon: '🍗' },
  { name: '大润发',  icon: '🛒' },
  { name: '正新鸡排', icon: '🍗' },
  { name: '霸王茶姬', icon: '👑' },
  { name: '绝味鸭脖', icon: '🦆' },
]

// 品牌 → 系统默认推荐的锚点（加盟商不用自己想，系统帮他选）
export const DEFAULT_ANCHORS = {
  '蜜雪冰城': ['古茗', '瑞幸咖啡', '正新鸡排', '大润发'],
  '古茗':     ['瑞幸咖啡', '蜜雪冰城', '麦当劳', '肯德基'],
  '正新鸡排': ['麦当劳', '肯德基', '蜜雪冰城', '绝味鸭脖'],
  '华莱士':   ['麦当劳', '肯德基', '正新鸡排', '蜜雪冰城'],
  '瑞幸咖啡': ['麦当劳', '肯德基', '古茗', '霸王茶姬'],
  '其他品牌': ['古茗', '瑞幸咖啡', '麦当劳'],
}

// 商圈-品牌适配评分（基于真实高德POI数据分析）
// score: 满分10分 | level: high/medium/low | anchors_found: 真实存在的锚点品牌
export const BRAND_SCORES = {
  '蜜雪冰城': {
    '金东区多湖商圈':  { score: 8.5, level: 'high',   anchors_found: ['古茗', '瑞幸咖啡', '库迪咖啡'], reason: '新区蓝海，0家竞品，古茗+瑞幸验证需求' },
    '义乌国际商贸城':  { score: 8.2, level: 'high',   anchors_found: ['喜茶', '霸王茶姬', '肯德基'],   reason: '全球最高密度流量，低价需求旺盛' },
    '义乌商城大道':   { score: 7.9, level: 'high',   anchors_found: ['古茗', '麦当劳'],              reason: '批发商客群，外来人口价格敏感' },
    '金华步行街':     { score: 7.8, level: 'high',   anchors_found: ['古茗', '喜茶', '霸王茶姬'],    reason: '核心步行街，市场体量大，已有蜜雪2家' },
    '金华火车站商圈':  { score: 7.5, level: 'high',   anchors_found: ['霸王茶姬', '喜茶', '茉酸奶'],  reason: '旅客高频需求，出站口是黄金位置' },
    '兰溪市区商圈':   { score: 7.3, level: 'medium', anchors_found: ['古茗', '正新鸡排'],            reason: '工人客群，价格极敏感，竞争压力低' },
    '宾虹路商业区':   { score: 7.1, level: 'medium', anchors_found: ['古茗', '大润发'],              reason: '社区型门店，稳定复购，租金低' },
    '浦江县城商圈':   { score: 6.8, level: 'medium', anchors_found: ['古茗'],                       reason: '县城下沉市场，低成本快回本' },
    '万达广场商圈':   { score: 6.5, level: 'medium', anchors_found: ['瑞幸咖啡', '古茗', '奈雪的茶'], reason: '外街可开，商场内客群偏高端' },
    '东阳市商圈':    { score: 6.5, level: 'medium', anchors_found: ['古茗', '霸王茶姬'],            reason: '消费力偏高，市区可开，景区不建议' },
  },
  '正新鸡排': {
    '义乌国际商贸城':  { score: 8.4, level: 'high',   anchors_found: ['麦当劳', '肯德基', '蜜雪冰城'], reason: '超高流量，快消需求旺，低价快餐天堂' },
    '金华火车站商圈':  { score: 8.0, level: 'high',   anchors_found: ['肯德基', '麦当劳'],            reason: '旅客快餐需求强，客单价契合' },
    '金华步行街':     { score: 7.8, level: 'high',   anchors_found: ['麦当劳', '蜜雪冰城'],          reason: '步行街逛吃场景，正餐替代需求大' },
    '金东区多湖商圈':  { score: 7.5, level: 'high',   anchors_found: ['蜜雪冰城', '肯德基'],          reason: '新区快餐缺口大，率先入驻优势明显' },
    '兰溪市区商圈':   { score: 7.3, level: 'medium', anchors_found: ['绝味鸭脖', '蜜雪冰城'],        reason: '工人区快消需求强，竞争少' },
    '宾虹路商业区':   { score: 6.8, level: 'medium', anchors_found: ['蜜雪冰城'],                   reason: '社区店，固定客流，竞争低' },
    '万达广场商圈':   { score: 6.5, level: 'medium', anchors_found: ['肯德基', '麦当劳'],            reason: '外街可开，内场竞争激烈' },
    '义乌商城大道':   { score: 6.5, level: 'medium', anchors_found: ['蜜雪冰城'],                   reason: '商贸城延伸区，可配套布局' },
    '浦江县城商圈':   { score: 6.2, level: 'medium', anchors_found: [],                            reason: '县城体量有限，谨慎评估' },
    '东阳市商圈':    { score: 5.8, level: 'low',    anchors_found: [],                            reason: '消费力偏高，快餐档次不匹配' },
  },
}

// 评分等级配置
export const SCORE_LEVEL = {
  high:   { label: '强烈推荐', color: 'text-green-700',  bg: 'bg-green-50',  border: 'border-green-200', dot: 'bg-green-500' },
  medium: { label: '可以考虑',  color: 'text-yellow-700', bg: 'bg-yellow-50', border: 'border-yellow-200', dot: 'bg-yellow-500' },
  low:    { label: '谨慎评估', color: 'text-red-600',    bg: 'bg-red-50',    border: 'border-red-200',    dot: 'bg-red-400' },
}
