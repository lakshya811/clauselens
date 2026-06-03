import { useEffect, useRef, useState } from 'react'
import { Send, Loader2, BookOpen, ChevronUp, ShieldCheck, MessageSquare } from 'lucide-react'
import { askQuestion, type CitedChunk } from '../api'
import { EmptyState } from './ui'
import type { ChatMessage } from '../App'

interface Props {
  docId: string | null
  messages: ChatMessage[]
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>
}

const SUGGESTIONS = [
  'What is the notice period for termination?',
  'Who owns IP created during the contract?',
  'What are the payment terms?',
  'Is there a liability cap?',
]

// Citation card — collapses to a one-liner, expands to show the exact source
// text highlighted like a document annotation (real contract text, verifiable).
function CitationCard({ c }: { c: CitedChunk }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <button
      onClick={() => setExpanded(e => !e)}
      className="w-full text-left text-xs rounded-lg border px-2.5 py-2 transition-colors space-y-1.5
        bg-slate-950/40 border-slate-700/60 hover:border-brand-500/50"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-brand-300 font-mono font-semibold">{c.citation}</span>
        <div className="flex items-center gap-2 text-slate-600">
          <span className="tnum">score {c.score.toFixed(2)}</span>
          {expanded
            ? <ChevronUp className="w-3 h-3" />
            : <span className="text-brand-400/80">read source ↓</span>}
        </div>
      </div>
      {!expanded && <p className="text-slate-500 line-clamp-1">{c.text_snippet}</p>}
      {expanded && (
        <div className="pt-1.5">
          <p className="text-[10px] text-amber-400/80 mb-1.5 uppercase tracking-wide font-semibold">
            Exact source text from contract
          </p>
          <blockquote className="bg-amber-500/[0.07] border-l-2 border-amber-400/60 pl-3 pr-2 py-2 rounded-r text-slate-200 whitespace-pre-wrap leading-relaxed">
            {c.text_snippet}
          </blockquote>
        </div>
      )}
    </button>
  )
}

const RETRIEVAL_STEPS = ['Running retrieval…', 'Reranking chunks…', 'Generating answer…']

export function ChatPanel({ docId, messages, setMessages }: Props) {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [stepIdx, setStepIdx] = useState(0)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function ask(question: string) {
    const q = question.trim()
    if (!q || !docId || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setLoading(true)
    setStepIdx(0)
    const interval = setInterval(() => setStepIdx(i => Math.min(i + 1, RETRIEVAL_STEPS.length - 1)), 1000)
    try {
      const res = await askQuestion(docId, q)
      setMessages(prev => [...prev, { role: 'assistant', content: res.answer, response: res }])
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Error'
      setMessages(prev => [...prev, { role: 'assistant', content: `⚠ ${msg}` }])
    } finally {
      clearInterval(interval)
      setLoading(false)
    }
  }

  if (!docId) {
    return (
      <EmptyState
        icon={<MessageSquare className="w-10 h-10" />}
        title="No contract loaded"
        hint="Upload a PDF or load a sample to ask questions and get citation-grounded answers."
      />
    )
  }

  return (
    <div className="flex flex-col h-[calc(100vh-13rem)] min-h-[480px]">
      {/* Trust banner */}
      <div className="flex items-center gap-2 mb-3 rounded-lg bg-emerald-500/[0.07] border border-emerald-500/20 px-3 py-2">
        <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
        <p className="text-xs text-slate-300">
          Every answer is grounded in the contract.{' '}
          <span className="text-emerald-300 font-medium">Click any citation to read the exact source text.</span>
        </p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 pr-1 pb-2">
        {messages.length === 0 && (
          <div className="pt-6 space-y-3">
            <p className="text-slate-500 text-sm text-center">Ask anything about the contract — try:</p>
            <div className="flex flex-wrap justify-center gap-2 max-w-lg mx-auto">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => ask(s)}
                  className="text-xs text-slate-300 bg-slate-800/70 hover:bg-slate-800 border border-slate-700 hover:border-brand-500/50 rounded-full px-3 py-1.5 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex animate-fade-in ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm space-y-2.5 ${
              msg.role === 'user'
                ? 'bg-brand-600 text-white rounded-br-md'
                : 'bg-slate-800/80 border border-slate-700/80 text-slate-200 rounded-bl-md'
            }`}>
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>

              {msg.response && msg.response.citations.length > 0 && (
                <div className="space-y-1.5 border-t border-slate-700/60 pt-2.5">
                  <p className="text-xs text-slate-500 flex items-center gap-1.5">
                    <BookOpen className="w-3 h-3" />
                    {msg.response.citations.length} source{msg.response.citations.length > 1 ? 's' : ''} retrieved
                  </p>
                  {msg.response.citations.slice(0, 5).map((c, ci) => <CitationCard key={ci} c={c} />)}
                </div>
              )}

              {msg.response && (
                <p className="text-xs text-slate-600 border-t border-slate-700/40 pt-1.5 tnum">
                  {(msg.response.latency_ms / 1000).toFixed(1)}s · ~${msg.response.cost_usd.toFixed(4)} · {msg.response.retrieval_hits} chunks · {msg.response.model}
                </p>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="w-4 h-4 animate-spin text-brand-400 shrink-0" />
              {RETRIEVAL_STEPS[stepIdx]}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="flex gap-2 pt-3 border-t border-slate-800">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && ask(input)}
          placeholder="Ask a question about the contract…"
          className="input"
          disabled={loading}
        />
        <button
          onClick={() => ask(input)}
          disabled={loading || !input.trim()}
          className="bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white px-3.5 rounded-lg transition-colors shrink-0"
          aria-label="Send"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
