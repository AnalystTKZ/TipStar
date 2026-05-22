import { useEffect, useState } from 'react'
import { ExternalLink, Globe } from 'lucide-react'
import { getNewsFeed } from '../api/client'

function ScoreDot({ score }) {
  const color = score >= 9 ? 'bg-success' : score >= 7 ? 'bg-primary' : score >= 5 ? 'bg-warning' : 'bg-muted'
  return <span className={`inline-block w-2 h-2 rounded-full ${color} mr-2 flex-shrink-0`} />
}

export default function NewsFeed({ limit = 10 }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getNewsFeed(1, limit)
      .then(r => setItems(r.data))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [limit])

  if (loading) return <div className="text-muted text-sm p-4">Loading news...</div>
  if (!items.length) return <div className="text-muted text-sm p-4">No news items found.</div>

  return (
    <div className="space-y-2">
      {items.map(item => (
        <div key={item.id} className="flex items-start gap-2 p-3 bg-surface rounded-lg hover:border-primary border border-transparent transition-colors">
          <ScoreDot score={item.relevance_score} />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white line-clamp-2">{item.title}</p>
            <div className="flex items-center gap-2 mt-1">
              <Globe size={11} className="text-muted" />
              <span className="text-xs text-muted">{item.source}</span>
              {item.is_world_cup && (
                <span className="badge bg-primary text-secondary text-xs">WC</span>
              )}
              {item.url && (
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="ml-auto text-muted hover:text-primary">
                  <ExternalLink size={11} />
                </a>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
