import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Login from './pages/Login'
import Results from './pages/Results'
import MyReports from './pages/MyReports'
import Profile from './pages/Profile'

function App() {
  return (
    <div className="min-h-screen bg-bg-warm">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/results" element={<Results />} />
        <Route path="/my-reports" element={<MyReports />} />
        <Route path="/profile" element={<Profile />} />
      </Routes>
    </div>
  )
}

export default App
