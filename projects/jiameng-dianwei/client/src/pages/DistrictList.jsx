import { useState, useEffect } from 'react'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import DistrictCard from '../components/custom/DistrictCard'
import { MVP_CITY } from '../config/constants'
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

const FILTERS = [
  { key: 'all',    label: '全部' },
  { key: 'high',   label: '🔥 人流量高' },
  { key: 'medium', label: '⚡ 人流量中' },
  { key: 'low',    label: '🌙 人流量低' },
]

export default function DistrictList() {
  const [districts, setDistricts] = useState([])
  const [search, setSearch]       = useState('')
  const [filter, setFilter]       = useState('all')
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')

  useEffect(() => {
    api.get('/districts', { params: { city: MVP_CITY } })
      .then((data) => setDistricts(Array.isArray(data) ? data : []))
      .catch(() => setError('加载失败，请刷新重试'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = districts.filter((d) => {
    const matchSearch = d.name.includes(search)
    const matchFilter = filter === 'all' || d.foot_traffic_level === filter
    return matchSearch && matchFilter
  })

  return (
    <div className="min-h-screen bg-[#FFF8F0] flex flex-col">
      <Navbar />

      <div className="flex-1 max-w-6xl mx-auto w-full px-4 py-8">
        {/* 页头 */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-text-main mb-1">
            📍 {MVP_CITY} · 商圈列表
          </h1>
          <p className="text-sm text-text-sub">
            {loading ? '加载中...' : `共 ${districts.length} 个商圈，数据每周更新`}
          </p>
        </div>

        {/* 搜索框 */}
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

        {/* 筛选标签 */}
        <div className="flex gap-2 mb-6 flex-wrap">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              onClick={() => setFilter(item.key)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                filter === item.key
                  ? 'bg-primary text-white shadow-sm shadow-primary/20'
                  : 'bg-white text-text-sub border border-gray-200 hover:border-primary hover:text-primary'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* 骨架屏 */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
          </div>
        )}

        {/* 错误 */}
        {error && (
          <div className="flex flex-col items-center py-20 text-center">
            <div className="text-5xl mb-4">😕</div>
            <p className="text-text-sub mb-4">{error}</p>
            <button
              onClick={() => { setError(''); setLoading(true); api.get('/districts', { params: { city: MVP_CITY } }).then(d => setDistricts(Array.isArray(d) ? d : [])).catch(() => setError('加载失败，请刷新重试')).finally(() => setLoading(false)) }}
              className="px-6 py-2.5 bg-primary text-white rounded-xl text-sm font-medium hover:bg-primary-dark"
            >
              重新加载
            </button>
          </div>
        )}

        {/* 列表 */}
        {!loading && !error && filtered.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((district) => (
              <DistrictCard key={district.id} district={district} />
            ))}
          </div>
        )}

        {/* 空状态 */}
        {!loading && !error && filtered.length === 0 && (
          <div className="flex flex-col items-center py-20 text-center">
            <div className="text-5xl mb-4">🔍</div>
            <p className="text-text-main font-medium mb-1">没有找到匹配的商圈</p>
            <p className="text-text-sub text-sm">试试清空搜索关键词或更换筛选条件</p>
            <button
              onClick={() => { setSearch(''); setFilter('all') }}
              className="mt-4 px-5 py-2 border border-gray-200 rounded-xl text-sm text-text-sub hover:border-primary hover:text-primary"
            >
              清除筛选
            </button>
          </div>
        )}
      </div>

      <Footer />
    </div>
  )
}
