import { useNavigate } from 'react-router-dom'
import Header from '../components/Header'
import Footer from '../components/Footer'

export default function SampleReport() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-navy">
      <Header />
      <div className="pt-24 pb-16 px-4">
        <div className="max-w-3xl mx-auto">

          {/* Banner */}
          <div className="card p-5 mb-8 border-primary/30 border text-center">
            <div className="text-xs text-primary font-semibold mb-1">📋 样本报告</div>
            <p className="text-text-secondary text-sm">以下为演示数据，真实报告需购买后生成</p>
          </div>

          {/* Sample Report Header */}
          <div className="card p-6 mb-6">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-text-muted text-xs mb-1">AI研判报告 · 样本</div>
                <h1 className="text-xl font-bold text-text-primary mb-1">蜜雪冰城 · 杭州拱墅区</h1>
                <p className="text-text-secondary text-sm">数据截止：2024-06-01</p>
              </div>
              <div className="flex flex-col items-center">
                <div className="w-16 h-16 rounded-full border-4 border-success flex items-center justify-center font-bold text-xl text-success">
                  A-
                </div>
                <div className="text-text-muted text-xs mt-1">综合评级</div>
              </div>
            </div>
            <div className="mt-4">
              <div className="flex justify-between text-xs text-text-secondary mb-1">
                <span>综合得分</span>
                <span className="text-success font-semibold">85/100</span>
              </div>
              <div className="h-2 bg-card-border rounded-full overflow-hidden">
                <div className="h-full bg-success rounded-full" style={{ width: '85%' }} />
              </div>
            </div>
          </div>

          {/* Data Overview */}
          <div className="card p-5 mb-6">
            <h2 className="text-text-primary font-semibold mb-4">数据概览</h2>
            <div className="space-y-3">
              {[
                { label: '周边竞品数量', value: '8家', note: '500m半径内', source: '高德POI' },
                { label: '日均人流量', value: '约11,500人', note: '工作日估算', source: '高德POI' },
                { label: '消费力指数', value: '82/100', note: '中高档', source: '百度指数' },
                { label: '品牌生态匹配', value: '极高', note: '古茗/茶百道伴生', source: '企查查' },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between">
                  <div>
                    <div className="text-text-primary font-semibold">{item.value}</div>
                    <div className="text-text-muted text-xs">{item.label} · {item.note}</div>
                  </div>
                  <span className="text-xs bg-card-border text-text-muted px-2 py-0.5 rounded">
                    来源: {item.source}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* AI Analysis */}
          <div className="card p-5 mb-6 border-primary/30 border">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded-full">AI研判</span>
            </div>
            <p className="text-text-secondary text-sm leading-relaxed">
              该区域综合评分85分（A-级），适合蜜雪冰城开店。主要优势：区域消费力指数较高，品牌生态完善，竞品密度在可控范围内。
              建议重点关注：拱墅区新开发区块的空白机会，较西湖区竞争更低，租金更合理。
              风险提示：区域内已有8家竞品，注意选址时与最近同类门店保持品牌规定距离。
            </p>
          </div>

          {/* CTA */}
          <div className="text-center">
            <p className="text-text-muted text-sm mb-4">想获取你的目标位置真实报告？</p>
            <button
              onClick={() => navigate('/wizard')}
              className="btn-primary px-8 py-3 text-base"
            >
              开始我的分析 →
            </button>
            <p className="text-text-muted text-xs mt-3">基础信息包 ¥59 · AI深度报告 ¥299</p>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  )
}
