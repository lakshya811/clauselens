import axios from 'axios'

// Empty string = same origin. Set VITE_API_URL only when frontend and backend
// are on different domains (never needed when FastAPI serves the SPA itself).
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
})

// ---- Upload ----------------------------------------------------------------
export interface UploadResponse {
  doc_id: string
  filename: string
  page_count: number
  chunk_count: number
  ocr_page_count: number
  embedded: boolean
}

export async function uploadPdf(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<UploadResponse>('/upload', form)
  return data
}

// ---- Demo samples ----------------------------------------------------------
export interface SampleInfo { id: string; label: string; description: string }

export async function listSamples(): Promise<SampleInfo[]> {
  const { data } = await api.get<SampleInfo[]>('/demo')
  return data
}

export async function loadSample(sampleId: string): Promise<UploadResponse> {
  const { data } = await api.post<UploadResponse>(`/demo/${sampleId}`)
  return data
}

// ---- Analyze ---------------------------------------------------------------
export interface Party { name: string; role: string }
export interface PaymentTerms { amount: string | null; due_date: string | null; late_penalty: string | null; currency: string | null }
export interface LiabilityTerms { cap: string | null; exclusions: string[]; indemnification: string | null }
export interface TerminationTerms { notice_period: string | null; for_cause: string | null; for_convenience: string | null; survival_clauses: string[] }
export interface ClauseBundle { parties: Party[]; effective_date: string | null; expiry_date: string | null; governing_law: string | null; payment: PaymentTerms; liability: LiabilityTerms; termination: TerminationTerms; confidence_note: string | null }
export type RiskSeverity = 'high' | 'medium' | 'low'
export interface RiskFlag { title: string; severity: RiskSeverity; clause_reference: string; explanation: string; recommendation: string }
export interface RiskReport { flags: RiskFlag[]; overall_risk: RiskSeverity; summary: string }
export interface AnalysisResponse { doc_id: string; clauses: ClauseBundle; risks: RiskReport; model: string; input_tokens: number; output_tokens: number; cached_tokens: number; cost_usd: number; latency_ms: number; request_id: string }

export async function analyzeDoc(docId: string): Promise<AnalysisResponse> {
  const { data } = await api.post<AnalysisResponse>(`/analyze/${docId}`)
  return data
}

// ---- Q&A -------------------------------------------------------------------
export interface CitedChunk { chunk_index: number; citation: string; text_snippet: string; score: number }
export interface AskResponse { answer: string; citations: CitedChunk[]; model: string; routing_reason: string; input_tokens: number; output_tokens: number; cached_tokens: number; cost_usd: number; latency_ms: number; retrieval_hits: number; request_id: string }

export async function askQuestion(docId: string, question: string, topK = 8): Promise<AskResponse> {
  const { data } = await api.post<AskResponse>('/ask', { doc_id: docId, question, top_k: topK })
  return data
}

// ---- Compare ---------------------------------------------------------------
export type ChangeType = 'structural' | 'semantic' | 'surface'
export interface ChangedClause { clause_reference: string; change_type: ChangeType; old_text: string | null; new_text: string | null; explanation: string; risk_delta: string | null }
export interface CompareResult { changes: ChangedClause[]; structural_count: number; semantic_count: number; surface_count: number; summary: string; favours: string | null }
export interface CompareResponse { doc_id_a: string; doc_id_b: string; result: CompareResult; model: string; input_tokens: number; output_tokens: number; cached_tokens: number; cost_usd: number; latency_ms: number; request_id: string }

export async function compareDocuments(docIdA: string, docIdB: string): Promise<CompareResponse> {
  const { data } = await api.post<CompareResponse>('/compare', { doc_id_a: docIdA, doc_id_b: docIdB })
  return data
}

// ---- Evals -----------------------------------------------------------------
export interface EvalsSummary {
  status: 'ok' | 'not_run' | 'error'
  timestamp?: string
  n_questions?: number
  n_scored?: number
  n_errors?: number
  correctness_mean?: number
  groundedness_mean?: number
  citation_accuracy_mean?: number
  overall_mean?: number
  total_cost_usd?: number
  cost_per_question_usd?: number
  total_input_tokens?: number
  total_output_tokens?: number
  judge_model?: string
  is_baseline?: boolean
  note?: string
  detail?: string
}

export async function fetchEvalsSummary(): Promise<EvalsSummary> {
  const { data } = await api.get<EvalsSummary>('/evals/summary')
  return data
}

export interface EvalsRunStatus {
  status: 'idle' | 'running' | 'done' | 'error' | 'quota_exhausted'
  started_at: number | null
  log: string[]
  error: string | null
}

export async function fetchEvalsStatus(): Promise<EvalsRunStatus> {
  const { data } = await api.get<EvalsRunStatus>('/evals/status')
  return data
}

export async function triggerEvalsRun(): Promise<{ message: string; status: string }> {
  const { data } = await api.post('/evals/run')
  return data
}

// ---- Metrics ---------------------------------------------------------------
export interface ModelMetrics { requests: number; total_cost_usd: number; latency_p50_ms: number; latency_p95_ms: number }
export interface MetricsResponse { window_size: number; total_requests: number; total_errors: number; error_rate: number; total_cost_usd: number; cost_per_query_usd: number; total_input_tokens: number; total_output_tokens: number; latency_p50_ms: number; latency_p95_ms: number; by_model: Record<string, ModelMetrics> }

export async function fetchMetrics(window = 500): Promise<MetricsResponse> {
  const { data } = await api.get<MetricsResponse>('/metrics', { params: { window } })
  return data
}
