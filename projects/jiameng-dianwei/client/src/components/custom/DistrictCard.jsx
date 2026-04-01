import { Link } from 'react-router-dom'
import { PRICE_BASIC, PRICE_AI } from '../../config/constants'

// 人流量等级对应的颜色和文字
const trafficLevels = {
  high: { color: 'text-green-600', bg: 'bg-green-50', label: '高' },
  medium: { color: 'text-yellow-600', bg: 'bg-yellow-50', label: '中' },
  low: { color: 'text-red-500', bg: 'bg-red-50', label: '低' },
}

export default function DistrictCard({ district }) {
  const traffic = trafficLevels[district.foot_traffic_level] || trafficLevels.medium

  return (
    <div className="bg-white rounded-card shadow-card p-4 hover:shadow-md transition-shadow">
      {/* 商圈名称 + 人流量 */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-text-main">
          📍 {district.name}
        </h3>
        <span className={`text-xs px-2 py-1 rounded-full ${traffic.bg} ${traffic.color}`}>
          人流量：{traffic.label}
        </span>
      </div>

      {/* 奶茶/咖啡数量预览（模糊） */}
      <div className="flex gap-4 text-sm text-text-sub mb-4">
        <span>🧋 奶茶店：<span className="blur-sm select-none">12</span> 家</span>
        <span>☕ 咖啡店：<span className="blur-sm select-none">8</span> 家</span>
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-2">
        <Link
          to={`/districts/${district.id}`}
          className="flex-1 text-center bg-price-bg text-primary py-2 rounded-btn text-sm font-medium hover:bg-orange-100"
        >
          基础报告 ¥{PRICE_BASIC}
        </Link>
        <Link
          to={`/districts/${district.id}?type=ai`}
          className="flex-1 text-center bg-gradient-to-r from-primary to-secondary text-white py-2 rounded-btn text-sm font-medium hover:opacity-90"
        >
          AI研判 ¥{PRICE_AI}
        </Link>
      </div>

      {/* 更新时间 */}
      <p className="text-xs text-text-sub mt-3">
        更新时间：{district.updated_at || '2026-03-31'}
      </p>
    </div>
  )
}
