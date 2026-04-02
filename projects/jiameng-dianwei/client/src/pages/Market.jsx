import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Header from '../components/Header'
import Footer from '../components/Footer'
import { marketAPI, checkoutAPI } from '../lib/api'

const TYPE_STYLE = {
  release:       { border: 'border-l-warning', bg: 'bg-warning/5',  badge: 'bg-warning/20 text-warning' },
  new_district:  { border: 'border-l-success', bg: 'bg-success/5',  badge: 'bg-success/20 text-success' },
  brand_window:  { border: 'border-l-primary', bg: 'bg-primary/5',  badge: 'bg-primary/20 text-primary' },
}

// Fallback本地数据（API不可用时）
const FALLBACK = {
  total: 4,
  this_week_new: 7,
  by_type: { release: 3, new_district: 1, brand_window: 0 },
  opportunities: [
    { id: 'opp-hz-001', type: '位置释放', type_key: 'release', badge: '🔥 紧急', title: '竞品撤店 · 黄金铺位空出', city: '杭州', district: '拱墅区', summary: '某头部奶茶品牌门店关闭，临街铺位预计下月空出', tags: ['临街铺位', '日流量6000+', '低竞争'], price: 599, locked: true },
    { id: 'opp-cd-001', type: '新商圈崛起', type_key: 'new_district', badge: '🌱 新兴', title: '新住宅区商业街开街', city: '成都', district: '天府新区', summary: '3.2万户新社区商业配套即将开业，品牌空白窗口期', tags: ['空白市场', '3.2万住户', '早期布局'], price: 599, locked: true },
    { id: 'opp-wh-001', type: '品牌红利窗口', type_key: 'brand_window', badge: '⚡ 限时', title: '古茗开放新城区代理', city: '武汉', district: '东湖新技术开发区', summary: '品牌官方开放该区域加盟申请，目前无竞争门店', tags: ['官方授权', '无竞争', '扩张期'], price: 599, locked: true },
    { id: 'opp-nb-001', type: '位置释放', type_key: 'release', badge: '📍 可用', title: '商场二楼奶茶区空铺', city: '宁波', district: '鄞州区', summary: '万象城二楼餐饮区奶茶档口空出，客流稳定', tags: ['商场位置', '稳定客流', '档口型'], price: 599, locked: false },
  ],
}

export default function Market() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [unlocking, setUnlocking] = useState(null)

  useEffect(() => {
    marketAPI.getOpportunities()
      .then(res => setData(res.data))
      .catch(() => setData(FALLBACK))
  }, [])

  const displayData = data || FALLBACK

  const handleUnlock = async (opp) => {
    setUnlocking(opp.id)
    try {
      const res = await checkoutAPI.createOrder(
        'opportunity', '', '', null, opp.id, null
      )
      const orderData = res.data
      if (orderData.payment_method === 'mock') {
        await checkoutAPI.mockPay(orderData.order_id)
        navigate(`/opportunity/${opp.id}?order_id=${orderData.order_id}`)
      } else {
        navigate('/checkout', { state: { orderData, opportunityId: opp.id } })
      }
    } catch (e) {
      navigate(`/opportunity/${opp.id}`)
    } finally {
      setUnlocking(null)
    }
  }

  return (
    <div className="min-h-screen bg-navy">
      <Header />
      <div className="pt-24 pb-16 px-4">
        <div className="max-w-3xl mx-auto">

          {/* Page Header */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-text-primary mb-2">机会集市</h1>
            <p className="text-text-secondary text-sm">
              AI持续扫描市场信号，主动发现稀缺选址机会。解锁即可查看完整地址和联系方式。
            </p>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-3 mb-8">
            {[
              { label: '本周新增', value: displayData.this_week_new, unit: '个' },
              { label: '位置释放', value: displayData.by_type?.release ?? 0, unit: '个' },
              { label: '新商圈', value: displayData.by_type?.new_district ?? 0, unit: '个' },
            ].map((s) => (
              <div key={s.label} className="card p-4 text-center">
                <div className="text-2xl font-bold text-text-primary">{s.value}</div>
                <div className="text-text-muted text-xs">{s.label}</div>
              </div>
            ))}
          </div>

          {/* Opportunity Cards */}
          <div className="space-y-4">
            {displayData.opportunities.map((opp) => {
              const style = TYPE_STYLE[opp.type_key] || TYPE_STYLE.release
              return (
                <div key={opp.id} className={`card border-l-4 ${style.border} ${style.bg} p-5`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex gap-2 items-center">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${style.badge}`}>
                        {opp.badge}
                      </span>
                      <span className="text-text-muted text-xs">{opp.type}</span>
                    </div>
                    <span className="text-text-muted text-xs flex-shrink-0">{opp.city} · {opp.district}</span>
                  </div>

                  <h3 className="text-text-primary font-semibold mb-2">{opp.title}</h3>

                  {opp.locked ? (
                    <div className="relative mb-3">
                      <p className="text-text-secondary text-sm blur-sm select-none">
                        {opp.summary}，具体地址：XX路XX号，联系人：XXXX，房租参考：XXXX元/月
                      </p>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-text-muted text-xs">🔒 解锁后查看完整信息</span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-text-secondary text-sm mb-3">{opp.summary}</p>
                  )}

                  <div className="flex gap-2 flex-wrap mb-4">
                    {opp.tags.map((tag) => (
                      <span key={tag} className="text-xs bg-card-border text-text-muted px-2 py-0.5 rounded">
                        {tag}
                      </span>
                    ))}
                  </div>

                  {opp.locked ? (
                    <button
                      onClick={() => handleUnlock(opp)}
                      disabled={unlocking === opp.id}
                      className="w-full border border-warning text-warning py-2.5 text-sm font-semibold rounded-btn hover:bg-warning/10 transition-colors disabled:opacity-50"
                    >
                      {unlocking === opp.id ? '处理中...' : `解锁完整机会 ¥${opp.price}`}
                    </button>
                  ) : (
                    <button
                      onClick={() => navigate(`/opportunity/${opp.id}`)}
                      className="w-full bg-primary hover:bg-primary-hover text-white py-2.5 text-sm font-semibold rounded-btn transition-colors"
                    >
                      查看完整详情 →
                    </button>
                  )}
                </div>
              )
            })}
          </div>

          <div className="mt-10 p-4 border border-card-border rounded-card">
            <p className="text-text-muted text-xs text-center">
              机会信息基于公开数据AI分析，不保证时效性。解锁后仍需实地核查，平台不承担投资决策责任。
            </p>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  )
}
