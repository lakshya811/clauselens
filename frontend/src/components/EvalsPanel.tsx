// Scores from: python evals/run_evals.py  (run with GOOGLE_API_KEY, see evals/)
// To regenerate: make eval  →  updates evals/results/summary_<ts>.json
const SCORES = {
  n_questions: 25,
  judge_model: 'gemini-2.5-flash',
  last_run: '2025-06-03',
  correctness: 4.2,
  groundedness: 4.5,
  citation_accuracy: 3.9,
  overall_mean: 4.2,
  cost_per_question_usd: 0.000312,
}

// Baseline = BM25-only, no reranking (first working retrieval implementation).
// Current  = BM25 + FAISS vector + RRF fusion + cross-encoder rerank.
// The delta tells the story: reranking helped citation accuracy the most.
const BASELINE = {
  correctness: 3.8,
  groundedness: 4.0,
  citation_accuracy: 3.1,
  overall_mean: 3.6,
}

type DimKey = 'correctness' | 'groundedness' | 'citation_accuracy'

const DIMENSIONS: { key: DimKey; label: string; desc: string; color: string }[] = [
  { key: 'correctness',       label: 'Correctness',       desc: 'Facts match the reference answer',            color: 'text-emerald-400' },
  { key: 'groundedness',      label: 'Groundedness',      desc: 'Every claim supported by retrieved context',  color: 'text-indigo-400' },
  { key: 'citation_accuracy', label: 'Citation accuracy', desc: 'Citations are specific and map correctly',    color: 'text-amber-400' },
]

const SAMPLE_RESULTS = [
  { id: 'q001', doc: 'NDA',        question: 'Who are the parties?',                             correct: 5, ground: 5, cite: 5 },
  { id: 'q003', doc: 'NDA',        question: 'How long does confidentiality last after termination?', correct: 5, ground: 5, cite: 4 },
  { id: 'q007', doc: 'SaaS',       question: 'What is the late payment penalty?',                correct: 4, ground: 5, cite: 4 },
  { id: 'q008', doc: 'SaaS',       question: 'What is the liability cap?',                       correct: 4, ground: 4, cite: 4 },
  { id: 'q014', doc: 'Employment', question: 'What is the non-compete period?',                  correct: 5, ground: 5, cite: 5 },
  { id: 'q015', doc: 'Employment', question: 'Who owns IP created during employment?',           correct: 5, ground: 5, cite: 4 },
  { id: 'q017', doc: 'Employment', question: 'Does this have an arbitration clause?',            correct: 4, ground: 4, cite: 3 },
  { id: 'q022', doc: 'License',    question: 'Does the agreement auto-renew?',                   correct: 4, ground: 5, cite: 4 },
]

function delta(current: number, baseline: number) {
  const d = current - baseline
  const sign = d >= 0 ? '+' : ''
  const cls = d > 0 ? 'text-emerald-400' : d < 0 ? 'text-red-400' : 'text-gray-500'
  return <span className={`text-xs font-mono font-semibold ${cls}`}>{sign}{d.toFixed(1)}</span>
}

function ScoreBar({ score, baseline }: { score: number; baseline: number }) {
  const color = score >= 4.5 ? 'bg-emerald-500' : score >= 3.5 ? 'bg-indigo-500' : 'bg-amber-500'
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-gray-800 rounded-full h-1.5 relative">
          {/* baseline marker */}
          <div
            className="absolute top-0 h-1.5 w-0.5 bg-gray-600 rounded"
            style={{ left: `${(baseline / 5) * 100}%` }}
            title={`Baseline: ${baseline}`}
          />
          <div className={`${color} h-1.5 rounded-full`} style={{ width: `${(score / 5) * 100}%` }} />
        </div>
        <span className="text-xs font-mono w-6 text-right text-gray-300">{score.toFixed(1)}</span>
      </div>
    </div>
  )
}

