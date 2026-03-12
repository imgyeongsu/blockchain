import { useState, useCallback } from 'react'

const COLORS = {
  success: '#00FF88',
  error: '#FF453A',
  info: '#007AFF',
  warning: '#FFD700',
}

let _setToasts = null

export function useToast() {
  const show = useCallback((message, type = 'info', duration = 3000) => {
    if (!_setToasts) return
    const id = Date.now()
    _setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      _setToasts((prev) => prev.filter((t) => t.id !== id))
    }, duration)
  }, [])
  return { show }
}

export function ToastContainer() {
  const [toasts, setToasts] = useState([])
  _setToasts = setToasts

  return (
    <div className="fixed top-16 right-4 z-[9999] flex flex-col gap-2" style={{ maxWidth: 320 }}>
      {toasts.map((t) => (
        <div
          key={t.id}
          className="glass-card px-4 py-3 text-sm flex items-center gap-2"
          style={{
            borderColor: `${COLORS[t.type]}40`,
            color: COLORS[t.type],
            animation: 'slideIn 0.3s ease',
          }}
        >
          <span>{t.message}</span>
        </div>
      ))}
      <style>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(20px); }
          to   { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>
  )
}
