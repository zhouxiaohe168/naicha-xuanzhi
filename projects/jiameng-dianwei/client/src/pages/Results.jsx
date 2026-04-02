import { useState, useEffect } from 'react'
import { useSearchParams, Link, useNavigate } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import api from '../config/api'

// 高德地图导航链接
function amapUrl(address, city) {
  return `https://www.amap.com/search?query=${encodeURIComponent(address)}&city=${encodeURIComponent(city)}`
}

function Skeleton() {
  return (
    <div className="space-y-4">
      {[1,2,3].map(i => (
        <div key={i} className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
          <div className="h-4 bg-gray-100 rounded w-1/3 mb-3" />
          <div className="h-7 bg-gray-100 rounded w-1/4 mb-2" />
          <div className="h-3 bg-gray-100 rounded w-2/3" />
        </div>
      ))}
      <p className="text-center text-xs text-gray-400 animate-pulse pt-2">
        正在查询高德地图数据，约需 10–20 秒…
      </p>
    </div>
  )
}

// 付费解锁弹窗（MVP mock）
function PayModal({ onConfirm, onCancel, brand }) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="bg-white rounded-2xl w-full max-w-sm p-6 shadow-xl">
        <div className="text-center mb-5">
          <div className="text-4xl mb-2">📍</div>
          <h2 className="text-lg font-bold text-gray-900">查看机会点位置</h2>
          <p className="text-sm text-gray-400 mt-1">
            获取每个机会点的具体地址 + 最近 {brand} 的距离
          </p>
        </div>
        <div className="bg-orange-50 border border-orange-100 rounded-xl p-4 mb-5">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-700">竞品机会报告</span>
            <span className="text-xl font-black text-primary">¥9.9</span>
          </div>
          <ul className="mt-2 space-y-1">
            {['机会点具体地址', '最近竞品距离', '一键导航去实地考察'].map(t => (
              <li key={t} className="text-xs text-gray-500 flex items-center gap-1.5">
                <span className="text-green-500">✓</span>{t}
              </li>
            ))}
          </ul>
        </div>
        <button
          onClick={onConfirm}
          className="w-full bg-primary text-white py-3.5 rounded-xl font-semibold text-base mb-2 hover:bg-orange-600 transition-colors"
        >
          确认支付 ¥9.9
        </button>
        <button onClick={onCancel} className="w-full text-gray-400 text-sm py-2">
          取消
        </button>
        <p className="text-center text-xs text-gray-300 mt-2">当前为体验版，支付后立即解锁</p>
      </div>
    </div>
  )
}

