import { Link } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import { APP_NAME, APP_SLOGAN, APP_DESC } from '../config/constants'

export default function Home() {
  return (
    <div>
      <Navbar />

      {/* Hero区域 */}
      <section className="bg-gradient-to-b from-white to-bg-warm py-16 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-4xl md:text-5xl font-bold text-text-main mb-4">
            🧋 {APP_SLOGAN}
          </h1>
          <p className="text-lg text-text-sub mb-8">{APP_DESC}</p>
          <Link
            to="/districts"
            className="inline-block bg-primary text-white px-8 py-3 rounded-btn text-lg font-medium hover:bg-primary-dark transition-colors"
          >
            免费查看商圈 →
          </Link>
        </div>
      </section>

      {/* 三个卖点 */}
      <section className="max-w-4xl mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-card shadow-card p-6 text-center">
            <div className="text-4xl mb-3">📊</div>
            <h3 className="text-lg font-semibold mb-2">竞品分析</h3>
            <p className="text-sm text-text-sub">
              周边奶茶咖啡店数量、品牌分布、竞争密度一目了然
            </p>
          </div>
          <div className="bg-white rounded-card shadow-card p-6 text-center">
            <div className="text-4xl mb-3">🤖</div>
            <h3 className="text-lg font-semibold mb-2">AI研判</h3>
            <p className="text-sm text-text-sub">
              AI帮你判断"这个位置能不能开店"，给出评分和建议
            </p>
          </div>
          <div className="bg-white rounded-card shadow-card p-6 text-center">
            <div className="text-4xl mb-3">💰</div>
            <h3 className="text-lg font-semibold mb-2">9.9元起</h3>
            <p className="text-sm text-text-sub">
              一杯奶茶的钱，避免几十万的选址失误
            </p>
          </div>
        </div>
      </section>

      {/* 使用流程 */}
      <section className="max-w-4xl mx-auto px-4 py-12">
        <h2 className="text-2xl font-bold text-center mb-8">怎么用？</h2>
        <div className="flex flex-col md:flex-row items-center justify-center gap-4">
          <div className="flex items-center gap-2 bg-white rounded-card shadow-card px-6 py-4">
            <span className="text-2xl font-bold text-primary">①</span>
            <span>选商圈</span>
          </div>
          <span className="text-2xl text-text-sub hidden md:block">→</span>
          <div className="flex items-center gap-2 bg-white rounded-card shadow-card px-6 py-4">
            <span className="text-2xl font-bold text-primary">②</span>
            <span>看数据</span>
          </div>
          <span className="text-2xl text-text-sub hidden md:block">→</span>
          <div className="flex items-center gap-2 bg-white rounded-card shadow-card px-6 py-4">
            <span className="text-2xl font-bold text-primary">③</span>
            <span>AI建议</span>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-primary py-12 px-4 text-center">
        <h2 className="text-2xl font-bold text-white mb-4">
          开店选址不再靠感觉
        </h2>
        <p className="text-white/80 mb-6">
          已覆盖金华市核心商圈，数据每周更新
        </p>
        <Link
          to="/districts"
          className="inline-block bg-white text-primary px-8 py-3 rounded-btn text-lg font-medium hover:bg-gray-50"
        >
          立即查看 →
        </Link>
      </section>

      <Footer />
    </div>
  )
}
