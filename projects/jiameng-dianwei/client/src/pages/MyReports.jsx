import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'
import api from '../config/api'

export default function MyReports() {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    if (!localStorage.getItem('token')) { navigate('/login'); return }
    api.get('/reports')
      .then(setReports)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div>
      <Navbar />
      <div className="text-center py-24 text-text-sub">加载中...</div>
    </div>
  )

  return (
    <div>
      <Navbar />
      <div className="max-w-4xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">📋 我的报告</h1>

        {reports.length === 0 ? (
          <div className="text-center py-16 text-text-sub">
            <div className="text-4xl mb-4">📭</div>
            <p>还没有购买过报告</p>
            <Link to="/districts" className="text-primary hover:underline mt-2 inline-block">
              去看看商圈 →
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {reports.map((report) => (
              <Link
                key={`${report.type}-${report.id}`}
                to={
                  report.type === 'ai_report'
                    ? `/districts/${report.district_id}/ai-report`
                    : `/districts/${report.district_id}`
                }
                className="block bg-white rounded-card shadow-card p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">📍 {report.district_name}</h3>
                    <p className="text-sm text-text-sub mt-1">
                      {report.created_at ? new Date(report.created_at).toLocaleDateString('zh-CN') : ''}
                    </p>
                  </div>
                  <div className="text-right flex flex-col items-end gap-1">
                    <span className={`text-sm px-3 py-1 rounded-full ${
                      report.type === 'ai_report'
                        ? 'bg-gradient-to-r from-primary to-secondary text-white'
                        : 'bg-price-bg text-primary'
                    }`}>
                      {report.type === 'ai_report' ? 'AI研判' : '基础报告'}
                    </span>
                    {report.ai_score != null && (
                      <span className="text-sm font-bold text-primary">评分 {report.ai_score}</span>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
      <Footer />
    </div>
  )
}
