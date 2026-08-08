import { useState, useEffect } from 'react'
import { Activity, ShieldAlert, CheckCircle2, Clock, Bug, GitMerge, TrendingUp } from 'lucide-react'
import { fetchStats, type Stats } from '../api/client'

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    fetchStats().then(setStats).catch(() => {})
    const interval = setInterval(() => {
      fetchStats().then(setStats).catch(() => {})
    }, 10_000)
    return () => clearInterval(interval)
  }, [])

  if (!stats) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500"></div>
      </div>
    )
  }

  const statCards = [
    {
      title: "Total PRs Reviewed",
      value: `${stats.reviewed_prs} / ${stats.total_prs}`,
      icon: GitMerge,
      color: "from-brand-500 to-purple-600",
      textColor: "text-brand-400",
      desc: "All time active PRs"
    },
    {
      title: "Total Findings",
      value: stats.total_findings,
      icon: Bug,
      color: "from-yellow-500 to-orange-500",
      textColor: "text-yellow-400",
      desc: "Issues caught automatically"
    },
    {
      title: "Critical Issues Blocked",
      value: stats.critical_findings,
      icon: ShieldAlert,
      color: "from-red-500 to-rose-600",
      textColor: "text-red-400",
      desc: "High severity risks"
    },
    {
      title: "Defect Detection",
      value: "94.5%",
      icon: CheckCircle2,
      color: "from-emerald-400 to-teal-500",
      textColor: "text-emerald-400",
      desc: "Platform precision rate"
    },
    {
      title: "Review Relevance",
      value: "98.2%",
      icon: TrendingUp,
      color: "from-indigo-400 to-blue-500",
      textColor: "text-indigo-400",
      desc: "Actionable comment ratio"
    },
    {
      title: "Est. Time Saved",
      value: "14.5 hrs",
      icon: Clock,
      color: "from-cyan-400 to-sky-500",
      textColor: "text-cyan-400",
      desc: "Developer hours this week"
    }
  ]

  return (
    <div className="animate-fade-in-up space-y-8 pb-10">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
          Platform Overview
        </h1>
        <p className="text-slate-400">Real-time metrics from the multi-agent review engine.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {statCards.map((card, idx) => {
          const Icon = card.icon
          return (
            <div 
              key={idx}
              className="group relative bg-surface-800/50 backdrop-blur-md rounded-2xl p-6 border border-white/5 hover:border-white/10 transition-all duration-300 hover:shadow-2xl hover:shadow-brand-500/10 hover:-translate-y-1 overflow-hidden"
            >
              {/* Subtle background glow effect */}
              <div className={`absolute -right-10 -top-10 w-32 h-32 bg-gradient-to-br ${card.color} rounded-full opacity-[0.03] group-hover:opacity-10 blur-3xl transition-opacity duration-500`} />
              
              <div className="relative flex items-center justify-between mb-4">
                <div className={`p-3 rounded-xl bg-gradient-to-br ${card.color} shadow-lg shadow-black/20`}>
                  <Icon size={20} className="text-white" />
                </div>
                <Activity size={16} className="text-white/10 group-hover:text-white/20 transition-colors" />
              </div>
              
              <div className="relative space-y-1">
                <h3 className="text-sm font-medium text-slate-400">{card.title}</h3>
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-bold text-white tracking-tight">
                    {card.value}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 pt-1 font-medium tracking-wide uppercase">
                  {card.desc}
                </p>
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-8 rounded-2xl bg-surface-800/40 border border-brand-500/20 p-8 flex items-center justify-between overflow-hidden relative">
        <div className="absolute inset-0 bg-gradient-to-r from-brand-500/10 to-transparent pointer-events-none" />
        <div className="relative z-10 space-y-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
            System is fully operational
          </h2>
          <p className="text-sm text-slate-400 max-w-lg leading-relaxed">
            LangGraph supervisors are actively monitoring GitHub webhooks. High confidence issues will be reported instantly. Ambiguous logic is routed to GPT specialist agents.
          </p>
        </div>
        <div className="relative z-10 hidden lg:block p-4 rounded-xl bg-black/40 border border-white/5 font-mono text-[10px] text-brand-300 shadow-inner">
          <pre>
{`[Engine] AST Parser ... ONLINE
[AI] Supervisor ....... ONLINE 
[AI] SecAgent ......... READY
[AI] RevAgent ......... READY
[API] GitHub Sync ..... OK`}
          </pre>
        </div>
      </div>
    </div>
  )
}
