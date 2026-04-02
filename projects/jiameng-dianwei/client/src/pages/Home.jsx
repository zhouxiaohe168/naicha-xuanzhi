import { useNavigate } from 'react-router-dom'
import Header from '../components/Header'
import Footer from '../components/Footer'

const advantages = [
  {
    icon: '🔗',
    title: 'AI多源数据融合',
    desc: '整合高德POI、企查查工商、百度指数等多维数据源，交叉验证，消除单一数据盲区',
  },
  {
    icon: '📡',
    title: '品牌生态雷达扫描',
    desc: '星巴克÷蜜雪冰城消费力指数，锁定奶茶加盟黄金赛道，精准判断区域消费层级',
  },
  {
    icon: '📈',
    title: '品牌扩张轨迹追踪',
    desc: '追踪目标品牌近6个月开店数据，识别快速扩张区域，抢先布局高潜力城市',
  },
  {
    icon: '💡',
    title: '机会主动发现',
    desc: '竞品撤店、新商圈崛起等信号实时监控，机会出现第一时间推送，不错过黄金窗口',
  },
]

const pricingPlans = [
  {
    name: '位置信息包',
    price: '59',
    borderColor: 'border-t-text-muted',
    badge: null,
    features: [
      '周边竞品数量与分布',
      '人流量与消费层级评分',
      '交通配套与曝光度评估',
      '区域消费力指数',
    ],
    cta: '立即获取',
    variant: 'outline',
  },
  {
    name: 'AI深度报告',
    price: '299',
    borderColor: 'border-t-primary',
    badge: '最受欢迎',
    features: [
      '包含位置信息包全部内容',
      'AI综合评分（A/B/C/D级）',
      '品牌选择匹配度分析',
      '多城市横向对比',
      '实地核查清单（PDF）',
      '品牌扩张轨迹追踪',
    ],
    cta: '获取AI报告',
    variant: 'primary',
  },
  {
    name: '机会解锁',
    price: '599',
    borderColor: 'border-t-warning',
    badge: '高价值',
    features: [
      'AI主动发现的稀缺机会',
      '竞品撤店位置独家信息',
      '新商圈崛起早期预警',
      '品牌红利窗口精准时机',
      '完整商圈数据包',
    ],
    cta: '解锁机会',
    variant: 'warning',
  },
]

