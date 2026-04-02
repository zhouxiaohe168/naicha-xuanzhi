import { Link, useNavigate } from 'react-router-dom'

export default function Header() {
  const navigate = useNavigate()

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-card-border bg-navy/90 backdrop-blur-sm">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-white font-bold text-sm">探</div>
          <span className="text-text-primary font-semibold text-lg">探铺</span>
        </Link>

        {/* Nav */}
        <nav className="hidden md:flex items-center gap-8">
          <Link to="/wizard" className="text-text-secondary hover:text-text-primary transition-colors text-sm">品牌研判</Link>
          <Link to="/market" className="text-text-secondary hover:text-text-primary transition-colors text-sm">机会集市</Link>
          <Link to="/sample" className="text-text-secondary hover:text-text-primary transition-colors text-sm">样本报告</Link>
        </nav>

        {/* CTA */}
        <button
          onClick={() => navigate('/wizard')}
          className="btn-primary px-5 py-2 text-sm"
        >
          开始分析
        </button>
      </div>
    </header>
  )
}
