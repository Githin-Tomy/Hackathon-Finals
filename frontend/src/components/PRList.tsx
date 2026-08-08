import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { GitPullRequest, AlertTriangle, RefreshCw, ExternalLink, ChevronRight, Bot, Cpu } from 'lucide-react'
import { fetchPRs, replayWebhook, syncGitHubPRs, type PRSummary } from '../api/client'

function RiskBar({ score }: { score: number }) {
  const safeScore = score || 0
  const pct = Math.min((safeScore / 10) * 100, 100)
  const color =
    safeScore >= 7 ? 'bg-red-500' :
    safeScore >= 4 ? 'bg-orange-400' :
    safeScore >= 2 ? 'bg-yellow-400' : 'bg-green-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-semibold ${
        safeScore >= 7 ? 'text-red-400' : safeScore >= 4 ? 'text-orange-400' : safeScore >= 2 ? 'text-yellow-400' : 'text-green-400'
      }`}>{safeScore.toFixed(1)}</span>
    </div>
  )
}

function StatusBadge({ status, summary }: { status: string; summary?: string }) {
  const cls: Record<string, string> = {
    done:      'badge-done',
    reviewing: 'badge-reviewing',
    pending:   'badge-pending',
    error:     'badge-error',
    closed:    'px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-500/20 text-slate-400 border border-slate-500/30',
    merged:    'px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/30',
  }

  if (status === 'reviewing') {
    const isNewCommit = summary?.includes('New commit')
    const isNew = summary?.includes('New PR')
    return (
      <span className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold bg-brand-500/20 text-brand-300 border border-brand-500/40">
        <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-ping shrink-0" />
        {isNewCommit ? '⟳ New Commit' : isNew ? '🆕 New PR' : '⟳ Reviewing'}
      </span>
    )
  }

  const labels: Record<string, string> = {
    done: 'Review Completed', pending: '🔄 Pending', error: '❌ Error', closed: '🚫 Closed', merged: '🔀 Merged'
  }
  return <span className={cls[status] || 'badge-pending'}>{labels[status] || status}</span>
}

export default function PRListPage() {
  const [prs, setPRs] = useState<PRSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [showClosed, setShowClosed] = useState(false)
  const [filter, setFilter] = useState('')
  const [replayingId, setReplayingId] = useState<number | null>(null)
  const navigate = useNavigate()

  const load = (silent = false) => {
    if (!silent) setLoading(true)
    fetchPRs(showClosed ? { include_closed: 'true' } : {})
      .then(data => { setPRs(data) })
      .finally(() => { if (!silent) setLoading(false) })
  }

  const handleSync = async () => {
    setSyncing(true)
    try {
      await syncGitHubPRs()
      load(false)
    } finally {
      setSyncing(false)
    }
  }

  useEffect(() => {
    load(false)

    // Adaptive polling: 3s if any PR is reviewing, else 8s
    const getInterval = () => {
      const hasActive = prs.some(p => p.status === 'reviewing' || p.status === 'pending')
      return hasActive ? 3000 : 8000
    }

    let iv = setInterval(() => load(true), getInterval())

    // Re-create interval whenever prs change to adapt speed
    const adaptIv = setInterval(() => {
      clearInterval(iv)
      iv = setInterval(() => load(true), getInterval())
    }, 8000)

    return () => { clearInterval(iv); clearInterval(adaptIv) }
  }, [showClosed])

  const filtered = prs.filter(pr =>
    pr.title.toLowerCase().includes(filter.toLowerCase()) ||
    pr.author.toLowerCase().includes(filter.toLowerCase())
  )

  const handleReplay = async (e: React.MouseEvent, prId: number) => {
    e.stopPropagation()
    setReplayingId(prId)
    try {
      await replayWebhook(prId)
      setTimeout(load, 1000)
    } finally {
      setTimeout(() => setReplayingId(null), 2000)
    }
  }

  return (
    <div className="animate-fade-in-up space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white flex items-center gap-2">
            <GitPullRequest size={20} className="text-brand-400" />
            Pull Requests
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {prs.length} {showClosed ? 'total' : 'active'} PRs tracked
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            id="pr-search"
            type="text"
            placeholder="Search PRs…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="bg-surface-700 border border-white/10 rounded-lg px-3 py-2 text-sm text-slate-200 
                       placeholder-slate-500 focus:outline-none focus:border-brand-500/50 w-48"
          />
          <button
            id="toggle-closed-prs"
            onClick={() => setShowClosed(s => !s)}
            className={`px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
              showClosed
                ? 'bg-slate-700 text-slate-200 border-white/20'
                : 'bg-surface-700 text-slate-400 border-white/10 hover:text-slate-200'
            }`}
          >
            {showClosed ? 'Active Only' : 'Include Closed'}
          </button>
          <button id="sync-github" onClick={handleSync} disabled={syncing} className="btn-primary flex items-center gap-2 text-xs">
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Syncing…' : 'Sync GitHub'}
          </button>
          <button id="refresh-prs" onClick={() => load(true)} className="btn-ghost flex items-center gap-2 text-xs">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Empty state */}
      {!loading && prs.length === 0 && (
        <div className="card text-center py-16">
          <GitPullRequest size={40} className="text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 font-medium">No pull requests found</p>
          <p className="text-slate-600 text-sm mt-1 mb-4">
            Click "Sync GitHub" to pull open PRs directly from your repositories.
          </p>
          <button onClick={handleSync} disabled={syncing} className="btn-primary inline-flex items-center gap-2">
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Syncing...' : 'Sync GitHub Now'}
          </button>
        </div>
      )}

      {/* PR Table */}
      {filtered.length > 0 && (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5 text-xs text-slate-500 uppercase tracking-wider">
                <th className="text-left px-5 py-3 font-medium">Pull Request</th>
                <th className="text-left px-5 py-3 font-medium">Author</th>
                <th className="text-left px-5 py-3 font-medium">Status</th>
                <th className="text-left px-5 py-3 font-medium">Risk</th>
                <th className="text-left px-5 py-3 font-medium">Findings</th>
                <th className="text-right px-5 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((pr, i) => (
                <tr
                  key={pr.id}
                  id={`pr-row-${pr.id}`}
                  onClick={() => navigate(`/pr/${pr.id}`)}
                  className="border-b border-white/5 last:border-0 hover:bg-white/3 cursor-pointer transition-colors group"
                  style={{ animationDelay: `${i * 40}ms` }}
                >
                  <td className="px-5 py-4">
                    <div className="flex items-start gap-2.5">
                      <GitPullRequest size={15} className="text-brand-400 mt-0.5 shrink-0" />
                      <div>
                        <p className="font-medium text-slate-100 group-hover:text-white transition-colors line-clamp-1">{pr.title}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-slate-500">#{pr.github_pr_number}</span>
                          {pr.status === 'reviewing' && (
                            <span className="text-[11px] text-brand-400 font-mono animate-pulse flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-ping" />
                              Analyzing in backend...
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-brand-500/20 flex items-center justify-center text-[10px] text-brand-400 font-bold">
                        {pr.author[0]?.toUpperCase()}
                      </div>
                      <span className="text-slate-300 text-xs">{pr.author}</span>
                    </div>
                  </td>
                  <td className="px-5 py-4"><StatusBadge status={pr.status} summary={pr.ai_summary} /></td>
                  <td className="px-5 py-4"><RiskBar score={pr.risk_score} /></td>
                  <td className="px-5 py-4">
                    <span className={`font-semibold ${pr.finding_count > 0 ? 'text-orange-400' : 'text-green-400'}`}>
                      {pr.finding_count}
                    </span>
                    <span className="text-slate-500 text-xs ml-1">issues</span>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex items-center justify-end gap-2" onClick={e => e.stopPropagation()}>
                      <button
                        id={`replay-${pr.id}`}
                        onClick={e => handleReplay(e, pr.id)}
                        disabled={replayingId === pr.id}
                        title="Re-run review pipeline"
                        className="p-1.5 rounded-lg hover:bg-white/10 text-slate-500 hover:text-slate-200 
                                   transition-colors disabled:opacity-50"
                      >
                        <RefreshCw size={13} className={replayingId === pr.id ? 'animate-spin' : ''} />
                      </button>
                      <a
                        href={pr.html_url}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 rounded-lg hover:bg-white/10 text-slate-500 hover:text-slate-200 transition-colors"
                        title="View on GitHub"
                      >
                        <ExternalLink size={13} />
                      </a>
                      <ChevronRight size={14} className="text-slate-600 group-hover:text-slate-400 transition-colors" />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-slate-500">
        <div className="flex items-center gap-1.5"><Cpu size={12} className="text-cyan-400" /> Rule Engine findings</div>
        <div className="flex items-center gap-1.5"><Bot size={12} className="text-purple-400" /> AI Agent findings</div>
        <div className="flex items-center gap-1.5"><AlertTriangle size={12} className="text-slate-500" /> Risk score 0–10</div>
      </div>
    </div>
  )
}
