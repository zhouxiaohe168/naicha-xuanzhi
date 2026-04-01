import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import { TARGET_BRANDS, ANCHOR_BRANDS, DEFAULT_ANCHORS } from '../config/constants'

export default function Home() {
  const navigate = useNavigate()
  const [selectedBrand, setSelectedBrand] = useState('')
  const [selectedAnchors, setSelectedAnchors] = useState([])
  const [step, setStep] = useState(1) // 1: 选品牌, 2: 选锚点

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
    <div className="min-h-screen bg-[#FFF8F0]">
      <Navbar />

      {/* ── Hero ── */}
      <section className="relative overflow-hidden py-16 px-4">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 right-0 w-96 h-96 bg-primary/5 rounded-full translate-x-1/3 -translate-y-1/3" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-secondary/5 rounded-full -translate-x-1/3 translate-y-1/3" />
        </div>

        <div className="relative max-w-2xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-white border border-orange-100 rounded-full px-4 py-1.5 text-sm text-primary font-medium mb-6 shadow-sm">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            已覆盖金华市全部核心商圈
          </div>

          <h1 className="text-4xl md:text-5xl font-bold text-text-main mb-4 leading-tight">
            找对位置，少走弯路
          </h1>
          <p className="text-lg text-text-sub mb-10 max-w-lg mx-auto">
            告诉我你要开什么品牌，AI 帮你找金华最优位置
          </p>

          {/* ── 选址向导卡片 ── */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-lg p-6 text-left">

            {/* Step 1: 选品牌 */}
            <div className="mb-5">
              <p className="text-sm font-semibold text-text-main mb-3">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary text-white text-xs mr-2">1</span>
                我想开什么品牌？
              </p>
              <div className="flex flex-wrap gap-2">
                {TARGET_BRANDS.map(brand => (
                  <button
                    key={brand.name}
                    onClick={() => handleSelectBrand(brand.name)}
                    className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm font-medium border transition-all ${
                      selectedBrand === brand.name
                        ? 'bg-primary text-white border-primary shadow-sm shadow-primary/20'
                        : 'bg-gray-50 text-text-sub border-gray-200 hover:border-primary hover:text-primary'
                    }`}
                  >
                    <span>{brand.icon}</span>
                    {brand.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Step 2: 选锚点（选完品牌后出现） */}
            {step === 2 && (
              <div className="mb-5 pt-4 border-t border-gray-50">
                <p className="text-sm font-semibold text-text-main mb-1">
                  <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary text-white text-xs mr-2">2</span>
                  参考哪些品牌在附近？
                </p>
                <p className="text-xs text-text-sub mb-3 ml-7">这些品牌存在的地方，通常意味着客流量和消费力已被验证</p>
                <div className="flex flex-wrap gap-2">
                  {ANCHOR_BRANDS.map(anchor => (
                    <button
                      key={anchor.name}
                      onClick={() => toggleAnchor(anchor.name)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                        selectedAnchors.includes(anchor.name)
                          ? 'bg-orange-50 text-primary border-primary'
                          : 'bg-gray-50 text-text-sub border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <span>{anchor.icon}</span>
                      {anchor.name}
                      {selectedAnchors.includes(anchor.name) && <span className="text-primary">✓</span>}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* CTA */}
            <button
              onClick={step === 2 ? handleSearch : undefined}
              disabled={!selectedBrand}
              className={`w-full py-3.5 rounded-xl text-base font-semibold transition-all ${
                selectedBrand
                  ? 'bg-primary text-white hover:bg-primary-dark shadow-sm shadow-primary/20 hover:-translate-y-0.5'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
            >
              {step === 1
                ? '选择品牌后查找位置 →'
                : `查找 ${selectedBrand} 的最优位置 →`}
            </button>

            {step === 2 && (
              <p className="text-center text-xs text-text-sub mt-3">
                也可以
                <Link to="/districts" className="text-primary hover:underline mx-1">
                  直接浏览全部商圈
                </Link>
              </p>
            )}
          </div>

          <div className="mt-6 flex flex-wrap justify-center gap-5 text-sm text-text-sub">
            <span>✅ 数据每周更新</span>
            <span>✅ AI 分析 30 秒出结果</span>
            <span>✅ 一次付费永久查看</span>
          </div>
        </div>
      </section>

      {/* ── 三大核心功能 ── */}
      <section className="max-w-5xl mx-auto px-4 py-10">
        <h2 className="text-2xl font-bold text-center text-text-main mb-2">选址决策全流程</h2>
        <p className="text-center text-text-sub mb-10">从数据到结论，全程 AI 辅助</p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            {
              icon: '🎯',
              title: '空白点雷达',
              desc: '找出锚点品牌在、但目标品牌不在的位置——这就是你的机会窗口',
              tag: '核心功能',
              tagColor: 'bg-orange-50 text-primary',
              border: 'border-orange-100',
            },
            {
              icon: '📊',
              title: '竞品评分分析',
              desc: '周边奶茶咖啡品牌评分、人均消费、竞争饱和度，比实地调研更全面',
              tag: '¥9.9',
              tagColor: 'bg-orange-50 text-primary',
              border: 'border-orange-100',
            },
            {
              icon: '🤖',
              title: 'AI 开店研判',
              desc: 'AI 综合评分 + 预计回本周期 + 具体位置建议，30秒给你明确答案',
              tag: '¥59.9',
              tagColor: 'bg-purple-50 text-purple-600',
              border: 'border-purple-100',
            },
          ].map((item) => (
            <div
              key={item.title}
              className={`bg-white rounded-2xl border ${item.border} p-6 shadow-card hover:shadow-md transition-all hover:-translate-y-0.5`}
            >
              <div className="text-4xl mb-4">{item.icon}</div>
              <div className="flex items-start justify-between mb-3">
                <h3 className="text-lg font-semibold text-text-main">{item.title}</h3>
                <span className={`text-xs px-2.5 py-1 rounded-full font-medium shrink-0 ml-2 ${item.tagColor}`}>
                  {item.tag}
                </span>
              </div>
              <p className="text-sm text-text-sub leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── 使用流程 ── */}
      <section className="max-w-4xl mx-auto px-4 py-10">
        <h2 className="text-2xl font-bold text-center text-text-main mb-10">三步找到最优位置</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { step: '01', title: '选品牌和锚点', desc: '告诉我你要开什么，参考哪些品牌在附近，系统帮你智能筛选' },
            { step: '02', title: '查商圈适配分', desc: '看哪个商圈对你的品牌最友好，竞争少、流量高、锚点多' },
            { step: '03', title: 'AI 出结论',    desc: '付费获取 AI 研判，给你具体位置建议和预计回本周期' },
          ].map((item, i) => (
            <div key={item.step} className="relative">
              {i < 2 && (
                <div className="hidden md:flex absolute top-8 right-0 translate-x-1/2 z-10 text-gray-300 text-xl items-center">→</div>
              )}
              <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6 text-center h-full">
                <div className="w-10 h-10 bg-primary/10 text-primary rounded-full flex items-center justify-center text-sm font-bold mx-auto mb-4">
                  {item.step}
                </div>
                <h3 className="font-semibold text-text-main mb-2">{item.title}</h3>
                <p className="text-sm text-text-sub leading-relaxed">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── 定价 ── */}
      <section id="pricing" className="max-w-4xl mx-auto px-4 py-10">
        <h2 className="text-2xl font-bold text-center text-text-main mb-2">透明定价</h2>
        <p className="text-center text-text-sub mb-10">一次付费，永久查看该商圈报告</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-2xl mx-auto">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-8">
            <div className="text-text-sub text-sm font-medium mb-2">竞品报告</div>
            <div className="flex items-end gap-1 mb-1">
              <span className="text-4xl font-bold text-text-main">¥9.9</span>
              <span className="text-text-sub mb-1.5 text-sm">/ 次</span>
            </div>
            <p className="text-xs text-text-sub mb-6">一杯奶茶的钱，看清商圈竞品</p>
            <ul className="space-y-3 text-sm text-text-sub mb-8">
              {['周边奶茶咖啡店总数', '主要品牌分布+评分', '竞品人均消费对比', '竞争饱和度指数'].map(t => (
                <li key={t} className="flex items-center gap-2">
                  <span className="text-green-500 text-base">✓</span> {t}
                </li>
              ))}
            </ul>
            <Link to="/districts" className="block w-full text-center bg-price-bg text-primary py-3 rounded-xl text-sm font-semibold hover:bg-orange-100 transition-colors">
              查看商圈
            </Link>
          </div>

          <div className="bg-gradient-to-b from-primary to-primary-dark rounded-2xl p-8 text-white relative overflow-hidden">
            <div className="absolute top-4 right-4 bg-white/20 text-white text-xs px-2.5 py-0.5 rounded-full font-medium">推荐</div>
            <div className="text-white/70 text-sm font-medium mb-2">AI 研判报告</div>
            <div className="flex items-end gap-1 mb-1">
              <span className="text-4xl font-bold">¥59.9</span>
              <span className="text-white/70 mb-1.5 text-sm">/ 次</span>
            </div>
            <p className="text-xs text-white/60 mb-6">一个决策的代价，换十万本金的安全感</p>
            <ul className="space-y-3 text-sm text-white/80 mb-8">
              {['包含所有竞品报告内容', 'AI 综合评分（满分 10 分）', '品牌专属开店建议', '预计日均出杯 + 回本周期', '最优位置具体推荐'].map(t => (
                <li key={t} className="flex items-center gap-2">
                  <span className="text-white text-base">✓</span> {t}
                </li>
              ))}
            </ul>
            <Link to="/districts" className="block w-full text-center bg-white text-primary py-3 rounded-xl text-sm font-semibold hover:bg-orange-50 transition-colors">
              立即使用
            </Link>
          </div>
        </div>
      </section>

      {/* ── CTA Banner ── */}
      <section className="mx-4 md:mx-auto max-w-4xl mb-16">
        <div className="bg-gradient-to-r from-primary to-secondary rounded-2xl p-10 text-center text-white">
          <h2 className="text-2xl font-bold mb-2">开店前，先找对位置</h2>
          <p className="text-white/80 mb-6 text-sm max-w-md mx-auto">
            9.9 元一杯奶茶的钱，可能帮你避开几十万的选址失误
          </p>
          <button
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            className="inline-block bg-white text-primary px-8 py-3 rounded-xl font-semibold hover:bg-orange-50 transition-colors shadow-lg"
          >
            立即开始选址 →
          </button>
        </div>
      </section>

      <Footer />
    </div>
  )
}
