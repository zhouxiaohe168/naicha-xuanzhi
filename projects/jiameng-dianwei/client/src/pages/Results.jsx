import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import api from '../config/api'

function densityConfig(count) {
  if (count >= 10) return { label: '非常多', color: 'text-green-700', bg: 'bg-green-50', border: 'border-green-200' }
  if (count >= 5)  return { label: '较多',   color: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200' }
  if (count >= 2)  return { label: '有一些', color: 'text-yellow-600', bg: 'bg-yellow-50', border: 'border-yellow-200' }
  if (count === 1) return { label: '极少',   color: 'text-blue-500',  bg: 'bg-blue-50',  border: 'border-blue-200' }
  return                  { label: '暂无',   color: 'text-gray-400',  bg: 'bg-gray-50',  border: 'border-gray-200' }
}

// 综合评级
function verdict(score, targetCount) {
  if (score >= 8)  return { emoji: '🟢', text: '值得考虑', sub: '客流旺、竞争小，空白机会好', color: 'bg-green-50 border-green-300 text-green-800' }
  if (score >= 5)  return { emoji: '🟡', text: '谨慎评估', sub: '有一定客流，但需考察竞争情况', color: 'bg-yellow-50 border-yellow-300 text-yellow-800' }
  if (targetCount > 8) return { emoji: '🔴', text: '竞争激烈', sub: '该区域已有较多同品牌，进入风险高', color: 'bg-red-50 border-red-300 text-red-800' }
  return { emoji: '⚪', text: '客流不足', sub: '参照品牌也偏少，该区域商业氛围较弱', color: 'bg-gray-50 border-gray-300 text-gray-700' }
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
  const brand    = searchParams.get('brand') || ''
  const anchors  = searchParams.get('anchors')?.split(',').filter(Boolean) || []
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

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />

      <div className="flex-1 max-w-2xl mx-auto w-full px-4 py-8">

        {/* 页头 */}
        <div className="mb-6">
          <Link to="/" className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-primary mb-3 transition-colors">
            ← 重新查询
          </Link>
          <h1 className="text-xl font-bold text-gray-900">
            {brand} · {street}
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">{city} {district !== city ? district : ''} {street !== district ? street : ''}</p>
        </div>

        {/* 加载 */}
        {loading && (
          <div className="space-y-4">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <p className="text-center text-xs text-gray-400 animate-pulse mt-2">
              正在查询高德地图数据，约需 5–15 秒…
            </p>
          </div>
        )}

        {/* 错误 */}
        {error && !loading && (
          <div className="flex flex-col items-center py-20 text-center">
            <p className="text-gray-600 mb-1 font-medium">查询失败</p>
            <p className="text-gray-400 text-sm mb-4">{error}</p>
            <button onClick={load} className="px-5 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-orange-600">重试</button>
          </div>
        )}

        {/* 结果 */}
        {data && !loading && (() => {
          const v = verdict(data.summary?.gap_score, data.summary?.target_count)
          return (
            <>
              {/* ── 总评 ── */}
              <div className={`rounded-xl border-2 p-5 mb-5 ${v.color}`}>
                <div className="flex items-center gap-3">
                  <span className="text-3xl">{v.emoji}</span>
                  <div>
                    <p className="text-lg font-bold">{v.text}</p>
                    <p className="text-sm mt-0.5 opacity-80">{v.sub}</p>
                  </div>
                  <div className="ml-auto text-right shrink-0">
                    <p className="text-2xl font-black">{data.summary?.gap_score}</p>
                    <p className="text-xs opacity-60">机会评分/10</p>
                  </div>
                </div>
              </div>

              {/* ── 两个核心数字 ── */}
              <div className="grid grid-cols-2 gap-3 mb-5">
                <div className="bg-white border border-gray-200 rounded-xl p-4">
                  <p className="text-xs text-gray-400 mb-1">参照品牌客流验证</p>
                  <p className="text-2xl font-black text-gray-900">
                    {data.summary?.total_anchors}
                    <span className="text-sm font-normal text-gray-400 ml-1">家合计</span>
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {anchors.join('、')} 在此街道的总门店数，越多说明人流越旺
                  </p>
                </div>
                <div className={`border rounded-xl p-4 ${data.summary?.target_count === 0 ? 'bg-green-50 border-green-300' : 'bg-white border-gray-200'}`}>
                  <p className="text-xs text-gray-400 mb-1">已有 {brand}</p>
                  <p className={`text-2xl font-black ${data.summary?.target_count === 0 ? 'text-green-700' : 'text-gray-900'}`}>
                    {data.summary?.target_count}
                    <span className="text-sm font-normal text-gray-400 ml-1">家</span>
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {data.summary?.target_count === 0
                      ? '暂无竞争，是空白市场'
                      : data.summary?.target_count <= 3
                        ? '竞争适中，仍有机会'
                        : '同品牌较多，进入需谨慎'}
                  </p>
                </div>
              </div>

              {/* ── 参照品牌明细 ── */}
              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-5">
                <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-bold text-gray-900">参照品牌详情</h2>
                    <p className="text-xs text-gray-400 mt-0.5">用知名品牌门店数量来判断该街道人流是否够旺</p>
                  </div>
                  <span className="text-xs text-gray-300">高德地图</span>
                </div>
                <div className="divide-y divide-gray-50">
                  {data.anchor_results?.map(item => {
                    const cfg = densityConfig(item.count)
                    return (
                      <div key={item.brand} className="px-5 py-3.5 flex items-center justify-between">
                        <span className="text-sm text-gray-700 font-medium">{item.brand}</span>
                        <div className={`flex items-center gap-1.5 px-3 py-1 rounded-lg border text-xs font-semibold ${cfg.bg} ${cfg.border} ${cfg.color}`}>
                          <span className="text-base font-black">{item.count}</span>
                          <span className="font-normal opacity-70">家</span>
                          <span className="ml-1">· {cfg.label}</span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* ── 付费解锁 ── */}
              <div className="relative rounded-xl overflow-hidden border border-gray-200">
                <div className="bg-white p-5 select-none pointer-events-none">
                  <h2 className="text-sm font-bold text-gray-900 mb-3">AI 综合研判</h2>
                  {['综合适配评分：8.5 / 10', '建议开店位置：稠江街道 XX 路附近，靠近…', '预计日均出杯：350–420 杯', '预计月净利润：¥18,000–¥24,000', '回本周期预测：约 14–18 个月'].map(t => (
                    <div key={t} className="py-2.5 border-b border-gray-50 last:border-0 text-sm text-gray-700 blur-sm">{t}</div>
                  ))}
                </div>
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
          )
        })()}
      </div>

      <Footer />
    </div>
  )
}
