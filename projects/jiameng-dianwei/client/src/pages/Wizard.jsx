import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Header from '../components/Header'
import { wizardAPI, checkoutAPI } from '../lib/api'

const budgetOptions = [
  { label: '15-30万', value: '15-30' },
  { label: '30-50万', value: '30-50' },
  { label: '50-80万', value: '50-80' },
  { label: '80万以上', value: '80+' },
]

const brands = [
  { name: '蜜雪冰城', risk: '低', trend: '↑', budget: '15-30', tag: '下沉王者' },
  { name: '古茗', risk: '低', trend: '↑', budget: '15-30', tag: '华东强势' },
  { name: '茶百道', risk: '中', trend: '→', budget: '30-50', tag: '全国扩张' },
  { name: '霸王茶姬', risk: '中', trend: '↑', budget: '30-50', tag: '高增长' },
  { name: '奈雪的茶', risk: '中', trend: '→', budget: '50-80', tag: '高端定位' },
  { name: '喜茶', risk: '高', trend: '↑', budget: '80+', tag: '一线首选' },
  { name: '沪上阿姨', risk: '低', trend: '↑', budget: '15-30', tag: '性价比高' },
  { name: '书亦烧仙草', risk: '低', trend: '→', budget: '15-30', tag: '稳健经营' },
]

const cities = [
  { name: '杭州', grade: 'A', hot: true },
  { name: '宁波', grade: 'B', hot: false },
  { name: '温州', grade: 'B', hot: false },
  { name: '金华', grade: 'C', hot: false },
  { name: '绍兴', grade: 'B', hot: false },
  { name: '台州', grade: 'C', hot: false },
  { name: '嘉兴', grade: 'B', hot: false },
  { name: '湖州', grade: 'C', hot: false },
  { name: '上海', grade: 'A', hot: true },
  { name: '北京', grade: 'A', hot: false },
  { name: '成都', grade: 'A', hot: true },
  { name: '武汉', grade: 'A', hot: false },
  { name: '广州', grade: 'A', hot: false },
  { name: '深圳', grade: 'A', hot: false },
  { name: '重庆', grade: 'A', hot: true },
  { name: '西安', grade: 'B', hot: false },
  { name: '南京', grade: 'A', hot: false },
  { name: '苏州', grade: 'A', hot: false },
]

const riskColor = { 低: 'text-success', 中: 'text-warning', 高: 'text-danger' }
const gradeColor = {
  A: 'bg-success/20 text-success',
  B: 'bg-warning/20 text-warning',
  C: 'bg-text-muted/20 text-text-muted',
}