export default function Results() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const brand    = searchParams.get('brand') || ''
  const anchors  = searchParams.get('anchors')?.split(',').filter(Boolean) || []
  const city     = searchParams.get('city') || ''
  const district = searchParams.get('district') || ''
  const street   = searchParams.get('street') || ''
  const radius   = Number(searchParams.get('radius') || 1000)

  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')
  const [unlocked, setUnlocked] = useState(false)
  const [showModal, setShowModal] = useState(false)

  const load = () => {
    setLoading(true); setError(''); setData(null)
    api.post('/analyze', { brand, anchors, city, district, street, radius })
      .then(d => setData(d))
      .catch(e => setError(e?.message || '查询失败，请稍后重试'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [brand, anchors.join(','), city, district, street, radius])

  const handleUnlock = () => {
    if (!localStorage.getItem('token')) {
      navigate(`/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`)
      return
    }
    setShowModal(true)
  }

  const confirmPay = () => {
    setShowModal(false)
    setUnlocked(true)
  }

  if (loading) return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-xl mx-auto px-4 py-8"><Skeleton /></div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />

      {showModal && (
        <PayModal
          brand={brand}
          onConfirm={confirmPay}
          onCancel={() => setShowModal(false)}
        />
      )}

      <div className="flex-1 max-w-xl mx-auto w-full px-4 py-6">

        {/* 页头 */}
        <Link to="/" className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-primary mb-4 transition-colors">
          ← 重新查询
        </Link>
        <h1 className="text-xl font-bold text-gray-900 mb-0.5">{brand} · {street}</h1>
        <p className="text-sm text-gray-400 mb-6">{city}{district !== city ? ` · ${district}` : ''}</p>

        {/* 错误 */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4">
            <p className="text-red-600 text-sm">{error}</p>
            <button onClick={load} className="mt-2 text-xs text-primary underline">重试</button>
          </div>
        )}

        {data && (() => {
          const oppCount = data.opportunity_count || 0
          const spots    = data.opportunity_spots || []
          const hasSpots = oppCount > 0

          return (
            <>
              {/* ── 核心结论 ── */}
              <div className={`rounded-xl border-2 p-5 mb-4 ${
                hasSpots
                  ? 'bg-green-50 border-green-300'
                  : 'bg-gray-50 border-gray-200'
              }`}>
                <div className="flex items-center gap-4">
                  <span className="text-4xl">{hasSpots ? '🟢' : '🔴'}</span>
                  <div className="flex-1">
                    {hasSpots ? (
                      <>
                        <p className="font-bold text-green-800 text-lg">
                          发现 <span className="text-2xl">{oppCount}</span> 个机会点
                        </p>
                        <p className="text-sm text-green-700 mt-0.5">
                          有参照品牌、但 {radius/1000}km 内无 {brand}，值得实地考察
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="font-bold text-gray-700 text-lg">未发现明显机会</p>
                        <p className="text-sm text-gray-500 mt-0.5">
                          参照品牌附近均已有 {brand}，竞争较为饱和
                        </p>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* ── 数据概览 ── */}
              <div className="bg-white border border-gray-200 rounded-xl divide-y divide-gray-50 mb-4">
                <div className="px-5 py-3 flex items-center justify-between">
                  <span className="text-sm text-gray-500">已有 {brand}</span>
                  <span className="font-bold text-gray-900">
                    {data.target_total} <span className="text-xs font-normal text-gray-400">家（{street}周边2km）</span>
                  </span>
                </div>
                {data.anchor_results?.map(item => (
                  <div key={item.brand} className="px-5 py-3 flex items-center justify-between">
                    <span className="text-sm text-gray-500">{item.brand}</span>
                    <span className="font-bold text-gray-900">
                      {item.count} <span className="text-xs font-normal text-gray-400">家</span>
                    </span>
                  </div>
                ))}
              </div>

              {/* ── 机会点区域 ── */}
              {hasSpots && (
                <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-4">
                  <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                    <div>
                      <h2 className="text-sm font-bold text-gray-900">📍 机会点位置</h2>
                      <p className="text-xs text-gray-400 mt-0.5">有参照品牌客流验证、无 {brand} 竞争的地点</p>
                    </div>
                    {!unlocked && (
                      <span className="text-xs bg-orange-50 text-primary border border-orange-100 px-2 py-1 rounded-lg font-semibold">
                        {oppCount} 个
                      </span>
                    )}
                  </div>

                  {!unlocked ? (
                    /* 锁定状态 */
                    <div className="p-5">
                      {/* 预览（模糊） */}
                      <div className="space-y-3 mb-5 select-none pointer-events-none">
                        {[...Array(Math.min(oppCount, 3))].map((_, i) => (
                          <div key={i} className="flex items-start gap-3 blur-sm">
                            <div className="w-8 h-8 bg-orange-100 rounded-lg flex-shrink-0" />
                            <div className="flex-1">
                              <div className="h-4 bg-gray-100 rounded w-3/4 mb-1.5" />
                              <div className="h-3 bg-gray-100 rounded w-1/2" />
                            </div>
                            <div className="h-7 w-16 bg-orange-50 rounded-lg" />
                          </div>
                        ))}
                        {oppCount > 3 && (
                          <p className="text-center text-xs text-gray-300 blur-sm">还有 {oppCount - 3} 个机会点…</p>
                        )}
                      </div>
                      {/* 解锁按钮 */}
                      <button
                        onClick={handleUnlock}
                        className="w-full bg-primary text-white py-3.5 rounded-xl font-semibold text-base hover:bg-orange-600 transition-colors shadow-sm shadow-orange-200"
                      >
                        查看 {oppCount} 个机会点位置  ¥9.9
                      </button>
                      <p className="text-center text-xs text-gray-400 mt-2">获取地址 + 最近竞品距离 + 一键导航</p>
                    </div>
                  ) : (
                    /* 解锁后显示 */
                    <div className="divide-y divide-gray-50">
                      {spots.map((spot, i) => (
                        <div key={i} className="px-5 py-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs bg-orange-50 text-primary border border-orange-100 px-2 py-0.5 rounded font-medium">
                                  {spot.anchor_brand}
                                </span>
                                <span className="text-sm font-semibold text-gray-900 truncate">{spot.anchor_name}</span>
                              </div>
                              <p className="text-xs text-gray-400 truncate">{spot.anchor_address || '地址详见高德地图'}</p>
                              <p className="text-xs text-green-600 font-medium mt-1">
                                最近 {brand}：{spot.nearest_target} 外
                              </p>
                            </div>
                            <a
                              href={amapUrl(spot.anchor_address || spot.anchor_name, city)}
                              target="_blank"
                              rel="noreferrer"
                              className="flex-shrink-0 bg-primary text-white text-xs px-3 py-2 rounded-lg hover:bg-orange-600 transition-colors font-medium"
                            >
                              导航
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* ── AI 研判（锁定）── */}
              <div className="relative rounded-xl overflow-hidden border border-gray-200">
                <div className="bg-white p-5 select-none pointer-events-none">
                  <h2 className="text-sm font-bold text-gray-900 mb-3">AI 深度研判</h2>
                  {[
                    `综合适配评分：8.5 / 10`,
                    `最优机会点推荐：${street} XX 路，建议优先考察`,
                    `预计日均出杯：350–420 杯`,
                    `预计月净利润：¥18,000–¥24,000`,
                    `回本周期：约 14–18 个月`,
                  ].map(t => (
                    <div key={t} className="py-2.5 border-b border-gray-50 last:border-0 text-sm text-gray-700 blur-sm">{t}</div>
                  ))}
                </div>
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 backdrop-blur-sm">
                  <div className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center mb-3">
                    <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                  </div>
                  <p className="text-sm font-semibold text-gray-900 mb-1">AI 深度研判报告</p>
                  <p className="text-xs text-gray-400 mb-4 text-center px-4">分析为什么没有竞品 + 选址建议 + 回本预测</p>
                  <button className="px-6 py-2.5 bg-gradient-to-r from-primary to-orange-400 text-white rounded-xl text-sm font-semibold hover:opacity-90 transition-opacity shadow-sm">
                    解锁 AI 研判  ¥59.9
                  </button>
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
