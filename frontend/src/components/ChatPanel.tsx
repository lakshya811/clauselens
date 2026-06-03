import { useEffect, useRef, useState } from 'react'
import { Send, Loader2, BookOpen, ChevronUp, ShieldCheck } from 'lucide-react'
import { askQuestion, type CitedChunk } from '../api'
import type { ChatMessage } from '../App'

interface Props {
  docId: string | null
  messages: ChatMessage[]
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>
}

// Citation card — collapses to a one-liner, expands to show the exact source
// text highlighted like a document annotation. The highlight is intentional:
// it signals "this is real contract text, not a paraphrase."
function CitationCard({ c }: { c: CitedChunk }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <button
      onClick={() => setExpanded(e => !e)}
      className="w-full text-left text-xs border rounded-lg px-2.5 py-2 transition-all space-y-1.5
        bg-gray-900/70 border-gray-700/60 hover:border-indigo-500/50"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-indigo-400 font-mono font-semibold">{c.citation}</span>
        <div className="flex items-center gap-2 text-gray-600">
          <span>score {c.score.toFixed(2)}</span>
          {expanded
            ? <ChevronUp className="w-3 h-3" />
            : <span className="text-indigo-500/70 text-xs">click to read source ↓</span>}
        </div>
      </div>

      {/* Collapsed preview */}
      {!expanded && (
        <p className="text-gray-500 line-clamp-1">{c.text_snippet}</p>
      )}

      {/* Expanded: full source text, styled like a document highlight */}
      {expanded && (
        <div className="mt-1 border-t border-gray-700/50 pt-2">
          <p className="text-[10px] text-amber-500/70 mb-1.5 uppercase tracking-wide font-semibold">
            Exact source text from contract
          </p>
          <blockquote className="bg-amber-950/30 border-l-2 border-amber-500/60 pl-3 pr-2 py-2 rounded-r text-gray-200 whitespace-pre-wrap leading-relaxed">
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

  async function send() {
    const q = input.trim()
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
    return <p className="text-gray-500 text-sm">Upload a document or load a sample first.</p>
  }

  return (
    <div className="flex flex-col h-[620px]">
      {/* Grounded badge — visible proof of RAG citations */}
      <div className="flex items-center gap-2 mb-3 px-1">
        <ShieldCheck className="w-4 h-4 text-emerald-500 shrink-0" />
        <p className="text-xs text-gray-400">
          Every answer is grounded in the contract.{' '}
          <span className="text-emerald-400 font-medium">Click any source citation to read the exact contract text.</span>
        </p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 pr-1 pb-2">
        {messages.length === 0 && (
          <p className="text-gray-600 text-sm text-center pt-8">
            Ask anything — "What is the notice period?", "Who owns IP created during the contract?", "What are the payment terms?"
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-xl px-4 py-3 text-sm space-y-2.5 ${
              msg.role === 'user'
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-800 border border-gray-700 text-gray-200'
            }`}>
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>

              {msg.response && msg.response.citations.length > 0 && (
                <div className="space-y-1.5 border-t border-gray-700/60 pt-2">
                  <p className="text-xs text-gray-500 flex items-center gap-1.5">
                    <BookOpen className="w-3 h-3" />
                    {msg.response.citations.length} source{msg.response.citations.length > 1 ? 's' : ''} retrieved — click to read contract text
                  </p>
                  {msg.response.citations.slice(0, 5).map((c, ci) => (
                    <CitationCard key={ci} c={c} />
                  ))}
                </div>
              )}

              {msg.response && (
                <p className="text-xs text-gray-600 border-t border-gray-700/40 pt-1.5">
                  answered in {(msg.response.latency_ms / 1000).toFixed(1)}s · ~${msg.response.cost_usd.toFixed(4)} · {msg.response.retrieval_hits} chunks retrieved · {msg.response.model}
                </p>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 flex items-center gap-2 text-sm text-gray-400">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-400 shrink-0" />
              {RETRIEVAL_STEPS[stepIdx]}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="flex gap-2 pt-3 border-t border-gray-800">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder="Ask a question about the contract…"
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-500"
          disabled={loading}
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-3 py-2 rounded-lg transition-colors"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
