import { useState, useEffect } from 'react'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import DistrictCard from '../components/custom/DistrictCard'
import { MVP_CITY } from '../config/constants'
import api from '../config/api'

export default function DistrictList() {
  const [districts, setDistricts] = useState([])
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/districts', { params: { city: MVP_CITY } })
      .then((data) => setDistricts(data))
      .catch(() => setError('加载失败，请刷新重试'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = districts.filter((d) => {
    const matchSearch = d.name.includes(search)
    const matchFilter = filter === 'all' || d.foot_traffic_level === filter
    return matchSearch && matchFilter
  })

  return (
    <div>
      <Navbar />
      <div className="max-w-6xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-4">📍 {MVP_CITY} · 商圈列表</h1>

        <div className="mb-4">
          <input
            type="text"
            placeholder="🔍 搜索商圈名称..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full border border-gray-200 rounded-btn px-4 py-3 focus:outline-none focus:border-primary"
          />
        </div>

        <div className="flex gap-2 mb-6">
          {[
            { key: 'all', label: '全部' },
            { key: 'high', label: '人流量高' },
            { key: 'medium', label: '人流量中' },
            { key: 'low', label: '人流量低' },
          ].map((item) => (
            <button
              key={item.key}
              onClick={() => setFilter(item.key)}
              className={`px-4 py-1.5 rounded-full text-sm ${
                filter === item.key
                  ? 'bg-primary text-white'
                  : 'bg-white text-text-sub border border-gray-200 hover:border-primary'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {loading && (
          <div className="text-center py-12 text-text-sub">加载中...</div>
        )}

        {error && (
          <div className="text-center py-12 text-red-500">{error}</div>
        )}

        {!loading && !error && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((district) => (
              <DistrictCard key={district.id} district={district} />
            ))}
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="text-center py-12 text-text-sub">没有找到匹配的商圈</div>
        )}
      </div>
      <Footer />
    </div>
  )
}
