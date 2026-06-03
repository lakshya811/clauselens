import { useEffect, useState } from 'react'
import { fetchMetrics, type MetricsResponse } from '../api'

export function MetricsBadge() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)

  useEffect(() => {
    fetchMetrics().then(setMetrics).catch(() => null)
    const id = setInterval(() => {
      fetchMetrics().then(setMetrics).catch(() => null)
    }, 30_000)
    return () => clearInterval(id)
  }, [])

  if (!metrics || metrics.total_requests === 0) return null

  return (
    <div className="hidden md:flex items-center gap-2.5 text-xs text-slate-400 bg-slate-900/70 border border-slate-800 rounded-full pl-2.5 pr-3 py-1.5 tnum">
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-500/60 animate-ping" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
      </span>
      <span><span className="text-slate-200 font-medium">{metrics.total_requests}</span> req</span>
      <span className="text-slate-700">·</span>
      <span>p50 {metrics.latency_p50_ms.toFixed(0)}ms</span>
      <span className="text-slate-700">·</span>
      <span><span className="text-slate-200 font-medium">${metrics.cost_per_query_usd.toFixed(5)}</span>/query</span>
      {metrics.error_rate > 0 && (
        <>
          <span className="text-slate-700">·</span>
          <span className="text-red-400">{(metrics.error_rate * 100).toFixed(1)}% err</span>
        </>
      )}
    </div>
  )
}
