import { useState } from 'react'
import {
  FileText, MessageSquare, GitCompare, Upload, FlaskConical,
  RotateCcw, ScanSearch,
} from 'lucide-react'
import { UploadPanel } from './components/UploadPanel'
import { AnalysisPanel } from './components/AnalysisPanel'
import { ChatPanel } from './components/ChatPanel'
import { ComparePanel } from './components/ComparePanel'
import { EvalsPanel } from './components/EvalsPanel'
import { MetricsBadge } from './components/MetricsBadge'
import { Button } from './components/ui'
import type { UploadResponse, AnalysisResponse, AskResponse } from './api'

type Tab = 'upload' | 'analysis' | 'chat' | 'compare' | 'evals'

// Lifted chat state so tab switches never reset the conversation
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  response?: AskResponse
}

interface NavItem {
  id: Tab
  label: string
  icon: React.ReactNode
  title: string
  subtitle: string
  needsDoc?: boolean
}

const NAV: NavItem[] = [
  { id: 'upload',   label: 'Upload',   icon: <Upload className="w-[18px] h-[18px]" />,        title: 'Upload a contract',     subtitle: 'Add your own PDF or load a public sample' },
  { id: 'analysis', label: 'Analysis', icon: <FileText className="w-[18px] h-[18px]" />,       title: 'Clause analysis',        subtitle: 'Key terms, parties, and automated risk flags', needsDoc: true },
  { id: 'chat',     label: 'Q&A',      icon: <MessageSquare className="w-[18px] h-[18px]" />,   title: 'Grounded Q&A',           subtitle: 'Answers cite the exact source clause', needsDoc: true },
  { id: 'compare',  label: 'Compare',  icon: <GitCompare className="w-[18px] h-[18px]" />,      title: 'Version comparison',     subtitle: 'Classify every change between two versions', needsDoc: true },
  { id: 'evals',    label: 'Evals',    icon: <FlaskConical className="w-[18px] h-[18px]" />,    title: 'Evaluation',             subtitle: 'LLM-as-Judge quality scores on a labeled set' },
]

function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid place-items-center w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 shadow-soft shrink-0">
        <ScanSearch className="w-[18px] h-[18px] text-white" />
      </div>
      {!compact && (
        <div className="leading-none">
          <span className="block font-semibold text-slate-100 tracking-tight">ClauseLens</span>
          <span className="block text-[11px] text-slate-500 mt-0.5">Contract Intelligence</span>
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState<Tab>('upload')
  const [docs, setDocs] = useState<UploadResponse[]>([])
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])

  function onUploaded(doc: UploadResponse) {
    setDocs(prev => [...prev.filter(d => d.doc_id !== doc.doc_id), doc])
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
  const meta = NAV.find(n => n.id === tab)!

  function NavButton({ item, mobile = false }: { item: NavItem; mobile?: boolean }) {
    const active = tab === item.id
    if (mobile) {
      return (
        <button
          onClick={() => setTab(item.id)}
          className={`flex items-center gap-2 px-3 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
            active
              ? 'border-brand-500 text-brand-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          {item.icon}
          {item.label}
        </button>
      )
    }
    return (
      <button
        onClick={() => setTab(item.id)}
        className={`group flex items-center gap-3 w-full rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
          active
            ? 'bg-brand-500/10 text-brand-200 ring-1 ring-inset ring-brand-500/25'
            : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/50'
        }`}
      >
        <span className={active ? 'text-brand-300' : 'text-slate-500 group-hover:text-slate-300'}>
          {item.icon}
        </span>
        {item.label}
        {item.needsDoc && !activeDoc && (
          <span className="ml-auto text-[10px] text-slate-600">requires doc</span>
        )}
      </button>
    )
  }

  return (
    <div className="min-h-screen flex">
      {/* ---- Sidebar (desktop) ---- */}
      <aside className="hidden lg:flex flex-col w-64 shrink-0 border-r border-slate-800/80 bg-slate-900/30 sticky top-0 h-screen">
        <div className="px-5 py-5">
          <Logo />
        </div>
        <nav className="px-3 space-y-1">
          {NAV.map(item => <NavButton key={item.id} item={item} />)}
        </nav>
        <div className="mt-auto px-5 py-4 border-t border-slate-800/80 space-y-2">
          {activeDoc && (
            <Button variant="secondary" size="sm" className="w-full" onClick={startNew}>
              <RotateCcw className="w-3.5 h-3.5" /> Start new session
            </Button>
          )}
          <p className="text-[11px] leading-relaxed text-slate-600">
            Public samples only (CUAD / SEC EDGAR). Gemini · FAISS · FastAPI.
          </p>
        </div>
      </aside>

      {/* ---- Main column ---- */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="sticky top-0 z-20 border-b border-slate-800/80 bg-[#0a0e17]/85 backdrop-blur-md">
          <div className="flex items-center gap-4 px-4 sm:px-6 h-16">
            <div className="lg:hidden">
              <Logo compact />
            </div>
            <div className="min-w-0 hidden sm:block">
              <h1 className="text-[15px] font-semibold text-slate-100 leading-tight truncate">
                {meta.title}
              </h1>
              <p className="text-xs text-slate-500 truncate">{meta.subtitle}</p>
            </div>
            <div className="ml-auto flex items-center gap-3">
              <MetricsBadge />
              {activeDoc && (
                <Button variant="ghost" size="sm" className="lg:hidden" onClick={startNew}>
                  <RotateCcw className="w-3.5 h-3.5" /> New
                </Button>
              )}
            </div>
          </div>

          {/* Mobile nav strip */}
          <nav className="lg:hidden flex items-center gap-1 px-2 overflow-x-auto border-t border-slate-800/60">
            {NAV.map(item => <NavButton key={item.id} item={item} mobile />)}
          </nav>
        </header>

        {/* Content */}
        <main className="flex-1 w-full">
          <div className="max-w-4xl mx-auto w-full px-4 sm:px-6 py-6">
            {/* Active document context */}
            {activeDoc && tab !== 'upload' && tab !== 'evals' && (
              <div className="flex items-center gap-2.5 mb-5 text-xs text-slate-500 flex-wrap">
                <span className="inline-flex items-center gap-1.5 rounded-md bg-slate-800/60 border border-slate-700/60 px-2 py-1">
                  <FileText className="w-3.5 h-3.5 text-brand-400" />
                  <span className="text-slate-300 font-medium">{activeDoc.filename}</span>
                </span>
                <span className="tnum">{activeDoc.chunk_count} chunks</span>
                {activeDoc.embedded
                  ? <span className="text-emerald-500">· vector indexed</span>
                  : <span>· BM25 mode</span>}
                {docs.length > 1 && <span>· +{docs.length - 1} more loaded</span>}
              </div>
            )}

            <div className="animate-fade-in" key={tab}>
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
                <ComparePanel docs={docs} />
              </div>
              <div className={tab === 'evals' ? '' : 'hidden'}>
                <EvalsPanel />
              </div>
            </div>
          </div>
        </main>

        <footer className="border-t border-slate-800/80 py-4 px-6">
          <p className="text-center text-[11px] text-slate-600">
            ClauseLens — built as an AI engineering portfolio project · Public contract data only
          </p>
        </footer>
      </div>
    </div>
  )
}
