import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import api from '../config/api'

const getScoreColor = (score) => {
  if (score >= 80) return 'text-green-600'
  if (score >= 60) return 'text-yellow-600'
  return 'text-red-500'
}

const getScoreLabel = (score) => {
  if (score >= 80) return '强烈推荐'
  if (score >= 65) return '建议考虑'
  if (score >= 50) return '谨慎评估'
  return '不建议'
}

export default function AIReport() {
  const { districtId } = useParams()   // 路由参数
  const navigate = useNavigate()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  // 先尝试拉已有报告，没有就生成
  useEffect(() => {
    if (!localStorage.getItem('token')) { navigate('/login'); return }
    generateReport()
  }, [districtId])

  const generateReport = async () => {
    setGenerating(true)
    setError('')
    try {
      const data = await api.post(`/districts/${districtId}/ai-report`)
      setReport(data)
    } catch (err) {
      const msg = err.response?.data?.detail || 'AI报告生成失败，请稍后重试'
      setError(msg)
    } finally {
      setGenerating(false)
      setLoading(false)
    }
  }

  if (loading || generating) {
    return (
      <div>
        <Navbar />
        <div className="max-w-4xl mx-auto px-4 py-24 text-center">
          <div className="text-4xl mb-4 animate-pulse">🤖</div>
          <p className="text-lg font-semibold mb-2">AI正在分析中...</p>
          <p className="text-sm text-text-sub">综合商圈数据、竞品情况、客群特征，预计10-30秒</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div>
        <Navbar />
        <div className="max-w-4xl mx-auto px-4 py-24 text-center">
          <div className="text-4xl mb-4">⚠️</div>
          <p className="text-red-500 mb-4">{error}</p>
          <button onClick={generateReport} className="bg-primary text-white px-6 py-2 rounded-btn">
            重试
          </button>
        </div>
      </div>
    )
  }

  if (!report) return null

  return (
    <div>
      <Navbar />
      <div className="max-w-4xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">🤖 AI研判报告</h1>

        {/* AI评分 */}
        <div className="bg-white rounded-card shadow-card p-8 text-center mb-6">
          <div className="text-sm text-text-sub mb-2">AI综合评分</div>
          <div className={`text-6xl font-bold font-price ${getScoreColor(report.ai_score)}`}>
            {report.ai_score}
          </div>
          <div className="text-sm text-text-sub mt-1">/100</div>
          <div className={`inline-block mt-3 px-4 py-1 rounded-full text-sm font-medium ${
            report.ai_score >= 80 ? 'bg-green-50 text-green-600' :
            report.ai_score >= 65 ? 'bg-yellow-50 text-yellow-600' :
            report.ai_score >= 50 ? 'bg-orange-50 text-orange-600' :
            'bg-red-50 text-red-500'
          }`}>
            {getScoreLabel(report.ai_score)}
          </div>
        </div>

        {/* 推荐品牌 */}
        {report.recommended_brands?.length > 0 && (
          <div className="bg-white rounded-card shadow-card p-6 mb-4">
            <h3 className="font-semibold text-green-600 mb-3">✅ 推荐开的品牌</h3>
            <div className="space-y-3">
              {report.recommended_brands.map((brand, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-sm font-medium shrink-0">
                    {brand.name}
                  </span>
                  <span className="text-sm text-text-sub">{brand.reason}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 不建议品牌 */}
        {report.warning_brands?.length > 0 && (
          <div className="bg-white rounded-card shadow-card p-6 mb-4">
            <h3 className="font-semibold text-red-500 mb-3">⚠️ 不建议开的品牌</h3>
            <div className="space-y-3">
              {report.warning_brands.map((brand, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="bg-red-100 text-red-600 px-2 py-0.5 rounded text-sm font-medium shrink-0">
                    {brand.name}
                  </span>
                  <span className="text-sm text-text-sub">{brand.reason}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 详细分析 */}
        <div className="bg-white rounded-card shadow-card p-6 mb-4">
          <h3 className="font-semibold mb-3">📊 详细分析</h3>
          <div className="space-y-3 divide-y divide-gray-100">
            {report.estimated_daily_cups && (
              <div className="flex justify-between pt-3 first:pt-0">
                <span className="text-text-sub">预估日均杯数</span>
                <span className="font-medium">{report.estimated_daily_cups}</span>
              </div>
            )}
          </div>
        </div>

        {/* 风险提醒 */}
        {report.risk_factors?.length > 0 && (
          <div className="bg-red-50 rounded-card p-6 mb-4">
            <h3 className="font-semibold text-red-600 mb-3">⚠️ 风险提醒</h3>
            <ul className="space-y-2">
              {report.risk_factors.map((risk, i) => (
                <li key={i} className="text-sm text-red-700">• {typeof risk === 'string' ? risk : JSON.stringify(risk)}</li>
              ))}
            </ul>
          </div>
        )}

        {/* 选址建议 */}
        {report.site_suggestion && (
          <div className="bg-green-50 rounded-card p-6 mb-6">
            <h3 className="font-semibold text-green-700 mb-3">💡 选址建议</h3>
            <p className="text-sm text-green-800 leading-relaxed">{report.site_suggestion}</p>
          </div>
        )}

        <p className="text-xs text-text-sub text-center">
          ⚠️ 以上分析基于公开数据和AI模型生成，仅供参考，不构成投资建议。实际选址请结合实地考察。
        </p>
        <p className="text-xs text-text-sub text-center mt-1">
          报告生成于 {report.created_at ? new Date(report.created_at).toLocaleString('zh-CN') : ''}
        </p>
      </div>
      <Footer />
    </div>
  )
}
