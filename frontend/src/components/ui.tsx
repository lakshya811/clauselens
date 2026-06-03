import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Loader2 } from 'lucide-react'

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------
export function Card({
  className = '',
  children,
}: {
  className?: string
  children: ReactNode
}) {
  return (
    <div className={`rounded-xl border border-slate-800 bg-slate-900/60 shadow-card ${className}`}>
      {children}
    </div>
  )
}

export function CardHeader({ title, right }: { title: string; right?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-slate-800">
      <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
      {right}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  loading?: boolean
}

const BTN_VARIANTS: Record<string, string> = {
  primary: 'bg-brand-600 hover:bg-brand-500 text-white shadow-soft',
  secondary:
    'border border-slate-700 hover:border-slate-600 bg-slate-800/60 hover:bg-slate-800 text-slate-200',
  ghost: 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60',
  danger: 'bg-red-600 hover:bg-red-500 text-white',
}

const BTN_SIZES: Record<string, string> = {
  sm: 'text-xs px-2.5 py-1.5 rounded-lg gap-1.5',
  md: 'text-sm px-4 py-2 rounded-lg gap-2',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  className = '',
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center font-medium transition-colors
        disabled:opacity-50 disabled:pointer-events-none
        ${BTN_SIZES[size]} ${BTN_VARIANTS[variant]} ${className}`}
      {...rest}
    >
      {loading && <Loader2 className="w-4 h-4 animate-spin" />}
      {children}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------
type Tone =
  | 'neutral'
  | 'brand'
  | 'success'
  | 'high'
  | 'medium'
  | 'low'
  | 'structural'
  | 'semantic'
  | 'surface'

const BADGE_TONES: Record<Tone, string> = {
  neutral: 'bg-slate-800 text-slate-300 ring-slate-700',
  brand: 'bg-brand-500/10 text-brand-300 ring-brand-500/30',
  success: 'bg-emerald-500/10 text-emerald-300 ring-emerald-500/30',
  high: 'bg-red-500/10 text-red-300 ring-red-500/30',
  medium: 'bg-amber-500/10 text-amber-300 ring-amber-500/30',
  low: 'bg-emerald-500/10 text-emerald-300 ring-emerald-500/30',
  structural: 'bg-red-500/10 text-red-300 ring-red-500/30',
  semantic: 'bg-amber-500/10 text-amber-300 ring-amber-500/30',
  surface: 'bg-sky-500/10 text-sky-300 ring-sky-500/30',
}

export function Badge({
  tone = 'neutral',
  className = '',
  children,
}: {
  tone?: Tone
  className?: string
  children: ReactNode
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold
        ring-1 ring-inset ${BADGE_TONES[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------
export function EmptyState({
  icon,
  title,
  hint,
}: {
  icon?: ReactNode
  title: string
  hint?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-14 px-4 gap-2.5">
      {icon && <div className="text-slate-600 mb-1">{icon}</div>}
      <p className="text-slate-300 font-medium">{title}</p>
      {hint && <p className="text-sm text-slate-500 max-w-sm leading-relaxed">{hint}</p>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inline alert (errors)
// ---------------------------------------------------------------------------
export function Alert({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
      {children}
    </div>
  )
}
