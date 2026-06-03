import { useState } from 'react'
import { Loader2, AlertTriangle, CheckCircle, Info, FileText } from 'lucide-react'
import { analyzeDoc, type AnalysisResponse, type RiskSeverity, type UploadResponse } from '../api'

interface Props {
  docId: string | null
  doc: UploadResponse | null
  result: AnalysisResponse | null
  setResult: (r: AnalysisResponse | null) => void
}

const STEPS = ['Extracting clauses…', 'Identifying parties and dates…', 'Flagging risks…', 'Classifying severity…']

function SeverityBadge({ severity }: { severity: RiskSeverity }) {
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded-full badge-${severity}`}>{severity.toUpperCase()}</span>
}
function SeverityIcon({ severity }: { severity: RiskSeverity }) {
  if (severity === 'high')   return <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
  if (severity === 'medium') return <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
  return <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
}

// Renders a labelled field only when val is non-empty
function Field({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <div>
      <dt className="text-gray-500 text-xs mb-0.5">{label}</dt>
      <dd className="text-gray-200 text-sm font-medium">{value}</dd>
    </div>
  )
}

// Renders a list field (e.g. exclusions, survival clauses)
function ListField({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null
  return (
    <div className="col-span-2">
      <dt className="text-gray-500 text-xs mb-1">{label}</dt>
      <dd className="flex flex-wrap gap-1.5">
        {items.map((item, i) => (
          <span key={i} className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-0.5 text-gray-300">{item}</span>
        ))}
      </dd>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card space-y-3">
      <h3 className="font-semibold text-gray-200 text-sm border-b border-gray-800 pb-2">{title}</h3>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
        {children}
      </dl>
    </div>
  )
}

export function AnalysisPanel({ docId, doc, result, setResult }: Props) {
  const [loading, setLoading] = useState(false)
  const [stepIdx, setStepIdx] = useState(0)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    if (!docId) return
    setError(null)
    setResult(null)
    setLoading(true)
    setStepIdx(0)
    const interval = setInterval(() => setStepIdx(i => (i + 1) % STEPS.length), 1800)
    try {
      setResult(await analyzeDoc(docId))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      clearInterval(interval)
      setLoading(false)
    }
  }

  if (!docId) {
    return <p className="text-gray-500 text-sm">Upload a document or load a sample first.</p>
  }

  return (
    <div className="space-y-4">
      {/* Document metadata header */}
      {doc && (
        <div className="flex items-center gap-3 bg-gray-900/60 border border-gray-800 rounded-xl px-4 py-3">
          <FileText className="w-5 h-5 text-indigo-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-200 truncate">{doc.filename}</p>
            <p className="text-xs text-gray-500 mt-0.5">
              {doc.page_count} page{doc.page_count !== 1 ? 's' : ''}
              {' · '}{doc.chunk_count} chunks
              {doc.ocr_page_count > 0 && ` · ${doc.ocr_page_count} OCR pages`}
              {doc.embedded
                ? <span className="text-emerald-500"> · vector indexed ✓</span>
                : <span className="text-gray-600"> · BM25-only mode</span>}
            </p>
          </div>
          <button
            onClick={run}
            disabled={loading}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shrink-0"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {loading ? STEPS[stepIdx] : result ? 'Re-run' : 'Analyse'}
          </button>
        </div>
      )}

      {!doc && (
        <button
          onClick={run}
          disabled={loading}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {loading && <Loader2 className="w-4 h-4 animate-spin" />}
          {loading ? STEPS[stepIdx] : result ? 'Re-run Analysis' : 'Run Analysis'}
        </button>
      )}

      {error && (
        <p className="text-red-400 text-sm bg-red-950/40 border border-red-800/50 rounded-lg px-3 py-2">{error}</p>
      )}

      {result && (
        <div className="space-y-4">
          {/* Parties */}
          {result.clauses.parties.length > 0 && (
            <div className="card space-y-2">
              <h3 className="font-semibold text-gray-200 text-sm border-b border-gray-800 pb-2">Parties</h3>
              <div className="flex flex-wrap gap-2">
                {result.clauses.parties.map((p, i) => (
                  <span key={i} className="text-xs bg-gray-800 border border-gray-700 rounded-full px-3 py-1">
                    <span className="text-indigo-400 font-medium">{p.role}</span>
                    <span className="text-gray-500 mx-1.5">·</span>
                    <span className="text-gray-200">{p.name}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Key dates + jurisdiction */}
          <Section title="Contract Overview">
            <Field label="Governing Law"  value={result.clauses.governing_law} />
            <Field label="Effective Date" value={result.clauses.effective_date} />
            <Field label="Expiry / End Date" value={result.clauses.expiry_date} />
          </Section>

          {/* Payment */}
          {(result.clauses.payment.amount || result.clauses.payment.due_date ||
            result.clauses.payment.late_penalty || result.clauses.payment.currency) && (
            <Section title="Payment Terms">
              <Field label="Amount / Schedule" value={result.clauses.payment.amount} />
              <Field label="Due Date"           value={result.clauses.payment.due_date} />
              <Field label="Currency"           value={result.clauses.payment.currency} />
              <Field label="Late Payment Penalty" value={result.clauses.payment.late_penalty} />
            </Section>
          )}

          {/* Liability */}
          {(result.clauses.liability.cap || result.clauses.liability.indemnification ||
            result.clauses.liability.exclusions.length > 0) && (
            <Section title="Liability">
              <Field label="Liability Cap"      value={result.clauses.liability.cap} />
              <Field label="Indemnification"    value={result.clauses.liability.indemnification} />
              <ListField label="Exclusions"     items={result.clauses.liability.exclusions} />
            </Section>
          )}

          {/* Termination */}
          {(result.clauses.termination.notice_period || result.clauses.termination.for_cause ||
            result.clauses.termination.for_convenience || result.clauses.termination.survival_clauses.length > 0) && (
            <Section title="Termination">
              <Field label="Notice Period"       value={result.clauses.termination.notice_period} />
              <Field label="For Cause"           value={result.clauses.termination.for_cause} />
              <Field label="For Convenience"     value={result.clauses.termination.for_convenience} />
              <ListField label="Survival Clauses" items={result.clauses.termination.survival_clauses} />
            </Section>
          )}

          {result.clauses.confidence_note && (
            <p className="text-xs text-amber-400 bg-amber-950/30 border border-amber-800/40 rounded-lg px-3 py-2">
              {result.clauses.confidence_note}
            </p>
          )}

          {/* Risk report */}
          <div className="card space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-200 text-sm">Risk Report</h3>
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
                          <span className="text-gray-500">Rec: </span>{flag.recommendation}
                        </p>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <p className="text-xs text-gray-600">
            answered in {(result.latency_ms / 1000).toFixed(1)}s · {result.input_tokens + result.output_tokens} tokens · ~${result.cost_usd.toFixed(4)} · {result.model}
          </p>
        </div>
      )}
    </div>
  )
}
