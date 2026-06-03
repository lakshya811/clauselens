import { useState } from 'react'
import { FileText, MessageSquare, GitCompare, BarChart2, Upload, FlaskConical, RotateCcw } from 'lucide-react'
import { UploadPanel } from './components/UploadPanel'
import { AnalysisPanel } from './components/AnalysisPanel'
import { ChatPanel } from './components/ChatPanel'
import { ComparePanel } from './components/ComparePanel'
import { EvalsPanel } from './components/EvalsPanel'
import { MetricsBadge } from './components/MetricsBadge'
import type { UploadResponse, AnalysisResponse, AskResponse } from './api'

type Tab = 'upload' | 'analysis' | 'chat' | 'compare' | 'evals'

// Lifted state types so tab switches never reset results
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  response?: AskResponse
}

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'upload', label: 'Upload', icon: <Upload className="w-4 h-4" /> },
  { id: 'analysis', label: 'Analysis', icon: <FileText className="w-4 h-4" /> },
  { id: 'chat', label: 'Q&A Chat', icon: <MessageSquare className="w-4 h-4" /> },
  { id: 'compare', label: 'Compare', icon: <GitCompare className="w-4 h-4" /> },
  { id: 'evals', label: 'Evals', icon: <FlaskConical className="w-4 h-4" /> },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('upload')
  const [docs, setDocs] = useState<UploadResponse[]>([])

  // Lifted state — survives tab switches
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])

  function onUploaded(doc: UploadResponse) {
    setDocs(prev => {
      const filtered = prev.filter(d => d.doc_id !== doc.doc_id)
      return [...filtered, doc]
    })
    // Reset per-doc state when a new doc loads
    setAnalysisResult(null)
    setChatMessages([])
    setTab('analysis')
  }

  function startNew() {
    setDocs([])
    setAnalysisResult(null)
    setChatMessages([])
    setTab('upload')
  }

  const activeDoc = docs[docs.length - 1] ?? null

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart2 className="w-5 h-5 text-indigo-400 shrink-0" />
            <div>
              <span className="font-semibold text-gray-100 tracking-tight">ClauseLens</span>
              <span className="hidden sm:inline text-xs text-gray-500 ml-2">
                Upload a contract → clause extraction, risk flags, and grounded Q&A
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <MetricsBadge />
            {activeDoc && (
              <button
                onClick={startNew}
                className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 border border-gray-700 hover:border-gray-500 rounded-lg px-2.5 py-1.5 transition-colors"
              >
                <RotateCcw className="w-3 h-3" />
                Start new
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-6">
        {/* Active doc pill */}
        {activeDoc && (
          <div className="mb-4 flex items-center gap-2 text-xs text-gray-500">
            <FileText className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-gray-400 font-medium">{activeDoc.filename}</span>
            <span className="text-gray-700">·</span>
            <span className="font-mono text-gray-600">{activeDoc.doc_id}</span>
            <span className="text-gray-700">·</span>
            <span>{activeDoc.chunk_count} chunks</span>
            {activeDoc.embedded && <span className="text-emerald-600">· indexed</span>}
            {docs.length > 1 && (
              <span className="ml-1 text-gray-600">(+{docs.length - 1} more)</span>
            )}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-6 border-b border-gray-800 mb-6 overflow-x-auto">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 pb-3 text-sm font-medium transition-colors whitespace-nowrap ${
                tab === t.id ? 'tab-active' : 'tab-inactive'
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>

        {/* Panel content — always mounted to preserve state */}
        <div className={tab === 'upload' ? '' : 'hidden'}>
          <UploadPanel onUploaded={onUploaded} />
        </div>
        <div className={tab === 'analysis' ? '' : 'hidden'}>
          <AnalysisPanel
            docId={activeDoc?.doc_id ?? null}
            doc={activeDoc}
            result={analysisResult}
            setResult={setAnalysisResult}
          />
        </div>
        <div className={tab === 'chat' ? '' : 'hidden'}>
          <ChatPanel
            docId={activeDoc?.doc_id ?? null}
            messages={chatMessages}
            setMessages={setChatMessages}
          />
        </div>
        <div className={tab === 'compare' ? '' : 'hidden'}>
          <ComparePanel docIds={docs.map(d => d.doc_id)} />
        </div>
        <div className={tab === 'evals' ? '' : 'hidden'}>
          <EvalsPanel />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-3">
        <p className="text-center text-xs text-gray-700">
          ClauseLens · Public sample contracts only (CUAD / SEC EDGAR) · Gemini + FAISS + FastAPI
        </p>
      </footer>
    </div>
  )
}
