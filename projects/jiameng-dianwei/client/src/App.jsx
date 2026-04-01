import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Login from './pages/Login'
import DistrictList from './pages/DistrictList'
import DistrictDetail from './pages/DistrictDetail'
import AIReport from './pages/AIReport'
import MyReports from './pages/MyReports'
import Profile from './pages/Profile'

function App() {
  return (
    <div className="min-h-screen bg-bg-warm">
      <Routes>
        {/* 首页/落地页 */}
        <Route path="/" element={<Home />} />
        {/* 登录注册 */}
        <Route path="/login" element={<Login />} />
        {/* 商圈列表 */}
        <Route path="/districts" element={<DistrictList />} />
        {/* 商圈详情 */}
        <Route path="/districts/:id" element={<DistrictDetail />} />
        {/* AI研判报告 */}
        <Route path="/reports/:id/ai" element={<AIReport />} />
        {/* 我的报告 */}
        <Route path="/my-reports" element={<MyReports />} />
        {/* 个人中心 */}
        <Route path="/profile" element={<Profile />} />
      </Routes>
    </div>
  )
}

export default App
