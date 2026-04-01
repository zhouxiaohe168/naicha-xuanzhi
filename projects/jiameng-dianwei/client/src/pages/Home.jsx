import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import {
  TARGET_BRANDS,
  ANCHOR_CATEGORIES,
  DEFAULT_ANCHORS,
  JINHUA_LOCATIONS,
  RADIUS_OPTIONS,
  DEFAULT_RADIUS,
} from '../config/constants'

export default function Home() {
  const navigate = useNavigate()
  const [step, setStep]                   = useState(1)
  const [selectedBrand, setSelectedBrand] = useState('')
  const [selectedAnchors, setSelectedAnchors] = useState([])
  const [anchorTab, setAnchorTab]         = useState('tea')
  const [city, setCity]                   = useState('')
  const [district, setDistrict]           = useState('')
  const [street, setStreet]               = useState('')
  const [radius, setRadius]               = useState(DEFAULT_RADIUS)

  // ── step 1: pick brand ──────────────────────────────────
  const handleSelectBrand = (brandName) => {
    setSelectedBrand(brandName)
    setSelectedAnchors(DEFAULT_ANCHORS[brandName] || DEFAULT_ANCHORS['其他品牌'])
    setStep(2)
  }

  // ── step 2: toggle anchor ───────────────────────────────
  const toggleAnchor = (name) => {
    setSelectedAnchors(prev =>
      prev.includes(name) ? prev.filter(a => a !== name) : [...prev, name]
    )
  }

  // ── step 3: cascading location ──────────────────────────
  const cities    = Object.keys(JINHUA_LOCATIONS)
  const districts = city ? Object.keys(JINHUA_LOCATIONS[city]) : []
  const streets   = city && district ? JINHUA_LOCATIONS[city][district] : []

  const handleCityChange = (v) => {
    setCity(v); setDistrict(''); setStreet('')
    // 如果该城市只有一个区直接选中
    const keys = v ? Object.keys(JINHUA_LOCATIONS[v]) : []
    if (keys.length === 1) { setDistrict(keys[0]) }
  }
  const handleDistrictChange = (v) => { setDistrict(v); setStreet('') }

  // ── submit ──────────────────────────────────────────────
  const canSubmit = selectedBrand && city && district && street
  const handleSearch = () => {
    if (!canSubmit) return
    const p = new URLSearchParams({
      brand:   selectedBrand,
      anchors: selectedAnchors.join(','),
      city, district, street,
      radius:  String(radius),
    })
    navigate(`/results?${p.toString()}`)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      {/* ── Hero + 向导 ── */}
      <section className="bg-white border-b border-gray-100">
        <div className="max-w-3xl mx-auto px-4 py-14">
          {/* 标题 */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 bg-orange-50 border border-orange-200 rounded-full px-3 py-1 text-xs text-primary font-medium mb-4">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              实时查询高德地图数据 · 金华全域覆盖
            </div>
            <h1 className="text-4xl font-black text-gray-900 mb-3 leading-tight tracking-tight">
              找对位置，少走弯路
            </h1>
            <p className="text-sm text-gray-400">
              选品牌 → 选锚点 → 选地址 → 看竞品数据
            </p>
          </div>

          {/* 向导卡片 */}
          <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">

            {/* ── Step 1: 品牌 ── */}
            <div className="p-6 border-b border-gray-100">
              <StepHeader n={1} title="我要开什么品牌？" />
              <div className="flex flex-wrap gap-2 mt-4">
                {TARGET_BRANDS.map(b => (
                  <button
                    key={b.name}
                    onClick={() => handleSelectBrand(b.name)}
                    className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium border transition-all ${
                      selectedBrand === b.name
                        ? 'bg-primary text-white border-primary shadow-sm'
                        : 'bg-gray-50 text-gray-600 border-gray-200 hover:border-primary hover:text-primary'
                    }`}
                  >
                    <span>{b.icon}</span>{b.name}
                  </button>
                ))}
              </div>
            </div>

            {/* ── Step 2: 锚点 ── */}
            {step >= 2 && (
              <div className="p-6 border-b border-gray-100 bg-gray-50/40">
                <StepHeader n={2} title="参考哪些品牌已在附近？" />
                <p className="text-xs text-gray-400 mt-0.5 mb-3 ml-8">
                  系统会统计这些品牌在你选的街道周边的密度，帮你判断客流潜力
                </p>

                {/* 品类 Tab */}
                <div className="flex gap-1.5 ml-8 mb-3">
                  {ANCHOR_CATEGORIES.map(cat => (
                    <button
                      key={cat.id}
                      onClick={() => setAnchorTab(cat.id)}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                        anchorTab === cat.id
                          ? 'bg-gray-900 text-white'
                          : 'bg-white text-gray-500 border border-gray-200 hover:border-gray-400'
                      }`}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>

                {/* 品牌 chips */}
                <div className="flex flex-wrap gap-2 ml-8">
                  {ANCHOR_CATEGORIES.find(c => c.id === anchorTab)?.brands.map(name => (
                    <button
                      key={name}
                      onClick={() => toggleAnchor(name)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                        selectedAnchors.includes(name)
                          ? 'bg-primary/10 text-primary border-primary/40'
                          : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400'
                      }`}
                    >
                      {selectedAnchors.includes(name) ? '✓ ' : ''}{name}
                    </button>
                  ))}
                </div>

                {selectedAnchors.length > 0 && (
                  <p className="text-xs text-gray-400 mt-2 ml-8">
                    已选 {selectedAnchors.length} 个锚点：{selectedAnchors.join('、')}
                  </p>
                )}

                {/* 进入 step 3 */}
                {step === 2 && (
                  <button
                    onClick={() => setStep(3)}
                    className="ml-8 mt-4 px-4 py-1.5 bg-gray-900 text-white text-xs rounded-lg font-medium hover:bg-gray-700 transition-colors"
                  >
                    下一步：选地址 →
                  </button>
                )}
              </div>
            )}

            {/* ── Step 3: 地址 ── */}
            {step >= 3 && (
              <div className="p-6 border-b border-gray-100">
                <StepHeader n={3} title="查询哪个街道的数据？" />
                <p className="text-xs text-gray-400 mt-0.5 mb-4 ml-8">
                  系统会查询该街道周边的所有竞品门店
                </p>

                <div className="ml-8 grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {/* 城市/县市 */}
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">城市 / 县市</label>
                    <select
                      value={city}
                      onChange={e => handleCityChange(e.target.value)}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 bg-white"
                    >
                      <option value="">请选择</option>
                      {cities.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>

                  {/* 区/县 */}
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">区 / 县</label>
                    <select
                      value={district}
                      onChange={e => handleDistrictChange(e.target.value)}
                      disabled={!city}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 bg-white disabled:bg-gray-50 disabled:text-gray-400"
                    >
                      <option value="">请选择</option>
                      {districts.map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </div>

                  {/* 街道/镇 */}
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">街道 / 镇</label>
                    <select
                      value={street}
                      onChange={e => setStreet(e.target.value)}
                      disabled={!district}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 bg-white disabled:bg-gray-50 disabled:text-gray-400"
                    >
                      <option value="">请选择</option>
                      {streets.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                </div>

                {/* 查询半径 */}
                <div className="ml-8 mt-4">
                  <label className="block text-xs text-gray-500 mb-2">查询半径</label>
                  <div className="flex gap-2">
                    {RADIUS_OPTIONS.map(opt => (
                      <button
                        key={opt.value}
                        onClick={() => setRadius(opt.value)}
                        className={`px-4 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                          radius === opt.value
                            ? 'bg-primary text-white border-primary'
                            : 'bg-white text-gray-500 border-gray-200 hover:border-primary hover:text-primary'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ── CTA ── */}
            <div className="p-4 bg-gray-50/30">
              <button
                onClick={handleSearch}
                disabled={!canSubmit}
                className={`w-full py-3 rounded-xl text-sm font-bold transition-all ${
                  canSubmit
                    ? 'bg-primary text-white hover:bg-orange-600 active:scale-[0.99] shadow-sm'
                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                }`}
              >
                {!selectedBrand
                  ? '第一步：选择目标品牌'
                  : step < 3
                    ? '第二步：选择参考锚点，然后点下一步'
                    : !canSubmit
                      ? '请完整选择地址（城市→区→街道）'
                      : `查询 ${street} 周边竞品数据 →`
                }
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── 数据说明 ── */}
      <section className="max-w-3xl mx-auto px-4 py-12">
        <h2 className="text-xl font-bold text-gray-900 mb-6 text-center">查询后你能看到什么？</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              icon: (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                </svg>
              ),
              title: '竞品密度地图',
              desc: '各锚点品牌在该街道的门店数量，判断客流是否已被验证',
              tag: '免费预览',
            },
            {
              icon: (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              ),
              title: '空白机会分析',
              desc: '锚点在、目标品牌不在——你的潜在开店窗口',
              tag: '¥9.9',
            },
            {
              icon: (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              ),
              title: 'AI 开店研判',
              desc: 'AI 综合分析 + 预计回本周期 + 具体位置建议',
              tag: '¥59.9',
            },
          ].map(f => (
            <div key={f.title} className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md transition-all hover:-translate-y-0.5">
              <div className="w-8 h-8 bg-gray-50 border border-gray-200 rounded-lg flex items-center justify-center text-gray-600 mb-3">
                {f.icon}
              </div>
              <div className="flex items-center gap-2 mb-1.5">
                <h3 className="text-sm font-bold text-gray-900">{f.title}</h3>
                <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-gray-50 text-gray-500 border border-gray-200">{f.tag}</span>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── 定价 ── */}
      <section id="pricing" className="bg-white border-y border-gray-100">
        <div className="max-w-3xl mx-auto px-4 py-12">
          <h2 className="text-xl font-bold text-gray-900 mb-2 text-center">透明定价</h2>
          <p className="text-sm text-gray-400 text-center mb-8">一次付费，永久查看该报告</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="bg-white border border-gray-200 rounded-xl p-6">
              <div className="text-xs text-gray-400 font-medium mb-3 uppercase tracking-wide">竞品报告</div>
              <div className="flex items-end gap-1 mb-1">
                <span className="text-4xl font-black text-gray-900">¥9.9</span>
                <span className="text-gray-400 mb-1.5 text-sm">/ 次</span>
              </div>
              <p className="text-xs text-gray-400 mb-5">一杯奶茶的钱，看清周边竞品</p>
              <ul className="space-y-2 text-sm text-gray-500 mb-6">
                {['各品牌门店数量统计', '竞品评分与人均消费', '竞争饱和度指数', '空白机会位置列表'].map(t => (
                  <li key={t} className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 shrink-0" />{t}
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-gray-900 rounded-xl p-6 text-white relative overflow-hidden">
              <div className="absolute top-4 right-4 bg-primary text-white text-xs px-2.5 py-0.5 rounded-full font-semibold">推荐</div>
              <div className="text-xs text-gray-400 font-medium mb-3 uppercase tracking-wide">AI 研判报告</div>
              <div className="flex items-end gap-1 mb-1">
                <span className="text-4xl font-black">¥59.9</span>
                <span className="text-gray-400 mb-1.5 text-sm">/ 次</span>
              </div>
              <p className="text-xs text-gray-500 mb-5">一个决策的代价，换十万本金的安全感</p>
              <ul className="space-y-2 text-sm text-gray-400 mb-6">
                {['包含所有竞品报告内容', 'AI 综合评分（满分 10 分）', '品牌专属开店建议', '预计日均出杯 + 回本周期', '最优位置具体推荐'].map(t => (
                  <li key={t} className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />{t}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA bar ── */}
      <section className="max-w-3xl mx-auto px-4 py-12">
        <div className="bg-primary rounded-2xl p-8 text-center text-white">
          <h2 className="text-xl font-bold mb-2">开店前，先找对位置</h2>
          <p className="text-white/70 mb-5 text-sm">9.9 元一杯奶茶的钱，可能帮你避开几十万的选址失误</p>
          <button
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            className="inline-block bg-white text-primary px-7 py-2.5 rounded-xl text-sm font-bold hover:bg-orange-50 transition-colors"
          >
            立即开始选址 →
          </button>
        </div>
      </section>

      <Footer />
    </div>
  )
}

function StepHeader({ n, title }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-6 h-6 rounded-full bg-primary text-white text-xs font-bold flex items-center justify-center shrink-0">
        {n}
      </span>
      <span className="text-sm font-semibold text-gray-900">{title}</span>
    </div>
  )
}
