import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Header from '../components/Header'
import Footer from '../components/Footer'

const tabs = ['数据概览', '品牌轨迹', '区域评分', '实地核查清单']

const gradeColor = {
  'A+': 'text-success border-success', 'A': 'text-success border-success', 'A-': 'text-success border-success',
  'B+': 'text-warning border-warning', 'B': 'text-warning border-warning', 'B-': 'text-warning border-warning',
  'C': 'text-danger border-danger', 'D': 'text-danger border-danger',
}

const gradeBarColor = {
  'A+': 'bg-success', 'A': 'bg-success', 'A-': 'bg-success',
  'B+': 'bg-warning', 'B': 'bg-warning', 'B-': 'bg-warning',
  'C': 'bg-danger', 'D': 'bg-danger',
}

const DEFAULT_CHECKLIST = [
  '确认店面面积是否达标（通常需30㎡以上）',
  '核实该街道是否已有同品牌（品牌保护距离）',
  '实地测量高峰期人流量（早8-9点、午12-13点）',
  '确认周边伴生品牌：古茗/茶百道是否存在',
  '查询最近6个月是否有同类门店撤店',
  '了解房东租期和租金年增幅条款',
  '确认排污、通风等店面基础条件',
]

function buildOverview(data) {
  if (!data) return []
  return [
    {
      label: `${data.brand || '目标品牌'}在该城市门店数`,
      value: `${data.data?.brand_count ?? '--'}家`,
      note: '高德POI实时数据',
      source: '高德POI',
    },
    {
      label: '主要竞品总数',
      value: `${data.data?.competitor_total ?? '--'}家`,
      note: '奶茶咖啡类门店合计',
      source: '高德POI',
    },
    {
      label: '消费力指数',
      value: `${data.data?.consumption_index ?? '--'}/100`,
      note: '高端/低端品牌密度比',
      source: '高德POI',
    },
    {
      label: '客流量级别',
      value: data.data?.traffic_level ?? '中',
      note: '根据竞品密度估算',
      source: '高德POI',
    },
    {
      label: '竞争饱和度',
      value: data.data?.saturation ?? '中',
      note: '该品牌在城市的密集程度',
      source: '高德POI',
    },
    ...(data.data?.ecosystem_brands?.length ? [{
      label: '活跃伴生品牌',
      value: data.data.ecosystem_brands.slice(0, 3).join('、'),
      note: '品牌生态共存验证',
      source: '高德POI',
    }] : []),
  ]
}

