import { useCallback, useEffect, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, Loader2, Sparkles, CheckCircle2, AlertTriangle } from 'lucide-react'
import { uploadPdf, loadSample, listSamples, type UploadResponse, type SampleInfo } from '../api'
import { Card, Alert } from './ui'

interface Props {
  onUploaded: (doc: UploadResponse) => void
}

export function UploadPanel({ onUploaded }: Props) {
  const [loading, setLoading] = useState(false)
  const [loadingLabel, setLoadingLabel] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [lastUploaded, setLastUploaded] = useState<UploadResponse | null>(null)
  const [samples, setSamples] = useState<SampleInfo[]>([])

  useEffect(() => {
    listSamples().then(setSamples).catch(() => null)
  }, [])

  const onDrop = useCallback(async (files: File[]) => {
    if (!files[0]) return
    setError(null)
    setLoading(true)
    setLoadingLabel('Parsing PDF…')
    try {
      const timer = setTimeout(() => setLoadingLabel('Chunking and indexing…'), 1200)
      const result = await uploadPdf(files[0])
      clearTimeout(timer)
      setLastUploaded(result)
      onUploaded(result)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Upload failed'
      if (msg.toLowerCase().includes('422') || msg.toLowerCase().includes('unprocessable')) {
        setError('Could not extract text from this PDF — it may be scanned or image-only. Try a text-based PDF, or use a sample below.')
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
      setLoadingLabel('')
    }
  }, [onUploaded])

  async function handleSample(id: string, label: string) {
    setError(null)
    setLoading(true)
    setLoadingLabel(`Loading ${label}…`)
    try {
      const result = await loadSample(id)
      setLastUploaded(result)
      onUploaded(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load sample')
    } finally {
      setLoading(false)
      setLoadingLabel('')
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: loading,
  })

  return (
    <div className="space-y-6">
      {/* Samples — primary call to action */}
      {samples.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-brand-400" />
            <h2 className="text-sm font-semibold text-slate-200">Try it instantly</h2>
            <span className="text-xs text-slate-500">— no upload needed, runs in seconds</span>
          </div>
          <div className="grid sm:grid-cols-3 gap-3">
            {samples.map(s => (
              <button
                key={s.id}
                onClick={() => handleSample(s.id, s.label)}
                disabled={loading}
                className="group text-left rounded-xl border border-slate-800 bg-slate-900/60 hover:border-brand-500/50 hover:bg-slate-900
                  disabled:opacity-50 disabled:pointer-events-none transition-colors p-4 shadow-card"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="grid place-items-center w-9 h-9 rounded-lg bg-brand-500/10 text-brand-300 ring-1 ring-inset ring-brand-500/20">
                    <FileText className="w-[18px] h-[18px]" />
                  </div>
                  <span className="text-[11px] text-slate-600 group-hover:text-brand-400 transition-colors">
                    Open →
                  </span>
                </div>
                <p className="text-sm font-medium text-slate-100">{s.label}</p>
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{s.description}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Divider */}
      <div className="flex items-center gap-3 text-xs text-slate-600">
        <span className="flex-1 hr" />
        or upload your own
        <span className="flex-1 hr" />
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`rounded-xl border-2 border-dashed p-10 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-brand-500 bg-brand-500/5'
            : 'border-slate-700 hover:border-slate-600 bg-slate-900/40'
        } ${loading ? 'opacity-60 pointer-events-none' : ''}`}
      >
        <input {...getInputProps()} />
        {loading ? (
          <div className="flex flex-col items-center gap-3 text-slate-400">
            <Loader2 className="w-9 h-9 animate-spin text-brand-400" />
            <p className="text-sm">{loadingLabel}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2.5">
            <div className="grid place-items-center w-12 h-12 rounded-xl bg-slate-800/80 text-brand-400 mb-1">
              <Upload className="w-6 h-6" />
            </div>
            <p className="text-base font-medium text-slate-200">
              {isDragActive ? 'Drop to upload' : 'Drag & drop a contract PDF'}
            </p>
            <p className="text-sm text-slate-500">or click to browse · max 15 MB</p>
          </div>
        )}
      </div>

      {error && (
        <Alert>
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </Alert>
      )}

      {lastUploaded && (
        <Card className="p-4 flex items-start gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 mt-0.5 shrink-0" />
          <div className="min-w-0">
            <p className="font-medium text-slate-100 truncate">{lastUploaded.filename}</p>
            <p className="text-sm text-slate-500 mt-0.5 tnum">
              {lastUploaded.page_count} pages · {lastUploaded.chunk_count} chunks
              {lastUploaded.ocr_page_count > 0 && ` · ${lastUploaded.ocr_page_count} OCR pages`}
              {lastUploaded.embedded && ' · vector indexed'}
            </p>
          </div>
        </Card>
      )}
    </div>
  )
}
