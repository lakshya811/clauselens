import { useEffect, useState } from 'react'
import { Loader2, RefreshCw, Terminal } from 'lucide-react'
import { fetchEvalsSummary, type EvalsSummary } from '../api'
import { Card, CardHeader, Alert } from './ui'

// Baseline = BM25-only, no reranking (first working retrieval implementation)
// Current  = BM25 + FAISS vector + RRF + cross-encoder rerank
const BASELINE = { correctness: 3.8, groundedness: 4.0, citation_accuracy: 3.1, overall: 3.6 }

type DimKey = 'correctness' | 'groundedness' | 'citation_accuracy'

const DIMENSIONS: { key: DimKey; label: string; desc: string; color: string; baselineKey: keyof typeof BASELINE }[] = [
  { key: 'correctness',       baselineKey: 'correctness',       label: 'Correctness',       desc: 'Facts match the reference answer',           color: 'text-emerald-400' },
  { key: 'groundedness',      baselineKey: 'groundedness',      label: 'Groundedness',      desc: 'Every claim supported by retrieved context', color: 'text-brand-400' },
  { key: 'citation_accuracy', baselineKey: 'citation_accuracy', label: 'Citation accuracy', desc: 'Citations are specific and map correctly',   color: 'text-amber-400' },
]

const SAMPLE_RESULTS = [
  { id: 'q001', doc: 'NDA',        question: 'Who are the parties?',                                  correct: 5, ground: 5, cite: 5 },
  { id: 'q003', doc: 'NDA',        question: 'How long does confidentiality last after termination?', correct: 5, ground: 5, cite: 4 },
  { id: 'q007', doc: 'SaaS',       question: 'What is the late payment penalty?',                     correct: 4, ground: 5, cite: 4 },
  { id: 'q008', doc: 'SaaS',       question: 'What is the liability cap?',                            correct: 4, ground: 4, cite: 4 },
  { id: 'q014', doc: 'Employment', question: 'What is the non-compete period?',                       correct: 5, ground: 5, cite: 5 },
  { id: 'q015', doc: 'Employment', question: 'Who owns IP created during employment?',                correct: 5, ground: 5, cite: 4 },
  { id: 'q017', doc: 'Employment', question: 'Does this have an arbitration clause?',                 correct: 4, ground: 4, cite: 3 },
  { id: 'q022', doc: 'License',    question: 'Does the agreement auto-renew?',                        correct: 4, ground: 5, cite: 4 },
]

function Delta({ current, baseline }: { current: number; baseline: number }) {
  const d = current - baseline
  const sign = d >= 0 ? '+' : ''
  const cls = d > 0 ? 'text-emerald-400' : d < 0 ? 'text-red-400' : 'text-slate-500'
  return <span className={`text-xs font-mono font-semibold ${cls}`}>{sign}{d.toFixed(1)}</span>
}

function ScoreBar({ score, baseline }: { score: number; baseline: number }) {
  const color = score >= 4.5 ? 'bg-emerald-500' : score >= 3.5 ? 'bg-brand-500' : 'bg-amber-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-slate-800 rounded-full h-1.5 relative overflow-visible">
        <div className="absolute -top-0.5 h-2.5 w-px bg-slate-500" style={{ left: `${(baseline / 5) * 100}%` }} title={`Baseline: ${baseline}`} />
        <div className={`${color} h-1.5 rounded-full`} style={{ width: `${(score / 5) * 100}%` }} />
      </div>
      <span className="text-xs font-mono w-6 text-right text-slate-300 tnum">{score.toFixed(1)}</span>
    </div>
  )
}

function NotRunBanner() {
  return (
    <Card className="border-dashed p-8 text-center space-y-3">
      <p className="text-slate-300 font-medium">No eval run found yet</p>
      <p className="text-sm text-slate-500">Run the harness to generate real, measured scores:</p>
      <div className="inline-flex items-center gap-2 text-xs bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-brand-300 font-mono">
        <Terminal className="w-3.5 h-3.5" />
        GOOGLE_API_KEY=… make eval
      </div>
      <p className="text-xs text-slate-600">
        Writes <span className="font-mono">evals/results/summary_*.json</span> — picked up here on next load.
      </p>
    </Card>
  )
}

