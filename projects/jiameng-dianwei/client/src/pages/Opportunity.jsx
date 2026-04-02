import { useNavigate, useParams } from 'react-router-dom'
import Header from '../components/Header'
import Footer from '../components/Footer'

const mockOpportunity = {
  id: 'opp-004',
  type: '位置释放',
  title: '商场二楼奶茶区空铺',
  city: '宁波',
  district: '鄞州区',
  address: '鄞州区天童南路万象城二楼F区23号铺',
  area: '45㎡',
  rent: '约8,500元/月',
  contact: '商场招商部 · 张经理',
  summary: '万象城二楼餐饮区奶茶档口空出，客流稳定，周边无同类竞品，适合蜜雪冰城/古茗等平价品牌入驻。',
  metrics: [
    { label: '日均客流', value: '约12,000人', source: '高德POI' },
    { label: '周边竞品', value: '3家（均为高端）', source: '高德POI' },
    { label: '消费力指数', value: '75/100', source: '百度指数' },
    { label: '空铺时间', value: '预计下月起', source: '实地核实' },
    { label: '推荐品牌', value: '蜜雪冰城 / 古茗', source: 'AI分析' },
  ],
  analysis: 'AI判断该位置综合评分82/100（A-级），主要优势：客流稳定、竞品空白、位置曝光好。风险点：商场租金年增幅需确认，建议谈判锁定3年固定租金。',
  checklist: [
    '实地确认铺位尺寸和装修状况',
    '核实商场客流高峰时段分布',
    '确认品牌保护范围（同品牌最近门店距离）',
    '了解商场扣点比例（通常5-8%）',
    '查阅周边竞品近期营业状态',
  ],
}

export default function Opportunity() {
  const { id } = useParams()
  const navigate = useNavigate()
  const opp = mockOpportunity

  return (
    <div className="min-h-screen bg-navy">
      <Header />
      <div className="pt-24 pb-16 px-4">
        <div className="max-w-3xl mx-auto">

          {/* Back */}
          <button
            onClick={() => navigate('/market')}
            className="text-text-secondary text-sm hover:text-text-primary mb-6 flex items-center gap-1"
          >
            ← 返回机会集市
          </button>

          {/* Header Card */}
          <div className="card border-l-4 border-l-warning p-6 mb-6">
            <div className="flex items-start justify-between mb-3">
              <span className="bg-warning/20 text-warning text-xs px-2 py-0.5 rounded-full font-medium">
                {opp.type}
              </span>
              <span className="text-text-muted text-xs">{opp.city} · {opp.district}</span>
            </div>
            <h1 className="text-xl font-bold text-text-primary mb-4">{opp.title}</h1>

            <div className="grid grid-cols-2 gap-3">
              {[
                { label: '详细地址', value: opp.address },
                { label: '铺面面积', value: opp.area },
                { label: '参考租金', value: opp.rent },
                { label: '联系方式', value: opp.contact },
              ].map((item) => (
                <div key={item.label} className="bg-card-border/30 rounded-lg p-3">
                  <div className="text-text-muted text-xs mb-1">{item.label}</div>
                  <div className="text-text-primary text-sm font-medium">{item.value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Summary */}
          <div className="card p-5 mb-6">
            <h2 className="text-text-primary font-semibold mb-3">机会说明</h2>
            <p className="text-text-secondary text-sm leading-relaxed">{opp.summary}</p>
          </div>

          {/* Metrics */}
          <div className="card p-5 mb-6">
            <h2 className="text-text-primary font-semibold mb-4">核心数据</h2>
            <div className="space-y-3">
              {opp.metrics.map((m) => (
                <div key={m.label} className="flex items-center justify-between">
                  <div>
                    <div className="text-text-primary text-sm">{m.value}</div>
                    <div className="text-text-muted text-xs">{m.label}</div>
                  </div>
                  <span className="text-xs bg-card-border text-text-muted px-2 py-0.5 rounded">
                    来源: {m.source}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* AI Analysis */}
          <div className="card p-5 mb-6 border-primary/30 border">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded-full">AI分析</span>
            </div>
            <p className="text-text-secondary text-sm leading-relaxed">{opp.analysis}</p>
          </div>

          {/* Checklist */}
          <div className="card p-5 mb-6">
            <h2 className="text-text-primary font-semibold mb-4">实地核查清单</h2>
            <div className="space-y-3">
              {opp.checklist.map((item, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="w-5 h-5 rounded border-2 border-card-border flex-shrink-0 mt-0.5" />
                  <span className="text-text-secondary text-sm">{item}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Disclaimer */}
          <div className="p-4 border border-card-border rounded-card">
            <p className="text-text-muted text-xs text-center">
              本机会信息基于公开数据AI分析，仅供参考，不构成投资建议。<br />
              请实地核查后自主决策，平台不承担投资损失责任。
            </p>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  )
}
