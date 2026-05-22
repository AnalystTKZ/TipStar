import { useState } from 'react'
import { Check, X, Edit2, Copy } from 'lucide-react'
import { postTypeColors } from '../styles/theme'
import { approvePost, rejectPost, editPost } from '../api/client'

// Relevance score colour indicator
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
    <span
      className="text-xs font-bold px-2.5 py-0.5 rounded-full border"
      style={{ background: cfg.bg, color: cfg.text, borderColor: cfg.border }}
    >
      {cfg.label}
    </span>
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

export default function PostCard({ post, onAction }) {
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState(post.content)
  const [editCaption, setEditCaption] = useState(post.caption || '')
  const [loading, setLoading] = useState(false)

  async function handleApprove() {
    setLoading(true)
    try {
      await approvePost(post.id)
      onAction?.()
    } finally { setLoading(false) }
  }

  async function handleReject() {
    setLoading(true)
    try {
      await rejectPost(post.id)
      onAction?.()
    } finally { setLoading(false) }
  }

  async function handleEditApprove() {
    if (!editing) { setEditing(true); return }
    setLoading(true)
    try {
      await editPost(post.id, editContent, editCaption)
      onAction?.()
    } finally { setLoading(false) }
  }

  function handleCopy() {
    navigator.clipboard.writeText(post.caption || post.content)
  }

  return (
    <div className="card hover:border-primary transition-colors">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <TypeBadge type={post.post_type} />
        {post.is_world_cup && (
          <span className="badge bg-primary text-secondary">World Cup</span>
        )}
        <ScorePill score={post.relevance_score} />
        <span className="text-muted text-xs ml-auto">{post.best_time}</span>
      </div>

      {/* Story title */}
      <p className="text-muted text-xs mb-3 line-clamp-2">{post.story_title}</p>

      {/* Content */}
      {editing ? (
        <div className="space-y-3">
          <textarea
            className="w-full bg-surface border border-border rounded-lg p-3 text-sm text-white resize-none focus:border-primary outline-none"
            rows={4}
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
          />
          <textarea
            className="w-full bg-secondary border border-border rounded-lg p-3 text-sm text-white resize-none focus:border-primary outline-none"
            rows={3}
            value={editCaption}
            onChange={e => setEditCaption(e.target.value)}
            placeholder="X caption"
          />
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm leading-relaxed text-white whitespace-pre-wrap">{post.content}</p>
          <div className="border border-border rounded-lg bg-secondary/60 p-3">
            <p className="text-[10px] uppercase tracking-wider text-primary mb-1">X caption</p>
            <p className="text-sm leading-relaxed text-white whitespace-pre-wrap">{post.caption || post.content}</p>
          </div>
        </div>
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

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4">
        <button
          onClick={handleApprove}
          disabled={loading}
          className="flex items-center gap-1.5 btn-primary text-sm py-1.5"
        >
          <Check size={14} /> Approve
        </button>
        <button
          onClick={handleReject}
          disabled={loading}
          className="flex items-center gap-1.5 btn-danger text-sm py-1.5"
        >
          <X size={14} /> Reject
        </button>
        <button
          onClick={handleEditApprove}
          disabled={loading}
          className="flex items-center gap-1.5 btn-ghost text-sm py-1.5"
          style={editing ? { borderColor: '#F59E0B', color: '#F59E0B' } : {}}
        >
          <Edit2 size={14} /> {editing ? 'Save & Approve' : 'Edit'}
        </button>
        {editing && (
          <button onClick={() => { setEditing(false); setEditContent(post.content); setEditCaption(post.caption || '') }} className="btn-ghost text-sm py-1.5">
            Cancel
          </button>
        )}
        <button onClick={handleCopy} className="ml-auto text-muted hover:text-primary transition-colors">
          <Copy size={14} />
        </button>
      </div>
    </div>
  )
}
