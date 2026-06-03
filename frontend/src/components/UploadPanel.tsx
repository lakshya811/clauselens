import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, Loader2 } from 'lucide-react'
import { uploadPdf, type UploadResponse } from '../api'

interface Props {
  onUploaded: (doc: UploadResponse) => void
}

export function UploadPanel({ onUploaded }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUploaded, setLastUploaded] = useState<UploadResponse | null>(null)

  const onDrop = useCallback(async (files: File[]) => {
    if (!files[0]) return
    setError(null)
    setLoading(true)
    try {
      const result = await uploadPdf(files[0])
      setLastUploaded(result)
      onUploaded(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setLoading(false)
    }
  }, [onUploaded])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: loading,
  })

  return (
    <div className="space-y-4">
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
            <p>Uploading and indexing…</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 text-gray-400">
            <Upload className="w-10 h-10 text-indigo-400" />
            <p className="text-lg font-medium text-gray-200">
              {isDragActive ? 'Drop to upload' : 'Drag & drop a PDF'}
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
              {lastUploaded.embedded && ' · indexed ✓'}
            </p>
            <p className="text-xs text-gray-600 mt-1 font-mono">{lastUploaded.doc_id}</p>
          </div>
        </div>
      )}
    </div>
  )
}
