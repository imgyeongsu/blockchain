import { NavLink, Outlet } from 'react-router-dom'

const NAV = [
  { to: '/',         label: '홈',     icon: '⬡' },
  { to: '/wallet',   label: '지갑',   icon: '💳' },
  { to: '/exchange', label: '교환',   icon: '🔄' },
  { to: '/lotto',    label: '로또',   icon: '🎰' },
  { to: '/explorer', label: '탐색기', icon: '🔍' },
  { to: '/network',  label: '네트워크', icon: '🌐' },
]

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#080808', fontFamily: 'monospace' }}>
      {/* Top nav */}
      <nav
        className="sticky top-0 z-50 flex items-center justify-between px-4 py-3"
        style={{
          background: 'rgba(8,8,8,0.85)',
          backdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
        }}
      >
        <NavLink to="/" className="flex items-center gap-2 no-underline">
          <span className="text-lg font-bold" style={{ color: '#007AFF' }}>싸또</span>
          <span className="text-lg font-bold" style={{ color: '#FFD700' }}>777</span>
        </NavLink>
        <div className="flex items-center gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) =>
                `px-2 py-1 rounded-lg text-xs transition-colors no-underline ${
                  isActive
                    ? 'text-white'
                    : 'text-gray-500 hover:text-gray-300'
                }`
              }
              style={({ isActive }) =>
                isActive ? { background: 'rgba(0,122,255,0.15)', color: '#007AFF' } : {}
              }
            >
              <span className="hidden sm:inline">{n.label}</span>
              <span className="sm:hidden">{n.icon}</span>
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Page content */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* Bottom nav (mobile) */}
      <nav
        className="sm:hidden fixed bottom-0 left-0 right-0 z-50 flex justify-around py-2"
        style={{
          background: 'rgba(8,8,8,0.95)',
          backdropFilter: 'blur(20px)',
          borderTop: '1px solid rgba(255,255,255,0.07)',
        }}
      >
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === '/'}
            className="flex flex-col items-center gap-0.5 px-2 no-underline"
            style={({ isActive }) => ({ color: isActive ? '#007AFF' : '#555' })}
          >
            <span className="text-xl">{n.icon}</span>
            <span className="text-[9px]">{n.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
