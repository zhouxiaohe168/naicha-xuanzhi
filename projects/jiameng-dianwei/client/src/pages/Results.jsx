import { useState, useEffect } from 'react'
import { useSearchParams, Link, useNavigate } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import api from '../config/api'

function amapUrl(address, city) {
  return `https://www.amap.com/search?query=${encodeURIComponent(address)}&city=${encodeURIComponent(city)}`
}

function Skeleton() {
  return (
    <div className="space-y-4 px-4 py-8 max-w-md mx-auto">
      <div className="h-24 bg-gray-100 rounded-2xl animate-pulse" />
      <div className="grid grid-cols-2 gap-3">
        <div className="h-20 bg-gray-100 rounded-2xl animate-pulse" />
        <div className="h-20 bg-gray-100 rounded-2xl animate-pulse" />
      </div>
      <div className="h-64 bg-gray-100 rounded-2xl animate-pulse" />
      <p className="text-center text-xs text-gray-400 animate-pulse pt-1">
        正在查询高德地图数据，约需 10–20 秒…
      </p>
    </div>
  )
}

function PayModal({ onConfirm, onCancel, brand, oppCount }) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="bg-white rounded-3xl w-full max-w-sm p-6 shadow-2xl">
        <div className="text-center mb-5">
          <div className="w-14 h-14 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
            <span className="text-2xl">📍</span>
          </div>
          <h2 className="text-lg font-bold text-gray-900">解锁机会点位置</h2>
          <p className="text-sm text-gray-500 mt-1">
            查看 {oppCount} 个具体地址 + 距最近 {brand} 的距离
          </p>
        </div>
        <div className="bg-green-50 border border-green-100 rounded-2xl p-4 mb-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-gray-700">竞品机会报告</span>
            <span className="text-2xl font-black text-green-600">¥9.9</span>
          </div>
          {['机会点具体地址', '最近竞品门店距离', '一键导航实地考察'].map(t => (
            <div key={t} className="flex items-center gap-2 text-sm text-gray-600 mb-1.5">
              <span className="w-4 h-4 bg-green-500 rounded-full flex items-center justify-center text-white text-xs">✓</span>
              {t}
            </div>
          ))}
        </div>
        <button
          onClick={onConfirm}
          className="w-full bg-green-500 text-white py-3.5 rounded-2xl font-bold text-base mb-2 hover:bg-green-600 transition-colors shadow-md shadow-green-200"
        >
          确认支付 ¥9.9
        </button>
        <button onClick={onCancel} className="w-full text-gray-400 text-sm py-2">
          取消
        </button>
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

  const [data, setData]         = useState(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')
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

  if (loading) return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <Skeleton />
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />

      {showModal && (
        <PayModal
          brand={brand}
          oppCount={data?.opportunity_count || 0}
          onConfirm={() => { setShowModal(false); setUnlocked(true) }}
          onCancel={() => setShowModal(false)}
        />
      )}

      <div className="flex-1 max-w-md mx-auto w-full px-4 py-5">

        {/* 顶部导航 */}
        <div className="flex items-center justify-between mb-4">
          <Link to="/" className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            重新查询
          </Link>
          <button className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-700">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
            </svg>
          </button>
        </div>

        {/* 地址标题 */}
        <div className="flex items-center gap-1.5 text-sm text-gray-500 mb-1">
          <svg className="w-3.5 h-3.5 text-gray-400" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
          </svg>
          {city}{district && district !== city ? ` · ${district}` : ''} · {street}
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-5">{brand} 选址分析</h1>

        {/* 错误提示 */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-4 mb-4">
            <p className="text-red-600 text-sm">{error}</p>
            <button onClick={load} className="mt-2 text-xs text-red-500 underline">重试</button>
          </div>
        )}

        {data && (() => {
          const oppCount = data.opportunity_count || 0
          const spots    = data.opportunity_spots || []
          const hasSpots = oppCount > 0

          return (
            <>
              {/* ── 核心结论卡 ── */}
              <div className={`rounded-2xl p-5 mb-4 ${
                hasSpots
                  ? 'bg-green-500'
                  : 'bg-gray-200'
              }`}>
                <div className="flex items-center gap-4">
                  <div className={`w-14 h-14 rounded-2xl flex items-center justify-center flex-shrink-0 ${
                    hasSpots ? 'bg-green-400' : 'bg-gray-300'
                  }`}>
                    {hasSpots ? (
                      <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-7 h-7 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    )}
                  </div>
                  <div className="flex-1">
                    {hasSpots ? (
                      <>
                        <div className="flex items-center gap-2">
                          <p className="text-white font-bold text-xl">
                            发现 {oppCount} 个机会点
                          </p>
                          <svg className="w-5 h-5 text-green-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                          </svg>
                        </div>
                        <p className="text-green-100 text-sm mt-0.5">
                          存在竞品但无{brand}覆盖的区域，建议实地考察评估
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="text-gray-700 font-bold text-xl">未发现明显机会</p>
                        <p className="text-gray-500 text-sm mt-0.5">
                          参照品牌附近均已有 {brand}，竞争较为饱和
                        </p>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* ── 数据概览 ── */}
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="bg-white rounded-2xl p-4 border border-gray-100 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-8 h-8 bg-red-50 rounded-xl flex items-center justify-center">
                      <span className="text-base">🧋</span>
                    </div>
                    <span className="text-xs text-gray-500">{brand}</span>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-black text-gray-900">{data.target_total}</span>
                    <span className="text-sm text-gray-400">家</span>
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">2km 范围内</p>
                </div>
                {data.anchor_results?.map(item => (
                  <div key={item.brand} className="bg-white rounded-2xl p-4 border border-gray-100 shadow-sm">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-8 h-8 bg-green-50 rounded-xl flex items-center justify-center">
                        <span className="text-base">🍵</span>
                      </div>
                      <span className="text-xs text-gray-500">{item.brand}</span>
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className="text-3xl font-black text-gray-900">{item.count}</span>
                      <span className="text-sm text-gray-400">家</span>
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5">2km 范围内</p>
                  </div>
                ))}
              </div>

              {/* ── 机会点区域 ── */}
              {hasSpots && (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden mb-4">
                  <div className="px-5 py-4 flex items-center justify-between border-b border-gray-50">
                    <div className="flex items-center gap-2">
                      <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
                      </svg>
                      <span className="text-sm font-bold text-gray-900">机会点详情</span>
                    </div>
                    {!unlocked && (
                      <div className="flex items-center gap-1 text-xs text-gray-400">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                        已锁定
                      </div>
                    )}
                  </div>

                  {!unlocked ? (
                    <div className="p-5">
                      {/* 模糊预览 */}
                      <div className="space-y-3 mb-5 select-none pointer-events-none">
                        {[...Array(Math.min(oppCount, 3))].map((_, i) => (
                          <div key={i} className="flex items-center gap-3 blur-sm">
                            <div className="w-8 h-8 bg-green-100 rounded-xl flex-shrink-0 flex items-center justify-center">
                              <span className="text-xs font-bold text-green-600">{i + 1}</span>
                            </div>
                            <div className="flex-1">
                              <div className="h-4 bg-gray-100 rounded w-3/4 mb-1.5" />
                              <div className="h-3 bg-gray-100 rounded w-1/2" />
                            </div>
                            <div className="text-xs text-green-500 font-medium">1.{i + 2}km</div>
                          </div>
                        ))}
                        {oppCount > 3 && (
                          <p className="text-center text-xs text-gray-300 blur-sm">还有 {oppCount - 3} 个机会点…</p>
                        )}
                      </div>

                      {/* 解锁 CTA */}
                      <div className="bg-gray-50 rounded-2xl p-4 text-center">
                        <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                          <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
                          </svg>
                        </div>
                        <p className="text-sm font-semibold text-gray-900 mb-1">查看完整地址信息</p>
                        <p className="text-xs text-gray-400 mb-4">解锁后可查看 {oppCount} 个机会点的详细地址并一键导航</p>
                        <button
                          onClick={handleUnlock}
                          className="w-full bg-green-500 text-white py-3.5 rounded-2xl font-bold text-sm hover:bg-green-600 transition-colors shadow-md shadow-green-200 flex items-center justify-center gap-2"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                          查看 {oppCount} 个机会点地址
                          <span className="bg-green-400 text-white text-xs px-2 py-0.5 rounded-full font-bold">¥9.9</span>
                        </button>
                        <p className="text-xs text-gray-400 mt-2 flex items-center justify-center gap-1">
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>
                          一次购买，永久查看
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="divide-y divide-gray-50">
                      {spots.map((spot, i) => (
                        <div key={i} className="px-5 py-4">
                          <div className="flex items-start gap-3">
                            <div className="w-7 h-7 bg-green-100 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5">
                              <span className="text-xs font-bold text-green-600">{i + 1}</span>
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-0.5">
                                <span className="text-xs bg-green-50 text-green-600 border border-green-100 px-1.5 py-0.5 rounded font-medium">{spot.anchor_brand}</span>
                                <span className="text-sm font-semibold text-gray-900 truncate">{spot.anchor_name}</span>
                              </div>
                              <p className="text-xs text-gray-400 truncate mb-1">{spot.anchor_address || '地址详见高德地图'}</p>
                              <div className="flex items-center gap-1 text-xs text-green-600 font-medium">
                                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                                  <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
                                </svg>
                                最近{brand} {spot.nearest_target} 外
                              </div>
                            </div>
                            <a
                              href={amapUrl(spot.anchor_address || spot.anchor_name, city)}
                              target="_blank"
                              rel="noreferrer"
                              className="flex-shrink-0 bg-green-500 text-white text-xs px-3 py-2 rounded-xl hover:bg-green-600 transition-colors font-medium"
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
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
                <div className="px-5 py-4 flex items-center justify-between border-b border-gray-50">
                  <div className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <span className="text-sm font-bold text-gray-900">AI 智能研判</span>
                    <span className="text-xs bg-purple-100 text-purple-600 px-1.5 py-0.5 rounded font-medium">Pro</span>
                  </div>
                </div>
                <div className="p-5">
                  {/* 模糊内容预览 */}
                  <div className="space-y-3 mb-5 select-none pointer-events-none blur-sm">
                    {[
                      { icon: '📊', title: '市场潜力评分', desc: '基于周边人口密度、消费能力、竞品分布等多维度分析，该区域开店成功率预估为...' },
                      { icon: '👥', title: '目标客群分析', desc: '周边3公里范围内主要人群画像为学生群体和年轻白领，日均客流量预估...' },
                      { icon: '🗺️', title: '最佳选址建议', desc: `综合分析后，推荐优先考察机会点 #2，该点位于商业中心核心位置，人流...` },
                    ].map(item => (
                      <div key={item.title} className="flex gap-3">
                        <div className="w-8 h-8 bg-purple-50 rounded-xl flex items-center justify-center flex-shrink-0 text-sm">{item.icon}</div>
                        <div>
                          <p className="text-sm font-semibold text-gray-900">{item.title}</p>
                          <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{item.desc}</p>
                        </div>
                      </div>
                    ))}
                    <div className="bg-purple-50 rounded-xl p-3 flex items-center justify-between">
                      <span className="text-xs text-purple-600 font-medium">综合开店成功率</span>
                      <span className="text-lg font-black text-purple-600">●●%</span>
                    </div>
                  </div>

                  {/* 解锁 AI */}
                  <div className="bg-gray-50 rounded-2xl p-4 text-center">
                    <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-3">
                      <svg className="w-6 h-6 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                    </div>
                    <p className="text-sm font-semibold text-gray-900 mb-1">AI 深度分析报告</p>
                    <p className="text-xs text-gray-400 mb-4">包含市场潜力评分、客群分析、竞品研判、最佳选址建议等专业内容</p>
                    <button className="w-full bg-gradient-to-r from-purple-500 to-purple-600 text-white py-3.5 rounded-2xl font-bold text-sm hover:opacity-90 transition-opacity shadow-md shadow-purple-200 flex items-center justify-center gap-2">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                      </svg>
                      解锁 AI 研判报告
                      <span className="bg-purple-400 text-white text-xs px-2 py-0.5 rounded-full font-bold">¥59.9</span>
                    </button>
                  </div>
                </div>
              </div>

              <p className="text-center text-xs text-gray-400 mt-4 pb-2">
                数据来源于公开信息，仅供参考 · 实际选址请结合实地考察
              </p>
            </>
          )
        })()}
      </div>

      <Footer />
    </div>
  )
}
