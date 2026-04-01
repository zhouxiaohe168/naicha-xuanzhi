import { Link } from 'react-router-dom'
import Navbar from '../components/common/Navbar'
import Footer from '../components/common/Footer'

// 临时mock数据
const MOCK_REPORTS = [
  { id: 1, district_name: '万达商圈', type: 'basic', amount: 9.9, created_at: '2026-03-31' },
  { id: 2, district_name: '江南商圈', type: 'ai', amount: 59.9, created_at: '2026-03-30' },
]

export default function MyReports() {
  return (
    <div>
      <Navbar />
      <div className="max-w-4xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">📋 我的报告</h1>

        {MOCK_REPORTS.length === 0 ? (
          <div className="text-center py-16 text-text-sub">
            <div className="text-4xl mb-4">📭</div>
            <p>还没有购买过报告</p>
            <Link to="/districts" className="text-primary hover:underline mt-2 inline-block">
              去看看商圈 →
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {MOCK_REPORTS.map((report) => (
              <Link
                key={report.id}
                to={report.type === 'ai'
                  ? `/reports/${report.id}/ai`
                  : `/districts/${report.id}`
                }
                className="block bg-white rounded-card shadow-card p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">📍 {report.district_name}</h3>
                    <p className="text-sm text-text-sub mt-1">{report.created_at}</p>
                  </div>
                  <div className="text-right">
                    <span className={`text-sm px-3 py-1 rounded-full ${
                      report.type === 'ai'
                        ? 'bg-gradient-to-r from-primary to-secondary text-white'
                        : 'bg-price-bg text-primary'
                    }`}>
                      {report.type === 'ai' ? 'AI研判' : '基础报告'}
                    </span>
                    <p className="text-sm text-text-sub mt-1">¥{report.amount}</p>
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
