import { useNavigate } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'

export default function Profile() {
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/')
  }

  return (
    <div>
      <Navbar />
      <div className="max-w-md mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">👤 个人中心</h1>

        <div className="bg-white rounded-card shadow-card p-6 mb-4">
          <div className="space-y-4">
            <div className="flex justify-between">
              <span className="text-text-sub">手机号</span>
              <span>138****8888</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-sub">注册时间</span>
              <span>2026-03-31</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-sub">已购报告</span>
              <span className="text-primary font-medium">2 份</span>
            </div>
          </div>
        </div>

        <button
          onClick={handleLogout}
          className="w-full border border-red-300 text-red-500 py-3 rounded-btn hover:bg-red-50"
        >
          退出登录
        </button>
      </div>
      <Footer />
    </div>
  )
}
