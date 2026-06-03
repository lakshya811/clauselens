import { useEffect, useRef, useState } from 'react'
import { Send, Loader2, BookOpen } from 'lucide-react'
import { askQuestion, type AskResponse } from '../api'

interface Message {
  role: 'user' | 'assistant'
  content: string
  response?: AskResponse
}

interface Props {
  docId: string | null
}

export function ChatPanel({ docId }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
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
    try {
      const res = await askQuestion(docId, q)
      setMessages(prev => [...prev, { role: 'assistant', content: res.answer, response: res }])
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Error'
      setMessages(prev => [...prev, { role: 'assistant', content: `⚠ ${msg}` }])
    } finally {
      setLoading(false)
    }
  }

  if (!docId) {
    return <p className="text-gray-500 text-sm">Upload a document first.</p>
  }

  return (
    <div className="flex flex-col h-[600px]">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 pb-2">
        {messages.length === 0 && (
          <p className="text-gray-600 text-sm text-center pt-8">
            Ask anything about the contract — try "What is the notice period?" or "Who bears liability?"
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-xl px-4 py-3 text-sm space-y-2 ${
              msg.role === 'user'
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-800 border border-gray-700 text-gray-200'
            }`}>
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              {msg.response && msg.response.citations.length > 0 && (
                <div className="border-t border-gray-700 pt-2 space-y-1">
                  <p className="text-xs text-gray-500 flex items-center gap-1">
                    <BookOpen className="w-3 h-3" /> Sources
                  </p>
                  {msg.response.citations.slice(0, 4).map((c, ci) => (
                    <div key={ci} className="text-xs bg-gray-900/60 rounded px-2 py-1">
                      <span className="text-indigo-400 font-mono">{c.citation}</span>
                      <span className="text-gray-500 ml-2">{c.text_snippet.slice(0, 80)}…</span>
                    </div>
                  ))}
                </div>
              )}
              {msg.response && (
                <p className="text-xs text-gray-600">
                  {msg.response.model} · {msg.response.retrieval_hits} hits · ${msg.response.cost_usd.toFixed(6)}
                </p>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
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