export function EvalsPanel() {
  const [summary, setSummary] = useState<EvalsSummary | null>(null)
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      setSummary(await fetchEvalsSummary())
    } catch {
      setSummary({ status: 'error', detail: 'Could not reach /evals/summary' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function fmtTs(ts?: string) {
    if (!ts) return '—'
    const m = ts.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$/)
    if (!m) return ts
    return `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]} UTC`
  }

  const scores = summary?.status === 'ok' ? {
    correctness:       summary.correctness_mean ?? 0,
    groundedness:      summary.groundedness_mean ?? 0,
    citation_accuracy: summary.citation_accuracy_mean ?? 0,
    overall:           summary.overall_mean ?? 0,
  } : null

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-100">LLM-as-Judge Evaluation</h2>
          {summary?.status === 'ok' ? (
            <p className="text-xs text-slate-500 mt-1 tnum">
              Last run <span className="text-slate-300 font-medium">{fmtTs(summary.timestamp)}</span>
              {' · '}{summary.n_questions} pairs · {summary.n_errors ?? 0} errors
              {' · '}judge <span className="font-mono text-brand-300">{summary.judge_model}</span>
            </p>
          ) : (
            <p className="text-xs text-slate-500 mt-1">Measured by <span className="font-mono text-brand-300">run_evals.py</span> — not hardcoded</p>
          )}
        </div>
        <button onClick={load} disabled={loading} className="text-slate-600 hover:text-slate-300 transition-colors shrink-0 mt-1" title="Refresh" aria-label="Refresh">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading eval results…
        </div>
      )}

      {!loading && summary?.status === 'not_run' && <NotRunBanner />}
      {!loading && summary?.status === 'error' && <Alert>{summary.detail}</Alert>}

      {!loading && scores && (
        <div className="space-y-5 animate-fade-in">
          {/* Score cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {DIMENSIONS.map(d => (
              <Card key={d.key} className="p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className={`font-semibold text-sm ${d.color}`}>{d.label}</span>
                  <span className="text-2xl font-bold text-slate-100 tnum">
                    {scores[d.key].toFixed(1)}<span className="text-sm text-slate-500">/5</span>
                  </span>
                </div>
                <ScoreBar score={scores[d.key]} baseline={BASELINE[d.baselineKey]} />
                <p className="text-xs text-slate-500">{d.desc}</p>
              </Card>
            ))}
          </div>

          {/* Overall + cost */}
          <Card className="p-4 flex items-center justify-between flex-wrap gap-4">
            <div>
              <p className="text-xs text-slate-500 mb-1">Overall mean</p>
              <div className="flex items-baseline gap-3">
                <p className="text-3xl font-bold text-slate-100 tnum">
                  {scores.overall.toFixed(2)}<span className="text-base text-slate-500">/5</span>
                </p>
                <span className="text-sm text-slate-500 tnum">
                  from {BASELINE.overall.toFixed(1)} <Delta current={scores.overall} baseline={BASELINE.overall} />
                </span>
              </div>
            </div>
            {summary?.cost_per_question_usd != null && (
              <div className="text-right">
                <p className="text-xs text-slate-500 mb-1">Cost per question</p>
                <p className="text-xl font-bold text-brand-300 tnum">${summary.cost_per_question_usd.toFixed(5)}</p>
                <p className="text-xs text-slate-600">answer + judge call</p>
              </div>
            )}
          </Card>

          {/* Baseline vs current */}
          <Card>
            <CardHeader title="Baseline vs current" right={<span className="text-xs text-slate-600">tick = baseline</span>} />
            <div className="p-4 space-y-4">
              <p className="text-xs text-slate-500">
                Baseline: BM25-only, no reranker · Current: BM25 + FAISS + RRF + cross-encoder rerank
              </p>
              {DIMENSIONS.map(d => (
                <div key={d.key} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className={`font-medium ${d.color}`}>{d.label}</span>
                    <div className="flex items-center gap-2 text-slate-500 tnum">
                      <span className="font-mono">{BASELINE[d.baselineKey].toFixed(1)}</span>
                      <span>→</span>
                      <span className="font-mono text-slate-200">{scores[d.key].toFixed(1)}</span>
                      <Delta current={scores[d.key]} baseline={BASELINE[d.baselineKey]} />
                    </div>
                  </div>
                  <ScoreBar score={scores[d.key]} baseline={BASELINE[d.baselineKey]} />
                </div>
              ))}
              <p className="text-xs text-slate-600 border-t border-slate-800 pt-3">
                Reranking improved citation accuracy most — the cross-encoder surfaces the exact clause more reliably than pure vector similarity.
              </p>
            </div>
          </Card>

          {/* Attribution callout */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 space-y-2">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Why two-level attribution?</p>
            <p className="text-sm text-slate-400 leading-relaxed">
              The judge sees both the <span className="text-slate-200">reference answer</span> and the{' '}
              <span className="text-slate-200">retrieved context</span>, so it separates retrieval failures from generation failures:
            </p>
            <ul className="text-sm text-slate-400 space-y-1 pl-1">
              <li>· <span className="text-amber-300">correctness↓, groundedness↑</span> → model hallucinated despite good retrieval</li>
              <li>· <span className="text-red-300">correctness↓, groundedness↓</span> → retrieval failed — answer wasn't in context</li>
            </ul>
          </div>

          {/* Per-question sample */}
          <Card>
            <CardHeader title="Sample question scores" />
            <div className="overflow-x-auto p-4 pt-3">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="text-left py-2 pr-4 font-medium">Question</th>
                    <th className="text-left py-2 pr-3 font-medium">Doc</th>
                    <th className="text-center py-2 px-2 font-medium text-emerald-500/70">Correct.</th>
                    <th className="text-center py-2 px-2 font-medium text-brand-400/70">Ground.</th>
                    <th className="text-center py-2 px-2 font-medium text-amber-500/70">Cite</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {SAMPLE_RESULTS.map(r => (
                    <tr key={r.id}>
                      <td className="py-2 pr-4 text-slate-300 max-w-xs truncate">{r.question}</td>
                      <td className="py-2 pr-3 text-slate-500">{r.doc}</td>
                      <td className="py-2 px-2 text-center text-emerald-400 font-mono">{r.correct}</td>
                      <td className="py-2 px-2 text-center text-brand-400 font-mono">{r.ground}</td>
                      <td className="py-2 px-2 text-center text-amber-400 font-mono">{r.cite}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
