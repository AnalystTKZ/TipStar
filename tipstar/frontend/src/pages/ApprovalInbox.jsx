import { useEffect, useState, useCallback } from 'react'
import { Check, X, Edit2, Copy, Trash2, CheckCheck, Sparkles } from 'lucide-react'
import { postTypeColors } from '../styles/theme'
import { getPendingPosts, approvePost, rejectPost, editPost, deletePost, generatePosts, getGenerationStatus } from '../api/client'

const TYPE_OPTIONS = [
  { value: '',             label: 'All Types' },
  { value: 'hot_take',     label: 'Hot Take' },
  { value: 'data_stats',   label: 'Data & Stats' },
  { value: 'tactical',     label: 'Tactical' },
  { value: 'wc_narrative', label: 'WC Narrative' },
]

function ScorePill({ score }) {
  const color = score >= 9 ? '#22C55E' : score >= 7 ? '#6CABDD' : score >= 5 ? '#F59E0B' : '#EF4444'
  return (
    <span className="text-xs font-bold px-2 py-0.5 rounded-full border" style={{ color, borderColor: color }}>
      {score}/10
    </span>
  )
}

function TypeBadge({ type }) {
  const cfg = postTypeColors[type] || { bg: '#1a2235', text: '#8b949e', border: '#1e2d4a', label: type }
  return (
    <span className="text-xs font-bold px-2.5 py-0.5 rounded-full border"
      style={{ background: cfg.bg, color: cfg.text, borderColor: cfg.border }}>
      {cfg.label}
    </span>
  )
}

function CharCount({ content }) {
  const len = (content || '').length
  const color = len > 280 ? '#EF4444' : len > 240 ? '#F59E0B' : '#6b7280'
  return (
    <span className="text-xs tabular-nums" style={{ color }}>{len}/280</span>
  )
}

function HashtagChips({ raw }) {
  if (!raw) return null
  const tags = raw.split(/[,\s]+/).filter(Boolean).map(t => t.startsWith('#') ? t : `#${t}`)
  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {tags.map(t => (
        <span key={t} className="text-xs text-primary bg-secondary px-2 py-0.5 rounded-full">{t}</span>
      ))}
    </div>
  )
}

