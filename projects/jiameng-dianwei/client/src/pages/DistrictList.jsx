import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import DistrictCard from '../components/custom/DistrictCard'
import { MVP_CITY, BRAND_SCORES, TARGET_BRANDS } from '../config/constants'
import api from '../config/api'

function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 animate-pulse">
      <div className="flex justify-between mb-4">
        <div className="h-5 bg-gray-100 rounded w-2/3" />
        <div className="h-5 bg-gray-100 rounded-full w-16" />
      </div>
      <div className="flex gap-4 mb-4">
        <div className="h-4 bg-gray-100 rounded w-24" />
        <div className="h-4 bg-gray-100 rounded w-24" />
      </div>
      <div className="border-t border-gray-50 mb-4" />
      <div className="flex gap-2">
        <div className="flex-1 h-10 bg-gray-100 rounded-xl" />
        <div className="flex-1 h-10 bg-gray-100 rounded-xl" />
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

  // 打分：如果有品牌，按品牌适配度排序
  const getScore = (district) => {
    if (!brand || !BRAND_SCORES[brand]) return null
    return BRAND_SCORES[brand][district.name] || null
  }

  const filtered = districts
    .filter((d) => d.name.includes(search))
    .sort((a, b) => {
      // 有品牌时按适配分排序
      if (brand && BRAND_SCORES[brand]) {
        const sa = BRAND_SCORES[brand][a.name]?.score || 0
        const sb = BRAND_SCORES[brand][b.name]?.score || 0
        return sb - sa
      }
      return 0
    })

  const brandInfo = TARGET_BRANDS.find(b => b.name === brand)

  return (
    <div className="min-h-screen bg-[#FFF8F0] flex flex-col">
      <Navbar />

      <div className="flex-1 max-w-6xl mx-auto w-full px-4 py-8">

        {/* ── 页头 ── */}
        <div className="mb-6">
          {brand ? (
            <>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">{brandInfo?.icon || '🏪'}</span>
                <h1 className="text-2xl font-bold text-text-main">
                  {brand} · 金华选址推荐
                </h1>
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <p className="text-sm text-text-sub">
                  {loading ? '分析中...' : `共 ${districts.length} 个商圈，按适配度排序`}
                </p>
                {anchors.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs text-text-sub">参考锚点：</span>
                    {anchors.map(a => (
                      <span key={a} className="text-xs bg-orange-50 text-primary px-2 py-0.5 rounded-full border border-orange-100">{a}</span>
                    ))}
                  </div>
                )}
              </div>
              {/* 重新选择 */}
              <Link to="/" className="inline-flex items-center gap-1 text-xs text-text-sub hover:text-primary mt-2 transition-colors">
                ← 重新选择品牌
              </Link>
            </>
          ) : (
            <>
              <h1 className="text-2xl font-bold text-text-main mb-1">
                📍 {MVP_CITY} · 商圈列表
              </h1>
              <p className="text-sm text-text-sub">
                {loading ? '加载中...' : `共 ${districts.length} 个商圈，数据每周更新`}
              </p>
            </>
          )}
        </div>

        {/* ── 搜索框 ── */}
        <div className="relative mb-4">
          <span className="absolute left-4 top-1/2 -translate-y-1/2 text-text-sub text-lg">🔍</span>
          <input
            type="text"
            placeholder="搜索商圈名称..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-white border border-gray-200 rounded-xl pl-11 pr-4 py-3 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
          />
        </div>


        {/* ── 品牌模式：有适配分时的说明条 ── */}
        {brand && !loading && (
          <div className="flex items-center gap-2 mb-5 px-4 py-2.5 bg-orange-50 border border-orange-100 rounded-xl text-sm text-primary">
            <span>🎯</span>
            <span>以下商圈已按 <strong>{brand}</strong> 适配度从高到低排列，绿色标记为强烈推荐位置</span>
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
            <div className="text-5xl mb-4">😕</div>
            <p className="text-text-sub mb-4">{error}</p>
            <button
              onClick={loadDistricts}
              className="px-6 py-2.5 bg-primary text-white rounded-xl text-sm font-medium hover:bg-primary-dark"
            >
              重新加载
            </button>
          </div>
        )}

        {/* ── 列表 ── */}
        {!loading && !error && filtered.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((district) => (
              <DistrictCard
                key={district.id}
                district={district}
                brand={brand}
                brandScore={getScore(district)}
              />
            ))}
          </div>
        )}

        {/* ── 空状态 ── */}
        {!loading && !error && filtered.length === 0 && (
          <div className="flex flex-col items-center py-20 text-center">
            <div className="text-5xl mb-4">🔍</div>
            <p className="text-text-main font-medium mb-1">没有找到匹配的商圈</p>
            <p className="text-text-sub text-sm">试试清空搜索关键词</p>
            <button
              onClick={() => setSearch('')}
              className="mt-4 px-5 py-2 border border-gray-200 rounded-xl text-sm text-text-sub hover:border-primary hover:text-primary"
            >
              清除搜索
            </button>
          </div>
        )}
      </div>

      <Footer />
    </div>
  )
}
