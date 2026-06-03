import { useState } from 'react'
import { GitCompare, AlertTriangle, ArrowRight } from 'lucide-react'
import { compareDocuments, type CompareResponse, type ChangeType, type UploadResponse } from '../api'
import { Card, CardHeader, Badge, Button, Alert, EmptyState } from './ui'

interface Props {
  docs: UploadResponse[]
}

export function ComparePanel({ docs }: Props) {
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

  if (docs.length < 2) {
    return (
      <EmptyState
        icon={<GitCompare className="w-10 h-10" />}
        title="Load two contracts to compare"
        hint="Upload (or load samples for) two versions of a contract, then return here to classify every change as Structural, Semantic, or Surface."
      />
    )
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="grid sm:grid-cols-[1fr_auto_1fr_auto] gap-3 items-end">
          <div>
            <label className="label">Version A — original</label>
            <select value={docA} onChange={e => setDocA(e.target.value)} className="select">
              <option value="">Select document</option>
              {docs.map(d => <option key={d.doc_id} value={d.doc_id}>{d.filename}</option>)}
            </select>
          </div>
          <div className="hidden sm:grid place-items-center pb-2.5 text-slate-600">
            <ArrowRight className="w-4 h-4" />
          </div>
          <div>
            <label className="label">Version B — revised</label>
            <select value={docB} onChange={e => setDocB(e.target.value)} className="select">
              <option value="">Select document</option>
              {docs.map(d => <option key={d.doc_id} value={d.doc_id}>{d.filename}</option>)}
            </select>
          </div>
          <Button onClick={run} loading={loading} disabled={!docA || !docB || docA === docB}>
            {!loading && <GitCompare className="w-4 h-4" />} Compare
          </Button>
        </div>
        {docA && docB && docA === docB && (
          <p className="text-xs text-amber-300 mt-2">Select two different documents.</p>
        )}
      </Card>

      {error && <Alert><AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" /><span>{error}</span></Alert>}

      {result && (
        <div className="space-y-4 animate-fade-in">
          <Card>
            <CardHeader title="Change summary" />
            <div className="p-4 space-y-3">
              <div className="flex items-center gap-2.5 flex-wrap">
                <Badge tone="structural">{result.result.structural_count} Structural</Badge>
                <Badge tone="semantic">{result.result.semantic_count} Semantic</Badge>
                <Badge tone="surface">{result.result.surface_count} Surface</Badge>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">{result.result.summary}</p>
              {result.result.favours && (
                <p className="text-xs text-brand-300">
                  <span className="text-slate-500">Favours — </span>{result.result.favours}
                </p>
              )}
            </div>
          </Card>

          {result.result.changes.length > 0 && (
            <ul className="space-y-3">
              {result.result.changes.map((c, i) => (
                <li key={i}>
                  <Card className="p-4 space-y-2.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge tone={c.change_type as ChangeType}>{c.change_type.toUpperCase()}</Badge>
                      <span className="text-sm font-medium text-slate-200">{c.clause_reference}</span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">{c.explanation}</p>
                    {(c.old_text || c.new_text) && (
                      <div className="grid sm:grid-cols-2 gap-2 text-xs">
                        {c.old_text && (
                          <div className="bg-red-500/[0.07] border border-red-500/20 rounded-lg p-2.5">
                            <p className="text-red-300 font-semibold mb-1">Version A</p>
                            <p className="text-slate-300 line-clamp-4 leading-relaxed">{c.old_text}</p>
                          </div>
                        )}
                        {c.new_text && (
                          <div className="bg-emerald-500/[0.07] border border-emerald-500/20 rounded-lg p-2.5">
                            <p className="text-emerald-300 font-semibold mb-1">Version B</p>
                            <p className="text-slate-300 line-clamp-4 leading-relaxed">{c.new_text}</p>
                          </div>
                        )}
                      </div>
                    )}
                    {c.risk_delta && (
                      <p className="text-xs text-amber-300">
                        <span className="text-slate-500">Risk delta — </span>{c.risk_delta}
                      </p>
                    )}
                  </Card>
                </li>
              ))}
            </ul>
          )}

          <p className="text-xs text-slate-600 tnum px-1">
            answered in {(result.latency_ms / 1000).toFixed(1)}s · {result.input_tokens + result.output_tokens} tokens · ~${result.cost_usd.toFixed(4)} · {result.model}
          </p>
        </div>
      )}
    </div>
  )
}
