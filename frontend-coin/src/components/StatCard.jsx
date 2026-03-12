export default function StatCard({ label, value, sub, color = '#007AFF', loading = false }) {
  return (
    <div className="glass-card p-4">
      <div className="text-xs text-gray-500 mb-1 uppercase tracking-wider">{label}</div>
      {loading ? (
        <div className="h-6 w-24 rounded" style={{ background: 'rgba(255,255,255,0.08)', animation: 'pulse 1.5s infinite' }} />
      ) : (
        <div className="text-xl font-bold" style={{ color }}>
          {value ?? '—'}
        </div>
      )}
      {sub && <div className="text-xs text-gray-600 mt-1">{sub}</div>}
    </div>
  )
}
