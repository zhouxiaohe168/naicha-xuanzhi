import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import { APP_NAME } from '../config/constants'

export default function Login() {
  const navigate = useNavigate()
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [codeSent, setCodeSent] = useState(false)
  const [countdown, setCountdown] = useState(0)

  // 发送验证码
  const sendCode = async () => {
    if (!phone || phone.length !== 11) {
      alert('请输入正确的手机号')
      return
    }
    // TODO: 调用后端发送短信验证码接口
    setCodeSent(true)
    setCountdown(60)
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  // 登录/注册
  const handleLogin = async (e) => {
    e.preventDefault()
    if (!phone || !code) {
      alert('请填写手机号和验证码')
      return
    }
    // TODO: 调用后端登录接口
    // const res = await api.post('/auth/login', { phone, code })
    // localStorage.setItem('token', res.token)
    localStorage.setItem('token', 'demo-token') // 临时mock
    navigate('/districts')
  }

  return (
    <div>
      <Navbar />
      <div className="max-w-md mx-auto px-4 py-16">
        <div className="bg-white rounded-card shadow-card p-8">
          <h2 className="text-2xl font-bold text-center mb-2">登录 {APP_NAME}</h2>
          <p className="text-sm text-text-sub text-center mb-8">
            手机号登录，新用户自动注册
          </p>

          <form onSubmit={handleLogin}>
            {/* 手机号 */}
            <div className="mb-4">
              <input
                type="tel"
                placeholder="请输入手机号"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                maxLength={11}
                className="w-full border border-gray-200 rounded-btn px-4 py-3 focus:outline-none focus:border-primary"
              />
            </div>

            {/* 验证码 */}
            <div className="flex gap-2 mb-6">
              <input
                type="text"
                placeholder="请输入验证码"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                maxLength={6}
                className="flex-1 border border-gray-200 rounded-btn px-4 py-3 focus:outline-none focus:border-primary"
              />
              <button
                type="button"
                onClick={sendCode}
                disabled={countdown > 0}
                className={`px-4 py-3 rounded-btn text-sm whitespace-nowrap ${
                  countdown > 0
                    ? 'bg-gray-100 text-text-sub cursor-not-allowed'
                    : 'bg-price-bg text-primary hover:bg-orange-100'
                }`}
              >
                {countdown > 0 ? `${countdown}秒` : '获取验证码'}
              </button>
            </div>

            {/* 登录按钮 */}
            <button
              type="submit"
              className="w-full bg-primary text-white py-3 rounded-btn text-lg font-medium hover:bg-primary-dark"
            >
              登录
            </button>
          </form>

          {/* 微信登录 */}
          <div className="mt-6 text-center">
            <div className="text-sm text-text-sub mb-3">—— 或 ——</div>
            <button
              className="w-full border border-green-500 text-green-600 py-3 rounded-btn hover:bg-green-50"
              onClick={() => alert('微信登录功能开发中')}
            >
              微信登录
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
