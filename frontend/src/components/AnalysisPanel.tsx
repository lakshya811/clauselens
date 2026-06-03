import { useState } from 'react'
import { AlertTriangle, CheckCircle, Info, FileText, ShieldAlert } from 'lucide-react'
import { analyzeDoc, type AnalysisResponse, type RiskSeverity, type UploadResponse } from '../api'
import { Card, CardHeader, Badge, Button, Alert, EmptyState } from './ui'

interface Props {
  docId: string | null
  doc: UploadResponse | null
  result: AnalysisResponse | null
  setResult: (r: AnalysisResponse | null) => void
}

const STEPS = ['Extracting clauses…', 'Identifying parties and dates…', 'Flagging risks…', 'Classifying severity…']

function SeverityIcon({ severity }: { severity: RiskSeverity }) {
  if (severity === 'high')   return <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
  if (severity === 'medium') return <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
  return <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-slate-500 mb-0.5">{label}</dt>
      <dd className="text-sm text-slate-100 font-medium">{value}</dd>
    </div>
  )
}

function ListField({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null
  return (
    <div className="col-span-2">
      <dt className="text-[11px] uppercase tracking-wide text-slate-500 mb-1.5">{label}</dt>
      <dd className="flex flex-wrap gap-1.5">
        {items.map((item, i) => (
          <span key={i} className="text-xs bg-slate-800 border border-slate-700 rounded-md px-2 py-0.5 text-slate-300">
            {item}
          </span>
        ))}
      </dd>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader title={title} />
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 p-4">{children}</dl>
    </Card>
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
    return (
      <EmptyState
        icon={<FileText className="w-10 h-10" />}
        title="No contract loaded"
        hint="Upload a PDF or load a sample from the Upload tab to run clause extraction and risk analysis."
      />
    )
  }

  const c = result?.clauses
  const r = result?.risks

  return (
    <div className="space-y-4">
      {/* Action header */}
      <Card className="p-4 flex items-center gap-3 flex-wrap">
        <div className="grid place-items-center w-10 h-10 rounded-lg bg-slate-800 text-brand-400 shrink-0">
          <FileText className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-100 truncate">{doc?.filename ?? docId}</p>
          <p className="text-xs text-slate-500 tnum">
            {doc ? (
              <>
                {doc.page_count} page{doc.page_count !== 1 ? 's' : ''} · {doc.chunk_count} chunks
                {doc.ocr_page_count > 0 && ` · ${doc.ocr_page_count} OCR`}
                {doc.embedded ? ' · vector indexed' : ' · BM25 mode'}
              </>
            ) : 'Ready to analyse'}
          </p>
        </div>
        <Button onClick={run} loading={loading} className="shrink-0">
          {loading ? STEPS[stepIdx] : result ? 'Re-run analysis' : 'Run analysis'}
        </Button>
      </Card>

      {error && <Alert><AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" /><span>{error}</span></Alert>}

      {result && c && r && (
        <div className="space-y-4 animate-fade-in">
          {/* Parties */}
          {c.parties.length > 0 && (
            <Card>
              <CardHeader title="Parties" />
              <div className="flex flex-wrap gap-2 p-4">
                {c.parties.map((p, i) => (
                  <span key={i} className="inline-flex items-center text-xs bg-slate-800 border border-slate-700 rounded-full px-3 py-1">
                    <span className="text-brand-300 font-medium">{p.role}</span>
                    <span className="text-slate-600 mx-1.5">·</span>
                    <span className="text-slate-200">{p.name}</span>
                  </span>
                ))}
              </div>
            </Card>
          )}

          <Section title="Contract Overview">
            <Field label="Governing Law"     value={c.governing_law} />
            <Field label="Effective Date"    value={c.effective_date} />
            <Field label="Expiry / End Date" value={c.expiry_date} />
          </Section>

          {(c.payment.amount || c.payment.due_date || c.payment.late_penalty || c.payment.currency) && (
            <Section title="Payment Terms">
              <Field label="Amount / Schedule"    value={c.payment.amount} />
              <Field label="Due Date"             value={c.payment.due_date} />
              <Field label="Currency"             value={c.payment.currency} />
              <Field label="Late Payment Penalty" value={c.payment.late_penalty} />
            </Section>
          )}

          {(c.liability.cap || c.liability.indemnification || c.liability.exclusions.length > 0) && (
            <Section title="Liability">
              <Field label="Liability Cap"   value={c.liability.cap} />
              <Field label="Indemnification" value={c.liability.indemnification} />
              <ListField label="Exclusions"  items={c.liability.exclusions} />
            </Section>
          )}

          {(c.termination.notice_period || c.termination.for_cause || c.termination.for_convenience || c.termination.survival_clauses.length > 0) && (
            <Section title="Termination">
              <Field label="Notice Period"        value={c.termination.notice_period} />
              <Field label="For Cause"            value={c.termination.for_cause} />
              <Field label="For Convenience"      value={c.termination.for_convenience} />
              <ListField label="Survival Clauses" items={c.termination.survival_clauses} />
            </Section>
          )}

          {c.confidence_note && (
            <p className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">
              {c.confidence_note}
            </p>
          )}

          {/* Risk report */}
          <Card>
            <CardHeader
              title="Risk Report"
              right={<Badge tone={r.overall_risk}><ShieldAlert className="w-3 h-3" />{r.overall_risk.toUpperCase()} RISK</Badge>}
            />
            <div className="p-4 space-y-3">
              <p className="text-sm text-slate-400">{r.summary}</p>
              {r.flags.length === 0 ? (
                <p className="text-sm text-emerald-400">No significant risks found.</p>
              ) : (
                <ul className="space-y-2.5">
                  {r.flags.map((flag, i) => (
                    <li key={i} className="bg-slate-800/50 border border-slate-800 rounded-lg p-3">
                      <div className="flex items-start gap-2">
                        <SeverityIcon severity={flag.severity} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-slate-100 text-sm">{flag.title}</span>
                            <Badge tone={flag.severity}>{flag.severity.toUpperCase()}</Badge>
                            <span className="text-xs text-slate-500 font-mono">{flag.clause_reference}</span>
                          </div>
                          <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">{flag.explanation}</p>
                          <p className="text-xs text-brand-300 mt-1.5">
                            <span className="text-slate-500">Recommendation — </span>{flag.recommendation}
                          </p>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Card>

          <p className="text-xs text-slate-600 tnum px-1">
            answered in {(result.latency_ms / 1000).toFixed(1)}s · {result.input_tokens + result.output_tokens} tokens · ~${result.cost_usd.toFixed(4)} · {result.model}
          </p>
        </div>
      )}
    </div>
  )
}
