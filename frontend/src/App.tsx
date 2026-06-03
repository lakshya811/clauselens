import { useState } from 'react'
import { FileText, MessageSquare, GitCompare, BarChart2, Upload } from 'lucide-react'
import { UploadPanel } from './components/UploadPanel'
import { AnalysisPanel } from './components/AnalysisPanel'
import { ChatPanel } from './components/ChatPanel'
import { ComparePanel } from './components/ComparePanel'
import { MetricsBadge } from './components/MetricsBadge'
import type { UploadResponse } from './api'

type Tab = 'upload' | 'analysis' | 'chat' | 'compare'

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'upload', label: 'Upload', icon: <Upload className="w-4 h-4" /> },
  { id: 'analysis', label: 'Analysis', icon: <FileText className="w-4 h-4" /> },
  { id: 'chat', label: 'Q&A Chat', icon: <MessageSquare className="w-4 h-4" /> },
  { id: 'compare', label: 'Compare', icon: <GitCompare className="w-4 h-4" /> },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('upload')
  const [docs, setDocs] = useState<UploadResponse[]>([])

  function onUploaded(doc: UploadResponse) {
    setDocs(prev => {
      const filtered = prev.filter(d => d.doc_id !== doc.doc_id)
      return [...filtered, doc]
    })
    setTab('analysis')
  }

  const activeDoc = docs[docs.length - 1] ?? null

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-indigo-400" />
            <span className="font-semibold text-gray-100 tracking-tight">ClauseLens</span>
            <span className="text-xs text-gray-600 ml-1">AI Contract Analysis</span>
          </div>
          <MetricsBadge />
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
            {docs.length > 1 && (
              <span className="ml-2 text-gray-600">(+{docs.length - 1} more uploaded)</span>
            )}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-6 border-b border-gray-800 mb-6">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 pb-3 text-sm font-medium transition-colors ${
                tab === t.id ? 'tab-active' : 'tab-inactive'
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>

        {/* Panel content */}
        <div>
          {tab === 'upload' && <UploadPanel onUploaded={onUploaded} />}
          {tab === 'analysis' && <AnalysisPanel docId={activeDoc?.doc_id ?? null} />}
          {tab === 'chat' && <ChatPanel docId={activeDoc?.doc_id ?? null} />}
          {tab === 'compare' && <ComparePanel docIds={docs.map(d => d.doc_id)} />}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-3">
        <p className="text-center text-xs text-gray-700">
          ClauseLens · Public sample contracts only · Built with Gemini + FAISS + FastAPI
        </p>
      </footer>
    </div>
  )
}
