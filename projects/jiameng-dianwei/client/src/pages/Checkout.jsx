import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Header from '../components/Header'
import { checkoutAPI } from '../lib/api'

const PRODUCT_LABELS = {
  basic: '位置信息包',
  ai: 'AI深度报告',
  opportunity: '机会解锁',
}

const PRODUCT_PRICES = {
  basic: '59',
  ai: '299',
  opportunity: '599',
}

export default function Checkout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { orderData, reportData, opportunityId } = location.state || {}

  const [polling, setPolling] = useState(false)
  const [paid, setPaid] = useState(false)
  const [error, setError] = useState('')

  const isMock = orderData?.payment_method === 'mock'

  // 轮询订单状态（支付宝跳转回来后用）
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const oid = params.get('order_id') || orderData?.order_id
    if (!oid || !polling) return

    const timer = setInterval(async () => {
      try {
        const res = await checkoutAPI.getOrder(oid)
        if (res.data.status === 'paid') {
          clearInterval(timer)
          setPolling(false)
          setPaid(true)
          navigate('/report', {
            state: { orderId: oid, reportData: res.data.report_data || reportData }
          })
        }
      } catch (e) {
        clearInterval(timer)
        setPolling(false)
      }
    }, 2000)

    return () => clearInterval(timer)
  }, [polling])

  const handleMockPay = async () => {
    if (!orderData?.order_id) return
    try {
      await checkoutAPI.mockPay(orderData.order_id)
      navigate('/report', {
        state: { orderId: orderData.order_id, reportData }
      })
    } catch (e) {
      setError('支付确认失败，请重试')
    }
  }

  const handleAlipayPay = () => {
    if (!orderData?.pay_url) return
    // 打开支付宝支付页面
    window.location.href = orderData.pay_url
    // 开始轮询（用户支付完成会跳回来）
    setPolling(true)
  }

  if (!orderData) {
    return (
      <div className="min-h-screen bg-navy flex items-center justify-center">
        <div className="text-center">
          <div className="text-text-secondary mb-4">订单信息丢失，请重新生成</div>
          <button onClick={() => navigate('/wizard')} className="btn-primary px-6 py-2">
            重新开始
          </button>
        </div>
      </div>
    )
  }

  const productType = orderData.product_type
  const priceYuan = orderData.amount_yuan || PRODUCT_PRICES[productType]

  return (
    <div className="min-h-screen bg-navy">
      <Header />
      <div className="pt-24 pb-16 px-4">
        <div className="max-w-md mx-auto">

          {/* Order Summary */}
          <div className="card p-6 mb-6">
            <h1 className="text-lg font-bold text-text-primary mb-4">确认订单</h1>

            <div className="space-y-3 mb-4">
              <div className="flex justify-between">
                <span className="text-text-secondary text-sm">产品</span>
                <span className="text-text-primary font-semibold text-sm">
                  {PRODUCT_LABELS[productType] || productType}
                </span>
              </div>
              {orderData.brand && (
                <div className="flex justify-between">
                  <span className="text-text-secondary text-sm">品牌</span>
                  <span className="text-text-primary text-sm">{orderData.brand}</span>
                </div>
              )}
              {orderData.city && (
                <div className="flex justify-between">
                  <span className="text-text-secondary text-sm">城市</span>
                  <span className="text-text-primary text-sm">{orderData.city}</span>
                </div>
              )}
              <div className="border-t border-card-border pt-3 flex justify-between">
                <span className="text-text-primary font-semibold">实付金额</span>
                <span className="text-2xl font-bold text-primary">¥{priceYuan}</span>
              </div>
            </div>

            <p className="text-text-muted text-xs">
              订单号：{orderData.order_id}
            </p>
          </div>

          {/* Payment */}
          <div className="card p-6 mb-6">
            <h2 className="text-text-primary font-semibold mb-4">选择支付方式</h2>

            {isMock ? (
              // 开发/测试模式
              <div>
                <div className="p-4 bg-warning/10 border border-warning/30 rounded-card mb-4">
                  <p className="text-warning text-sm font-medium">🧪 测试模式</p>
                  <p className="text-text-secondary text-xs mt-1">
                    支付宝尚未配置，点击下方按钮直接模拟支付成功
                  </p>
                </div>
                <button
                  onClick={handleMockPay}
                  className="w-full bg-primary hover:bg-primary-hover text-white py-3 rounded-btn font-semibold transition-colors"
                >
                  模拟支付 ¥{priceYuan} →
                </button>
              </div>
            ) : (
              // 真实支付宝
              <div>
                <button
                  onClick={handleAlipayPay}
                  className="w-full flex items-center justify-center gap-3 bg-[#1677FF] hover:bg-blue-600 text-white py-3 rounded-btn font-semibold transition-colors"
                >
                  <span className="text-lg">💳</span>
                  支付宝支付 ¥{priceYuan}
                </button>
                {polling && (
                  <p className="text-center text-text-secondary text-sm mt-3">
                    等待支付确认中...
                  </p>
                )}
              </div>
            )}

            {error && (
              <p className="text-danger text-sm mt-3 text-center">{error}</p>
            )}
          </div>

          {/* Disclaimer */}
          <p className="text-center text-text-muted text-xs">
            付款后立即生成报告，无需等待。<br />
            本平台仅提供数据参考，不构成投资建议。
          </p>
        </div>
      </div>
    </div>
  )
}
