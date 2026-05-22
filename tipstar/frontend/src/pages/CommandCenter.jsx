import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Inbox, Globe, Zap, Trophy, RefreshCw, Sparkles, Send } from 'lucide-react'
import WorldCupTicker from '../components/WorldCupTicker'
import NewsFeed from '../components/NewsFeed'
import DramaCard from '../components/DramaCard'
import { getAnalyticsSummary, getPendingPosts, getDrama, harvestNews, generatePosts, getGenerationStatus, publishApproved } from '../api/client'

function StatCard({ label, value, icon: Icon, color = '#6CABDD', to }) {
  const content = (
    <>
      <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${color}20` }}>
        <Icon size={22} style={{ color }} />
      </div>
      <div>
        <p className="text-2xl font-bold text-white">{value ?? '--'}</p>
        <p className="text-xs text-muted">{label}</p>
      </div>
    </>
  )

  if (!to) {
    return <div className="card flex items-center gap-4">{content}</div>
  }

  return (
    <Link
      to={to}
      className="card flex items-center gap-4 hover:border-primary focus:border-primary focus:outline-none transition-colors cursor-pointer"
      title={`Filter by ${label}`}
    >
      {content}
    </Link>
  )
}

export default function CommandCenter() {
  const [stats, setStats] = useState(null)
  const [pendingCount, setPendingCount] = useState(0)
  const [recentDrama, setRecentDrama] = useState([])
  const [harvesting, setHarvesting] = useState(false)
  const [harvestMsg, setHarvestMsg] = useState('')
  const [generating, setGenerating] = useState(false)
  const [generateMsg, setGenerateMsg] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [publishMsg, setPublishMsg] = useState('')
  const [genLimit, setGenLimit] = useState(20)
  const [genMinScore, setGenMinScore] = useState(5)

  const reloadStats = () => {
    getAnalyticsSummary().then(r => setStats(r.data)).catch(() => {})
    getPendingPosts().then(r => setPendingCount(r.data.length)).catch(() => {})
  }

  useEffect(() => {
    reloadStats()
    getDrama().then(r => setRecentDrama(r.data.slice(0, 3))).catch(() => {})
  }, [])

  const handleHarvest = async () => {
    setHarvesting(true)
    setHarvestMsg('')
    try {
      const r = await harvestNews()
      const { inserted, skipped, total_fetched } = r.data
      setHarvestMsg(`Harvested ${total_fetched} stories - ${inserted} new, ${skipped} duplicates.`)
    } catch {
      setHarvestMsg('Harvest failed - check NEWS_API_KEY in .env.')
    } finally {
      setHarvesting(false)
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    setGenerateMsg('')
    try {
      const r = await generatePosts(genLimit, genMinScore)
      setGenerateMsg(r.data.message)
      pollGenerationJob(r.data.job_id)
    } catch {
      setGenerateMsg('Generation failed - check GROQ_API_KEY in .env.')
      setGenerating(false)
    }
  }

  const pollGenerationJob = (jobId) => {
    if (!jobId) {
      setGenerating(false)
      setGenerateMsg('Generation started, but no job id was returned. Refresh the inbox in a moment.')
      return
    }

    const poll = async () => {
      try {
        const r = await getGenerationStatus(jobId)
        const job = r.data
        const total = job.total || 0
        const progress = total ? ` ${job.processed}/${total}` : ''
        const generated = job.generated_posts || 0
        const skipped = job.skipped || 0
        setGenerateMsg(`${job.message}${progress} | Posts: ${generated} | Skipped: ${skipped}`)

        getPendingPosts().then(p => setPendingCount(p.data.length)).catch(() => {})
        getAnalyticsSummary().then(s => setStats(s.data)).catch(() => {})

        if (job.status === 'complete' || job.status === 'failed') {
          setGenerating(false)
          return
        }
      } catch {
        setGenerateMsg('Waiting for generation status...')
      }
      setTimeout(poll, 2500)
    }
    setTimeout(poll, 1000)
  }

  const handlePublish = async () => {
    setPublishing(true)
    setPublishMsg('')
    try {
      await publishApproved()
      setPublishMsg('Published to X. Check the History tab.')
      reloadStats()
    } catch (e) {
      const detail = e?.response?.data?.detail || 'Publish failed - check Twitter credentials.'
      setPublishMsg(detail)
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-primary mb-6">Command Center</h1>

      <WorldCupTicker />

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Generated Today"  value={stats?.total_today}  icon={Globe}  color="#6CABDD" to="/history?status=all&created=today" />
        <StatCard label="Pending Approval" value={pendingCount}         icon={Inbox}  color="#F59E0B" to="/inbox" />
        <StatCard label="Approved Posts"   value={stats?.approved}      icon={Trophy} color="#22C55E" to="/history?status=approved" />
        <StatCard label="World Cup Posts"  value={stats?.world_cup}     icon={Zap}    color="#EF4444" to="/history?status=all&wc=1" />
      </div>

      {/* Action bar */}
      <div className="card mb-6">
        <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-4">Content Pipeline</h2>
        <div className="flex flex-wrap gap-4 items-end">

          {/* Generate block */}
          <div className="flex flex-col gap-2 flex-1 min-w-64">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-xs text-muted">
                <span>Stories:</span>
                <input
                  type="number" min={1} max={50} value={genLimit}
                  onChange={e => setGenLimit(Number(e.target.value))}
                  className="w-14 bg-surface border border-border rounded px-2 py-1 text-white text-xs focus:border-primary outline-none"
                />
              </div>
              <div className="flex items-center gap-1.5 text-xs text-muted">
                <span>Min score:</span>
                <input
                  type="number" min={1} max={10} value={genMinScore}
                  onChange={e => setGenMinScore(Number(e.target.value))}
                  className="w-12 bg-surface border border-border rounded px-2 py-1 text-white text-xs focus:border-primary outline-none"
                />
              </div>
            </div>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="btn-primary inline-flex items-center gap-2 text-sm disabled:opacity-60"
            >
              <Sparkles size={14} className={generating ? 'animate-pulse' : ''} />
              {generating ? 'Generating…' : 'Generate posts'}
            </button>
            {generateMsg && <p className="text-xs text-muted">{generateMsg}</p>}
          </div>

          <div className="w-px h-12 bg-border hidden md:block" />

          {/* Publish block */}
          <div className="flex flex-col gap-2">
            <p className="text-xs text-muted">Posts approved and ready to go live</p>
            <button
              onClick={handlePublish}
              disabled={publishing}
              className="btn-ghost inline-flex items-center gap-2 text-sm disabled:opacity-60 border-green-600 text-green-400 hover:bg-green-600/10"
            >
              <Send size={14} className={publishing ? 'animate-pulse' : ''} />
              {publishing ? 'Publishing…' : 'Publish to X'}
            </button>
            {publishMsg && <p className="text-xs text-muted">{publishMsg}</p>}
          </div>
        </div>
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
