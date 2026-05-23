import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Copy, Filter, Send, Pencil, Trash2, Check, X } from 'lucide-react'
import { getPosts, publishApproved, editPost, deletePost } from '../api/client'
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

function CharCount({ text, limit }) {
  const len = (text || '').length
  const color = len > limit ? 'text-red-400' : len > limit * 0.85 ? 'text-yellow-400' : 'text-muted'
  return <span className={`text-xs tabular-nums ${color}`}>{len}/{limit}</span>
}

function HistoryEntry({ post, onUpdated, onDeleted }) {
  const [copied, setCopied]     = useState(false)
  const [editing, setEditing]   = useState(false)
  const [draft, setDraft]       = useState(post.content)
  const [saving, setSaving]     = useState(false)
  const [deleteArmed, setDeleteArmed] = useState(false)
  const deleteTimer = useRef(null)

  const isApproved = post.status === 'approved'

  function copy() {
    navigator.clipboard.writeText(post.caption || post.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  function startEdit() {
    setDraft(post.content)
    setEditing(true)
  }

  function cancelEdit() {
    setEditing(false)
    setDraft(post.content)
  }

  async function saveEdit() {
    if (!draft.trim() || draft === post.content) { cancelEdit(); return }
    setSaving(true)
    try {
      await editPost(post.id, draft.trim())
      onUpdated(post.id, draft.trim())
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  function armDelete() {
    setDeleteArmed(true)
    deleteTimer.current = setTimeout(() => setDeleteArmed(false), 3000)
  }

  async function confirmDelete() {
    clearTimeout(deleteTimer.current)
    await deletePost(post.id)
    onDeleted(post.id)
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

      {editing ? (
        <div className="mt-1">
          <textarea
            value={draft}
            onChange={e => setDraft(e.target.value)}
            rows={5}
            className="w-full bg-surface border border-primary rounded-lg p-3 text-sm text-white resize-none focus:outline-none"
            autoFocus
          />
          <div className="flex items-center justify-between mt-1">
            <CharCount text={draft} limit={280} />
            <div className="flex gap-2">
              <button onClick={cancelEdit} className="flex items-center gap-1 text-xs text-muted hover:text-white transition-colors px-2 py-1">
                <X size={12} /> Cancel
              </button>
              <button
                onClick={saveEdit}
                disabled={saving || !draft.trim()}
                className="flex items-center gap-1 text-xs bg-primary text-secondary px-3 py-1 rounded-lg disabled:opacity-50"
              >
                <Check size={12} /> {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-sm text-white whitespace-pre-wrap leading-relaxed">{post.content}</p>
      )}

      <div className="border border-border rounded-lg bg-secondary/60 p-3 mt-3">
        <p className="text-[10px] uppercase tracking-wider text-primary mb-1">X caption</p>
        <p className="text-sm text-white whitespace-pre-wrap leading-relaxed">{post.caption || post.content}</p>
      </div>
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

      <div className="flex items-center gap-3 mt-3">
        <button onClick={copy} className="flex items-center gap-1.5 text-xs text-muted hover:text-primary transition-colors">
          <Copy size={12} />
          {copied ? 'Copied!' : 'Copy'}
        </button>
        {isApproved && !editing && (
          <>
            <button onClick={startEdit} className="flex items-center gap-1.5 text-xs text-muted hover:text-primary transition-colors">
              <Pencil size={12} /> Edit
            </button>
            <button
              onClick={deleteArmed ? confirmDelete : armDelete}
              className={`flex items-center gap-1.5 text-xs transition-colors ${deleteArmed ? 'text-red-400 hover:text-red-300' : 'text-muted hover:text-red-400'}`}
            >
              <Trash2 size={12} />
              {deleteArmed ? 'Confirm delete' : 'Delete'}
            </button>
          </>
        )}
      </div>
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
  const [publishing, setPublishing] = useState(false)
  const [publishMsg, setPublishMsg] = useState('')

  function handleUpdated(id, newContent) {
    setPosts(prev => prev.map(p => p.id === id ? { ...p, content: newContent } : p))
  }

  function handleDeleted(id) {
    setPosts(prev => prev.filter(p => p.id !== id))
  }

  useEffect(() => {
    const nextStatus = searchParams.get('status') || 'posted'
    const createdToday = searchParams.get('created') === 'today'
    setStatusFilter(nextStatus)
    setWcOnly(searchParams.get('wc') === '1')
    setDateMode(createdToday ? 'created' : 'display')
    setDateFrom(createdToday ? todayISO() : '')
    setDateTo(createdToday ? todayISO() : '')
  }, [searchParams])

  function loadPosts() {
    setLoading(true)
    const status = statusFilter === 'all' ? '' : statusFilter
    getPosts(status)
      .then(r => setPosts(r.data))
      .catch(() => setPosts([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadPosts()
  }, [statusFilter])

  async function handlePublishApproved() {
    setPublishing(true)
    setPublishMsg('')
    try {
      const r = await publishApproved()
      const data = r.data || {}
      setPublishMsg(data.message || `Published ${data.published || 0} approved posts.`)
      loadPosts()
    } catch (e) {
      setPublishMsg(e?.response?.data?.detail || 'Publish failed. Check Twitter credentials and backend logs.')
    } finally {
      setPublishing(false)
    }
  }

  const filtered = posts.filter(p => {
    if (typeFilter && p.post_type !== typeFilter) return false
    if (wcOnly && !p.is_world_cup) return false
    const dateValue = dateMode === 'created' ? p.created_at : (p.posted_at || p.created_at)
    if (dateFrom && (!dateValue || dateValue < dateFrom)) return false
    if (dateTo && (!dateValue || dateValue > dateTo + 'T23:59:59')) return false
    return true
  })

  const canPublishFromView = statusFilter === 'approved'

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-primary">Post History</h1>
        <div className="flex items-center gap-3">
          {canPublishFromView && (
            <button
              onClick={handlePublishApproved}
              disabled={publishing || !filtered.length}
              className="btn-primary inline-flex items-center gap-2 text-sm disabled:opacity-60"
              title="Post all approved, unposted items to X"
            >
              <Send size={14} className={publishing ? 'animate-pulse' : ''} />
              {publishing ? 'Posting...' : 'Post approved'}
            </button>
          )}
          <span className="text-muted text-sm">{filtered.length} posts</span>
        </div>
      </div>
      {publishMsg && (
        <div className="card mb-4 border-primary/60 bg-primary/5">
          <p className="text-sm text-white">{publishMsg}</p>
        </div>
      )}

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
        {filtered.map(post => (
          <HistoryEntry key={post.id} post={post} onUpdated={handleUpdated} onDeleted={handleDeleted} />
        ))}
      </div>
    </div>
  )
}
