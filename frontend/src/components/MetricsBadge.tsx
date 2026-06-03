import { useEffect, useState } from 'react'
import { Activity } from 'lucide-react'
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
    <div className="flex items-center gap-2 text-xs text-gray-500 bg-gray-900 border border-gray-800 rounded-full px-3 py-1.5">
      <Activity className="w-3 h-3 text-emerald-500" />
      <span>{metrics.total_requests} req</span>
      <span className="text-gray-700">·</span>
      <span>p50 {metrics.latency_p50_ms.toFixed(0)} ms</span>
      <span className="text-gray-700">·</span>
      <span>${metrics.cost_per_query_usd.toFixed(5)}/query</span>
      {metrics.error_rate > 0 && (
        <>
          <span className="text-gray-700">·</span>
          <span className="text-red-400">{(metrics.error_rate * 100).toFixed(1)}% err</span>
        </>
      )}
    </div>
  )
}
