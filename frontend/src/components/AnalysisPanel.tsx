import { useState } from 'react'
import { Loader2, AlertTriangle, CheckCircle, Info } from 'lucide-react'
import { analyzeDoc, type AnalysisResponse, type RiskSeverity } from '../api'

interface Props {
  docId: string | null
}

function SeverityBadge({ severity }: { severity: RiskSeverity }) {
  const cls = `text-xs font-semibold px-2 py-0.5 rounded-full badge-${severity}`
  return <span className={cls}>{severity.toUpperCase()}</span>
}

function SeverityIcon({ severity }: { severity: RiskSeverity }) {
  if (severity === 'high') return <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
  if (severity === 'medium') return <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
  return <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
}

export function AnalysisPanel({ docId }: Props) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    if (!docId) return
    setError(null)
    setLoading(true)
    try {
      setResult(await analyzeDoc(docId))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  if (!docId) {
    return <p className="text-gray-500 text-sm">Upload a document first.</p>
  }

  return (
    <div className="space-y-4">
      <button
        onClick={run}
        disabled={loading}
        className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
      >
        {loading && <Loader2 className="w-4 h-4 animate-spin" />}
        {loading ? 'Analysing…' : 'Run Analysis'}
      </button>

      {error && (
        <p className="text-red-400 text-sm bg-red-950/40 border border-red-800/50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {result && (
        <div className="space-y-4">
          {/* Key terms */}
          <div className="card space-y-3">
            <h3 className="font-semibold text-gray-200">Key Contract Terms</h3>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              {[
                ['Governing Law', result.clauses.governing_law],
                ['Effective Date', result.clauses.effective_date],
                ['Expiry Date', result.clauses.expiry_date],
                ['Payment Amount', result.clauses.payment.amount],
                ['Currency', result.clauses.payment.currency],
                ['Liability Cap', result.clauses.liability.cap],
                ['Notice Period', result.clauses.termination.notice_period],
              ].map(([label, val]) => val ? (
                <div key={label as string}>
                  <dt className="text-gray-500">{label}</dt>
                  <dd className="text-gray-200 font-medium">{val}</dd>
                </div>
              ) : null)}
            </dl>
            {result.clauses.parties.length > 0 && (
              <div>
                <p className="text-gray-500 text-sm mb-1">Parties</p>
                <div className="flex flex-wrap gap-2">
                  {result.clauses.parties.map((p, i) => (
                    <span key={i} className="text-xs bg-gray-800 border border-gray-700 rounded-full px-2.5 py-0.5">
                      <span className="text-indigo-400">{p.role}</span>
                      <span className="text-gray-400 mx-1">·</span>
                      {p.name}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {result.clauses.confidence_note && (
              <p className="text-xs text-amber-400 border-t border-gray-800 pt-2">{result.clauses.confidence_note}</p>
            )}
          </div>

          {/* Risk report */}
          <div className="card space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-200">Risk Report</h3>
              <SeverityBadge severity={result.risks.overall_risk} />
            </div>
            <p className="text-sm text-gray-400">{result.risks.summary}</p>
            {result.risks.flags.length === 0 ? (
              <p className="text-sm text-emerald-400">No significant risks found.</p>
            ) : (
              <ul className="space-y-3">
                {result.risks.flags.map((flag, i) => (
                  <li key={i} className="bg-gray-800/60 rounded-lg p-3 space-y-1.5">
                    <div className="flex items-start gap-2">
                      <SeverityIcon severity={flag.severity} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium text-gray-100 text-sm">{flag.title}</span>
                          <SeverityBadge severity={flag.severity} />
                          <span className="text-xs text-gray-500 font-mono">{flag.clause_reference}</span>
                        </div>
                        <p className="text-xs text-gray-400 mt-1">{flag.explanation}</p>
                        <p className="text-xs text-indigo-300 mt-1">
                          <span className="text-gray-500">Recommendation: </span>
                          {flag.recommendation}
                        </p>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Cost badge */}
          <p className="text-xs text-gray-600">
            {result.model} · {result.input_tokens + result.output_tokens} tokens · ${result.cost_usd.toFixed(6)} · {result.latency_ms.toFixed(0)} ms
          </p>
        </div>
      )}
    </div>
  )
}
