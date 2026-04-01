import { Link } from 'react-router-dom'
import { PRICE_BASIC, PRICE_AI, SCORE_LEVEL } from '../../config/constants'

const trafficConfig = {
  high:   { label: '人流量高', dot: 'bg-green-400',  text: 'text-green-700',  bg: 'bg-green-50'  },
  medium: { label: '人流量中', dot: 'bg-yellow-400', text: 'text-yellow-700', bg: 'bg-yellow-50' },
  low:    { label: '人流量低', dot: 'bg-red-400',    text: 'text-red-600',    bg: 'bg-red-50'    },
}

export default function DistrictCard({ district, brand, brandScore }) {
  const traffic = trafficConfig[district.foot_traffic_level] ?? trafficConfig.medium
  const updatedDate = district.updated_at
    ? new Date(district.updated_at).toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })
    : '近期'

  const scoreConfig = brandScore ? SCORE_LEVEL[brandScore.level] : null

  return (
    <div className={`bg-white rounded-2xl border shadow-card hover:shadow-md hover:-translate-y-0.5 transition-all flex flex-col ${
      scoreConfig ? `${scoreConfig.border}` : 'border-gray-100'
    }`}>

      {/* 品牌适配评分条（有品牌时显示） */}
      {brandScore && scoreConfig && (
        <div className={`px-5 pt-4 pb-3 flex items-center justify-between ${scoreConfig.bg} rounded-t-2xl`}>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${scoreConfig.dot}`} />
            <span className={`text-xs font-semibold ${scoreConfig.color}`}>{scoreConfig.label}</span>
          </div>
          <div className={`text-2xl font-bold ${scoreConfig.color}`}>
            {brandScore.score}
            <span className={`text-xs font-normal ml-0.5 ${scoreConfig.color} opacity-60`}>/10</span>
          </div>
        </div>
      )}

      {/* 顶部：名称 + 人流量标签 */}
      <div className={`px-5 flex items-start justify-between gap-2 ${brandScore ? 'pt-3 pb-3' : 'pt-5 pb-4'}`}>
        <h3 className="text-base font-semibold text-text-main leading-snug">
          {district.name}
        </h3>
        {!brandScore && (
          <span className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium shrink-0 ${traffic.bg} ${traffic.text}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${traffic.dot}`} />
            {traffic.label}
          </span>
        )}
      </div>

      {/* 锚点品牌标签（品牌模式下显示） */}
      {brandScore?.anchors_found?.length > 0 && (
        <div className="px-5 pb-3 flex flex-wrap gap-1.5">
          {brandScore.anchors_found.map(anchor => (
            <span key={anchor} className="text-xs bg-gray-50 text-text-sub border border-gray-100 px-2 py-0.5 rounded-md">
              ✓ {anchor}
            </span>
          ))}
        </div>
      )}

      {/* 适配理由（品牌模式下显示） */}
      {brandScore?.reason && (
        <div className="px-5 pb-3">
          <p className="text-xs text-text-sub leading-relaxed">{brandScore.reason}</p>
        </div>
      )}

      {/* 数据预览（模糊，无品牌模式显示） */}
      {!brandScore && (
        <div className="px-5 pb-4 flex gap-5 text-sm text-text-sub">
          <div className="flex items-center gap-1.5">
            <span>🧋</span>
            <span>奶茶店</span>
            <span className="font-medium text-text-main blur-sm select-none pointer-events-none">
              {district.tea_shop_count ?? 12}
            </span>
            <span>家</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span>☕</span>
            <span>咖啡店</span>
            <span className="font-medium text-text-main blur-sm select-none pointer-events-none">
              {district.coffee_shop_count ?? 8}
            </span>
            <span>家</span>
          </div>
        </div>
      )}

      {/* 分割线 */}
      <div className="border-t border-gray-50 mx-5" />

      {/* 操作区 */}
      <div className="p-5 pt-4 flex gap-2.5 mt-auto">
        <Link
          to={`/districts/${district.id}${brand ? `?brand=${encodeURIComponent(brand)}` : ''}`}
          className="flex-1 text-center bg-price-bg text-primary py-2.5 rounded-xl text-sm font-semibold hover:bg-orange-100 transition-colors"
        >
          竞品报告 <span className="font-bold">¥{PRICE_BASIC}</span>
        </Link>
        <Link
          to={`/districts/${district.id}?type=ai${brand ? `&brand=${encodeURIComponent(brand)}` : ''}`}
          className="flex-1 text-center bg-gradient-to-r from-primary to-secondary text-white py-2.5 rounded-xl text-sm font-semibold hover:opacity-90 transition-opacity"
        >
          AI 研判 <span className="font-bold">¥{PRICE_AI}</span>
        </Link>
      </div>

      {/* 更新时间 */}
      <div className="px-5 pb-4 text-xs text-text-sub">
        数据更新于 {updatedDate}
      </div>
    </div>
  )
}
