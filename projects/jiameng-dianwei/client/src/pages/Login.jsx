import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import api from '../config/api'

export default function Login() {
  const navigate = useNavigate()
  const [phone, setPhone]       = useState('')
  const [code, setCode]         = useState('')
  const [countdown, setCountdown] = useState(0)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')
  const [codeSent, setCodeSent] = useState(false)

  const sendCode = async () => {
    if (!phone || phone.length !== 11) { setError('请输入正确的 11 位手机号'); return }
    setError('')
    try {
      await api.post('/auth/send-code', { phone })
      setCodeSent(true)
      setCountdown(60)
      const timer = setInterval(() => {
        setCountdown((prev) => { if (prev <= 1) { clearInterval(timer); return 0 } return prev - 1 })
      }, 1000)
    } catch {
      setError('验证码发送失败，请稍后重试')
    }
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!phone || !code) { setError('请填写手机号和验证码'); return }
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/auth/login', { phone, code })
      localStorage.setItem('token', res.token)
      navigate('/districts')
    } catch (err) {
      setError(err.response?.data?.detail || '验证码错误，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#FFF8F0] flex flex-col">
      {/* 简化顶栏 */}
      <div className="bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <span className="text-2xl">🧋</span>
          <span className="text-lg font-bold text-primary">奶茶选址通</span>
        </Link>
        <Link to="/districts" className="text-sm text-text-sub hover:text-primary transition-colors">
          先看商圈 →
        </Link>
      </div>

      {/* 登录卡片 */}
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          {/* 标题 */}
          <div className="text-center mb-8">
            <div className="text-5xl mb-4">🧋</div>
            <h1 className="text-2xl font-bold text-text-main mb-1">登录 / 注册</h1>
            <p className="text-sm text-text-sub">手机号登录，新用户自动注册</p>
          </div>

          <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-8">
            {/* 错误提示 */}
            {error && (
              <div className="mb-5 flex items-center gap-2 px-4 py-3 bg-red-50 border border-red-100 text-red-600 text-sm rounded-xl">
                <span>⚠️</span> {error}
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-4">
              {/* 手机号 */}
              <div>
                <label className="block text-xs font-medium text-text-sub mb-1.5">手机号</label>
                <input
                  type="tel"
                  placeholder="请输入 11 位手机号"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  maxLength={11}
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
                />
              </div>

              {/* 验证码 */}
              <div>
                <label className="block text-xs font-medium text-text-sub mb-1.5">验证码</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="请输入验证码"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    maxLength={6}
                    className="flex-1 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
                  />
                  <button
                    type="button"
                    onClick={sendCode}
                    disabled={countdown > 0}
                    className={`px-4 py-3 rounded-xl text-sm font-medium whitespace-nowrap transition-all ${
                      countdown > 0
                        ? 'bg-gray-100 text-text-sub cursor-not-allowed'
                        : 'bg-price-bg text-primary hover:bg-orange-100'
                    }`}
                  >
                    {countdown > 0 ? `${countdown}s` : '获取验证码'}
                  </button>
                </div>
                {codeSent && !error && (
                  <p className="text-xs text-green-600 mt-1.5">✓ 验证码已发送</p>
                )}
              </div>

              {/* 登录按钮 */}
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-primary text-white py-3.5 rounded-xl text-base font-semibold hover:bg-primary-dark disabled:opacity-60 transition-all shadow-sm shadow-primary/20 mt-2"
              >
                {loading ? '登录中...' : '登录 / 注册'}
              </button>
            </form>

            {/* 微信登录 */}
            <div className="mt-5">
              <div className="flex items-center gap-3 my-4">
                <div className="flex-1 border-t border-gray-100" />
                <span className="text-xs text-text-sub">或</span>
                <div className="flex-1 border-t border-gray-100" />
              </div>
              <button
                onClick={() => alert('微信登录功能即将上线')}
                className="w-full flex items-center justify-center gap-2 border border-gray-200 py-3 rounded-xl text-sm font-medium text-text-sub hover:border-green-400 hover:text-green-600 transition-all"
              >
                <span className="text-lg">💚</span> 微信一键登录
              </button>
            </div>
          </div>

          <p className="text-center text-xs text-text-sub mt-6">
            登录即代表同意
            <span className="text-primary cursor-pointer hover:underline mx-1">用户协议</span>
            和
            <span className="text-primary cursor-pointer hover:underline mx-1">隐私政策</span>
          </p>
        </div>
      </div>
    </div>
  )
}
