import { useState, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import { PRICE_BASIC, PRICE_AI, PRICE_UPGRADE, RANGE_OPTIONS, DEFAULT_RANGE, BRAND_COLORS, BRAND_SCORES } from '../config/constants'
import api from '../config/api'

export default function DistrictDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const brand = searchParams.get('brand') || ''

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
    if (!localStorage.getItem('token')) { navigate('/login'); return }
    const price = type === 'basic' ? PRICE_BASIC : PRICE_AI
    if (!confirm(`确认支付 ¥${price}？`)) return
    setPaying(true)
    try {
      await api.post('/orders', {
        district_id: Number(id),
        product_type: type === 'basic' ? 'basic_report' : 'ai_report',
        payment_method: 'mock',
      })
      fetchDetail()
    } catch (err) {
      alert(err.response?.data?.detail || '支付失败，请重试')
    } finally {
      setPaying(false)
    }
  }

  const getBrandColor = (b) => BRAND_COLORS[b] || BRAND_COLORS.default

  if (loading) return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="flex items-center justify-center py-32">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    </div>
  )

  if (error) return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="flex flex-col items-center justify-center py-32 text-center">
        <p className="text-gray-400 mb-4">{error}</p>
        <button onClick={fetchDetail} className="px-5 py-2 bg-primary text-white rounded-lg text-sm">重新加载</button>
      </div>
    </div>
  )

  if (!data) return null

  const analysis = data.analysis || {}
  const brands = analysis.brand_distribution ? Object.keys(analysis.brand_distribution) : []
  const surrounding = analysis.surrounding_facilities || {}
  const brandScore = brand && BRAND_SCORES[brand] ? BRAND_SCORES[brand][data.name] : null

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />

      <div className="flex-1 max-w-4xl mx-auto w-full px-4 py-8">

        {/* ── 面包屑导航 ── */}
        <div className="flex items-center gap-2 text-xs text-gray-400 mb-6">
          <Link to="/" className="hover:text-primary transition-colors">首页</Link>
          <span>/</span>
          <Link
            to={brand ? `/districts?brand=${encodeURIComponent(brand)}` : '/districts'}
            className="hover:text-primary transition-colors"
          >
            {brand ? `${brand} · 选址推荐` : '商圈列表'}
          </Link>
          <span>/</span>
          <span className="text-gray-600">{data.name}</span>
        </div>

        {/* ── 标题区 ── */}
        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              {brand && (
                <div className="text-xs text-primary font-semibold mb-1 uppercase tracking-wide">{brand} 选址分析</div>
              )}
              <h1 className="text-2xl font-bold text-gray-900 mb-1">{data.name}</h1>
              <p className="text-sm text-gray-400">{data.city}</p>
            </div>
            {brandScore && (
              <div className={`shrink-0 text-center px-4 py-2 rounded-xl border ${
                brandScore.level === 'high' ? 'bg-green-50 border-green-200' :
                brandScore.level === 'medium' ? 'bg-yellow-50 border-yellow-200' :
                'bg-red-50 border-red-200'
              }`}>
                <div className={`text-3xl font-black ${
                  brandScore.level === 'high' ? 'text-green-700' :
                  brandScore.level === 'medium' ? 'text-yellow-700' : 'text-red-600'
                }`}>{brandScore.score}</div>
                <div className={`text-xs font-semibold ${
                  brandScore.level === 'high' ? 'text-green-600' :
                  brandScore.level === 'medium' ? 'text-yellow-600' : 'text-red-500'
                }`}>
                  {brandScore.level === 'high' ? '强烈推荐' : brandScore.level === 'medium' ? '可以考虑' : '谨慎评估'}
                </div>
              </div>
            )}
          </div>

          {brandScore?.reason && (
            <div className="mt-4 pt-4 border-t border-gray-100 text-sm text-gray-500 leading-relaxed">
              {brandScore.reason}
            </div>
          )}
          {brandScore?.anchors_found?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {brandScore.anchors_found.map(a => (
                <span key={a} className="text-xs bg-gray-50 border border-gray-200 text-gray-500 px-2 py-0.5 rounded-md font-medium">✓ {a}</span>
              ))}
            </div>
          )}
        </div>

        {data.locked ? (
          /* ── 未付费 ── */
          <>
            {/* 模糊预览 */}
            <div className="bg-white border border-gray-200 rounded-xl p-6 mb-5 relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-b from-transparent via-white/60 to-white z-10 flex flex-col items-center justify-end pb-8">
                <div className="w-10 h-10 bg-gray-100 border border-gray-200 rounded-xl flex items-center justify-center mb-3">
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-gray-700 mb-1">付费后解锁完整数据</p>
                <p className="text-xs text-gray-400">竞品数量 · 品牌分布 · 消费热度 · 周边配套</p>
              </div>
              <div className="blur-sm select-none pointer-events-none space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  {['奶茶店', '咖啡店', '消费热度'].map((label, i) => (
                    <div key={label} className="text-center p-3 bg-gray-50 rounded-lg">
                      <div className="text-2xl font-black text-gray-900">{[12, 8, '高'][i]}</div>
                      <div className="text-xs text-gray-400 mt-0.5">{label}</div>
                    </div>
                  ))}
                </div>
                <div className="flex flex-wrap gap-2">
                  {['蜜雪冰城', '瑞幸咖啡', '喜茶', '古茗'].map(b => (
                    <span key={b} className="px-3 py-1 bg-orange-50 text-primary text-xs rounded-full border border-orange-100">{b}</span>
                  ))}
                </div>
                <div className="grid grid-cols-4 gap-3">
                  {['写字楼 5个', '学校 3个', '小区 8个', '医院 1个'].map(t => (
                    <div key={t} className="text-center p-2 bg-gray-50 rounded-lg text-xs text-gray-400">{t}</div>
                  ))}
                </div>
              </div>
            </div>

            {/* 购买卡片 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <button
                onClick={() => handlePay('basic')}
                disabled={paying}
                className="bg-white border border-gray-200 rounded-xl p-6 text-left hover:border-primary hover:shadow-md transition-all disabled:opacity-60 group"
              >
                <div className="text-xs text-gray-400 font-medium mb-3 uppercase tracking-wide">竞品报告</div>
                <div className="text-4xl font-black text-gray-900 mb-1">¥{PRICE_BASIC}</div>
                <p className="text-xs text-gray-400 mb-5">一杯奶茶的钱，看清商圈竞品</p>
                <ul className="space-y-2 text-xs text-gray-500 mb-6">
                  {['竞品数量 · 品牌分布', '人均消费对比', '竞争饱和度指数', '周边配套数据'].map(t => (
                    <li key={t} className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-400 shrink-0" />{t}
                    </li>
                  ))}
                </ul>
                <div className="w-full text-center border border-primary text-primary py-2 rounded-lg text-sm font-semibold group-hover:bg-orange-50 transition-colors">
                  {paying ? '处理中...' : `解锁竞品报告 ¥${PRICE_BASIC}`}
                </div>
              </button>

              <button
                onClick={() => handlePay('ai')}
                disabled={paying}
                className="bg-gray-900 border border-gray-900 rounded-xl p-6 text-left hover:shadow-md transition-all disabled:opacity-60 relative overflow-hidden"
              >
                <div className="absolute top-4 right-4 bg-primary text-white text-xs px-2 py-0.5 rounded-full font-semibold">推荐</div>
                <div className="text-xs text-gray-500 font-medium mb-3 uppercase tracking-wide">AI 研判报告</div>
                <div className="text-4xl font-black text-white mb-1">¥{PRICE_AI}</div>
                <p className="text-xs text-gray-500 mb-5">一个决策，换十万本金的安全感</p>
                <ul className="space-y-2 text-xs text-gray-400 mb-6">
                  {['包含所有竞品报告内容', 'AI 综合评分（满分10分）', '品牌专属开店建议', '预计回本周期', '最优位置具体推荐'].map(t => (
                    <li key={t} className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />{t}
                    </li>
                  ))}
                </ul>
                <div className="w-full text-center bg-primary text-white py-2 rounded-lg text-sm font-semibold hover:bg-orange-600 transition-colors">
                  {paying ? '处理中...' : `解锁 AI 研判 ¥${PRICE_AI}`}
                </div>
              </button>
            </div>
          </>
        ) : (
          /* ── 已付费内容 ── */
          <>
            {/* 范围切换 */}
            <div className="flex items-center gap-2 mb-5">
              <span className="text-xs text-gray-400">分析范围：</span>
              {RANGE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setRange(opt.value)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium border transition-all ${
                    range === opt.value
                      ? 'bg-primary text-white border-primary'
                      : 'bg-white border-gray-200 text-gray-500 hover:border-primary'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* 数据概览 */}
            <div className="grid grid-cols-3 gap-4 mb-5">
              {[
                { value: analysis.tea_shop_count ?? '-', label: '奶茶店' },
                { value: analysis.coffee_shop_count ?? '-', label: '咖啡店' },
                { value: analysis.consumption_heat === 'high' ? '高' : analysis.consumption_heat === 'medium' ? '中' : '低', label: '消费热度' },
              ].map((item) => (
                <div key={item.label} className="bg-white border border-gray-200 rounded-xl p-5 text-center">
                  <div className="text-3xl font-black text-gray-900">{item.value}</div>
                  <div className="text-xs text-gray-400 mt-1">{item.label}</div>
                </div>
              ))}
            </div>

            {/* 品牌分布 */}
            {brands.length > 0 && (
              <div className="bg-white border border-gray-200 rounded-xl p-5 mb-5">
                <h3 className="text-sm font-bold text-gray-900 mb-3">已进驻品牌</h3>
                <div className="flex flex-wrap gap-2">
                  {brands.map((b) => {
                    const color = getBrandColor(b)
                    return (
                      <span key={b} className="px-3 py-1 rounded-full text-xs font-medium"
                        style={{ backgroundColor: color.bg, color: color.text }}>
                        {b} <span className="opacity-50">×{analysis.brand_distribution[b]}</span>
                      </span>
                    )
                  })}
                </div>
              </div>
            )}

            {/* 地图占位 */}
            <div className="bg-white border border-gray-200 rounded-xl p-5 mb-5">
              <h3 className="text-sm font-bold text-gray-900 mb-3">品牌分布地图</h3>
              <div className="bg-gray-50 rounded-lg h-56 flex items-center justify-center text-gray-400 text-sm border border-dashed border-gray-200">
                地图即将接入
              </div>
            </div>

            {/* 周边配套 */}
            {Object.keys(surrounding).length > 0 && (
              <div className="bg-white border border-gray-200 rounded-xl p-5 mb-5">
                <h3 className="text-sm font-bold text-gray-900 mb-3">周边配套</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(surrounding).map(([key, val]) => {
                    const icons = { office: '🏢', school: '🏫', residential: '🏘️', hospital: '🏥' }
                    const labels = { office: '写字楼', school: '学校', residential: '小区', hospital: '医院' }
                    return (
                      <div key={key} className="text-center p-3 bg-gray-50 border border-gray-200 rounded-lg">
                        <div className="text-lg mb-1">{icons[key] || '📍'}</div>
                        <div className="text-xs text-gray-400">{labels[key] || key}</div>
                        <div className="text-base font-bold text-gray-900 mt-0.5">{val}个</div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* 升级AI研判 */}
            {!data.has_ai_report && (
              <div className="bg-gray-900 rounded-xl p-6 flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-bold text-white mb-1">升级 AI 研判</h3>
                  <p className="text-xs text-gray-400">让AI告诉你这里能不能开店，补差价 ¥{PRICE_UPGRADE}</p>
                </div>
                <button
                  onClick={() => handlePay('ai')}
                  disabled={paying}
                  className="shrink-0 bg-primary text-white px-5 py-2 rounded-lg text-sm font-semibold hover:bg-orange-600 disabled:opacity-60 transition-colors"
                >
                  升级 →
                </button>
              </div>
            )}

            {data.has_ai_report && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-400" />
                  <span className="text-sm text-green-700 font-medium">已购买 AI 研判报告</span>
                </div>
                <Link to="/reports" className="text-sm text-green-700 underline font-medium">查看报告 →</Link>
              </div>
            )}
          </>
        )}
      </div>

      <Footer />
    </div>
  )
}
