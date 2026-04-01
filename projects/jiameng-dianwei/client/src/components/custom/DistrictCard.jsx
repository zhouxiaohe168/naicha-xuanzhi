import { Link } from 'react-router-dom'
import { PRICE_BASIC, PRICE_AI, SCORE_LEVEL } from '../../config/constants'

export default function DistrictCard({ district, brand, brandScore, rank }) {
  const scoreConfig = brandScore ? SCORE_LEVEL[brandScore.level] : null

  return (
    <div className={`bg-white rounded-xl border flex flex-col transition-all hover:-translate-y-0.5 hover:shadow-lg ${
      scoreConfig ? scoreConfig.border : 'border-gray-200'
    }`}>

      {/* 顶部色条 + 评分 */}
      {brandScore && scoreConfig ? (
        <div className={`px-5 py-4 flex items-center justify-between ${scoreConfig.bg} rounded-t-xl`}>
          <div className="flex items-center gap-2">
            {rank && (
              <span className={`text-xs font-bold px-2 py-0.5 rounded ${scoreConfig.color} bg-white/60`}>
                #{rank}
              </span>
            )}
            <span className={`text-xs font-semibold ${scoreConfig.color}`}>{scoreConfig.label}</span>
          </div>
          <div className="flex items-end gap-0.5">
            <span className={`text-3xl font-black ${scoreConfig.color} leading-none`}>{brandScore.score}</span>
            <span className={`text-xs ${scoreConfig.color} opacity-50 mb-0.5`}>/10</span>
          </div>
        </div>
      ) : (
        <div className="px-5 pt-5" />
      )}

      {/* 商圈名称 */}
      <div className="px-5 py-3">
        <h3 className="text-base font-bold text-gray-900 leading-snug">{district.name}</h3>
      </div>

      {/* 锚点标签 */}
      {brandScore?.anchors_found?.length > 0 && (
        <div className="px-5 pb-2 flex flex-wrap gap-1.5">
          {brandScore.anchors_found.map(anchor => (
            <span key={anchor} className="text-xs bg-gray-50 text-gray-500 border border-gray-200 px-2 py-0.5 rounded-md font-medium">
              ✓ {anchor}
            </span>
          ))}
        </div>
      )}

      {/* 选址理由 */}
      {brandScore?.reason && (
        <div className="px-5 pb-3">
          <p className="text-xs text-gray-500 leading-relaxed border-l-2 border-gray-200 pl-2">{brandScore.reason}</p>
        </div>
      )}

      {/* 无品牌模式：模糊数据预览 */}
      {!brandScore && (
        <div className="px-5 pb-4 flex gap-6 text-sm text-gray-400">
          <span>奶茶店 <span className="font-semibold text-gray-900 blur-sm select-none">12</span> 家</span>
          <span>咖啡店 <span className="font-semibold text-gray-900 blur-sm select-none">8</span> 家</span>
        </div>
      )}

      {/* 分割线 */}
      <div className="border-t border-gray-100 mx-5 mt-auto" />

      {/* 操作按钮 */}
      <div className="p-4 flex gap-2">
        <Link
          to={`/districts/${district.id}${brand ? `?brand=${encodeURIComponent(brand)}` : ''}`}
          className="flex-1 text-center border border-primary text-primary py-2 rounded-lg text-sm font-semibold hover:bg-orange-50 transition-colors"
        >
          竞品报告 <span>¥{PRICE_BASIC}</span>
        </Link>
        <Link
          to={`/districts/${district.id}?type=ai${brand ? `&brand=${encodeURIComponent(brand)}` : ''}`}
          className="flex-1 text-center bg-primary text-white py-2 rounded-lg text-sm font-semibold hover:bg-orange-600 transition-colors"
        >
          AI 研判 <span>¥{PRICE_AI}</span>
        </Link>
      </div>
    </div>
  )
}
