import { useState } from 'react'
import { useParams } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import { PRICE_BASIC, PRICE_AI, PRICE_UPGRADE, RANGE_OPTIONS, DEFAULT_RANGE, BRAND_COLORS } from '../config/constants'

// 临时mock数据
const MOCK_DETAIL = {
  id: 1,
  name: '万达商圈',
  city: '金华市',
  foot_traffic_level: 'high',
  tea_shop_count: 12,
  coffee_shop_count: 8,
  brands: ['蜜雪冰城', '瑞幸咖啡', '喜茶', '库迪咖啡', '沪上阿姨', '书亦烧仙草'],
  surrounding: { office: 5, school: 3, residential: 8, hospital: 1 },
  consumption_heat: '高',
}

export default function DistrictDetail() {
  const { id } = useParams()
  const [range, setRange] = useState(DEFAULT_RANGE)
  const [paid, setPaid] = useState(false) // 临时状态，后端接好后改为真实查询

  const data = MOCK_DETAIL

  // 模拟付费
  const handlePay = (type) => {
    // TODO: 调用支付接口
    if (confirm(`确认支付 ¥${type === 'basic' ? PRICE_BASIC : PRICE_AI}？（演示模式）`)) {
      setPaid(true)
    }
  }

  // 品牌标签颜色
  const getBrandColor = (brand) => BRAND_COLORS[brand] || BRAND_COLORS.default

  return (
    <div>
      <Navbar />
      <div className="max-w-4xl mx-auto px-4 py-6">
        {/* 商圈标题 */}
        <h1 className="text-2xl font-bold mb-1">📍 {data.name}</h1>
        <p className="text-text-sub mb-2">{data.city}</p>
        <span className="inline-block text-sm px-3 py-1 rounded-full bg-green-50 text-green-600 mb-6">
          人流量：高
        </span>

        {paid ? (
          /* === 付费后：完整报告 === */
          <>
            {/* 范围选择 */}
            <div className="flex items-center gap-2 mb-6">
              <span className="text-sm text-text-sub">分析范围：</span>
              {RANGE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setRange(opt.value)}
                  className={`px-3 py-1 rounded-full text-sm ${
                    range === opt.value
                      ? 'bg-primary text-white'
                      : 'bg-white border border-gray-200 text-text-sub hover:border-primary'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* 数据卡片 */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-white rounded-card shadow-card p-4 text-center">
                <div className="text-3xl font-bold text-primary font-price">{data.tea_shop_count}</div>
                <div className="text-sm text-text-sub mt-1">奶茶店</div>
              </div>
              <div className="bg-white rounded-card shadow-card p-4 text-center">
                <div className="text-3xl font-bold text-primary font-price">{data.coffee_shop_count}</div>
                <div className="text-sm text-text-sub mt-1">咖啡店</div>
              </div>
              <div className="bg-white rounded-card shadow-card p-4 text-center">
                <div className="text-3xl font-bold text-primary font-price">{data.consumption_heat}</div>
                <div className="text-sm text-text-sub mt-1">消费热度</div>
              </div>
            </div>

            {/* 品牌分布 */}
            <div className="bg-white rounded-card shadow-card p-4 mb-6">
              <h3 className="font-semibold mb-3">已进驻品牌</h3>
              <div className="flex flex-wrap gap-2">
                {data.brands.map((brand) => {
                  const color = getBrandColor(brand)
                  return (
                    <span
                      key={brand}
                      className="px-3 py-1 rounded-full text-sm"
                      style={{ backgroundColor: color.bg, color: color.text }}
                    >
                      {brand}
                    </span>
                  )
                })}
              </div>
            </div>

            {/* 地图占位 */}
            <div className="bg-white rounded-card shadow-card p-4 mb-6">
              <h3 className="font-semibold mb-3">品牌分布地图</h3>
              <div className="bg-gray-100 rounded-lg h-64 flex items-center justify-center text-text-sub">
                🗺️ 高德地图（开发中）
              </div>
            </div>

            {/* 周边配套 */}
            <div className="bg-white rounded-card shadow-card p-4 mb-6">
              <h3 className="font-semibold mb-3">周边配套</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="text-center p-3 bg-bg-warm rounded-lg">
                  <div className="text-lg">🏢</div>
                  <div className="text-sm text-text-sub">写字楼</div>
                  <div className="font-bold text-primary">{data.surrounding.office}个</div>
                </div>
                <div className="text-center p-3 bg-bg-warm rounded-lg">
                  <div className="text-lg">🏫</div>
                  <div className="text-sm text-text-sub">学校</div>
                  <div className="font-bold text-primary">{data.surrounding.school}个</div>
                </div>
                <div className="text-center p-3 bg-bg-warm rounded-lg">
                  <div className="text-lg">🏘️</div>
                  <div className="text-sm text-text-sub">小区</div>
                  <div className="font-bold text-primary">{data.surrounding.residential}个</div>
                </div>
                <div className="text-center p-3 bg-bg-warm rounded-lg">
                  <div className="text-lg">🏥</div>
                  <div className="text-sm text-text-sub">医院</div>
                  <div className="font-bold text-primary">{data.surrounding.hospital}个</div>
                </div>
              </div>
            </div>

            {/* 升级AI研判 */}
            <div className="bg-gradient-to-r from-primary to-secondary rounded-card p-6 text-center text-white">
              <h3 className="text-lg font-bold mb-2">🤖 升级AI研判</h3>
              <p className="text-white/80 mb-4">让AI告诉你这里能不能开店，补差价 ¥{PRICE_UPGRADE}</p>
              <button
                onClick={() => handlePay('ai')}
                className="bg-white text-primary px-6 py-2 rounded-btn font-medium hover:bg-gray-50"
              >
                升级AI研判 →
              </button>
            </div>
          </>
        ) : (
          /* === 未付费：模糊信息 + 付费按钮 === */
          <>
            <div className="bg-white rounded-card shadow-card p-6 mb-6">
              <div className="text-center py-8">
                <div className="text-4xl mb-4">🔒</div>
                <h3 className="text-lg font-semibold mb-2">以下内容需付费解锁</h3>
                <div className="space-y-2 text-text-sub blur-sm select-none mb-6">
                  <p>🧋 奶茶店：12 家 | ☕ 咖啡店：8 家</p>
                  <p>已进驻品牌：蜜雪冰城、瑞幸咖啡、喜茶...</p>
                  <p>周边配套：写字楼5个、学校3个...</p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <button
                onClick={() => handlePay('basic')}
                className="bg-white rounded-card shadow-card p-6 text-center hover:shadow-md transition-shadow"
              >
                <div className="text-3xl font-bold text-primary font-price mb-2">¥{PRICE_BASIC}</div>
                <div className="font-semibold mb-2">基础报告</div>
                <div className="text-sm text-text-sub">竞品数量 · 品牌分布 · 周边配套</div>
              </button>
              <button
                onClick={() => handlePay('ai')}
                className="bg-gradient-to-r from-primary to-secondary rounded-card shadow-card p-6 text-center text-white hover:opacity-95 transition-opacity"
              >
                <div className="text-3xl font-bold font-price mb-2">¥{PRICE_AI}</div>
                <div className="font-semibold mb-2">AI研判报告</div>
                <div className="text-sm text-white/80">评分 · 品牌推荐 · 风险预警 · 选址建议</div>
              </button>
            </div>
          </>
        )}
      </div>
      <Footer />
    </div>
  )
}
