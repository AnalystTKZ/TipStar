import { useEffect, useState } from 'react'
import { Copy, Filter } from 'lucide-react'
import { getPostHistory } from '../api/client'
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

  const postedAt = post.posted_at
    ? new Date(post.posted_at).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })
    : 'Unknown'

  return (
    <div className="card hover:border-primary transition-colors">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <TypeBadge type={post.post_type} />
        {post.is_world_cup && <span className="badge bg-primary text-secondary text-xs">World Cup</span>}
        <span className="text-xs text-muted ml-auto">{postedAt}</span>
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

export default function PostHistory() {
  const [posts, setPosts]         = useState([])
  const [loading, setLoading]     = useState(true)
  const [typeFilter, setTypeFilter] = useState('')
  const [wcOnly, setWcOnly]       = useState(false)
  const [dateFrom, setDateFrom]   = useState('')
  const [dateTo, setDateTo]       = useState('')

  useEffect(() => {
    getPostHistory()
      .then(r => setPosts(r.data))
      .catch(() => setPosts([]))
      .finally(() => setLoading(false))
  }, [])

  const filtered = posts.filter(p => {
    if (typeFilter && p.post_type !== typeFilter) return false
    if (wcOnly && !p.is_world_cup) return false
    if (dateFrom && p.posted_at && p.posted_at < dateFrom) return false
    if (dateTo && p.posted_at && p.posted_at > dateTo + 'T23:59:59') return false
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
          <p className="text-muted">No posted content found.</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filtered.map(post => <HistoryEntry key={post.id} post={post} />)}
      </div>
    </div>
  )
}
