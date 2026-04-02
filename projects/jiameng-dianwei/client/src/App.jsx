import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Wizard from './pages/Wizard'
import Report from './pages/Report'
import Market from './pages/Market'
import Opportunity from './pages/Opportunity'
import SampleReport from './pages/SampleReport'
import Checkout from './pages/Checkout'

function App() {
  return (
    <div className="min-h-screen bg-navy">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/wizard" element={<Wizard />} />
        <Route path="/report" element={<Report />} />
        <Route path="/market" element={<Market />} />
        <Route path="/opportunity/:id" element={<Opportunity />} />
        <Route path="/sample" element={<SampleReport />} />
        <Route path="/checkout" element={<Checkout />} />
      </Routes>
    </div>
  )
}

export default App