export default function Report() {
  const location = useLocation()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState(0)
  const [checklist, setChecklist] = useState(DEFAULT_CHECKLIST.map(c => ({ text: c, done: false })))

  const { reportData } = location.state || {}

  if (!reportData) {
    return (
      <div className="min-h-screen bg-navy flex items-center justify-center">
        <div className="text-center">
          <div className="text-text-secondary mb-4">找不到报告数据，请重新生成</div>
          <button onClick={() => navigate('/wizard')} className="bg-primary text-white px-6 py-2 rounded-btn font-semibold">
            重新开始
          </button>
        </div>
      </div>
    )
  }

  const { brand, city, grade, score, ai_analysis, data } = reportData
  const overview = buildOverview(reportData)
  const gradeCls = gradeColor[grade] || 'text-text-secondary border-text-secondary'
  const barCls = gradeBarColor[grade] || 'bg-text-secondary'
  const isAI = reportData.report_type === 'ai'

  const toggleCheck = (i) => {
    const updated = [...checklist]
    updated[i].done = !updated[i].done
    setChecklist(updated)
  }

  // mock trajectory for brand growth
  const trajectory = reportData.trajectory || [
    { month: '2024-01', count: 2 },
    { month: '2024-02', count: 1 },
    { month: '2024-03', count: 3 },
    { month: '2024-04', count: 4 },
    { month: '2024-05', count: 2 },
    { month: '2024-06', count: 5 },
  ]
  const maxCount = Math.max(...trajectory.map(t => t.count), 1)

  return (
    <div className="min-h-screen bg-navy">
      <Header />
      <div className="pt-24 pb-16 px-4">
        <div className="max-w-3xl mx-auto">

          {/* Report Header */}
          <div className="card p-6 mb-6">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-text-muted text-xs mb-1">AI研判报告 · {isAI ? '深度版' : '基础版'}</div>
                <h1 className="text-xl font-bold text-text-primary mb-1">{brand} · {city}</h1>
                <p className="text-text-secondary text-sm">生成时间：{new Date().toLocaleDateString('zh-CN')}</p>
              </div>
              <div className="flex flex-col items-center flex-shrink-0 ml-4">
                <div className={`w-16 h-16 rounded-full border-4 flex items-center justify-center font-bold text-xl ${gradeCls}`}>
                  {grade}
                </div>
                <div className="text-text-muted text-xs mt-1">综合评级</div>
              </div>
            </div>
            <div className="mt-4">
              <div className="flex justify-between text-xs text-text-secondary mb-1">
                <span>综合得分</span>
                <span className={`font-semibold ${gradeCls.split(' ')[0]}`}>{score}/100</span>
              </div>
              <div className="h-2 bg-card-border rounded-full overflow-hidden">
                <div className={`h-full ${barCls} rounded-full transition-all`} style={{ width: `${score}%` }} />
              </div>
            </div>
          </div>

          {/* AI Analysis Block（AI报告专属）*/}
          {isAI && ai_analysis && (
            <div className="card p-5 mb-6 border-primary/30 border">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded-full font-medium">⚡ AI研判</span>
                <span className="text-text-muted text-xs">Claude AI · 基于高德实时数据</span>
              </div>
              <p className="text-text-secondary text-sm leading-relaxed">{ai_analysis}</p>
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-1 bg-card-bg border border-card-border rounded-card p-1 mb-6">
            {tabs.map((t, i) => (
              <button
                key={t}
                onClick={() => setActiveTab(i)}
                className={`flex-1 py-2 text-xs font-medium rounded transition-colors ${
                  activeTab === i ? 'bg-primary text-white' : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Tab: 数据概览 */}
          {activeTab === 0 && (
            <div className="space-y-3">
              {overview.map((item) => (
                <div key={item.label} className="card p-4 flex items-center justify-between">
                  <div>
                    <div className="text-text-primary font-semibold">{item.value}</div>
                    <div className="text-text-muted text-xs">{item.label} · {item.note}</div>
                  </div>
                  <span className="text-xs bg-card-border text-text-muted px-2 py-0.5 rounded flex-shrink-0">
                    来源: {item.source}
                  </span>
                </div>
              ))}
              {!isAI && (
                <div className="card p-4 border-primary/30 border text-center">
                  <p className="text-text-secondary text-sm mb-2">升级AI深度报告获取更多维度分析</p>
                  <button
                    onClick={() => navigate('/wizard')}
                    className="text-primary text-sm font-semibold hover:underline"
                  >
                    升级到AI报告 ¥299 →
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Tab: 品牌轨迹 */}
          {activeTab === 1 && (
            <div className="card p-5">
              <h3 className="text-text-primary font-semibold mb-4">近6个月 {brand} {city}开店趋势</h3>
              <div className="space-y-2">
                {trajectory.map((t) => (
                  <div key={t.month} className="flex items-center gap-3">
                    <span className="text-text-muted text-xs w-16 flex-shrink-0">{t.month}</span>
                    <div className="flex-1 h-4 bg-card-border rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all"
                        style={{ width: `${(t.count / maxCount) * 100}%` }}
                      />
                    </div>
                    <span className="text-text-secondary text-sm w-8 text-right flex-shrink-0">+{t.count}</span>
                  </div>
                ))}
              </div>
              <p className="text-text-muted text-xs mt-4">
                {brand}近期扩张趋势：{data?.brand_count > 20 ? '积极扩张，品牌认可度高' : '稳步进入，仍有大量空白'}
              </p>
            </div>
          )}

          {/* Tab: 区域评分 */}
          {activeTab === 2 && (
            <div>
              <div className="space-y-3 mb-4">
                {[
                  { name: '商业综合体', score: Math.min(95, (score || 70) + 8), grade: 'A-', note: '客流稳定，竞争可控' },
                  { name: '成熟居住区', score: score || 72, grade: grade || 'B+', note: '消费稳定，口碑积累' },
                  { name: '新兴商圈', score: Math.max(40, (score || 70) - 5), grade: 'B', note: '待验证，早期红利' },
                  { name: '高端写字楼', score: Math.max(40, (score || 70) - 12), grade: 'B-', note: '消费层级不匹配' },
                ].map((d) => (
                  <div key={d.name} className="card p-4 flex items-center justify-between">
                    <div>
                      <div className="text-text-primary font-semibold">{d.name}</div>
                      <div className="text-text-muted text-xs">{d.note}</div>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <div className="text-text-secondary text-sm">{d.score}/100</div>
                      <div className={`font-bold ${(gradeColor[d.grade] || '').split(' ')[0]}`}>{d.grade}</div>
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-text-muted text-xs text-center">区域类型评分基于该城市整体数据推算</p>
            </div>
          )}

          {/* Tab: 实地核查清单 */}
          {activeTab === 3 && (
            <div>
              <div className="space-y-3 mb-6">
                {checklist.map((item, i) => (
                  <button
                    key={i}
                    onClick={() => toggleCheck(i)}
                    className={`card w-full p-4 text-left flex items-start gap-3 transition-colors ${
                      item.done ? 'border-success/40' : 'hover:border-primary/40'
                    }`}
                  >
                    <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 ${
                      item.done ? 'bg-success border-success' : 'border-card-border'
                    }`}>
                      {item.done && <span className="text-white text-xs">✓</span>}
                    </div>
                    <span className={`text-sm ${item.done ? 'text-text-muted line-through' : 'text-text-secondary'}`}>
                      {item.text}
                    </span>
                  </button>
                ))}
              </div>
              <div className="flex gap-3">
                <button className="flex-1 border border-card-border text-text-secondary py-2.5 text-sm rounded-btn hover:border-primary transition-colors">
                  重置清单
                </button>
                <button className="flex-1 border border-primary text-primary py-2.5 text-sm rounded-btn hover:bg-primary/10 transition-colors">
                  下载 PDF
                </button>
              </div>
            </div>
          )}

          {/* Disclaimer */}
          <div className="mt-8 p-4 border border-card-border rounded-card">
            <p className="text-text-muted text-xs text-center">
              本报告基于高德POI公开数据AI分析生成，仅供参考，不构成投资建议。<br />
              加盟决策风险由用户自行承担，请结合实地考察综合判断。
            </p>
          </div>

          {/* Upgrade CTA（基础报告底部）*/}
          {!isAI && (
            <div className="mt-6 card p-5 border-primary/30 border text-center">
              <p className="text-text-primary font-semibold mb-1">想要更深入的AI研判？</p>
              <p className="text-text-secondary text-sm mb-4">AI深度报告包含Claude AI研判文字、品牌匹配分析和实地核查清单PDF</p>
              <button
                onClick={() => navigate('/wizard')}
                className="bg-primary hover:bg-primary-hover text-white px-6 py-2.5 rounded-btn font-semibold text-sm transition-colors"
              >
                升级AI报告 ¥299
              </button>
            </div>
          )}
        </div>
      </div>
      <Footer />
    </div>
  )
}
