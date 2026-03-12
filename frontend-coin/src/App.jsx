import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import { ToastContainer } from './components/Toast'
import Home from './pages/Home'
import Wallet from './pages/Wallet'
import Exchange from './pages/Exchange'
import Lotto from './pages/Lotto'
import LottoHistory from './pages/LottoHistory'
import Jackpot from './pages/Jackpot'
import Explorer from './pages/Explorer'
import Network from './pages/Network'
import Mining from './pages/Mining'

export default function App() {
  return (
    <BrowserRouter>
      <ToastContainer />
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/wallet" element={<Wallet />} />
          <Route path="/exchange" element={<Exchange />} />
          <Route path="/lotto" element={<Lotto />} />
          <Route path="/lotto/history" element={<LottoHistory />} />
          <Route path="/jackpot" element={<Jackpot />} />
          <Route path="/explorer" element={<Explorer />} />
          <Route path="/network" element={<Network />} />
          <Route path="/mining" element={<Mining />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