export default function Home() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-navy">
      <Header />

      {/* Hero */}
      <section className="pt-32 pb-24 px-4 text-center">
        <div className="inline-flex items-center gap-2 bg-card-bg border border-card-border rounded-full px-4 py-1.5 text-sm text-text-secondary mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-success inline-block"></span>
          实数据 · 真机会 · 你决策
        </div>

        <h1 className="text-4xl md:text-6xl font-bold text-text-primary leading-tight mb-6">
          找到你的奶茶加盟<br />
          <span className="text-primary">黄金位置</span>
        </h1>

        <p className="text-text-secondary text-lg md:text-xl mb-10 max-w-xl mx-auto">
          实数据 · AI研判 · 你决策 — 比实地考察快100倍
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
          <button
            onClick={() => navigate('/wizard')}
            className="btn-primary px-8 py-3.5 text-base"
          >
            免费体验一次
          </button>
          <button
            onClick={() => navigate('/sample')}
            className="btn-outline px-8 py-3.5 text-base"
          >
            查看样本报告
          </button>
        </div>

        {/* Stats Badges */}
        <div className="flex flex-wrap justify-center gap-4">
          {[
            { icon: '📍', value: '覆盖全国', sub: '持续扩展中' },
            { icon: '📊', value: '50+ 品牌', sub: '主流加盟品牌' },
            { icon: '⚡', value: 'AI大数据', sub: '多源实时分析' },
          ].map((s) => (
            <div key={s.value} className="card px-5 py-3 flex items-center gap-3">
              <span className="text-xl">{s.icon}</span>
              <div className="text-left">
                <div className="text-text-primary font-semibold text-sm">{s.value}</div>
                <div className="text-text-muted text-xs">{s.sub}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Advantages */}
      <section className="py-20 px-4">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-center text-2xl md:text-3xl font-bold text-text-primary mb-3">
            为什么选择探铺
          </h2>
          <p className="text-center text-text-secondary mb-12">AI大数据驱动，让每一个选址决策都有数据支撑</p>

          <div className="grid md:grid-cols-2 gap-5">
            {advantages.map((a) => (
              <div key={a.title} className="card p-6 border-l-2 border-l-primary">
                <div className="text-2xl mb-3">{a.icon}</div>
                <h3 className="text-text-primary font-semibold mb-2">{a.title}</h3>
                <p className="text-text-secondary text-sm leading-relaxed">{a.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 px-4" style={{ background: 'rgba(17,24,39,0.3)' }}>
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-2xl md:text-3xl font-bold text-text-primary mb-12">三步获得AI研判报告</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { step: '01', title: '选择品牌和预算', desc: '告诉我们你想开什么，打算投多少' },
              { step: '02', title: '选定目标城市', desc: '圈定意向区域，我们扫描全部数据' },
              { step: '03', title: '获取AI研判结果', desc: '数分钟内拿到综合评分和完整报告' },
            ].map((s) => (
              <div key={s.step} className="card p-6">
                <div className="text-primary font-mono font-bold text-3xl mb-3">{s.step}</div>
                <h3 className="text-text-primary font-semibold mb-2">{s.title}</h3>
                <p className="text-text-secondary text-sm">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-20 px-4">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-center text-2xl md:text-3xl font-bold text-text-primary mb-3">透明定价，按需购买</h2>
          <p className="text-center text-text-secondary mb-12">无订阅，无月费，用多少买多少</p>

          <div className="grid md:grid-cols-3 gap-6">
            {pricingPlans.map((plan) => (
              <div key={plan.name} className={`card p-6 border-t-2 ${plan.borderColor} relative`}>
                {plan.badge && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-white text-xs font-semibold px-3 py-1 rounded-full whitespace-nowrap">
                    {plan.badge}
                  </div>
                )}
                <h3 className="text-text-primary font-semibold mb-1">{plan.name}</h3>
                <div className="text-3xl font-bold text-text-primary mb-4">
                  ¥{plan.price}
                  <span className="text-sm font-normal text-text-secondary"> /次</span>
                </div>
                <ul className="space-y-2 mb-6">
                  {plan.features.map((f) => (
                    <li key={f} className="text-text-secondary text-sm flex items-start gap-2">
                      <span className="text-success mt-0.5">✓</span>
                      {f}
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => navigate(plan.variant === 'warning' ? '/market' : '/wizard')}
                  className={`w-full py-2.5 text-sm font-semibold rounded-btn transition-colors ${
                    plan.variant === 'primary'
                      ? 'bg-primary hover:bg-primary-hover text-white'
                      : plan.variant === 'warning'
                      ? 'border border-warning text-warning hover:bg-warning/10'
                      : 'border border-card-border text-text-primary hover:border-primary'
                  }`}
                >
                  {plan.cta}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Market CTA */}
      <section className="py-16 px-4">
        <div className="max-w-3xl mx-auto card p-8 border border-warning/30 text-center">
          <div className="text-3xl mb-3">💡</div>
          <h2 className="text-xl font-bold text-text-primary mb-2">机会集市</h2>
          <p className="text-text-secondary text-sm mb-6">
            AI主动发现竞品撤店、新商圈崛起等稀缺机会，你只需要决定要不要解锁
          </p>
          <button
            onClick={() => navigate('/market')}
            className="border border-warning text-warning px-6 py-2.5 text-sm font-semibold rounded-btn hover:bg-warning/10 transition-colors"
          >
            查看当前机会 →
          </button>
        </div>
      </section>

      <Footer />
    </div>
  )
}
