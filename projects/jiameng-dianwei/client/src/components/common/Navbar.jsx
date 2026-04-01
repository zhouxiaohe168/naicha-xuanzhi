import { Link, useNavigate } from 'react-router-dom'

export default function Navbar() {
  const navigate = useNavigate()
  const token = localStorage.getItem('token')

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/')
  }

  return (
    <nav className="bg-white/90 backdrop-blur-sm border-b border-gray-100 sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <span className="text-2xl">🧋</span>
          <span className="text-base font-bold text-primary">奶茶选址通</span>
        </Link>

        {/* 右侧 */}
        <div className="flex items-center gap-2">
          {token ? (
            <>
              <Link
                to="/my-reports"
                className="text-sm text-text-sub hover:text-primary transition-colors px-3 py-1.5 rounded-lg hover:bg-price-bg"
              >
                我的报告
              </Link>
              <Link
                to="/profile"
                className="text-sm text-text-sub hover:text-primary transition-colors px-3 py-1.5 rounded-lg hover:bg-price-bg"
              >
                个人中心
              </Link>
              <button
                onClick={handleLogout}
                className="text-sm text-text-sub hover:text-red-500 transition-colors px-3 py-1.5"
              >
                退出
              </button>
            </>
          ) : (
            <>
              <Link
                to="/districts"
                className="text-sm text-text-sub hover:text-primary transition-colors px-3 py-1.5 hidden sm:block"
              >
                查看商圈
              </Link>
              <Link
                to="/login"
                className="bg-primary text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-primary-dark transition-colors"
              >
                登录
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}
