import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Copy, Filter } from 'lucide-react'
import { getPosts } from '../api/client'
import { postTypeColors } from '../styles/theme'

function TypeBadge({ type }) {
  const cfg = postTypeColors[type] || { bg: '#1a2235', text: '#8b949e', border: '#1e2d4a', label: type }
  return (
    <span
      className="text-xs font-bold px-2 py-0.5 rounded-full border"
      style={{ background: cfg.bg, color: cfg.text, borderColor: cfg.border }}
    >
      {cfg.label}
    </span>
  )
}

function HistoryEntry({ post }) {
  const [copied, setCopied] = useState(false)

  function copy() {
    navigator.clipboard.writeText(post.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const displayDate = post.posted_at || post.created_at
  const displayDateLabel = post.posted_at ? 'Posted' : 'Created'
  const shownAt = displayDate
    ? new Date(displayDate).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })
    : 'Unknown'

  return (
    <div className="card hover:border-primary transition-colors">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <TypeBadge type={post.post_type} />
        <span className="badge bg-surface text-muted text-xs capitalize">{post.status}</span>
        {post.is_world_cup && <span className="badge bg-primary text-secondary text-xs">World Cup</span>}
        <span className="text-xs text-muted ml-auto">{displayDateLabel}: {shownAt}</span>
      </div>
      <p className="text-xs text-muted mb-2 line-clamp-1">{post.story_title}</p>
      <p className="text-sm text-white whitespace-pre-wrap leading-relaxed">{post.content}</p>
      {post.hashtags && (
        <div className="flex flex-wrap gap-1 mt-2">
          {post.hashtags.split(/[,\s]+/).filter(Boolean).map(t => (
            <span key={t} className="text-xs text-primary">
              {t.startsWith('#') ? t : `#${t}`}
            </span>
          ))}
        </div>
      )}
      {post.image_url && (
        <div className="mt-4 overflow-hidden rounded-lg border border-border bg-surface">
          <img
            src={post.image_url}
            alt="Generated post visual preview"
            className="w-full max-h-[460px] object-contain bg-black"
            loading="lazy"
          />
        </div>
      )}
      <button
        onClick={copy}
        className="flex items-center gap-1.5 text-xs text-muted hover:text-primary mt-3 transition-colors"
      >
        <Copy size={12} />
        {copied ? 'Copied!' : 'Copy'}
      </button>
    </div>
  )
}

const TYPE_OPTIONS = [
  { value: '',             label: 'All Types' },
  { value: 'hot_take',     label: 'Hot Take' },
  { value: 'data_stats',   label: 'Data & Stats' },
  { value: 'tactical',     label: 'Tactical' },
  { value: 'wc_narrative', label: 'WC Narrative' },
]

const STATUS_OPTIONS = [
  { value: 'all',      label: 'All Statuses' },
  { value: 'posted',   label: 'Posted' },
  { value: 'approved', label: 'Approved' },
  { value: 'pending',  label: 'Pending' },
  { value: 'rejected', label: 'Rejected' },
]

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

export default function PostHistory() {
  const [searchParams] = useSearchParams()
  const [posts, setPosts]         = useState([])
  const [loading, setLoading]     = useState(true)
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || 'posted')
  const [typeFilter, setTypeFilter] = useState('')
  const [wcOnly, setWcOnly]       = useState(searchParams.get('wc') === '1')
  const [dateMode, setDateMode]   = useState(searchParams.get('created') === 'today' ? 'created' : 'display')
  const [dateFrom, setDateFrom]   = useState(searchParams.get('created') === 'today' ? todayISO() : '')
  const [dateTo, setDateTo]       = useState(searchParams.get('created') === 'today' ? todayISO() : '')

  useEffect(() => {
    const nextStatus = searchParams.get('status') || 'posted'
    const createdToday = searchParams.get('created') === 'today'
    setStatusFilter(nextStatus)
    setWcOnly(searchParams.get('wc') === '1')
    setDateMode(createdToday ? 'created' : 'display')
    setDateFrom(createdToday ? todayISO() : '')
    setDateTo(createdToday ? todayISO() : '')
  }, [searchParams])

  useEffect(() => {
    const status = statusFilter === 'all' ? '' : statusFilter
    getPosts(status)
      .then(r => setPosts(r.data))
      .catch(() => setPosts([]))
      .finally(() => setLoading(false))
  }, [statusFilter])

  const filtered = posts.filter(p => {
    if (typeFilter && p.post_type !== typeFilter) return false
    if (wcOnly && !p.is_world_cup) return false
    const dateValue = dateMode === 'created' ? p.created_at : (p.posted_at || p.created_at)
    if (dateFrom && (!dateValue || dateValue < dateFrom)) return false
    if (dateTo && (!dateValue || dateValue > dateTo + 'T23:59:59')) return false
    return true
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-primary">Post History</h1>
        <span className="text-muted text-sm">{filtered.length} posts</span>
      </div>

      {/* Filters */}
      <div className="card mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <Filter size={16} className="text-muted flex-shrink-0" />
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="bg-surface border border-border text-white text-sm rounded-lg px-3 py-2 focus:border-primary outline-none"
          >
            {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <select
            value={dateMode}
            onChange={e => setDateMode(e.target.value)}
            className="bg-surface border border-border text-white text-sm rounded-lg px-3 py-2 focus:border-primary outline-none"
          >
            <option value="display">Posted/Created Date</option>
            <option value="created">Created Date</option>
          </select>
          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            className="bg-surface border border-border text-white text-sm rounded-lg px-3 py-2 focus:border-primary outline-none"
          />
          <span className="text-muted text-sm">to</span>
          <input
            type="date"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
            className="bg-surface border border-border text-white text-sm rounded-lg px-3 py-2 focus:border-primary outline-none"
          />
          <select
            value={typeFilter}
            onChange={e => setTypeFilter(e.target.value)}
            className="bg-surface border border-border text-white text-sm rounded-lg px-3 py-2 focus:border-primary outline-none"
          >
            {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <label className="flex items-center gap-2 text-sm text-muted cursor-pointer">
            <input type="checkbox" checked={wcOnly} onChange={e => setWcOnly(e.target.checked)} className="accent-primary" />
            World Cup only
          </label>
        </div>
      </div>

      {loading && <p className="text-muted text-sm">Loading history...</p>}
      {!loading && !filtered.length && (
        <div className="card text-center py-12">
          <p className="text-muted">No content found for these filters.</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filtered.map(post => <HistoryEntry key={post.id} post={post} />)}
      </div>
    </div>
  )
}
