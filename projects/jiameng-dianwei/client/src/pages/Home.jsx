import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import { TARGET_BRANDS, ANCHOR_BRANDS, DEFAULT_ANCHORS } from '../config/constants'

const STATS = [
  { value: '10+', label: '金华核心商圈' },
  { value: '341', label: '蜜雪门店已分析' },
  { value: '53', label: '空白机会位置' },
  { value: '¥9.9', label: '竞品报告起步价' },
]

const FEATURES = [
  {
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
      </svg>
    ),
    title: '空白点雷达',
    desc: '找出锚点品牌在、目标品牌不在的位置——你的机会窗口',
    tag: '核心',
    tagStyle: 'bg-orange-50 text-primary border border-orange-200',
  },
  {
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
    title: '竞品评分分析',
    desc: '周边品牌评分、人均消费、竞争饱和度，比实地调研更全面',
    tag: '¥9.9',
    tagStyle: 'bg-gray-50 text-gray-600 border border-gray-200',
  },
  {
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
    title: 'AI 开店研判',
    desc: 'AI 综合评分 + 预计回本周期 + 具体位置建议，30秒明确答案',
    tag: '¥59.9',
    tagStyle: 'bg-purple-50 text-purple-600 border border-purple-200',
  },
]

export default function Home() {
  const navigate = useNavigate()
  const [selectedBrand, setSelectedBrand] = useState('')
  const [selectedAnchors, setSelectedAnchors] = useState([])
  const [step, setStep] = useState(1)

  const handleSelectBrand = (brandName) => {
    setSelectedBrand(brandName)
    setSelectedAnchors(DEFAULT_ANCHORS[brandName] || DEFAULT_ANCHORS['其他品牌'])
    setStep(2)
  }

  const toggleAnchor = (anchorName) => {
    setSelectedAnchors(prev =>
      prev.includes(anchorName)
        ? prev.filter(a => a !== anchorName)
        : [...prev, anchorName]
    )
  }

  const handleSearch = () => {
    const params = new URLSearchParams()
    if (selectedBrand) params.set('brand', selectedBrand)
    if (selectedAnchors.length) params.set('anchors', selectedAnchors.join(','))
    navigate(`/districts?${params.toString()}`)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      {/* ── Hero ── */}
      <section className="bg-white border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-4 py-16">
          <div className="max-w-2xl mx-auto text-center mb-10">
            <div className="inline-flex items-center gap-2 bg-orange-50 border border-orange-200 rounded-full px-3 py-1 text-xs text-primary font-medium mb-5">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              已覆盖金华市全部核心商圈
            </div>
            <h1 className="text-4xl md:text-5xl font-black text-gray-900 mb-4 leading-tight tracking-tight">
              找对位置<span className="text-primary">，</span><br className="md:hidden" />少走弯路
            </h1>
            <p className="text-base text-gray-500 max-w-md mx-auto">
              告诉我你要开什么品牌，AI 帮你找金华最优位置
            </p>
          </div>

          {/* 选址向导 */}
          <div className="max-w-2xl mx-auto bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">
            {/* Step 1 */}
            <div className="p-6 border-b border-gray-100">
              <div className="flex items-center gap-2 mb-4">
                <span className="w-6 h-6 rounded-full bg-primary text-white text-xs font-bold flex items-center justify-center">1</span>
                <span className="text-sm font-semibold text-gray-900">我想开什么品牌？</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {TARGET_BRANDS.map(brand => (
                  <button
                    key={brand.name}
                    onClick={() => handleSelectBrand(brand.name)}
                    className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium border transition-all ${
                      selectedBrand === brand.name
                        ? 'bg-primary text-white border-primary'
                        : 'bg-gray-50 text-gray-600 border-gray-200 hover:border-primary hover:text-primary'
                    }`}
                  >
                    <span>{brand.icon}</span>
                    {brand.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Step 2 */}
            {step === 2 && (
              <div className="p-6 border-b border-gray-100 bg-gray-50/50">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-6 h-6 rounded-full bg-primary text-white text-xs font-bold flex items-center justify-center">2</span>
                  <span className="text-sm font-semibold text-gray-900">参考哪些品牌在附近？</span>
                </div>
                <p className="text-xs text-gray-400 mb-3 ml-8">这些品牌存在的地方，通常意味着客流量已被验证</p>
                <div className="flex flex-wrap gap-2 ml-8">
                  {ANCHOR_BRANDS.map(anchor => (
                    <button
                      key={anchor.name}
                      onClick={() => toggleAnchor(anchor.name)}
                      className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                        selectedAnchors.includes(anchor.name)
                          ? 'bg-primary/10 text-primary border-primary/30'
                          : 'bg-white text-gray-500 border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <span>{anchor.icon}</span>
                      {anchor.name}
                      {selectedAnchors.includes(anchor.name) && <span className="text-primary ml-0.5">✓</span>}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* CTA */}
            <div className="p-4">
              <button
                onClick={step === 2 ? handleSearch : undefined}
                disabled={!selectedBrand}
                className={`w-full py-3 rounded-xl text-sm font-bold transition-all ${
                  selectedBrand
                    ? 'bg-primary text-white hover:bg-orange-600 active:scale-[0.99]'
                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                }`}
              >
                {step === 1 ? '选择品牌后开始分析 →' : `查找 ${selectedBrand} 的最优位置 →`}
              </button>
              {step === 2 && (
                <p className="text-center text-xs text-gray-400 mt-2">
                  也可以 <Link to="/districts" className="text-primary hover:underline">直接浏览全部商圈</Link>
                </p>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ── 数据统计 ── */}
      <section className="bg-white border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-4 py-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {STATS.map((s) => (
              <div key={s.label} className="text-center">
                <div className="text-3xl font-black text-gray-900 mb-1">{s.value}</div>
                <div className="text-xs text-gray-400">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 三大功能 ── */}
      <section className="max-w-5xl mx-auto px-4 py-14">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">选址决策全流程</h2>
          <p className="text-gray-400 text-sm">从数据到结论，全程 AI 辅助</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {FEATURES.map((f) => (
            <div key={f.title} className="bg-white border border-gray-200 rounded-xl p-6 hover:shadow-md transition-all hover:-translate-y-0.5">
              <div className="w-9 h-9 bg-gray-50 border border-gray-200 rounded-lg flex items-center justify-center text-gray-600 mb-4">
                {f.icon}
              </div>
              <div className="flex items-center gap-2 mb-2">
                <h3 className="text-sm font-bold text-gray-900">{f.title}</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${f.tagStyle}`}>{f.tag}</span>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── 使用步骤 ── */}
      <section className="bg-white border-y border-gray-100">
        <div className="max-w-5xl mx-auto px-4 py-14">
          <h2 className="text-2xl font-bold text-center text-gray-900 mb-10">三步找到最优位置</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 relative">
            {[
              { n: '01', title: '选品牌和锚点', desc: '告诉我你要开什么，参考哪些品牌，系统智能筛选适配商圈' },
              { n: '02', title: '查商圈适配分', desc: '看哪个商圈对你的品牌最友好——竞争少、锚点多、潜力高' },
              { n: '03', title: 'AI 出结论', desc: '付费获取 AI 研判，具体位置建议 + 预计回本周期' },
            ].map((item, i) => (
              <div key={item.n} className="relative flex gap-4 bg-gray-50 rounded-xl p-5 border border-gray-200">
                <div className="shrink-0 w-10 h-10 bg-primary/10 text-primary rounded-lg flex items-center justify-center text-sm font-black">
                  {item.n}
                </div>
                <div>
                  <h3 className="text-sm font-bold text-gray-900 mb-1">{item.title}</h3>
                  <p className="text-xs text-gray-500 leading-relaxed">{item.desc}</p>
                </div>
                {i < 2 && (
                  <div className="hidden md:flex absolute -right-3 top-1/2 -translate-y-1/2 z-10 w-6 h-6 bg-white border border-gray-200 rounded-full items-center justify-center">
                    <svg className="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 定价 ── */}
      <section id="pricing" className="max-w-5xl mx-auto px-4 py-14">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">透明定价</h2>
          <p className="text-gray-400 text-sm">一次付费，永久查看该商圈报告</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 max-w-2xl mx-auto">
          <div className="bg-white border border-gray-200 rounded-xl p-7">
            <div className="text-xs text-gray-400 font-medium mb-3 uppercase tracking-wide">竞品报告</div>
            <div className="flex items-end gap-1 mb-1">
              <span className="text-4xl font-black text-gray-900">¥9.9</span>
              <span className="text-gray-400 mb-1.5 text-sm">/ 次</span>
            </div>
            <p className="text-xs text-gray-400 mb-6">一杯奶茶的钱，看清商圈竞品</p>
            <ul className="space-y-2.5 text-sm text-gray-500 mb-7">
              {['周边奶茶咖啡店总数', '主要品牌分布+评分', '竞品人均消费对比', '竞争饱和度指数'].map(t => (
                <li key={t} className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 shrink-0" />
                  {t}
                </li>
              ))}
            </ul>
            <Link to="/districts" className="block w-full text-center border border-primary text-primary py-2.5 rounded-lg text-sm font-semibold hover:bg-orange-50 transition-colors">
              查看商圈
            </Link>
          </div>

          <div className="bg-gray-900 rounded-xl p-7 text-white relative overflow-hidden">
            <div className="absolute top-4 right-4 bg-primary text-white text-xs px-2.5 py-0.5 rounded-full font-semibold">推荐</div>
            <div className="text-xs text-gray-400 font-medium mb-3 uppercase tracking-wide">AI 研判报告</div>
            <div className="flex items-end gap-1 mb-1">
              <span className="text-4xl font-black">¥59.9</span>
              <span className="text-gray-400 mb-1.5 text-sm">/ 次</span>
            </div>
            <p className="text-xs text-gray-500 mb-6">一个决策的代价，换十万本金的安全感</p>
            <ul className="space-y-2.5 text-sm text-gray-400 mb-7">
              {['包含所有竞品报告内容', 'AI 综合评分（满分 10 分）', '品牌专属开店建议', '预计日均出杯 + 回本周期', '最优位置具体推荐'].map(t => (
                <li key={t} className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                  {t}
                </li>
              ))}
            </ul>
            <Link to="/districts" className="block w-full text-center bg-primary text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-orange-600 transition-colors">
              立即使用
            </Link>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="max-w-5xl mx-auto px-4 pb-16">
        <div className="bg-primary rounded-2xl p-10 text-center text-white">
          <h2 className="text-2xl font-bold mb-2">开店前，先找对位置</h2>
          <p className="text-white/70 mb-6 text-sm">9.9 元一杯奶茶的钱，可能帮你避开几十万的选址失误</p>
          <button
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            className="inline-block bg-white text-primary px-8 py-2.5 rounded-xl text-sm font-bold hover:bg-orange-50 transition-colors"
          >
            立即开始选址 →
          </button>
        </div>
      </section>

      <Footer />
    </div>
  )
}
