import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import DistrictCard from '../components/custom/DistrictCard'
import { MVP_CITY, BRAND_SCORES, TARGET_BRANDS } from '../config/constants'
import api from '../config/api'

function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
      <div className="flex justify-between mb-4">
        <div className="h-4 bg-gray-100 rounded w-1/2" />
        <div className="h-8 bg-gray-100 rounded w-12" />
      </div>
      <div className="h-5 bg-gray-100 rounded w-2/3 mb-3" />
      <div className="flex gap-2 mb-4">
        <div className="h-5 bg-gray-100 rounded w-16" />
        <div className="h-5 bg-gray-100 rounded w-16" />
      </div>
      <div className="border-t border-gray-50 mb-3" />
      <div className="flex gap-2">
        <div className="flex-1 h-9 bg-gray-100 rounded-lg" />
        <div className="flex-1 h-9 bg-gray-100 rounded-lg" />
      </div>
    </div>
  )
}

export default function DistrictList() {
  const [searchParams] = useSearchParams()
  const brand   = searchParams.get('brand') || ''
  const anchors = searchParams.get('anchors')?.split(',').filter(Boolean) || []

  const [districts, setDistricts] = useState([])
  const [search, setSearch]       = useState('')
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')

  const loadDistricts = () => {
    setLoading(true)
    setError('')
    api.get('/districts', { params: { city: MVP_CITY } })
      .then((data) => setDistricts(Array.isArray(data) ? data : []))
      .catch(() => setError('加载失败，请刷新重试'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadDistricts() }, [])

  const getScore = (district) => {
    if (!brand || !BRAND_SCORES[brand]) return null
    return BRAND_SCORES[brand][district.name] || null
  }

  const filtered = districts
    .filter((d) => d.name.includes(search))
    .sort((a, b) => {
      if (brand && BRAND_SCORES[brand]) {
        const sa = BRAND_SCORES[brand][a.name]?.score || 0
        const sb = BRAND_SCORES[brand][b.name]?.score || 0
        return sb - sa
      }
      return 0
    })

  const brandInfo = TARGET_BRANDS.find(b => b.name === brand)

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Navbar />

      <div className="flex-1 max-w-6xl mx-auto w-full px-4 py-8">

        {/* ── 页头 ── */}
        {brand ? (
          <div className="mb-8">
            <Link to="/" className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-primary mb-4 transition-colors">
              ← 重新选择
            </Link>
            <div className="flex items-start justify-between flex-wrap gap-4">
              <div>
                <h1 className="text-2xl font-bold text-gray-900 mb-1">
                  {brandInfo?.icon} {brand} · 金华选址推荐
                </h1>
                <p className="text-sm text-gray-500">
                  {loading ? '分析中...' : `${filtered.length} 个商圈，按适配度从高到低排列`}
                </p>
              </div>
              {anchors.length > 0 && (
                <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-lg px-4 py-2">
                  <span className="text-xs text-gray-400 shrink-0">参考锚点</span>
                  <div className="flex gap-1.5 flex-wrap">
                    {anchors.map(a => (
                      <span key={a} className="text-xs bg-orange-50 text-primary px-2 py-0.5 rounded-md border border-orange-100 font-medium">{a}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-gray-900 mb-1">商圈列表 · {MVP_CITY}</h1>
            <p className="text-sm text-gray-500">
              {loading ? '加载中...' : `共 ${districts.length} 个商圈，数据每周更新`}
            </p>
          </div>
        )}

        {/* ── 搜索框 ── */}
        <div className="relative mb-6">
          <svg className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="搜索商圈名称..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-white border border-gray-200 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
          />
        </div>

        {/* ── 品牌提示条 ── */}
        {brand && !loading && (
          <div className="flex items-center gap-2 mb-6 px-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600">
            <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
            以下商圈已按 <strong className="text-gray-900">{brand}</strong> 适配度排序，数字越大越适合开店
          </div>
        )}

        {/* ── 骨架屏 ── */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
          </div>
        )}

        {/* ── 错误 ── */}
        {error && (
          <div className="flex flex-col items-center py-20 text-center">
            <div className="w-12 h-12 bg-red-50 rounded-full flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <p className="text-gray-500 mb-4">{error}</p>
            <button onClick={loadDistricts} className="px-5 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-orange-600">
              重新加载
            </button>
          </div>
        )}

        {/* ── 列表 ── */}
        {!loading && !error && filtered.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((district, index) => (
              <DistrictCard
                key={district.id}
                district={district}
                brand={brand}
                brandScore={getScore(district)}
                rank={brand ? index + 1 : null}
              />
            ))}
          </div>
        )}

        {/* ── 空状态 ── */}
        {!loading && !error && filtered.length === 0 && (
          <div className="flex flex-col items-center py-20 text-center">
            <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <p className="text-gray-900 font-medium mb-1">没有找到匹配的商圈</p>
            <p className="text-gray-400 text-sm mb-4">试试清空搜索关键词</p>
            <button onClick={() => setSearch('')} className="px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-500 hover:border-primary hover:text-primary">
              清除搜索
            </button>
          </div>
        )}
      </div>

      <Footer />
    </div>
  )
}
