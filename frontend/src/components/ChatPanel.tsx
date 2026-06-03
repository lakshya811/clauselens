import { useEffect, useRef, useState } from 'react'
import { Send, Loader2, BookOpen, ChevronDown, ChevronUp } from 'lucide-react'
import { askQuestion, type CitedChunk } from '../api'
import type { ChatMessage } from '../App'

interface Props {
  docId: string | null
  messages: ChatMessage[]
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>
}

// Expandable citation card — clicking reveals the full source text
function CitationCard({ c }: { c: CitedChunk }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <button
      onClick={() => setExpanded(e => !e)}
      className="w-full text-left text-xs bg-gray-900/70 hover:bg-gray-900 border border-gray-700/60 hover:border-indigo-600/40 rounded-lg px-2.5 py-2 transition-colors space-y-1"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-indigo-400 font-mono font-semibold">{c.citation}</span>
        <div className="flex items-center gap-1.5 text-gray-500">
          <span className="text-gray-600">score {c.score.toFixed(2)}</span>
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </div>
      </div>
      {!expanded && (
        <p className="text-gray-500 line-clamp-1">{c.text_snippet}</p>
      )}
      {expanded && (
        <p className="text-gray-300 whitespace-pre-wrap leading-relaxed border-t border-gray-700/50 pt-1.5 mt-1">
          {c.text_snippet}
        </p>
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
    <div className="flex flex-col h-[600px]">
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

              {/* Verifiable citations — click to expand full source text */}
              {msg.response && msg.response.citations.length > 0 && (
                <div className="space-y-1.5 border-t border-gray-700/60 pt-2">
                  <p className="text-xs text-gray-500 flex items-center gap-1">
                    <BookOpen className="w-3 h-3" />
                    Sources — click to verify
                  </p>
                  {msg.response.citations.slice(0, 5).map((c, ci) => (
                    <CitationCard key={ci} c={c} />
                  ))}
                </div>
              )}

              {/* Cost / latency footer */}
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
