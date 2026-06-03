import { useState } from 'react'
import { Loader2, GitCompare } from 'lucide-react'
import { compareDocuments, type CompareResponse, type ChangeType } from '../api'

interface Props {
  docIds: string[]
}

function ChangeBadge({ type }: { type: ChangeType }) {
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full badge-${type}`}>
      {type.toUpperCase()}
    </span>
  )
}

export function ComparePanel({ docIds }: Props) {
  const [docA, setDocA] = useState('')
  const [docB, setDocB] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<CompareResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    if (!docA || !docB) return
    setError(null)
    setLoading(true)
    try {
      setResult(await compareDocuments(docA, docB))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Comparison failed')
    } finally {
      setLoading(false)
    }
  }

  if (docIds.length < 2) {
    return <p className="text-gray-500 text-sm">Upload at least two documents to compare versions.</p>
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-3 items-end">
        <div className="flex-1">
          <label className="text-xs text-gray-500 block mb-1">Version A (original)</label>
          <select
            value={docA}
            onChange={e => setDocA(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="">Select document</option>
            {docIds.map(id => <option key={id} value={id}>{id}</option>)}
          </select>
        </div>
        <div className="flex-1">
          <label className="text-xs text-gray-500 block mb-1">Version B (revised)</label>
          <select
            value={docB}
            onChange={e => setDocB(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="">Select document</option>
            {docIds.map(id => <option key={id} value={id}>{id}</option>)}
          </select>
        </div>
        <button
          onClick={run}
          disabled={loading || !docA || !docB || docA === docB}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <GitCompare className="w-4 h-4" />}
          Compare
        </button>
      </div>

      {error && (
        <p className="text-red-400 text-sm bg-red-950/40 border border-red-800/50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {result && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="card space-y-3">
            <div className="flex items-center gap-4">
              <span className="badge-structural text-xs font-semibold px-2 py-0.5 rounded-full">
                {result.result.structural_count} Structural
              </span>
              <span className="badge-semantic text-xs font-semibold px-2 py-0.5 rounded-full">
                {result.result.semantic_count} Semantic
              </span>
              <span className="badge-surface text-xs font-semibold px-2 py-0.5 rounded-full">
                {result.result.surface_count} Surface
              </span>
            </div>
            <p className="text-sm text-gray-300">{result.result.summary}</p>
            {result.result.favours && (
              <p className="text-xs text-indigo-300">
                <span className="text-gray-500">Favours: </span>{result.result.favours}
              </p>
            )}
          </div>

          {/* Change list */}
          {result.result.changes.length > 0 && (
            <ul className="space-y-3">
              {result.result.changes.map((c, i) => (
                <li key={i} className="card space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <ChangeBadge type={c.change_type} />
                    <span className="text-sm font-medium text-gray-200">{c.clause_reference}</span>
                  </div>
                  <p className="text-xs text-gray-400">{c.explanation}</p>
                  {(c.old_text || c.new_text) && (
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {c.old_text && (
                        <div className="bg-red-950/30 border border-red-800/30 rounded p-2">
                          <p className="text-red-400 font-semibold mb-1">Version A</p>
                          <p className="text-gray-300 line-clamp-3">{c.old_text}</p>
                        </div>
                      )}
                      {c.new_text && (
                        <div className="bg-emerald-950/30 border border-emerald-800/30 rounded p-2">
                          <p className="text-emerald-400 font-semibold mb-1">Version B</p>
                          <p className="text-gray-300 line-clamp-3">{c.new_text}</p>
                        </div>
                      )}
                    </div>
                  )}
                  {c.risk_delta && (
                    <p className="text-xs text-amber-400">
                      <span className="text-gray-500">Risk delta: </span>{c.risk_delta}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}

          <p className="text-xs text-gray-600">
            {result.model} · {result.input_tokens + result.output_tokens} tokens · ${result.cost_usd.toFixed(6)} · {result.latency_ms.toFixed(0)} ms
          </p>
        </div>
      )}
    </div>
  )
}
