import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import { PRICE_BASIC, PRICE_AI, PRICE_UPGRADE, RANGE_OPTIONS, DEFAULT_RANGE, BRAND_COLORS } from '../config/constants'
import api from '../config/api'

const TRAFFIC_LABEL = { high: '高', medium: '中', low: '低' }
const TRAFFIC_COLOR = { high: 'text-green-600 bg-green-50', medium: 'text-yellow-600 bg-yellow-50', low: 'text-gray-500 bg-gray-50' }

export default function DistrictDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [range, setRange] = useState(DEFAULT_RANGE)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [paying, setPaying] = useState(false)
  const [error, setError] = useState('')

  const fetchDetail = () => {
    setLoading(true)
    api.get(`/districts/${id}`)
      .then(setData)
      .catch(() => setError('加载失败，请刷新重试'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchDetail() }, [id])

  const handlePay = async (type) => {
    if (!localStorage.getItem('token')) {
      navigate('/login')
      return
    }
    const price = type === 'basic' ? PRICE_BASIC : PRICE_AI
    if (!confirm(`确认支付 ¥${price}？`)) return
    setPaying(true)
    try {
      await api.post('/orders', {
        district_id: Number(id),
        product_type: type === 'basic' ? 'basic_report' : 'ai_report',
        payment_method: 'mock',  // MVP mock支付，M5接入真实支付
      })
      fetchDetail()  // 重新拉取，locked 变 false
    } catch (err) {
      alert(err.response?.data?.detail || '支付失败，请重试')
    } finally {
      setPaying(false)
    }
  }

  const getBrandColor = (brand) => BRAND_COLORS[brand] || BRAND_COLORS.default

  if (loading) return <div className="text-center py-24 text-text-sub">加载中...</div>
  if (error) return <div className="text-center py-24 text-red-500">{error}</div>
  if (!data) return null

  const analysis = data.analysis || {}
  const brands = analysis.brand_distribution ? Object.keys(analysis.brand_distribution) : []
  const surrounding = analysis.surrounding_facilities || {}

  return (
    <div>
      <Navbar />
      <div className="max-w-4xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-1">📍 {data.name}</h1>
        <p className="text-text-sub mb-2">{data.city}</p>
        <span className={`inline-block text-sm px-3 py-1 rounded-full mb-6 ${TRAFFIC_COLOR[data.foot_traffic_level] || 'text-gray-500 bg-gray-50'}`}>
          人流量：{TRAFFIC_LABEL[data.foot_traffic_level] || '未知'}
        </span>

        {data.locked ? (
          /* === 未付费 === */
          <>
            <div className="bg-white rounded-card shadow-card p-6 mb-6">
              <div className="text-center py-8">
                <div className="text-4xl mb-4">🔒</div>
                <h3 className="text-lg font-semibold mb-2">以下内容需付费解锁</h3>
                <div className="space-y-2 text-text-sub blur-sm select-none mb-6">
                  <p>🧋 奶茶店：12 家 | ☕ 咖啡店：8 家</p>
                  <p>已进驻品牌：蜜雪冰城、瑞幸咖啡、喜茶...</p>
                  <p>周边配套：写字楼5个、学校3个...</p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <button
                onClick={() => handlePay('basic')}
                disabled={paying}
                className="bg-white rounded-card shadow-card p-6 text-center hover:shadow-md transition-shadow disabled:opacity-60"
              >
                <div className="text-3xl font-bold text-primary font-price mb-2">¥{PRICE_BASIC}</div>
                <div className="font-semibold mb-2">基础报告</div>
                <div className="text-sm text-text-sub">竞品数量 · 品牌分布 · 周边配套</div>
              </button>
              <button
                onClick={() => handlePay('ai')}
                disabled={paying}
                className="bg-gradient-to-r from-primary to-secondary rounded-card shadow-card p-6 text-center text-white hover:opacity-95 transition-opacity disabled:opacity-60"
              >
                <div className="text-3xl font-bold font-price mb-2">¥{PRICE_AI}</div>
                <div className="font-semibold mb-2">AI研判报告</div>
                <div className="text-sm text-white/80">评分 · 品牌推荐 · 风险预警 · 选址建议</div>
              </button>
            </div>
          </>
        ) : (
          /* === 已付费 === */
          <>
            <div className="flex items-center gap-2 mb-6">
              <span className="text-sm text-text-sub">分析范围：</span>
              {RANGE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setRange(opt.value)}
                  className={`px-3 py-1 rounded-full text-sm ${
                    range === opt.value
                      ? 'bg-primary text-white'
                      : 'bg-white border border-gray-200 text-text-sub hover:border-primary'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-white rounded-card shadow-card p-4 text-center">
                <div className="text-3xl font-bold text-primary font-price">{analysis.tea_shop_count ?? '-'}</div>
                <div className="text-sm text-text-sub mt-1">奶茶店</div>
              </div>
              <div className="bg-white rounded-card shadow-card p-4 text-center">
                <div className="text-3xl font-bold text-primary font-price">{analysis.coffee_shop_count ?? '-'}</div>
                <div className="text-sm text-text-sub mt-1">咖啡店</div>
              </div>
              <div className="bg-white rounded-card shadow-card p-4 text-center">
                <div className="text-3xl font-bold text-primary font-price">
                  {analysis.consumption_heat === 'high' ? '高' : analysis.consumption_heat === 'medium' ? '中' : '低'}
                </div>
                <div className="text-sm text-text-sub mt-1">消费热度</div>
              </div>
            </div>

            {brands.length > 0 && (
              <div className="bg-white rounded-card shadow-card p-4 mb-6">
                <h3 className="font-semibold mb-3">已进驻品牌</h3>
                <div className="flex flex-wrap gap-2">
                  {brands.map((brand) => {
                    const color = getBrandColor(brand)
                    return (
                      <span key={brand} className="px-3 py-1 rounded-full text-sm"
                        style={{ backgroundColor: color.bg, color: color.text }}>
                        {brand}
                        <span className="ml-1 opacity-60">×{analysis.brand_distribution[brand]}</span>
                      </span>
                    )
                  })}
                </div>
              </div>
            )}

            <div className="bg-white rounded-card shadow-card p-4 mb-6">
              <h3 className="font-semibold mb-3">品牌分布地图</h3>
              <div className="bg-gray-100 rounded-lg h-64 flex items-center justify-center text-text-sub">
                🗺️ 高德地图（M3后续接入）
              </div>
            </div>

            {Object.keys(surrounding).length > 0 && (
              <div className="bg-white rounded-card shadow-card p-4 mb-6">
                <h3 className="font-semibold mb-3">周边配套</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(surrounding).map(([key, val]) => {
                    const icons = { office: '🏢', school: '🏫', residential: '🏘️', hospital: '🏥' }
                    const labels = { office: '写字楼', school: '学校', residential: '小区', hospital: '医院' }
                    return (
                      <div key={key} className="text-center p-3 bg-bg-warm rounded-lg">
                        <div className="text-lg">{icons[key] || '📍'}</div>
                        <div className="text-sm text-text-sub">{labels[key] || key}</div>
                        <div className="font-bold text-primary">{val}个</div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {!data.has_ai_report && (
              <div className="bg-gradient-to-r from-primary to-secondary rounded-card p-6 text-center text-white">
                <h3 className="text-lg font-bold mb-2">🤖 升级AI研判</h3>
                <p className="text-white/80 mb-4">让AI告诉你这里能不能开店，补差价 ¥{PRICE_UPGRADE}</p>
                <button
                  onClick={() => handlePay('ai')}
                  disabled={paying}
                  className="bg-white text-primary px-6 py-2 rounded-btn font-medium hover:bg-gray-50 disabled:opacity-60"
                >
                  升级AI研判 →
                </button>
              </div>
            )}

            {data.has_ai_report && (
              <div className="bg-green-50 border border-green-200 rounded-card p-4 text-center text-green-700">
                ✅ 已购买AI研判报告 · <a href={`/reports`} className="underline">前往查看</a>
              </div>
            )}
          </>
        )}
      </div>
      <Footer />
    </div>
  )
}
