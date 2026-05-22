import { useEffect, useState, useCallback } from 'react'
import PostCard from '../components/PostCard'
import { getPendingPosts } from '../api/client'

const TYPE_OPTIONS = [
  { value: '',             label: 'All Types' },
  { value: 'hot_take',     label: 'Hot Take' },
  { value: 'data_stats',   label: 'Data & Stats' },
  { value: 'tactical',     label: 'Tactical' },
  { value: 'wc_narrative', label: 'WC Narrative' },
]

export default function ApprovalInbox() {
  const [posts, setPosts]         = useState([])
  const [loading, setLoading]     = useState(true)
  const [typeFilter, setTypeFilter] = useState('')
  const [wcOnly, setWcOnly]       = useState(false)
  const [minScore, setMinScore]   = useState(5)

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

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-primary">Approval Inbox</h1>
        <span className="badge bg-warning/20 text-warning border border-warning text-sm">
          {filtered.length} pending
        </span>
      </div>

      {/* Filter bar */}
      <div className="card mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <select
            value={typeFilter}
            onChange={e => setTypeFilter(e.target.value)}
            className="bg-surface border border-border text-white text-sm rounded-lg px-3 py-2 focus:border-primary outline-none"
          >
            {TYPE_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          <label className="flex items-center gap-2 text-sm text-muted cursor-pointer">
            <input
              type="checkbox"
              checked={wcOnly}
              onChange={e => setWcOnly(e.target.checked)}
              className="accent-primary"
            />
            World Cup only
          </label>

          <div className="flex items-center gap-3 flex-1 min-w-48">
            <span className="text-sm text-muted whitespace-nowrap">Min score: {minScore}</span>
            <input
              type="range" min={1} max={10} value={minScore}
              onChange={e => setMinScore(Number(e.target.value))}
              className="flex-1 accent-primary"
            />
          </div>

          <button onClick={loadPosts} className="btn-ghost text-sm py-1.5">Refresh</button>
        </div>
      </div>

      {loading && <p className="text-muted text-sm">Loading posts...</p>}
      {!loading && !filtered.length && (
        <div className="card text-center py-12">
          <p className="text-muted">No posts match your filters.</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filtered.map(post => (
          <PostCard key={post.id} post={post} onAction={loadPosts} />
        ))}
      </div>
    </div>
  )
}
