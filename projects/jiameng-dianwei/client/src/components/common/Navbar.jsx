import { Link } from 'react-router-dom'
import { APP_NAME } from '../../config/constants'

export default function Navbar() {
  const token = localStorage.getItem('token')

  return (
    <nav className="bg-white shadow-sm sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2">
          <span className="text-2xl">🧋</span>
          <span className="text-lg font-bold text-primary">{APP_NAME}</span>
        </Link>

        {/* 右侧按钮 */}
        <div className="flex items-center gap-3">
          {token ? (
            <>
              <Link to="/my-reports" className="text-sm text-text-sub hover:text-primary">
                我的报告
              </Link>
              <Link to="/profile" className="text-sm text-text-sub hover:text-primary">
                个人中心
              </Link>
            </>
          ) : (
            <Link
              to="/login"
              className="bg-primary text-white px-4 py-1.5 rounded-btn text-sm hover:bg-primary-dark"
            >
              登录
            </Link>
          )}
        </div>
      </div>
    </nav>
  )
}