export function EvalsPanel() {
  return (
    <div className="space-y-6">
      {/* Header with provenance */}
      <div>
        <h2 className="text-lg font-semibold text-gray-100">LLM-as-Judge Evaluation</h2>
        <p className="text-xs text-gray-500 mt-1">
          Last run: <span className="text-gray-400 font-medium">{SCORES.last_run}</span>
          {' · '}{SCORES.n_questions} labeled pairs
          {' · '}judge: <span className="font-mono text-indigo-300">{SCORES.judge_model}</span>
          {' · '}1–5 rubric · <span className="text-gray-600">regenerate with <span className="font-mono">make eval</span></span>
        </p>
      </div>

      {/* Baseline vs current — the improvement story */}
      <div className="card space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-200 text-sm">Baseline vs current</h3>
          <span className="text-xs text-gray-600">gray tick = baseline · bar = current</span>
        </div>
        <p className="text-xs text-gray-500">
          Baseline: BM25-only retrieval, no reranker.
          Current: BM25 + FAISS vector + Reciprocal Rank Fusion + cross-encoder rerank.
        </p>
        <div className="space-y-4">
          {DIMENSIONS.map(d => (
            <div key={d.key} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className={`font-medium ${d.color}`}>{d.label}</span>
                <div className="flex items-center gap-2 text-gray-500">
                  <span className="font-mono">{BASELINE[d.key].toFixed(1)}</span>
                  <span>→</span>
                  <span className="font-mono text-gray-200">{SCORES[d.key].toFixed(1)}</span>
                  {delta(SCORES[d.key], BASELINE[d.key])}
                </div>
              </div>
              <ScoreBar score={SCORES[d.key]} baseline={BASELINE[d.key]} />
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-600 border-t border-gray-800 pt-2">
          Reranking improved citation accuracy most (+0.8) — the cross-encoder
          surfaces the exact clause more reliably than pure vector similarity.
        </p>
      </div>

      {/* Aggregate cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {DIMENSIONS.map(d => (
          <div key={d.key} className="card space-y-2">
            <div className="flex items-center justify-between">
              <span className={`font-semibold text-sm ${d.color}`}>{d.label}</span>
              <span className="text-2xl font-bold text-gray-100">
                {SCORES[d.key].toFixed(1)}
                <span className="text-sm text-gray-500">/5</span>
              </span>
            </div>
            <ScoreBar score={SCORES[d.key]} baseline={BASELINE[d.key]} />
            <p className="text-xs text-gray-500">{d.desc}</p>
          </div>
        ))}
      </div>

      {/* Overall + cost */}
      <div className="card flex items-center justify-between flex-wrap gap-4">
        <div>
          <p className="text-xs text-gray-500 mb-1">Overall mean (3-dimension average)</p>
          <div className="flex items-baseline gap-3">
            <p className="text-3xl font-bold text-gray-100">
              {SCORES.overall_mean.toFixed(2)}
              <span className="text-base text-gray-500">/5</span>
            </p>
            <span className="text-sm text-gray-500">
              from baseline {BASELINE.overall_mean.toFixed(1)} {delta(SCORES.overall_mean, BASELINE.overall_mean)}
            </span>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-500 mb-1">Cost per question</p>
          <p className="text-xl font-bold text-indigo-300">${SCORES.cost_per_question_usd.toFixed(5)}</p>
          <p className="text-xs text-gray-600">answer + judge call</p>
        </div>
      </div>

      {/* Attribution design */}
      <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4 space-y-2">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Why two-level attribution?</p>
        <p className="text-sm text-gray-400">
          The judge sees both the <span className="text-gray-200">reference answer</span> and the{' '}
          <span className="text-gray-200">retrieved context</span>. This separates retrieval failures from generation failures:
        </p>
        <ul className="text-sm text-gray-400 space-y-1 pl-4">
          <li>· <span className="text-amber-300">correctness↓, groundedness↑</span> → model hallucinated despite good retrieval</li>
          <li>· <span className="text-red-300">correctness↓, groundedness↓</span> → retrieval failed — right answer wasn't in context</li>
        </ul>
        <p className="text-xs text-gray-600">A single accuracy number hides which component to fix.</p>
      </div>

      {/* Per-question sample */}
      <div className="card space-y-3">
        <h3 className="font-semibold text-gray-200 text-sm">Sample question scores</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-1.5 pr-4 font-medium">Question</th>
                <th className="text-left py-1.5 pr-3 font-medium">Doc</th>
                <th className="text-center py-1.5 px-2 font-medium text-emerald-500/70">Correct.</th>
                <th className="text-center py-1.5 px-2 font-medium text-indigo-500/70">Ground.</th>
                <th className="text-center py-1.5 px-2 font-medium text-amber-500/70">Cite</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {SAMPLE_RESULTS.map(r => (
                <tr key={r.id}>
                  <td className="py-1.5 pr-4 text-gray-300 max-w-xs truncate">{r.question}</td>
                  <td className="py-1.5 pr-3 text-gray-500">{r.doc}</td>
                  <td className="py-1.5 px-2 text-center text-emerald-400 font-mono">{r.correct}</td>
                  <td className="py-1.5 px-2 text-center text-indigo-400 font-mono">{r.ground}</td>
                  <td className="py-1.5 px-2 text-center text-amber-400 font-mono">{r.cite}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
