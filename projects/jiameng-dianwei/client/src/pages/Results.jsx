import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import api from '../config/api'

// ── 品牌色调 helper ──────────────────────────────────────
function densityConfig(count) {
  if (count >= 5) return { label: '高密度', color: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200' }
  if (count >= 2) return { label: '中密度', color: 'text-yellow-600', bg: 'bg-yellow-50', border: 'border-yellow-200' }
  if (count === 1) return { label: '低密度', color: 'text-blue-500', bg: 'bg-blue-50', border: 'border-blue-200' }
  return { label: '未发现', color: 'text-gray-400', bg: 'bg-gray-50', border: 'border-gray-200' }
}

function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
      <div className="h-4 bg-gray-100 rounded w-1/3 mb-3" />
      <div className="h-8 bg-gray-100 rounded w-1/4 mb-2" />
      <div className="h-3 bg-gray-100 rounded w-2/3" />
    </div>
  )
}

export default function Results() {
  const [searchParams] = useSearchParams()
  const brand   = searchParams.get('brand') || ''
  const anchors = searchParams.get('anchors')?.split(',').filter(Boolean) || []
  const city     = searchParams.get('city') || ''
  const district = searchParams.get('district') || ''
  const street   = searchParams.get('street') || ''
  const radius   = Number(searchParams.get('radius') || 1000)

  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  const load = () => {
    setLoading(true)
    setError('')
    setData(null)
    api.post('/analyze', { brand, anchors, city, district, street, radius })
      .then(d => setData(d))
      .catch(e => setError(e?.message || '查询失败，请稍后重试'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [brand, anchors.join(','), city, district, street, radius])

  const location = [city !== district ? city : '', district !== street ? district : '', street].filter(Boolean).join(' · ')

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />

      <div className="flex-1 max-w-4xl mx-auto w-full px-4 py-8">

        {/* 页头 */}
        <div className="mb-8">
          <Link to="/" className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-primary mb-3 transition-colors">
            ← 重新查询
          </Link>
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 mb-1">
                {brand} · {street} 竞品分析
              </h1>
              <p className="text-sm text-gray-400">{location} · 查询半径 {radius >= 1000 ? radius / 1000 + 'km' : radius + 'm'}</p>
            </div>
            {anchors.length > 0 && (
              <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-lg px-3 py-1.5">
                <span className="text-xs text-gray-400 shrink-0">锚点</span>
                <div className="flex gap-1 flex-wrap">
                  {anchors.map(a => (
                    <span key={a} className="text-xs bg-orange-50 text-primary px-2 py-0.5 rounded border border-orange-100 font-medium">{a}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 加载骨架 */}
        {loading && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse">
              <div className="h-4 bg-gray-100 rounded w-1/4 mb-4" />
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex justify-between items-center py-3 border-b border-gray-50 last:border-0">
                  <div className="h-3 bg-gray-100 rounded w-1/4" />
                  <div className="h-6 bg-gray-100 rounded w-12" />
                </div>
              ))}
            </div>
            <p className="text-center text-xs text-gray-400 mt-4 animate-pulse">
              正在查询高德地图数据，约需 5–15 秒…
            </p>
          </>
        )}

        {/* 错误 */}
        {error && !loading && (
          <div className="flex flex-col items-center py-20 text-center">
            <div className="w-12 h-12 bg-red-50 rounded-full flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <p className="text-gray-600 mb-1 font-medium">查询失败</p>
            <p className="text-gray-400 text-sm mb-4">{error}</p>
            <button onClick={load} className="px-5 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-orange-600">
              重试
            </button>
          </div>
        )}

        {/* 结果 */}
        {data && !loading && (
          <>
            {/* ── 摘要卡片 ── */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              <SummaryCard label="锚点总门店" value={data.summary?.total_anchors ?? '—'} unit="家" />
              <SummaryCard label={`${brand} 门店`} value={data.summary?.target_count ?? '—'} unit="家" highlight={data.summary?.target_count === 0} />
              <SummaryCard label="空白机会" value={data.summary?.gap_score ?? '—'} unit="分" />
              <SummaryCard label="查询品牌数" value={data.anchor_results?.length ?? '—'} unit="个" />
            </div>

            {/* ── 机会提示 ── */}
            {data.summary?.target_count === 0 && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-6 flex items-start gap-3">
                <div className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center shrink-0 mt-0.5">
                  <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-semibold text-green-800 mb-0.5">发现空白机会！</p>
                  <p className="text-xs text-green-600">
                    {street} 周边 {radius >= 1000 ? radius / 1000 + 'km' : radius + 'm'} 内暂无 {brand} 门店，
                    但锚点品牌已有 {data.summary?.total_anchors} 家，客流已被验证
                  </p>
                </div>
              </div>
            )}

            {/* ── 锚点明细 ── */}
            <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-6">
              <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                <h2 className="text-sm font-bold text-gray-900">锚点品牌分布</h2>
                <span className="text-xs text-gray-400">数据来源：高德地图</span>
              </div>
              <div className="divide-y divide-gray-50">
                {data.anchor_results?.map(item => {
                  const cfg = densityConfig(item.count)
                  return (
                    <div key={item.brand} className="px-5 py-3.5 flex items-center justify-between">
                      <span className="text-sm text-gray-700 font-medium">{item.brand}</span>
                      <div className="flex items-center gap-3">
                        {item.count > 0 && (
                          <div className="hidden sm:flex gap-1">
                            {[...Array(Math.min(item.count, 8))].map((_, i) => (
                              <span key={i} className={`w-2 h-4 rounded-sm ${cfg.bg} border ${cfg.border}`} />
                            ))}
                            {item.count > 8 && <span className="text-xs text-gray-400 self-center">+{item.count - 8}</span>}
                          </div>
                        )}
                        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-semibold ${cfg.bg} ${cfg.border} ${cfg.color}`}>
                          <span>{item.count}</span>
                          <span className="font-normal opacity-70">家</span>
                          <span className="ml-0.5">· {cfg.label}</span>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* ── 目标品牌 ── */}
            {data.target_result && (
              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-6">
                <div className="px-5 py-4 border-b border-gray-100">
                  <h2 className="text-sm font-bold text-gray-900">{brand} 现状</h2>
                </div>
                <div className="px-5 py-4 flex items-center justify-between">
                  <div>
                    <p className="text-3xl font-black text-gray-900">{data.target_result.count} <span className="text-base font-normal text-gray-400">家</span></p>
                    <p className="text-xs text-gray-400 mt-1">
                      {data.target_result.count === 0
                        ? `${street} 周边暂无 ${brand}，存在市场空白`
                        : `已有 ${data.target_result.count} 家 ${brand}，竞争需注意`}
                    </p>
                  </div>
                  <div className={`px-4 py-2 rounded-lg text-sm font-semibold border ${
                    data.target_result.count === 0
                      ? 'bg-green-50 text-green-700 border-green-200'
                      : data.target_result.count <= 2
                        ? 'bg-yellow-50 text-yellow-700 border-yellow-200'
                        : 'bg-red-50 text-red-600 border-red-200'
                  }`}>
                    {data.target_result.count === 0 ? '空白市场' : data.target_result.count <= 2 ? '竞争适中' : '竞争激烈'}
                  </div>
                </div>
              </div>
            )}

            {/* ── 付费解锁 ── */}
            <div className="relative rounded-xl overflow-hidden border border-gray-200">
              {/* 模糊预览 */}
              <div className="bg-white p-5 select-none pointer-events-none">
                <h2 className="text-sm font-bold text-gray-900 mb-3">AI 综合研判</h2>
                {['综合适配评分：8.5 / 10', '建议开店位置：稠江街道 XX 路附近，靠近…', '预计日均出杯：350–420 杯', '预计月净利润：¥18,000–¥24,000', '回本周期预测：约 14–18 个月'].map(t => (
                  <div key={t} className="py-2.5 border-b border-gray-50 last:border-0 text-sm text-gray-700 blur-sm">{t}</div>
                ))}
              </div>
              {/* 锁遮罩 */}
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 backdrop-blur-sm">
                <div className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center mb-3">
                  <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-gray-900 mb-1">解锁 AI 研判报告</p>
                <p className="text-xs text-gray-400 mb-4">30 秒明确选址建议 + 回本周期预测</p>
                <div className="flex gap-3">
                  <button className="px-5 py-2 border border-primary text-primary rounded-lg text-sm font-semibold hover:bg-orange-50 transition-colors">
                    竞品报告 ¥9.9
                  </button>
                  <button className="px-5 py-2 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-orange-600 transition-colors">
                    AI 研判 ¥59.9
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      <Footer />
    </div>
  )
}

function SummaryCard({ label, value, unit, highlight }) {
  return (
    <div className={`bg-white border rounded-xl p-4 ${highlight ? 'border-green-300 bg-green-50' : 'border-gray-200'}`}>
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className={`text-2xl font-black ${highlight ? 'text-green-700' : 'text-gray-900'}`}>
        {value}
        <span className="text-sm font-normal text-gray-400 ml-0.5">{unit}</span>
      </p>
    </div>
  )
}