function PostCard({ post, onAction }) {
  const [editing, setEditing]       = useState(false)
  const [editContent, setEditContent] = useState(post.content)
  const [loading, setLoading]       = useState(false)
  const [confirming, setConfirming] = useState(false)

  async function act(fn) {
    setLoading(true)
    try { await fn() } finally { setLoading(false) }
  }

  const handleApprove = () => act(async () => { await approvePost(post.id); onAction?.() })
  const handleReject  = () => act(async () => { await rejectPost(post.id);  onAction?.() })

  const handleDelete = async () => {
    if (!confirming) {
      setConfirming(true)
      setTimeout(() => setConfirming(false), 3000)
      return
    }
    await act(async () => { await deletePost(post.id); onAction?.() })
  }

  const handleEditApprove = () => act(async () => {
    if (!editing) { setEditing(true); setLoading(false); return }
    await editPost(post.id, editContent)
    onAction?.()
  })

  const handleCopy = () => navigator.clipboard.writeText(post.content)

  return (
    <div className="bg-card border border-border rounded-xl p-4 hover:border-primary/50 transition-colors">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <TypeBadge type={post.post_type} />
        {post.is_world_cup && <span className="badge bg-primary text-secondary">World Cup</span>}
        <ScorePill score={post.relevance_score} />
        <span className="text-muted text-xs ml-auto">{post.best_time}</span>
      </div>

      {editing ? (
        <div className="relative">
          <textarea
            className="w-full bg-surface border border-border rounded-lg p-3 text-sm text-white resize-none focus:border-primary outline-none"
            rows={4}
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            autoFocus
          />
          <div className="absolute bottom-2 right-3">
            <CharCount content={editContent} />
          </div>
        </div>
      ) : (
        <p className="text-sm leading-relaxed text-white whitespace-pre-wrap">{post.content}</p>
      )}

      <HashtagChips raw={post.hashtags} />

      {post.image_url && (
        <div className="mt-4 overflow-hidden rounded-lg border border-border bg-surface">
          <img
            src={post.image_url}
            alt="Generated post visual preview"
            className="w-full max-h-[420px] object-contain bg-black"
            loading="lazy"
          />
        </div>
      )}

      <div className="flex items-center gap-2 mt-4 flex-wrap">
        <button onClick={handleApprove} disabled={loading}
          className="flex items-center gap-1.5 btn-primary text-sm py-1.5 disabled:opacity-60">
          <Check size={14} /> Approve
        </button>
        <button onClick={handleReject} disabled={loading}
          className="flex items-center gap-1.5 btn-danger text-sm py-1.5 disabled:opacity-60">
          <X size={14} /> Reject
        </button>
        <button onClick={handleEditApprove} disabled={loading}
          className="flex items-center gap-1.5 btn-ghost text-sm py-1.5"
          style={editing ? { borderColor: '#F59E0B', color: '#F59E0B' } : {}}>
          <Edit2 size={14} /> {editing ? 'Save & Approve' : 'Edit'}
        </button>
        {editing && (
          <button onClick={() => { setEditing(false); setEditContent(post.content) }}
            className="btn-ghost text-sm py-1.5">Cancel</button>
        )}
        <div className="ml-auto flex items-center gap-2">
          {!editing && <CharCount content={post.content} />}
          <button onClick={handleCopy} title="Copy" className="text-muted hover:text-primary transition-colors p-1">
            <Copy size={14} />
          </button>
          <button onClick={handleDelete} title={confirming ? 'Click again to confirm delete' : 'Delete'}
            className={`transition-colors p-1 ${confirming ? 'text-danger' : 'text-muted hover:text-danger'}`}>
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ApprovalInbox() {
  const [posts, setPosts]             = useState([])
  const [loading, setLoading]         = useState(true)
  const [typeFilter, setTypeFilter]   = useState('')
  const [wcOnly, setWcOnly]           = useState(false)
  const [minScore, setMinScore]       = useState(5)
  const [bulkLoading, setBulkLoading] = useState(false)
  const [generating, setGenerating]   = useState(false)
  const [msg, setMsg]                 = useState('')

  const loadPosts = useCallback(() => {
    setLoading(true)
    getPendingPosts()
      .then(r => setPosts(r.data))
      .catch(() => setPosts([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadPosts() }, [loadPosts])

  const filtered = posts.filter(p =>
    p.relevance_score >= minScore &&
    (!wcOnly || p.is_world_cup) &&
    (!typeFilter || p.post_type === typeFilter)
  )

  // Group by story_title
  const groups = filtered.reduce((acc, post) => {
    const key = post.story_title || 'Ungrouped'
    if (!acc[key]) acc[key] = []
    acc[key].push(post)
    return acc
  }, {})

  const handleBulkApprove = async () => {
    setBulkLoading(true)
    setMsg('')
    try {
      await Promise.all(filtered.map(p => approvePost(p.id)))
      setMsg(`Approved ${filtered.length} posts.`)
      loadPosts()
    } catch {
      setMsg('Bulk approve partially failed.')
    } finally {
      setBulkLoading(false)
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    setMsg('')
    try {
      const r = await generatePosts(20, minScore)
      setMsg(r.data.message)
      pollGenerationJob(r.data.job_id)
    } catch {
      setMsg('Generation failed - check GROQ_API_KEY.')
      setGenerating(false)
    }
  }

  const pollGenerationJob = (jobId) => {
    if (!jobId) {
      setGenerating(false)
      setMsg('Generation started, but no job id was returned. Refresh again in a moment.')
      return
    }

    const poll = async () => {
      try {
        const r = await getGenerationStatus(jobId)
        const job = r.data
        const total = job.total || 0
        const progress = total ? ` ${job.processed}/${total}` : ''
        setMsg(`${job.message}${progress} | Posts: ${job.generated_posts || 0} | Skipped: ${job.skipped || 0}`)

        getPendingPosts().then(p => setPosts(p.data)).catch(() => {})

        if (job.status === 'complete' || job.status === 'failed') {
          setGenerating(false)
          return
        }
      } catch {
        setMsg('Waiting for generation status...')
      }
      setTimeout(poll, 2500)
    }
    setTimeout(poll, 1000)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-primary">Approval Inbox</h1>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="badge bg-warning/20 text-warning border border-warning text-sm">
            {filtered.length} pending
          </span>
          {filtered.length > 0 && (
            <button onClick={handleBulkApprove} disabled={bulkLoading}
              className="btn-primary inline-flex items-center gap-1.5 text-sm py-1.5 disabled:opacity-60">
              <CheckCheck size={14} />
              {bulkLoading ? 'Approving…' : `Approve all (${filtered.length})`}
            </button>
          )}
          <button onClick={handleGenerate} disabled={generating}
            className="btn-ghost inline-flex items-center gap-1.5 text-sm py-1.5 disabled:opacity-60">
            <Sparkles size={14} className={generating ? 'animate-pulse' : ''} />
            {generating ? 'Generating…' : 'Generate more'}
          </button>
        </div>
      </div>

      {msg && <div className="mb-4 text-xs text-muted border border-border bg-card rounded-lg px-4 py-2.5">{msg}</div>}

      {/* Filter bar */}
      <div className="card mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
            className="bg-surface border border-border text-white text-sm rounded-lg px-3 py-2 focus:border-primary outline-none">
            {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <label className="flex items-center gap-2 text-sm text-muted cursor-pointer">
            <input type="checkbox" checked={wcOnly} onChange={e => setWcOnly(e.target.checked)}
              className="accent-primary" />
            World Cup only
          </label>

          <div className="flex items-center gap-3 flex-1 min-w-48">
            <span className="text-sm text-muted whitespace-nowrap">Min score: {minScore}</span>
            <input type="range" min={1} max={10} value={minScore}
              onChange={e => setMinScore(Number(e.target.value))}
              className="flex-1 accent-primary" />
          </div>

          <button onClick={loadPosts} className="btn-ghost text-sm py-1.5">Refresh</button>
        </div>
      </div>

      {loading && <p className="text-muted text-sm">Loading posts...</p>}

      {!loading && !filtered.length && (
        <div className="card text-center py-12">
          <p className="text-muted mb-3">No posts in queue.</p>
          <button onClick={handleGenerate} disabled={generating}
            className="btn-primary inline-flex items-center gap-2 mx-auto disabled:opacity-60">
            <Sparkles size={14} />
            {generating ? 'Generating…' : 'Generate from latest news'}
          </button>
        </div>
      )}

      {/* Grouped by story */}
      {!loading && Object.entries(groups).map(([storyTitle, storyPosts]) => (
        <div key={storyTitle} className="mb-8">
          <div className="flex items-start gap-2 mb-3">
            <div className="flex-1 min-w-0">
              <p className="text-xs text-muted uppercase tracking-wider mb-0.5">Story</p>
              <p className="text-sm font-medium text-white leading-snug">{storyTitle}</p>
            </div>
            <span className="text-xs text-muted flex-shrink-0 mt-4">{storyPosts.length} post{storyPosts.length !== 1 ? 's' : ''}</span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {storyPosts.map(post => (
              <PostCard key={post.id} post={post} onAction={loadPosts} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