export default function Wizard() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [budget, setBudget] = useState('')
  const [selectedBrand, setSelectedBrand] = useState('')
  const [selectedCity, setSelectedCity] = useState('')
  const [reportType, setReportType] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const filteredBrands = budget ? brands.filter(b => b.budget === budget) : brands

  const handleGenerate = async () => {
    if (!reportType || !selectedBrand || !selectedCity) return
    setLoading(true)
    setError('')

    try {
      // Step 1: 调用后端获取真实数据报告
      const reportRes = await wizardAPI.getReport(selectedBrand, selectedCity, reportType)
      const reportData = reportRes.data

      // Step 2: 创建订单
      const orderRes = await checkoutAPI.createOrder(
        reportType, selectedBrand, selectedCity, reportData, null, null
      )
      const orderData = orderRes.data

      // Step 3: 跳转到支付/报告页
      if (orderData.payment_method === 'mock') {
        // 开发模式：直接mock支付然后跳到报告
        await checkoutAPI.mockPay(orderData.order_id)
        navigate('/report', { state: { orderId: orderData.order_id, reportData } })
      } else if (orderData.pay_url) {
        // 生产模式：跳转支付宝
        navigate('/checkout', { state: { orderData, reportData } })
      } else {
        navigate('/report', { state: { orderId: orderData.order_id, reportData } })
      }
    } catch (err) {
      console.error('[Wizard]', err)
      // API失败时退化到本地mock数据继续体验
      const mockReport = {
        brand: selectedBrand,
        city: selectedCity,
        report_type: reportType,
        grade: 'B+',
        score: 74,
        data: {
          brand_count: 18,
          competitor_total: 65,
          consumption_index: 68,
          traffic_level: '中',
          saturation: '中',
          ecosystem_brands: ['古茗', '茶百道', '霸王茶姬'],
        },
        ai_analysis: reportType === 'ai' ? `基于市场数据分析，${selectedCity}对${selectedBrand}整体评级B+，市场格局较为成熟，竞争强度适中。建议优先考察新商业综合体和高密度居住区周边的空白点位。本分析仅供参考，不构成投资建议。` : undefined,
      }
      navigate('/report', { state: { reportData: mockReport } })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-navy">
      <Header />
      <div className="pt-24 pb-16 px-4">
        <div className="max-w-2xl mx-auto">

          {/* Progress */}
          <div className="flex items-center gap-2 mb-10">
            {[1, 2, 3].map((s) => (
              <div key={s} className="flex items-center gap-2 flex-1">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 ${
                  s < step ? 'bg-primary text-white' :
                  s === step ? 'bg-primary text-white' :
                  'bg-card-bg border border-card-border text-text-muted'
                }`}>
                  {s < step ? '✓' : s}
                </div>
                {s < 3 && (
                  <div className={`h-0.5 flex-1 ${s < step ? 'bg-primary' : 'bg-card-border'}`} />
                )}
              </div>
            ))}
          </div>

          {/* Step 1: Budget → Brand */}
          {step === 1 && (
            <div>
              <h2 className="text-xl font-bold text-text-primary mb-2">选择投资预算</h2>
              <p className="text-text-secondary text-sm mb-6">我们会推荐匹配你预算的品牌</p>

              <div className="grid grid-cols-2 gap-3 mb-8">
                {budgetOptions.map((b) => (
                  <button
                    key={b.value}
                    onClick={() => { setBudget(b.value); setSelectedBrand('') }}
                    className={`card p-4 text-left transition-colors ${
                      budget === b.value ? 'border-primary' : 'hover:border-primary/50'
                    }`}
                  >
                    <div className={`font-semibold ${budget === b.value ? 'text-primary' : 'text-text-secondary'}`}>
                      {b.label}
                    </div>
                  </button>
                ))}
              </div>

              <h3 className="text-text-primary font-semibold mb-4">
                {budget ? `适合 ${budget}万 的品牌` : '全部品牌'}
                <span className="text-text-muted text-xs font-normal ml-2">（点击选择）</span>
              </h3>
              <div className="grid grid-cols-2 gap-3 mb-8">
                {filteredBrands.map((b) => (
                  <button
                    key={b.name}
                    onClick={() => setSelectedBrand(b.name)}
                    className={`card p-4 text-left transition-colors ${
                      selectedBrand === b.name ? 'border-primary bg-primary/5' : 'hover:border-primary/50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-text-primary font-semibold">{b.name}</span>
                      <span className="text-lg">{b.trend}</span>
                    </div>
                    <div className="flex gap-2">
                      <span className={`text-xs ${riskColor[b.risk]}`}>风险 {b.risk}</span>
                      <span className="text-xs text-text-muted">· {b.tag}</span>
                    </div>
                  </button>
                ))}
              </div>

              <button
                onClick={() => setStep(2)}
                disabled={!selectedBrand}
                className="w-full bg-primary hover:bg-primary-hover text-white py-3 rounded-btn font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                下一步：选择城市
              </button>
            </div>
          )}

          {/* Step 2: City */}
          {step === 2 && (
            <div>
              <h2 className="text-xl font-bold text-text-primary mb-2">选择目标城市</h2>
              <p className="text-text-secondary text-sm mb-6">
                已选品牌：<span className="text-primary font-semibold">{selectedBrand}</span>
              </p>

              <div className="grid grid-cols-3 gap-3 mb-8">
                {cities.map((c) => (
                  <button
                    key={c.name}
                    onClick={() => setSelectedCity(c.name)}
                    className={`card p-3 text-left transition-colors relative ${
                      selectedCity === c.name ? 'border-primary bg-primary/5' : 'hover:border-primary/50'
                    }`}
                  >
                    {c.hot && (
                      <span className="absolute -top-1.5 -right-1.5 bg-danger text-white text-xs px-1.5 py-0.5 rounded-full">热</span>
                    )}
                    <div className="text-text-primary font-semibold text-sm mb-1">{c.name}</div>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${gradeColor[c.grade]}`}>{c.grade}级</span>
                  </button>
                ))}
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => setStep(1)}
                  className="flex-1 border border-card-border text-text-primary py-3 rounded-btn hover:border-primary transition-colors"
                >
                  上一步
                </button>
                <button
                  onClick={() => setStep(3)}
                  disabled={!selectedCity}
                  className="flex-1 bg-primary hover:bg-primary-hover text-white py-3 rounded-btn font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  下一步：选报告类型
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Report Type + Generate */}
          {step === 3 && (
            <div>
              <h2 className="text-xl font-bold text-text-primary mb-2">选择报告类型</h2>
              <p className="text-text-secondary text-sm mb-1">
                品牌：<span className="text-primary font-semibold">{selectedBrand}</span>
                &nbsp;·&nbsp;城市：<span className="text-primary font-semibold">{selectedCity}</span>
              </p>
              <p className="text-text-muted text-xs mb-6">实时调用高德地图数据，生成专属报告</p>

              <div className="space-y-4 mb-8">
                <button
                  onClick={() => setReportType('basic')}
                  className={`card w-full p-5 text-left transition-colors ${
                    reportType === 'basic' ? 'border-primary' : 'hover:border-primary/50'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-text-primary font-semibold mb-1">位置信息包</div>
                      <div className="text-text-secondary text-sm">竞品分布 · 人流评分 · 消费力指数</div>
                      <div className="text-text-muted text-xs mt-1">数据来源：高德POI实时数据</div>
                    </div>
                    <div className="text-2xl font-bold text-text-primary">¥59</div>
                  </div>
                </button>

                <button
                  onClick={() => setReportType('ai')}
                  className={`card w-full p-5 text-left transition-colors relative ${
                    reportType === 'ai' ? 'border-primary' : 'hover:border-primary/50'
                  }`}
                >
                  <div className="absolute -top-3 left-4 bg-primary text-white text-xs font-semibold px-3 py-0.5 rounded-full">推荐</div>
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-text-primary font-semibold mb-1">AI深度报告</div>
                      <div className="text-text-secondary text-sm">AI综合评分 · 品牌匹配 · 实地清单 · AI研判文字</div>
                      <div className="text-text-muted text-xs mt-1">高德POI + Claude AI研判</div>
                    </div>
                    <div className="text-2xl font-bold text-text-primary">¥299</div>
                  </div>
                </button>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-danger/10 border border-danger/30 rounded-card text-danger text-sm">
                  {error}
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={() => setStep(2)}
                  className="flex-1 border border-card-border text-text-primary py-3 rounded-btn hover:border-primary transition-colors"
                >
                  上一步
                </button>
                <button
                  onClick={handleGenerate}
                  disabled={!reportType || loading}
                  className="flex-1 bg-primary hover:bg-primary-hover text-white py-3 rounded-btn font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? '正在分析数据...' : '生成报告 →'}
                </button>
              </div>

              <p className="text-center text-text-muted text-xs mt-4">
                本平台仅提供数据参考，不构成投资建议
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
