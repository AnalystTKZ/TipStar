import { useEffect, useState } from 'react'
import { Inbox, Globe, Zap, Trophy, RefreshCw } from 'lucide-react'
import WorldCupTicker from '../components/WorldCupTicker'
import NewsFeed from '../components/NewsFeed'
import DramaCard from '../components/DramaCard'
import { getAnalyticsSummary, getPendingPosts, getDrama, harvestNews } from '../api/client'

function StatCard({ label, value, icon: Icon, color = '#6CABDD' }) {
  return (
    <div className="card flex items-center gap-4">
      <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${color}20` }}>
        <Icon size={22} style={{ color }} />
      </div>
      <div>
        <p className="text-2xl font-bold text-white">{value ?? '--'}</p>
        <p className="text-xs text-muted">{label}</p>
      </div>
    </div>
  )
}

export default function CommandCenter() {
  const [stats, setStats] = useState(null)
  const [pendingCount, setPendingCount] = useState(0)
  const [recentDrama, setRecentDrama] = useState([])
  const [harvesting, setHarvesting] = useState(false)
  const [harvestMsg, setHarvestMsg] = useState('')
  useEffect(() => {
    getAnalyticsSummary().then(r => setStats(r.data)).catch(() => {})
    getPendingPosts().then(r => setPendingCount(r.data.length)).catch(() => {})
    getDrama().then(r => setRecentDrama(r.data.slice(0, 3))).catch(() => {})
  }, [])

  const handleHarvest = async () => {
    setHarvesting(true)
    setHarvestMsg('')
    try {
      const r = await harvestNews()
      const { inserted, skipped, total_fetched } = r.data
      setHarvestMsg(`Harvested ${total_fetched} stories — ${inserted} new, ${skipped} duplicates.`)
    } catch {
      setHarvestMsg('Harvest failed — check NEWS_API_KEY in .env.')
    } finally {
      setHarvesting(false)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-primary mb-6">Command Center</h1>

      <WorldCupTicker />

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Generated Today"  value={stats?.total_today}  icon={Globe}  color="#6CABDD" />
        <StatCard label="Pending Approval" value={pendingCount}         icon={Inbox}  color="#F59E0B" />
        <StatCard label="Approved Today"   value={stats?.approved}      icon={Trophy} color="#22C55E" />
        <StatCard label="World Cup Posts"  value={stats?.world_cup}     icon={Zap}    color="#EF4444" />
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-primary uppercase tracking-wider">Incoming News</h2>
            <button
              onClick={handleHarvest}
              disabled={harvesting}
              className="btn-ghost inline-flex items-center gap-1 text-xs disabled:opacity-60"
            >
              <RefreshCw size={13} className={harvesting ? 'animate-spin' : ''} />
              {harvesting ? 'Fetching…' : 'Fetch latest'}
            </button>
          </div>
          {harvestMsg && (
            <p className="text-xs text-muted mb-2">{harvestMsg}</p>
          )}
          <div className="card p-0 overflow-hidden">
            <NewsFeed limit={12} key={harvestMsg} />
          </div>
        </div>
        <div>
          <h2 className="text-sm font-semibold text-danger uppercase tracking-wider mb-3">Drama Alerts</h2>
          <div className="space-y-3">
            {recentDrama.length
              ? recentDrama.map(d => <DramaCard key={d.id} drama={d} />)
              : <p className="text-muted text-sm">No active drama entries.</p>
            }
          </div>
        </div>
      </div>
    </div>
  )
}
