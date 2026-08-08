import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Editor from '@monaco-editor/react'
import {
  ArrowLeft, Bot, Cpu, ExternalLink, ChevronDown, ChevronUp, ChevronRight,
  AlertTriangle, CheckCircle, GitCommit, ShieldCheck, FileSearch,
  Zap, FileText, CheckSquare, XSquare, Clock, RefreshCw
} from 'lucide-react'
import { fetchPR, fetchChecks, approvePR, rejectPR, replayWebhook, syncRepoContext, type PRDetail, type Finding, type CiCheck } from '../api/client'

// ── Pipeline Steps ─────────────────────────────────────────────────────────────
const PIPELINE_STEPS = [
  { key: 'step1', icon: FileSearch, label: 'Fetching PR Files',       match: 'Step 1' },
  { key: 'step2', icon: Cpu,        label: 'AST & Rule Engine',        match: 'Step 2' },
  { key: 'step3', icon: Bot,        label: 'LangGraph AI Agents',      match: 'Step 3' },
  { key: 'step4', icon: FileText,   label: 'Summary & CI/CD Context',  match: 'Step 4' },
]

function PipelineProgress({ summary, status }: { summary: string | null; status: string }) {
  const isDone = status === 'done'
  const isError = status === 'error'

  // Figure out which step we're currently on from the ai_summary text
  const currentStep = PIPELINE_STEPS.findIndex(s => summary?.includes(s.match))

  return (
    <div className="card border border-brand-500/40 bg-gradient-to-br from-brand-500/10 to-purple-500/5 p-4 rounded-xl">
      <div className="flex items-center gap-3 mb-4">
        {isDone ? (
          <CheckCircle size={18} className="text-green-400 shrink-0" />
        ) : isError ? (
          <XSquare size={18} className="text-red-400 shrink-0" />
        ) : (
          <div className="w-5 h-5 border-2 border-brand-400 border-t-transparent rounded-full animate-spin shrink-0" />
        )}
        <div>
          <h3 className="text-sm font-semibold text-brand-300">
            {isDone ? 'AI Review Complete' : isError ? 'Review Error' : 'Live AI Review in Progress'}
          </h3>
          <p className="text-[11px] text-slate-400 font-mono mt-0.5 leading-relaxed">
            {summary || '⚙️ Initializing multi-agent review pipeline...'}
          </p>
        </div>
      </div>

      {/* Step-by-step pipeline tracker */}
      <div className="grid grid-cols-4 gap-2">
        {PIPELINE_STEPS.map((step, i) => {
          const Icon = step.icon
          const done = isDone || i < currentStep
          const active = !isDone && i === currentStep
          const pending = !isDone && i > currentStep

          return (
            <div key={step.key}
              className={`flex flex-col items-center gap-1.5 p-2 rounded-lg border text-center transition-all duration-500 ${
                done    ? 'border-green-500/30 bg-green-500/10' :
                active  ? 'border-brand-500/50 bg-brand-500/15 shadow-sm shadow-brand-500/20' :
                          'border-white/5 bg-white/3 opacity-40'
              }`}
            >
              <div className={`relative ${active ? 'animate-pulse' : ''}`}>
                <Icon size={16} className={
                  done ? 'text-green-400' : active ? 'text-brand-400' : 'text-slate-600'
                } />
                {active && (
                  <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-brand-400 rounded-full animate-ping" />
                )}
              </div>
              <p className={`text-[10px] font-medium leading-tight ${
                done ? 'text-green-300' : active ? 'text-brand-300' : 'text-slate-600'
              }`}>{step.label}</p>
              {done && <CheckCircle size={10} className="text-green-400" />}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── CI/CD Status Panel ─────────────────────────────────────────────────────────
function CiPanel({ prId, status }: { prId: number; status: string }) {
  const navigate = useNavigate()
  const [checks, setChecks] = useState<CiCheck[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedJobs, setExpandedJobs] = useState<Record<string, boolean>>({})

  useEffect(() => {
    fetchChecks(prId)
      .then((data) => {
        setChecks(data)
        // Automatically expand jobs that are in_progress or failed
        const initialExpanded: Record<string, boolean> = {}
        data.forEach((job) => {
          if (job.status === "in_progress" || job.conclusion === "failure") {
            initialExpanded[job.name] = true;
          }
        })
        setExpandedJobs(prev => ({ ...initialExpanded, ...prev }))
      })
      .catch(() => setChecks([]))
      .finally(() => setLoading(false))

    // Refresh CI checks while reviewing or running
    const iv = setInterval(() => {
      fetchChecks(prId)
        .then((data) => {
          setChecks(data)
          // Update expansion for newly failed/in-progress jobs
          setExpandedJobs((prev) => {
            const next = { ...prev }
            data.forEach((job) => {
              if (job.status === "in_progress" || job.conclusion === "failure") {
                if (next[job.name] === undefined) {
                  next[job.name] = true
                }
              }
            })
            return next
          })
        })
        .catch(() => {})
    }, status === 'reviewing' ? 5000 : 20000)
    return () => clearInterval(iv)
  }, [prId, status])

  if (loading) return (
    <div className="card p-4 flex items-center justify-center">
      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-brand-500"></div>
    </div>
  )
  if (checks.length === 0) return null

  const toggleJob = (jobName: string) => {
    setExpandedJobs(prev => ({ ...prev, [jobName]: !prev[jobName] }))
  }

  const jobIcon = (conclusion: string | null, st: string) => {
    if (st === 'in_progress' || st === 'queued') return <Clock size={14} className="text-yellow-400 animate-pulse shrink-0" />
    if (conclusion === 'success') return <CheckSquare size={14} className="text-green-400 shrink-0" />
    if (conclusion === 'failure') return <XSquare size={14} className="text-red-400 shrink-0" />
    return <AlertTriangle size={14} className="text-slate-500 shrink-0" />
  }

  const stepIcon = (conclusion: string | null, st: string) => {
    if (st === 'in_progress' || st === 'queued') return <RefreshCw size={11} className="text-yellow-400 animate-spin shrink-0" />
    if (conclusion === 'success') return <div className="w-3 h-3 rounded-full bg-green-500/20 border border-green-500 flex items-center justify-center shrink-0"><div className="w-1.5 h-1.5 rounded-full bg-green-400" /></div>
    if (conclusion === 'failure') return <div className="w-3 h-3 rounded-full bg-red-500/20 border border-red-500 flex items-center justify-center shrink-0"><div className="w-1.5 h-1.5 rounded-full bg-red-400" /></div>
    return <div className="w-3 h-3 rounded-full bg-slate-800 border border-slate-700 shrink-0" />
  }

  const jobColorClass = (conclusion: string | null, st: string) => {
    if (st === 'in_progress' || st === 'queued') return 'text-yellow-300'
    if (conclusion === 'success') return 'text-green-300'
    if (conclusion === 'failure') return 'text-red-300'
    return 'text-slate-400'
  }

  return (
    <div className="card p-4 space-y-4 bg-surface-800/80 backdrop-blur-md border border-white/5 shadow-xl">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
          <Zap size={13} className="text-yellow-400 animate-pulse" /> Live CI/CD Pipeline
        </h3>
        <button 
          onClick={() => navigate(`/pr/${prId}/pipeline`)}
          className="text-[10px] font-semibold text-brand-400 hover:text-brand-300 transition-colors flex items-center gap-1 border border-brand-500/20 bg-brand-500/5 px-2 py-1 rounded"
        >
          Inspect <ChevronRight size={10} />
        </button>
      </div>
      
      <div className="space-y-3">
        {checks.map((job, idx) => {
          const isExpanded = !!expandedJobs[job.name]
          const hasSteps = job.steps && job.steps.length > 0
          
          return (
            <div key={idx} className="border border-white/5 rounded-xl bg-surface-900/40 overflow-hidden transition-all duration-300">
              {/* Job Header */}
              <div 
                onClick={() => hasSteps && toggleJob(job.name)}
                className={`flex items-center justify-between p-3 text-xs font-medium cursor-pointer hover:bg-white/3 select-none transition-colors ${
                  job.status === 'in_progress' ? 'bg-brand-500/5' : ''
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  {jobIcon(job.conclusion, job.status)}
                  <span className="text-slate-200 font-semibold truncate">{job.name}</span>
                </div>
                
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded bg-black/40 ${jobColorClass(job.conclusion, job.status)}`}>
                    {job.status === 'in_progress' ? 'Running…' : job.status === 'queued' ? 'Queued' : (job.conclusion || 'pending')}
                  </span>
                  
                  {job.details_url && (
                    <a 
                      href={job.details_url} 
                      target="_blank" 
                      rel="noreferrer" 
                      onClick={(e) => e.stopPropagation()}
                      className="text-slate-500 hover:text-brand-400 transition-colors p-1"
                    >
                      <ExternalLink size={12} />
                    </a>
                  )}
                  
                  {hasSteps && (
                    <div className="text-slate-500">
                      {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </div>
                  )}
                </div>
              </div>

              {/* Job Steps */}
              {hasSteps && isExpanded && (
                <div className="px-4 pb-3 pt-1 border-t border-white/5 bg-black/10 relative">
                  {/* Vertical line connecting steps */}
                  <div className="absolute left-[21px] top-[14px] bottom-[20px] w-[1px] bg-slate-800" />
                  
                  <div className="space-y-2.5 pt-1">
                    {job.steps!.map((step, sIdx) => (
                      <div key={sIdx} className="flex items-center gap-3 text-[11px] relative z-10">
                        {stepIcon(step.conclusion, step.status)}
                        <span className={`truncate flex-1 ${
                          step.status === 'in_progress' ? 'text-brand-300 font-medium' :
                          step.conclusion === 'failure' ? 'text-red-400 font-medium' :
                          step.conclusion === 'success' ? 'text-slate-400' : 'text-slate-600'
                        }`}>
                          {step.name}
                        </span>
                        
                        <span className={`text-[9px] font-mono shrink-0 uppercase tracking-wider ${
                          step.status === 'in_progress' ? 'text-yellow-400 animate-pulse' :
                          step.conclusion === 'success' ? 'text-green-500' :
                          step.conclusion === 'failure' ? 'text-red-500' : 'text-slate-600'
                        }`}>
                          {step.status === 'in_progress' ? 'active' : (step.conclusion || 'pending')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Finding Cards ──────────────────────────────────────────────────────────────
function SeverityBadge({ severity }: { severity: string }) {
  const cls: Record<string, string> = {
    critical: 'badge-critical', high: 'badge-high',
    medium: 'badge-medium',    low: 'badge-low',
  }
  return <span className={cls[severity] || 'badge-low'}>{severity.toUpperCase()}</span>
}

function SourceBadge({ source }: { source: string }) {
  return source === 'ai'
    ? <span className="badge-ai flex items-center gap-1"><Bot size={10} /> AI Agent</span>
    : <span className="badge-rule flex items-center gap-1"><Cpu size={10} /> Rule Engine</span>
}

function FindingCard({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false)

  return (
    <div id={`finding-${finding.id}`}
      className={`border rounded-lg transition-all duration-200 ${
        finding.severity === 'critical' ? 'border-red-500/30 bg-red-500/5' :
        finding.severity === 'high'     ? 'border-orange-500/30 bg-orange-500/5' :
        finding.severity === 'medium'   ? 'border-yellow-500/20 bg-yellow-500/3' :
                                          'border-white/10 bg-surface-700'
      }`}
    >
      <button
        className="w-full text-left px-4 py-3 flex items-center justify-between gap-3"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <SeverityBadge severity={finding.severity} />
          <SourceBadge source={finding.source} />
          <span className="font-mono text-xs text-slate-400">{finding.rule_id}</span>
          <span className="text-slate-200 text-sm font-medium truncate">{finding.message}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0 text-xs text-slate-500">
          <span className="font-mono">{finding.file_path.split('/').pop()}:{finding.line_number}</span>
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-white/5 pt-3">
          {finding.code_snippet && finding.code_snippet !== 'N/A' && (
            <pre className="rounded-lg border border-white/5 bg-zinc-950 p-4 font-mono text-[11px] text-zinc-300 overflow-x-auto whitespace-pre shadow-inner">
              {finding.code_snippet}
            </pre>
          )}

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Analysis</p>
              <p className="text-slate-300">{finding.message}</p>
            </div>
            {finding.suggestion && (
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">💡 Suggestion</p>
                <p className="text-slate-300">{finding.suggestion}</p>
              </div>
            )}
          </div>

          <div className="flex items-center gap-4 text-xs text-slate-500">
            <span>Confidence: <span className="text-slate-300 font-medium">{(finding.confidence * 100).toFixed(0)}%</span></span>
            <span>Category: <span className="text-slate-300 font-medium">{finding.category}</span></span>
            <span>File: <code className="text-brand-400">{finding.file_path}:{finding.line_number}</code></span>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Risk Panel ─────────────────────────────────────────────────────────────────
function RiskPanel({ 
  pr, 
  onRerun, 
  rerunning,
  onSyncContext,
  syncingContext
}: { 
  pr: PRDetail; 
  onRerun: () => void; 
  rerunning: boolean;
  onSyncContext: () => void;
  syncingContext: boolean;
}) {
  const score = pr.risk_score || 0
  const level = score >= 7 ? 'Critical' : score >= 4 ? 'High' : score >= 2 ? 'Medium' : 'Low'
  const color = score >= 7 ? 'text-red-400' : score >= 4 ? 'text-orange-400' : score >= 2 ? 'text-yellow-400' : 'text-green-400'
  const ring = score >= 7 ? 'stroke-red-500' : score >= 4 ? 'stroke-orange-400' : score >= 2 ? 'stroke-yellow-400' : 'stroke-green-500'

  const circumference = 2 * Math.PI * 40
  const dashOffset = circumference - (score / 10) * circumference

  return (
    <div className="card space-y-4">
      <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Risk Score</h2>

      <div className="flex items-center justify-center">
        <div className="relative">
          <svg width="100" height="100" viewBox="0 0 100 100" className="-rotate-90">
            <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
            <circle
              cx="50" cy="50" r="40" fill="none" strokeWidth="8"
              strokeLinecap="round"
              className={`${ring} transition-all duration-700`}
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {pr.status === 'reviewing' ? (
              <RefreshCw size={20} className="text-brand-400 animate-spin" />
            ) : (
              <>
                <span className={`text-2xl font-bold ${color}`}>{score.toFixed(1)}</span>
                <span className="text-xs text-slate-500">/ 10</span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="text-center">
        {pr.status === 'reviewing' ? (
          <span className="text-sm font-semibold text-brand-400 animate-pulse">Analyzing…</span>
        ) : (
          <span className={`text-sm font-semibold ${color}`}>{level} Risk</span>
        )}
      </div>

      <div className="border-t border-white/5 pt-4 space-y-2 text-xs">
        {[
          ['PR', `#${pr.github_pr_number}`],
          ['Author', pr.author],
          ['Branch', `${pr.head_branch} → ${pr.base_branch}`],
          ['Status', pr.status],
        ].map(([k, v]) => (
          <div key={k} className="flex justify-between">
            <span className="text-slate-500">{k}</span>
            <span className="text-slate-300 font-medium">{v}</span>
          </div>
        ))}
      </div>

      <div className="flex gap-2 w-full pt-1">
        <a href={pr.html_url} target="_blank" rel="noreferrer"
          className="btn-ghost flex-1 flex items-center justify-center gap-1.5 text-xs">
          <ExternalLink size={12} /> GitHub
        </a>
        <button
          onClick={onRerun}
          disabled={rerunning || pr.status === 'reviewing'}
          className="btn-ghost flex-1 flex items-center justify-center gap-1.5 text-xs disabled:opacity-50"
        >
          <RefreshCw size={12} className={rerunning ? 'animate-spin' : ''} /> Rerun
        </button>
      </div>

      <button
        onClick={onSyncContext}
        disabled={syncingContext || pr.status === 'reviewing'}
        className="btn-ghost w-full flex items-center justify-center gap-2 text-xs py-2 mt-2 disabled:opacity-50 border border-white/5 hover:border-brand-500/30"
      >
        <RefreshCw size={12} className={syncingContext ? 'animate-spin' : ''} /> Sync Architecture
      </button>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export default function PRDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [pr, setPR] = useState<PRDetail | null>(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [actionLoading, setActionLoading] = useState(false)
  const [showFeedbackInput, setShowFeedbackInput] = useState(false)
  const [feedbackText, setFeedbackText] = useState('')
  const [activeMainTab, setActiveMainTab] = useState<'findings' | 'summary'>('findings')
  const [rerunning, setRerunning] = useState(false)
  const [syncingContext, setSyncingContext] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Auto-switch tabs when findings or summary loads
  useEffect(() => {
    if (pr) {
      const finds = pr.findings || []
      if (finds.length === 0 && pr.ai_summary) {
        setActiveMainTab('summary')
      }
    }
  }, [pr])

  useEffect(() => {
    if (!id) return

    setInitialLoading(true)
    setPR(null)

    const scheduleNext = (ms: number) => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      intervalRef.current = setInterval(() => load(true), ms)
    }

    const load = (silent = false) => {
      fetchPR(Number(id))
        .then(data => {
          setPR(data)
          if (!silent) setInitialLoading(false)
          // Poll fast while reviewing, slow down when done
          const isActive = data.status === 'reviewing' || data.status === 'pending'
          scheduleNext(isActive ? 1500 : 15000)
        })
        .catch(() => {
          if (!silent) setInitialLoading(false)
        })
    }

    load(false)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [id])

  const handleAction = async (action: 'approve' | 'reject') => {
    if (action === 'reject' && !showFeedbackInput) {
      setShowFeedbackInput(true)
      return
    }

    if (!pr) return
    setActionLoading(true)
    try {
      if (action === 'approve') await approvePR(pr.id)
      else await rejectPR(pr.id, feedbackText)
      setPR({ ...pr, status: action === 'approve' ? 'approved' : 'rejected' })
    } catch (e) {
      alert("Action failed")
    } finally {
      setActionLoading(false)
    }
  }

  const handleRerun = async () => {
    if (!pr) return
    setRerunning(true)
    try {
      await replayWebhook(pr.id)
      setPR({ ...pr, status: 'reviewing', ai_summary: '🔄 Rerun review initiated. Re-analyzing PR...' })
    } catch (e) {
      alert("Failed to trigger review rerun")
    } finally {
      setRerunning(false)
    }
  }

  const handleSyncContext = async () => {
    if (!pr) return
    setSyncingContext(true)
    try {
      await syncRepoContext(pr.repo_id)
      alert("Architecture context sync started in the background!")
    } catch (e) {
      alert("Failed to sync architecture context: " + e)
    } finally {
      setSyncingContext(false)
    }
  }

  // Show spinner ONLY on absolute first load with zero data
  if (initialLoading && !pr) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm">Loading PR…</p>
        </div>
      </div>
    )
  }

  if (!pr) return <div className="text-slate-500">PR not found</div>

  const findings = pr.findings || []
  const categories = ['all', ...new Set(findings.map(f => f.category))]
  const displayed = (categoryFilter === 'all'
    ? findings
    : findings.filter(f => f.category === categoryFilter)
  ).sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  const isReviewing = pr.status === 'reviewing' || pr.status === 'pending'

  return (
    <div className="animate-fade-in-up space-y-5">
      {/* Back */}
      <button onClick={() => navigate('/')} id="back-to-prs"
        className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 transition-colors">
        <ArrowLeft size={15} /> Back to Pull Requests
      </button>

      {/* Live Pipeline Progress (only shown while reviewing) */}
      {isReviewing && (
        <PipelineProgress summary={pr.ai_summary || null} status={pr.status} />
      )}

      <div className="grid grid-cols-[340px_1fr] gap-6 items-start">
        
        {/* Left Sidebar (Sticky & Non-scrollable with the page) */}
        <div className="sticky top-0 max-h-[85vh] overflow-y-auto pr-2 space-y-4 custom-scrollbar">
          
          <RiskPanel pr={pr} onRerun={handleRerun} rerunning={rerunning} onSyncContext={handleSyncContext} syncingContext={syncingContext} />

          {/* Action Buttons for Pending Approval / Approved / Rejected / Done */}
          {['pending_approval', 'done', 'approved', 'rejected'].includes(pr.status) && (
            <div className={`card p-5 flex flex-col gap-4 border ${
              pr.status === 'approved' ? 'bg-green-500/10 border-green-500/30' :
              pr.status === 'rejected' ? 'bg-red-500/10 border-red-500/30' :
              'bg-surface-800/80 border-brand-500/30'
            }`}>
              <div>
                <h3 className={`text-base font-bold flex items-center gap-2 mb-1 ${
                  pr.status === 'approved' ? 'text-green-400' :
                  pr.status === 'rejected' ? 'text-red-400' :
                  'text-white'
                }`}>
                  {pr.status === 'approved' && <CheckCircle size={16} className="text-green-400" />}
                  {pr.status === 'rejected' && <XSquare size={16} className="text-red-400" />}
                  {['pending_approval', 'done'].includes(pr.status) && <ShieldCheck size={16} className="text-brand-400" />}
                  
                  {pr.status === 'approved' ? 'Approved' :
                   pr.status === 'rejected' ? 'Changes Requested' :
                   pr.status === 'pending_approval' ? 'Clean PR' :
                   'Review Complete'}
                </h3>
                <p className="text-xs text-slate-400">
                  {pr.status === 'approved' ? 'You approved this. You can still request changes.' :
                   pr.status === 'rejected' ? 'You requested changes. You can approve it later.' :
                   pr.status === 'pending_approval' ? 'No critical issues. Please verify and approve.' :
                   'Review the findings and decide.'}
                </p>
              </div>

              <div className="flex flex-col gap-2 mt-2">
                {pr.status !== 'approved' && (
                  <button 
                    onClick={() => handleAction('approve')}
                    disabled={actionLoading}
                    className="btn-primary w-full bg-green-500 hover:bg-green-600 shadow-green-500/25"
                  >
                    {actionLoading ? 'Processing...' : 'Approve PR'}
                  </button>
                )}
                {pr.status !== 'rejected' && (
                  <button 
                    onClick={() => handleAction('reject')}
                    disabled={actionLoading}
                    className="btn-ghost w-full text-red-400 hover:text-red-300 hover:bg-red-500/10 border-red-500/20"
                  >
                    {showFeedbackInput ? 'Submit Changes' : 'Request Changes'}
                  </button>
                )}
              </div>
              
              {showFeedbackInput && pr.status !== 'rejected' && (
                <div className="animate-fade-in-up">
                  <textarea
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    placeholder="Enter custom feedback..."
                    className="w-full bg-surface-900 border border-white/10 rounded-lg p-3 text-xs text-slate-300 placeholder:text-slate-600 focus:outline-none focus:border-brand-500/50 transition-colors resize-none h-20"
                  />
                </div>
              )}
            </div>
          )}

          <CiPanel prId={pr.id} status={pr.status} />

        </div>

        {/* Right Main Content (Findings & Summary Tabs) */}
        <div className="space-y-4 flex-1 min-w-0">

          {/* ── Agent Execution Flow Path Banner — LIVE ─────────────────────── */}
          {(() => {
            const summary = pr.ai_summary || ''
            const hasCiFailure = findings.some(f => f.category === 'ci_failure') ||
              summary.includes('CI/CD build failed') || summary.includes('Analyzing failure logs')
            const isDone = !isReviewing && (pr.status !== 'reviewing')

            // ── Live step detection from ai_summary text (updated by backend every few secs) ──
            // Step indices: 0=PR Created, 1=CI Polling, 2=Supervisor, 3=Agents, 4=Summary
            const ciPollingActive  = summary.includes('Waiting for GitHub Actions') || summary.includes('CI/CD checks')
            const supervisorActive = summary.includes('LangGraph Multi-Agent Supervisor') || summary.includes('Running LangGraph')
            const agentsActive     = summary.includes('CI/CD build failed') || summary.includes('Security') || summary.includes('Analyzing failure')
            const summaryActive    = summary.includes('Generating PR risk summary') || summary.includes('Step 4/4')

            type S = 'done' | 'active' | 'pending' | 'fail'

            const deriveState = (isActiveNow: boolean, isAfter: boolean): S => {
              if (isDone) return hasCiFailure && isAfter ? 'fail' : 'done'
              if (isActiveNow) return 'active'
              return 'pending'
            }

            type FlowStep = { icon: React.ElementType; label: string; sublabel: string; state: S; liveMsg?: string }

            const steps: FlowStep[] = [
              {
                icon: GitCommit,
                label: 'PR Created',
                sublabel: 'Webhook received',
                state: 'done',
              },
              {
                icon: Zap,
                label: 'CI/CD Polling',
                sublabel: 'GitHub Actions',
                state: ciPollingActive ? 'active' :
                       (supervisorActive || agentsActive || summaryActive || isDone) ? 'done' : 'pending',
                liveMsg: ciPollingActive ? summary : undefined,
              },
              {
                icon: Bot,
                label: 'Supervisor',
                sublabel: hasCiFailure ? '🔴 CI Failure Route' : '🟢 Review Route',
                state: supervisorActive ? 'active' :
                       (agentsActive || summaryActive || isDone) ? (hasCiFailure ? 'fail' : 'done') :
                       ciPollingActive ? 'pending' : 'pending',
                liveMsg: supervisorActive ? 'Routing agents...' : undefined,
              },
              {
                icon: hasCiFailure ? AlertTriangle : ShieldCheck,
                label: hasCiFailure ? 'CI Log Agent' : 'Security + Review',
                sublabel: hasCiFailure ? 'Trace analysis' : 'Chroma RAG + AST',
                state: agentsActive ? (hasCiFailure ? 'fail' : 'active') :
                       (summaryActive || isDone) ? (hasCiFailure ? 'fail' : 'done') : 'pending',
                liveMsg: agentsActive && !hasCiFailure ? 'Auditing code...' : undefined,
              },
              {
                icon: FileText,
                label: 'Summary',
                sublabel: 'Risk score computed',
                state: summaryActive ? 'active' : isDone ? 'done' : 'pending',
                liveMsg: summaryActive ? 'Writing report...' : undefined,
              },
            ]

            const connectorColor = (i: number) => {
              const next = steps[i + 1]
              if (!next) return 'bg-white/10'
              if (next.state === 'done') return 'bg-brand-500/60'
              if (next.state === 'fail') return 'bg-red-500/60'
              if (next.state === 'active') return 'bg-brand-500/40'
              return 'bg-white/10'
            }

            const activeStep = steps.find(s => s.state === 'active')

            return (
              <div className="card border border-white/5 bg-surface-800/60 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-bold text-brand-300 uppercase tracking-widest flex items-center gap-2">
                    <Cpu size={13} /> Agent Execution Flow Path
                  </h2>
                  <span className={`text-[10px] font-semibold px-2.5 py-1 rounded-full uppercase tracking-wider border ${
                    !isDone ? 'text-brand-400 border-brand-500/30 bg-brand-500/10 animate-pulse' :
                    hasCiFailure ? 'text-red-400 border-red-500/30 bg-red-500/10' :
                    'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
                  }`}>
                    {!isDone ? '● Live' : hasCiFailure ? 'CI Failure' : 'Complete'}
                  </span>
                </div>

                {/* Horizontal stepper */}
                <div className="flex items-start gap-0">
                  {steps.map((step, i) => {
                    const Icon = step.icon
                    const isLast = i === steps.length - 1
                    return (
                      <div key={i} className="flex items-start flex-1">
                        <div className="flex flex-col items-center gap-2 min-w-0 flex-shrink-0" style={{ width: '72px' }}>
                          <div className={`w-10 h-10 rounded-xl flex items-center justify-center border-2 transition-all duration-500 ${
                            step.state === 'done'   ? 'bg-brand-500/20 border-brand-500/60 shadow-sm shadow-brand-500/20' :
                            step.state === 'fail'   ? 'bg-red-500/20 border-red-500/60 shadow-sm shadow-red-500/20' :
                            step.state === 'active' ? 'bg-brand-500/15 border-brand-400/70 shadow-lg shadow-brand-500/30 animate-pulse' :
                                                      'bg-white/3 border-white/5 opacity-35'
                          }`}>
                            <Icon size={17} className={
                              step.state === 'done'   ? 'text-brand-400' :
                              step.state === 'fail'   ? 'text-red-400' :
                              step.state === 'active' ? 'text-brand-300' :
                                                        'text-slate-600'
                            } />
                          </div>
                          <div className="text-center w-full px-0.5">
                            <p className={`text-[10px] font-bold leading-tight ${
                              step.state === 'done'   ? 'text-slate-200' :
                              step.state === 'fail'   ? 'text-red-300' :
                              step.state === 'active' ? 'text-brand-200' :
                                                        'text-slate-600'
                            }`}>{step.label}</p>
                            <p className={`text-[9px] mt-0.5 leading-tight ${
                              step.state === 'fail' ? 'text-red-400/70' :
                              step.state === 'active' ? 'text-brand-400/80' : 'text-slate-500'
                            }`}>{step.liveMsg || step.sublabel}</p>
                          </div>
                        </div>

                        {!isLast && (
                          <div className="flex-1 flex items-center mt-5 px-1">
                            <div className={`h-0.5 w-full rounded-full transition-all duration-700 ${connectorColor(i)}`} />
                            <ChevronRight size={10} className={`shrink-0 -ml-1 ${
                              steps[i+1].state === 'done' ? 'text-brand-500' :
                              steps[i+1].state === 'fail' ? 'text-red-500' :
                              steps[i+1].state === 'active' ? 'text-brand-400' : 'text-white/10'
                            }`} />
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>

                {/* Live status ticker — shows the raw backend message while running */}
                {isReviewing && summary && (
                  <div className="flex items-center gap-2.5 bg-brand-500/5 border border-brand-500/15 rounded-lg px-3 py-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-ping shrink-0" />
                    <p className="text-[11px] text-brand-300 font-mono truncate">{summary}</p>
                  </div>
                )}

                {/* Completion banner */}
                {isDone && (
                  <div className={`flex items-center gap-2 pt-3 border-t border-white/5 text-[11px] ${
                    hasCiFailure ? 'text-red-400' : 'text-emerald-400'
                  }`}>
                    {hasCiFailure ? <AlertTriangle size={12} /> : <CheckCircle size={12} />}
                    <span className="font-semibold">
                      {hasCiFailure
                        ? 'Build failed — Supervisor routed to CI/CD Log Analysis Agent. Code review skipped.'
                        : 'Build succeeded — Supervisor ran Security + Code Review agents with Chroma RAG context.'}
                    </span>
                  </div>
                )}
              </div>
            )
          })()}

          {/* PR Title Card */}
          <div className="card p-5">
            <h1 className="text-lg font-bold text-white truncate">{pr.title}</h1>
            <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-500">
              <span className="flex items-center gap-1 font-mono">
                <GitCommit size={12} /> #{pr.github_pr_number}
              </span>
              <span>·</span>
              <span className="font-medium text-slate-300">{pr.author}</span>
              <span>·</span>
              <span className="text-green-400">{findings.filter(f => f.source === 'rule').length} rule-based</span>
              <span>·</span>
              <span className="text-purple-400">{findings.filter(f => f.source === 'ai').length} AI-reviewed</span>
              {isReviewing && (
                <>
                  <span>·</span>
                  <span className="text-brand-400 flex items-center gap-1.5 animate-pulse font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-ping" />
                    Analyzing…
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Core Workflow Deviation Alert Callout */}
          {!isReviewing && (() => {
            const archDeviations = findings.filter(f => f.rule_id === 'CS-ARCH-DEV');
            if (archDeviations.length > 0) {
              return (
                <div className="card border-red-500/30 bg-red-500/5 p-5 space-y-3 relative overflow-hidden animate-fade-in shadow-[0_0_15px_rgba(239,68,68,0.1)]">
                  <div className="absolute inset-y-0 left-0 w-1 bg-red-500" />
                  <div className="flex items-center gap-2.5 text-red-400 font-bold text-xs uppercase tracking-wide">
                    <AlertTriangle size={16} />
                    Detection of Core Workflow Deviation
                  </div>
                  <div className="space-y-4 pt-1">
                    {archDeviations.map(dev => (
                      <div key={dev.id} className="space-y-2">
                        <div className="text-xs text-slate-400 font-medium">
                          File: <span className="font-mono text-slate-300 bg-white/5 px-1.5 py-0.5 rounded">{dev.file_path}</span> at Line {dev.line_number}
                        </div>
                        <p className="text-sm text-slate-200 leading-relaxed">{dev.message}</p>
                        {dev.suggestion && (
                          <div className="bg-black/35 border border-white/5 p-3 rounded-lg text-xs font-mono text-emerald-400 shadow-inner">
                            <span className="text-slate-400 font-semibold uppercase block mb-1">Recommended Fix</span>
                            {dev.suggestion}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            } else {
              return (
                <div className="card border-emerald-500/20 bg-emerald-500/5 py-3.5 px-4 flex items-center justify-between animate-fade-in">
                  <div className="flex items-center gap-2.5 text-emerald-400 font-semibold text-xs uppercase tracking-wider">
                    <CheckCircle size={14} className="text-emerald-400" />
                    No Core Workflow Deviation Detected
                  </div>
                  <span className="text-[10px] text-slate-500 font-medium font-mono uppercase bg-white/5 px-2 py-0.5 rounded">
                    Aligns with design patterns
                  </span>
                </div>
              );
            }
          })()}

          {/* Premium Tab Selector Bar */}
          <div className="flex border border-white/5 bg-surface-800/40 rounded-xl p-1 shadow-inner">
            <button
              onClick={() => setActiveMainTab('findings')}
              className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
                activeMainTab === 'findings'
                  ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Findings & Issues ({findings.length})
            </button>
            <button
              onClick={() => setActiveMainTab('summary')}
              className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
                activeMainTab === 'summary'
                  ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              AI Summary Report
            </button>
          </div>

          {/* Tab 1 Content: Findings List */}
          {activeMainTab === 'findings' && (
            <div className="space-y-4 animate-fade-in-up">
              {/* Findings while reviewing — show placeholder */}
              {isReviewing && findings.length === 0 && (
                <div className="card border border-white/5 p-8 text-center space-y-3">
                  <Bot size={32} className="text-brand-400 mx-auto animate-pulse" />
                  <p className="text-slate-400 font-medium">AI Agents are analysing the code…</p>
                  <p className="text-slate-600 text-xs">Findings will appear here as they are detected</p>
                </div>
              )}

              {/* Category filter — only if we have findings */}
              {findings.length > 0 && (
                <div className="flex gap-2 flex-wrap">
                  {categories.map(cat => (
                    <button
                      key={cat}
                      id={`filter-${cat}`}
                      onClick={() => setCategoryFilter(cat)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                        categoryFilter === cat
                          ? 'bg-brand-500/20 text-brand-400 border-brand-500/40'
                          : 'bg-surface-700 text-slate-400 border-white/10 hover:border-white/20'
                      }`}
                    >
                      {cat.charAt(0).toUpperCase() + cat.slice(1)}
                      {cat !== 'all' && (
                        <span className="ml-1.5 text-[10px] text-slate-500">
                          ({findings.filter(f => f.category === cat).length})
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}

              {/* Findings */}
              {findings.length > 0 ? (
                <div className="space-y-2">
                  {displayed.length === 0 ? (
                    <div className="card text-center py-12">
                      <CheckCircle size={32} className="text-green-500 mx-auto mb-2" />
                      <p className="text-slate-400">No findings in this category</p>
                    </div>
                  ) : (
                    displayed.map(finding => (
                      <FindingCard key={finding.id} finding={finding} />
                    ))
                  )}
                </div>
              ) : (
                !isReviewing && (
                  <div className="card border border-green-500/20 bg-green-500/5 text-center py-12">
                    <ShieldCheck size={36} className="text-green-400 mx-auto mb-3" />
                    <p className="text-green-300 font-semibold">No Issues Found</p>
                    <p className="text-slate-500 text-sm mt-1">This PR passed all security and code quality checks</p>
                  </div>
                )
              )}
            </div>
          )}

          {/* Tab 2 Content: Summary Report */}
          {activeMainTab === 'summary' && (
            <div className="space-y-4 animate-fade-in-up">
              {pr.ai_summary ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {/* Left Column: Markdown Report */}
                  <div className="card bg-surface-800/40 border border-white/5 p-6 space-y-4">
                    <h3 className="text-sm font-semibold text-brand-300 uppercase tracking-wider mb-2 flex items-center gap-2">
                      <Bot size={16} /> Final AI Review Report
                    </h3>
                    <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap font-sans">
                      {pr.ai_summary}
                    </div>
                  </div>

                  {/* Right Column: Execution Stepper */}
                  <div className="card bg-surface-800/40 border border-white/5 p-6 space-y-6">
                    <h3 className="text-sm font-semibold text-brand-300 uppercase tracking-wider flex items-center gap-2">
                      <Cpu size={16} /> Agent Execution Flow Path
                    </h3>

                    <div className="relative pl-8 space-y-6 before:absolute before:inset-y-1 before:left-[11px] before:w-0.5 before:bg-white/10">
                      {/* Step 1: Pull Request Created */}
                      <div className="relative">
                        <div className="absolute -left-[30px] top-0.5 w-[22px] h-[22px] rounded-full bg-brand-500 border-4 border-surface-900 flex items-center justify-center shadow-lg shadow-brand-500/20" />
                        <div className="space-y-1">
                          <h4 className="text-xs font-bold text-slate-200">1. Pull Request Triggered</h4>
                          <p className="text-[11px] text-slate-400 leading-relaxed">
                            Webhook registered the PR modification. Core files and downstream callers were gathered to form the codebase context map.
                          </p>
                        </div>
                      </div>

                      {/* Step 2: CI/CD Execution */}
                      <div className="relative">
                        <div className="absolute -left-[30px] top-0.5 w-[22px] h-[22px] rounded-full bg-brand-500 border-4 border-surface-900 flex items-center justify-center shadow-lg shadow-brand-500/20" />
                        <div className="space-y-1">
                          <h4 className="text-xs font-bold text-slate-200">2. GitHub Actions CI/CD Polling</h4>
                          <p className="text-[11px] text-slate-400 leading-relaxed">
                            Backend polled GitHub check runs. Automated compilers, pytest suites, and SAST linters executed to confirm build readiness.
                          </p>
                        </div>
                      </div>

                      {/* Step 3: Conditional Supervisor Swarm Routing */}
                      <div className="relative">
                        <div className={`absolute -left-[30px] top-0.5 w-[22px] h-[22px] rounded-full border-4 border-surface-900 flex items-center justify-center shadow-lg ${
                          findings.some(f => f.category === 'ci_failure') 
                            ? 'bg-red-500 shadow-red-500/20' 
                            : 'bg-emerald-500 shadow-emerald-500/20'
                        }`} />
                        <div className="space-y-1">
                          <h4 className="text-xs font-bold text-slate-200">3. LangGraph Swarm Orchestration</h4>
                          {findings.some(f => f.category === 'ci_failure') ? (
                            <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3 mt-1.5 space-y-1">
                              <span className="text-[10px] text-red-400 font-bold uppercase block">CI Failure Route Selected</span>
                              <p className="text-[11px] text-slate-300 leading-relaxed">
                                Build failure detected. The supervisor bypassed code quality and security reviews, routing execution to the **CI/CD Log Analysis Agent** to debug stack traces.
                              </p>
                            </div>
                          ) : (
                            <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3 mt-1.5 space-y-1">
                              <span className="text-[10px] text-emerald-400 font-bold uppercase block">Success Code-Review Route Selected</span>
                              <p className="text-[11px] text-slate-300 leading-relaxed">
                                Build succeeded. The supervisor spawned the parallel agent swarm: **Security Agent** audited input boundaries, and the **Code Review Agent** checked interface breakages and Chroma DB design compliance.
                              </p>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Step 4: Summary Generated */}
                      <div className="relative">
                        <div className="absolute -left-[30px] top-0.5 w-[22px] h-[22px] rounded-full bg-brand-500 border-4 border-surface-900 flex items-center justify-center shadow-lg shadow-brand-500/20" />
                        <div className="space-y-1">
                          <h4 className="text-xs font-bold text-slate-200">4. Executive Summary Synthesis</h4>
                          <p className="text-[11px] text-slate-400 leading-relaxed">
                            All parsed alerts and agent suggestions were compiled by the Summary Agent. An overall Risk Score was computed and published.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="card border border-white/5 p-8 text-center space-y-3">
                  <Clock size={32} className="text-slate-600 mx-auto animate-pulse" />
                  <p className="text-slate-400 font-medium">AI Report is being generated…</p>
                  <p className="text-slate-600 text-xs">The summary will appear here once the supervisor finishes auditing.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
