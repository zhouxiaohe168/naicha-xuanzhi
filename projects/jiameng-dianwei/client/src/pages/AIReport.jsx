import { useParams } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'

// 临时mock AI研判数据
const MOCK_AI_REPORT = {
  score: 78,
  summary: '该商圈适合开奶茶店',
  recommended_brands: [
    { name: '蜜雪冰城', reason: '性价比匹配周边消费水平' },
    { name: '书亦烧仙草', reason: '差异化空间大，周边暂无同品牌' },
  ],
  warning_brands: [
    { name: '喜茶', reason: '已有2家，市场饱和' },
    { name: '瑞幸咖啡', reason: '周边3家，竞争激烈' },
  ],
  analysis: {
    saturation: '中等（还能再开1-2家）',
    daily_cups: '150-200杯',
    main_customers: '上班族为主(60%)、学生(25%)、居民(15%)',
  },
  risks: [
    '周边租金偏高，月租约1.5-2万，注意成本控制',
    '500米内已有3家奶茶店，需差异化经营',
  ],
  suggestion: '建议选择商圈北侧靠近写字楼的位置，午间白领客流量最大。避开南侧已有蜜雪冰城和喜茶的区域。',
}

// 评分颜色
const getScoreColor = (score) => {
  if (score >= 80) return 'text-green-600'
  if (score >= 60) return 'text-yellow-600'
  return 'text-red-500'
}

export default function AIReport() {
  const { id } = useParams()
  const report = MOCK_AI_REPORT

  return (
    <div>
      <Navbar />
      <div className="max-w-4xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">🤖 AI研判报告</h1>

        {/* AI评分 */}
        <div className="bg-white rounded-card shadow-card p-8 text-center mb-6">
          <div className="text-sm text-text-sub mb-2">AI综合评分</div>
          <div className={`text-6xl font-bold font-price ${getScoreColor(report.score)}`}>
            {report.score}
          </div>
          <div className="text-sm text-text-sub mt-1">/100</div>
          <div className="text-lg font-semibold mt-4">{report.summary}</div>
        </div>

        {/* 推荐品牌 */}
        <div className="bg-white rounded-card shadow-card p-6 mb-4">
          <h3 className="font-semibold text-green-600 mb-3">✅ 推荐品牌</h3>
          {report.recommended_brands.map((brand) => (
            <div key={brand.name} className="flex items-start gap-2 mb-2 last:mb-0">
              <span className="font-medium">{brand.name}</span>
              <span className="text-sm text-text-sub">— {brand.reason}</span>
            </div>
          ))}
        </div>

        {/* 不建议品牌 */}
        <div className="bg-white rounded-card shadow-card p-6 mb-4">
          <h3 className="font-semibold text-red-500 mb-3">⚠️ 不建议品牌</h3>
          {report.warning_brands.map((brand) => (
            <div key={brand.name} className="flex items-start gap-2 mb-2 last:mb-0">
              <span className="font-medium">{brand.name}</span>
              <span className="text-sm text-text-sub">— {brand.reason}</span>
            </div>
          ))}
        </div>

        {/* 详细分析 */}
        <div className="bg-white rounded-card shadow-card p-6 mb-4">
          <h3 className="font-semibold mb-3">📊 详细分析</h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-text-sub">竞争饱和度</span>
              <span className="font-medium">{report.analysis.saturation}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-sub">预估日均杯数</span>
              <span className="font-medium">{report.analysis.daily_cups}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-sub">周边客群</span>
              <span className="font-medium">{report.analysis.main_customers}</span>
            </div>
          </div>
        </div>

        {/* 风险提醒 */}
        <div className="bg-red-50 rounded-card p-6 mb-4">
          <h3 className="font-semibold text-red-600 mb-3">⚠️ 风险提醒</h3>
          <ul className="space-y-2">
            {report.risks.map((risk, i) => (
              <li key={i} className="text-sm text-red-700">• {risk}</li>
            ))}
          </ul>
        </div>

        {/* 选址建议 */}
        <div className="bg-green-50 rounded-card p-6 mb-6">
          <h3 className="font-semibold text-green-700 mb-3">💡 选址建议</h3>
          <p className="text-sm text-green-800">{report.suggestion}</p>
        </div>

        {/* 免责声明 */}
        <p className="text-xs text-text-sub text-center">
          ⚠️ 以上分析基于公开数据和AI模型生成，仅供参考，不构成投资建议。
          实际选址请结合实地考察。
        </p>
      </div>
      <Footer />
    </div>
  )
}
