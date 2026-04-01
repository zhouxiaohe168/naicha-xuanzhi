import { useState, useEffect } from 'react'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import DistrictCard from '../components/custom/DistrictCard'
import { MVP_CITY } from '../config/constants'

// 临时mock数据，后端接好后替换
const MOCK_DISTRICTS = [
  { id: 1, name: '万达商圈', foot_traffic_level: 'high', updated_at: '2026-03-31' },
  { id: 2, name: '义乌小商品城商圈', foot_traffic_level: 'high', updated_at: '2026-03-31' },
  { id: 3, name: '江南商圈', foot_traffic_level: 'medium', updated_at: '2026-03-31' },
  { id: 4, name: '火车站商圈', foot_traffic_level: 'high', updated_at: '2026-03-31' },
  { id: 5, name: '金华学院周边', foot_traffic_level: 'medium', updated_at: '2026-03-31' },
  { id: 6, name: '秋滨工业区', foot_traffic_level: 'low', updated_at: '2026-03-31' },
]

export default function DistrictList() {
  const [districts, setDistricts] = useState([])
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all') // all / high / medium / low

  useEffect(() => {
    // TODO: 替换为真实API调用
    // const data = await api.get('/districts', { params: { city: MVP_CITY } })
    setDistricts(MOCK_DISTRICTS)
  }, [])

  // 搜索和筛选
  const filtered = districts.filter((d) => {
    const matchSearch = d.name.includes(search)
    const matchFilter = filter === 'all' || d.foot_traffic_level === filter
    return matchSearch && matchFilter
  })

  return (
    <div>
      <Navbar />
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* 城市标题 */}
        <h1 className="text-2xl font-bold mb-4">📍 {MVP_CITY} · 商圈列表</h1>

        {/* 搜索框 */}
        <div className="mb-4">
          <input
            type="text"
            placeholder="🔍 搜索商圈名称..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full border border-gray-200 rounded-btn px-4 py-3 focus:outline-none focus:border-primary"
          />
        </div>

        {/* 筛选标签 */}
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

        {/* 商圈卡片列表 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((district) => (
            <DistrictCard key={district.id} district={district} />
          ))}
        </div>

        {/* 空状态 */}
        {filtered.length === 0 && (
          <div className="text-center py-12 text-text-sub">
            没有找到匹配的商圈
          </div>
        )}
      </div>
      <Footer />
    </div>
  )
}
