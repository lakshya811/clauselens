import { useCallback, useEffect, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, Loader2, Sparkles } from 'lucide-react'
import { uploadPdf, loadSample, listSamples, type UploadResponse, type SampleInfo } from '../api'

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
      // Simulate pipeline step labels
      const timer = setTimeout(() => setLoadingLabel('Chunking and indexing…'), 1200)
      const result = await uploadPdf(files[0])
      clearTimeout(timer)
      setLastUploaded(result)
      onUploaded(result)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Upload failed'
      // Surface helpful message for scanned/bad PDFs
      if (msg.toLowerCase().includes('422') || msg.toLowerCase().includes('unprocessable')) {
        setError('Could not extract text from this PDF. It may be scanned or image-only. Try a text-based PDF.')
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
    <div className="space-y-5">
      {/* Sample buttons */}
      {samples.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-gray-500 flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 text-indigo-400" />
            Try with a public sample contract — no upload needed
          </p>
          <div className="flex flex-wrap gap-2">
            {samples.map(s => (
              <button
                key={s.id}
                onClick={() => handleSample(s.id, s.label)}
                disabled={loading}
                className="flex items-center gap-2 bg-indigo-950/60 hover:bg-indigo-900/60 border border-indigo-800/50 hover:border-indigo-600/60 disabled:opacity-50 text-indigo-300 px-3 py-2 rounded-lg text-sm transition-colors"
              >
                <FileText className="w-3.5 h-3.5 shrink-0" />
                <span className="font-medium">{s.label}</span>
                <span className="text-indigo-500 text-xs hidden sm:inline">{s.description}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-indigo-500 bg-indigo-950/30'
            : 'border-gray-700 hover:border-gray-500 bg-gray-900/50'
        } ${loading ? 'opacity-60 pointer-events-none' : ''}`}
      >
        <input {...getInputProps()} />
        {loading ? (
          <div className="flex flex-col items-center gap-3 text-gray-400">
            <Loader2 className="w-10 h-10 animate-spin text-indigo-400" />
            <p className="text-sm">{loadingLabel}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 text-gray-400">
            <Upload className="w-10 h-10 text-indigo-400" />
            <p className="text-lg font-medium text-gray-200">
              {isDragActive ? 'Drop to upload' : 'Drag & drop your own PDF'}
            </p>
            <p className="text-sm">or click to browse · max 15 MB</p>
          </div>
        )}
      </div>

      {error && (
        <p className="text-red-400 text-sm bg-red-950/40 border border-red-800/50 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {lastUploaded && (
        <div className="card flex items-start gap-3">
          <FileText className="w-5 h-5 text-indigo-400 mt-0.5 shrink-0" />
          <div className="min-w-0">
            <p className="font-medium text-gray-100 truncate">{lastUploaded.filename}</p>
            <p className="text-sm text-gray-400 mt-0.5">
              {lastUploaded.page_count} pages · {lastUploaded.chunk_count} chunks
              {lastUploaded.ocr_page_count > 0 && ` · ${lastUploaded.ocr_page_count} OCR pages`}
              {lastUploaded.embedded && ' · vector indexed ✓'}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
