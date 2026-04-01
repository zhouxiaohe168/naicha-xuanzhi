import { Link } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'

export default function Home() {
  return (
    <div className="min-h-screen bg-[#FFF8F0]">
      <Navbar />

      {/* ── Hero ── */}
      <section className="relative overflow-hidden py-20 px-4">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 right-0 w-96 h-96 bg-primary/5 rounded-full translate-x-1/3 -translate-y-1/3" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-secondary/5 rounded-full -translate-x-1/3 translate-y-1/3" />
        </div>

        <div className="relative max-w-3xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-white border border-orange-100 rounded-full px-4 py-1.5 text-sm text-primary font-medium mb-6 shadow-sm">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            已覆盖金华市全部核心商圈
          </div>

          <h1 className="text-4xl md:text-5xl font-bold text-text-main mb-5 leading-tight">
            开奶茶店选址，
            <br />
            <span className="text-primary">AI 帮你做决定</span>
          </h1>
          <p className="text-lg text-text-sub mb-10 max-w-xl mx-auto leading-relaxed">
            不用实地考察，花 <strong className="text-primary">9.9 元</strong>看清周边竞品；
            花 <strong className="text-primary">59.9 元</strong>让 AI 直接告诉你「这里能不能开店」
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/districts"
              className="inline-block bg-primary text-white px-8 py-3.5 rounded-xl text-base font-semibold hover:bg-primary-dark transition-all shadow-lg shadow-primary/20 hover:-translate-y-0.5"
            >
              免费查看商圈列表 →
            </Link>
            <a
              href="#pricing"
              className="inline-block bg-white text-text-main px-8 py-3.5 rounded-xl text-base font-medium border border-gray-200 hover:border-primary hover:text-primary transition-all"
            >
              查看定价
            </a>
          </div>

          <div className="mt-10 flex flex-wrap justify-center gap-6 text-sm text-text-sub">
            <span>✅ 数据每周更新</span>
            <span>✅ AI 分析 30 秒出结果</span>
            <span>✅ 一次付费永久查看</span>
          </div>
        </div>
      </section>

      {/* ── 三大核心功能 ── */}
      <section className="max-w-5xl mx-auto px-4 py-12">
        <h2 className="text-2xl font-bold text-center text-text-main mb-2">一站式选址工具</h2>
        <p className="text-center text-text-sub mb-10">从数据到决策，全程 AI 辅助</p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            {
              icon: '📊',
              title: '商圈竞品分析',
              desc: '周边奶茶咖啡店数量、品牌分布、饱和度一目了然，比实地调研更全面',
              tag: '¥9.9',
              tagColor: 'bg-orange-50 text-primary',
              border: 'border-orange-100',
            },
            {
              icon: '🤖',
              title: 'AI 开店研判',
              desc: 'AI 综合评分 + 详细开店建议，30秒告诉你「这里适不适合开」',
              tag: '¥59.9',
              tagColor: 'bg-purple-50 text-purple-600',
              border: 'border-purple-100',
            },
            {
              icon: '📍',
              title: '品牌专项分析',
              desc: '针对蜜雪冰城、瑞幸、喜茶等品牌的专属选址建议，精准匹配',
              tag: '即将上线',
              tagColor: 'bg-gray-100 text-text-sub',
              border: 'border-gray-100',
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
      <section className="max-w-4xl mx-auto px-4 py-12">
        <h2 className="text-2xl font-bold text-center text-text-main mb-10">三步完成选址决策</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { step: '01', title: '选择商圈', desc: '浏览金华市所有核心商圈，找到你感兴趣的目标位置' },
            { step: '02', title: '查看数据', desc: '付 9.9 元解锁竞品分析，看清周边竞争格局和品牌分布' },
            { step: '03', title: 'AI 出结论', desc: '付 59.9 元获得 AI 研判，30秒给你「能开 / 不建议开」的明确建议' },
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
      <section id="pricing" className="max-w-4xl mx-auto px-4 py-12">
        <h2 className="text-2xl font-bold text-center text-text-main mb-2">透明定价</h2>
        <p className="text-center text-text-sub mb-10">一次付费，永久查看该商圈报告</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-2xl mx-auto">
          {/* 基础版 */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-8">
            <div className="text-text-sub text-sm font-medium mb-2">基础报告</div>
            <div className="flex items-end gap-1 mb-1">
              <span className="text-4xl font-bold text-text-main">¥9.9</span>
              <span className="text-text-sub mb-1.5 text-sm">/ 次</span>
            </div>
            <p className="text-xs text-text-sub mb-6">一杯奶茶的钱，看清商圈竞品</p>
            <ul className="space-y-3 text-sm text-text-sub mb-8">
              {[
                '周边奶茶咖啡店总数',
                '主要品牌分布列表',
                '商圈人流量等级',
                '竞争饱和度指数',
              ].map((t) => (
                <li key={t} className="flex items-center gap-2">
                  <span className="text-green-500 text-base">✓</span> {t}
                </li>
              ))}
            </ul>
            <Link
              to="/districts"
              className="block w-full text-center bg-price-bg text-primary py-3 rounded-xl text-sm font-semibold hover:bg-orange-100 transition-colors"
            >
              查看商圈
            </Link>
          </div>

          {/* AI 版 */}
          <div className="bg-gradient-to-b from-primary to-primary-dark rounded-2xl p-8 text-white relative overflow-hidden">
            <div className="absolute top-4 right-4 bg-white/20 text-white text-xs px-2.5 py-0.5 rounded-full font-medium">
              推荐
            </div>
            <div className="text-white/70 text-sm font-medium mb-2">AI 研判报告</div>
            <div className="flex items-end gap-1 mb-1">
              <span className="text-4xl font-bold">¥59.9</span>
              <span className="text-white/70 mb-1.5 text-sm">/ 次</span>
            </div>
            <p className="text-xs text-white/60 mb-6">一个决策的代价，换十万本金的安全感</p>
            <ul className="space-y-3 text-sm text-white/80 mb-8">
              {[
                '包含所有基础报告内容',
                'AI 综合评分（满分 10 分）',
                '竞争风险深度分析',
                '开店可行性明确建议',
                '推荐适配加盟品牌',
              ].map((t) => (
                <li key={t} className="flex items-center gap-2">
                  <span className="text-white text-base">✓</span> {t}
                </li>
              ))}
            </ul>
            <Link
              to="/districts"
              className="block w-full text-center bg-white text-primary py-3 rounded-xl text-sm font-semibold hover:bg-orange-50 transition-colors"
            >
              立即使用
            </Link>
          </div>
        </div>
      </section>

      {/* ── CTA Banner ── */}
      <section className="mx-4 md:mx-auto max-w-4xl mb-16">
        <div className="bg-gradient-to-r from-primary to-secondary rounded-2xl p-10 text-center text-white">
          <h2 className="text-2xl font-bold mb-2">开店前，先问问 AI</h2>
          <p className="text-white/80 mb-6 text-sm max-w-md mx-auto">
            9.9 元一杯奶茶的钱，可能帮你避开几十万的选址失误
          </p>
          <Link
            to="/districts"
            className="inline-block bg-white text-primary px-8 py-3 rounded-xl font-semibold hover:bg-orange-50 transition-colors shadow-lg"
          >
            立即查看金华商圈 →
          </Link>
        </div>
      </section>

      <Footer />
    </div>
  )
}
