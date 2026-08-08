import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Clock, CheckCircle2, XCircle, AlertTriangle, Zap, Terminal, RefreshCw, ChevronRight, ChevronDown, ChevronUp, ExternalLink, FileText, Bug } from 'lucide-react'
import { fetchPR, fetchChecks, fetchLogs, fetchFindings, type PRDetail, type CiCheck, type CiStep, type Finding } from '../api/client'

export default function PipelineDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const prId = parseInt(id || '0')

  const [pr, setPr] = useState<PRDetail | null>(null)
  const [checks, setChecks] = useState<CiCheck[]>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [rawLogs, setRawLogs] = useState<string>('')
  const [selectedJob, setSelectedJob] = useState<CiCheck | null>(null)
  const [selectedStep, setSelectedStep] = useState<CiStep | null>(null)
  const [activeTab, setActiveTab] = useState<'issues' | 'logs'>('issues')
  const [loading, setLoading] = useState(true)
  const [logsLoading, setLogsLoading] = useState(false)

  useEffect(() => {
    if (!prId) return

    Promise.all([
      fetchPR(prId),
      fetchChecks(prId),
      fetchFindings(prId)
    ]).then(([prData, checksData, findingsData]) => {
      setPr(prData)
      setChecks(checksData)
      setFindings(findingsData)
      
      // Auto-select first job, or the one that failed
      if (checksData.length > 0) {
        const failedJob = checksData.find(c => c.conclusion === 'failure')
        const activeJob = failedJob || checksData.find(c => c.status === 'in_progress') || checksData[0]
        setSelectedJob(activeJob)
        
        // Auto-select failed step inside that job
        if (activeJob.steps && activeJob.steps.length > 0) {
          const failedStep = activeJob.steps.find(s => s.conclusion === 'failure')
          const stepToSelect = failedStep || activeJob.steps.find(s => s.status === 'in_progress') || activeJob.steps[0]
          setSelectedStep(stepToSelect)
          
          // Determine default active tab
          const stepFindings = getStepFindingsForName(stepToSelect.name, findingsData)
          setActiveTab(stepFindings.length > 0 ? 'issues' : 'logs')
        }
      }
    }).catch(err => {
      console.error(err)
    }).finally(() => {
      setLoading(false)
    })

    // Fetch raw build logs
    setLogsLoading(true)
    fetchLogs(prId).then(data => {
      setRawLogs(data.logs || '')
    }).catch(() => {
      setRawLogs('Failed to load raw logs from GitHub Actions.')
    }).finally(() => {
      setLogsLoading(false)
    })
  }, [prId])

  // Poll checks if they are running
  useEffect(() => {
    if (!prId || !pr || pr.status !== 'reviewing') return

    const iv = setInterval(() => {
      Promise.all([
        fetchChecks(prId),
        fetchFindings(prId)
      ]).then(([checksData, findingsData]) => {
        setChecks(checksData)
        setFindings(findingsData)
        
        // Update selected job and step state in real-time
        if (selectedJob) {
          const updated = checksData.find(c => c.name === selectedJob.name)
          if (updated) {
            setSelectedJob(updated)
            if (selectedStep && updated.steps) {
              const updatedStep = updated.steps.find(s => s.name === selectedStep.name)
              if (updatedStep) setSelectedStep(updatedStep)
            }
          }
        }
      }).catch(() => {})
    }, 5000)
    return () => clearInterval(iv)
  }, [prId, pr, selectedJob, selectedStep])

  if (loading || !pr) {
    return (
      <div className="h-full flex items-center justify-center bg-surface-900">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500"></div>
      </div>
    )
  }

  // Get matching findings for a step name
  const getStepFindingsForName = (stepName: string, allFindings: Finding[]) => {
    const name = stepName.toLowerCase()
    return allFindings.filter(f => {
      const rid = f.rule_id.toLowerCase()
      const msg = f.message.toLowerCase()
      const path = f.file_path.toLowerCase()
      
      if (name.includes('flake8') || name.includes('lint') || name.includes('format')) {
        return rid.includes('flake8') || rid.includes('pep8') || rid.includes('pycodestyle') || msg.includes('flake8')
      }
      if (name.includes('bandit') || name.includes('sast') || name.includes('security')) {
        return rid.includes('bandit') || rid.includes('sast') || msg.includes('bandit') || rid.includes('sec')
      }
      if (name.includes('pytest') || name.includes('test') || name.includes('unit')) {
        return rid.includes('pytest') || rid.includes('fail') || rid.includes('test') || msg.includes('test') || path.includes('test')
      }
      return false
    })
  }

  const stepFindings = selectedStep ? getStepFindingsForName(selectedStep.name, findings) : []

  // Get list of all step names in the active job for segment splitting
  const allStepNames = selectedJob?.steps?.map(s => s.name) || []

  // Extract log segment for active step
  const getLogSegment = () => {
    if (logsLoading) return 'Loading build output...'
    if (!rawLogs) return 'Waiting for build outputs to stream...'
    if (!selectedStep) return rawLogs

    const stepName = selectedStep.name
    const lines = rawLogs.split('\n')
    let startIndex = -1

    // 1. Try to find the step header
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].toLowerCase()
      if (line.includes(stepName.toLowerCase()) && (line.includes('starting') || line.includes('run') || line.includes('step') || line.includes('##[group]'))) {
        startIndex = i
        break
      }
    }

    // 2. Fallback: Search for step name anywhere in logs
    if (startIndex === -1) {
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].toLowerCase().includes(stepName.toLowerCase())) {
          startIndex = Math.max(0, i - 3)
          break
        }
      }
    }

    if (startIndex === -1) {
      return rawLogs // Fallback to full logs
    }

    // Find where the next step starts
    let endIndex = lines.length
    const otherSteps = allStepNames.filter(s => s !== stepName)
    for (let i = startIndex + 1; i < lines.length; i++) {
      const line = lines[i].toLowerCase()
      const hitsOther = otherSteps.some(os => line.includes(os.toLowerCase()) && (line.includes('starting') || line.includes('run') || line.includes('step') || line.includes('##[group]')))
      if (hitsOther) {
        endIndex = i
        break
      }
    }

    return lines.slice(startIndex, endIndex).join('\n')
  }

  const activeLogs = getLogSegment()

  const formatLogLine = (line: string, index: number) => {
    const lowerLine = line.toLowerCase()
    
    // Check if it's an error, failure, traceback line, or command header
    const isError = lowerLine.includes('error:') || 
                    lowerLine.includes('fail') || 
                    line.startsWith('E ') || 
                    lowerLine.includes('exception') ||
                    lowerLine.includes('failed') ||
                    line.startsWith('>')
                    
    const isWarning = lowerLine.includes('warning:') || lowerLine.includes('warn')
    const isHeader = line.includes('===') || line.includes('---') || line.startsWith('Run ') || line.includes('##[group]')
    
    let contentCls = "text-slate-300"
    let containerCls = "hover:bg-zinc-900/50 px-2 py-0.5 flex items-start font-mono text-[11px] transition-colors leading-relaxed whitespace-pre-wrap break-all"
    
    if (isError) {
      contentCls = "text-red-400 font-semibold flex-1"
      containerCls += " bg-red-950/15 border-l-2 border-red-500 pl-1.5"
    } else if (isWarning) {
      contentCls = "text-amber-400 flex-1"
      containerCls += " bg-amber-950/10 border-l-2 border-amber-500 pl-1.5"
    } else if (isHeader) {
      contentCls = "text-cyan-400 font-bold flex-1"
      containerCls += " border-b border-zinc-900 pb-1 mt-2 first:mt-0"
    } else {
      contentCls = "text-zinc-300 flex-1 font-mono"
    }
    
    return (
      <div className={containerCls} key={index}>
        <span className="text-zinc-600 select-none w-10 text-right pr-3 mr-3 border-r border-zinc-850 shrink-0 font-mono text-[10px]">
          {index + 1}
        </span>
        <span className={contentCls}>{line}</span>
      </div>
    )
  }

  const stepStatusIcon = (conclusion: string | null, st: string) => {
    if (st === 'in_progress' || st === 'queued') return <RefreshCw size={13} className="text-yellow-400 animate-spin" />
    if (conclusion === 'success') return <CheckCircle2 size={13} className="text-green-400" />
    if (conclusion === 'failure') return <XCircle size={13} className="text-red-400" />
    return <Clock size={13} className="text-slate-600" />
  }

  const handleStepSelect = (step: CiStep) => {
    setSelectedStep(step)
    const stepFinds = getStepFindingsForName(step.name, findings)
    // Default tab: if findings exist, show issues; else show logs
    setActiveTab(stepFinds.length > 0 ? 'issues' : 'logs')
  }

  return (
    <div className="animate-fade-in-up space-y-6 pb-12 h-full flex flex-col">
      {/* Top bar navigation */}
      <div className="flex items-center justify-between pb-2 border-b border-white/5">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => navigate(`/pr/${prId}`)}
            className="p-2 rounded-lg bg-surface-800 border border-white/5 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <Zap size={16} className="text-yellow-400" /> CI/CD Build Run Details
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              PR #{pr.github_pr_number} · {pr.title} · by {pr.author}
            </p>
          </div>
        </div>
        
        {selectedJob?.details_url && (
          <a 
            href={selectedJob.details_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-brand-500/30 bg-brand-500/10 text-xs text-brand-400 font-medium hover:bg-brand-500/25 transition-all shadow-lg shadow-brand-500/10"
          >
            Open in GitHub Actions <ExternalLink size={12} />
          </a>
        )}
      </div>

      {/* Main Grid split: Sidebar & Logs/Issues Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-[70vh]">
        {/* Left Sidebar: Jobs & Steps List */}
        <div className="space-y-4">
          {/* Job Selection Tabs */}
          <div className="space-y-2">
            <label className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Jobs</label>
            <div className="flex flex-col gap-1.5">
              {checks.map((job, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setSelectedJob(job)
                    if (job.steps && job.steps.length > 0) {
                      const failedStep = job.steps.find(s => s.conclusion === 'failure')
                      handleStepSelect(failedStep || job.steps[0])
                    } else {
                      setSelectedStep(null)
                    }
                  }}
                  className={`flex items-center justify-between p-3.5 rounded-xl border text-left transition-all ${
                    selectedJob?.name === job.name
                      ? 'border-brand-500 bg-brand-500/10 text-white shadow-lg shadow-brand-500/5'
                      : 'border-white/5 bg-surface-800/40 text-slate-400 hover:border-white/15'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {stepStatusIcon(job.conclusion, job.status)}
                    <span className="font-semibold text-xs truncate">{job.name}</span>
                  </div>
                  <span className={`text-[9px] font-mono uppercase px-2 py-0.5 rounded ${
                    job.conclusion === 'success' ? 'bg-green-500/10 text-green-400' :
                    job.conclusion === 'failure' ? 'bg-red-500/10 text-red-400' :
                    'bg-yellow-500/10 text-yellow-400'
                  }`}>
                    {job.status === 'in_progress' ? 'running' : (job.conclusion || 'pending')}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Steps List */}
          {selectedJob && (
            <div className="card p-4 space-y-3 bg-surface-800/20 border-white/5 flex-1">
              <div className="flex items-center justify-between pb-2 border-b border-white/5">
                <label className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                  Steps inside {selectedJob.name}
                </label>
                <span className="text-[10px] font-mono text-slate-600">
                  {selectedJob.steps?.length || 0} total
                </span>
              </div>
              
              <div className="space-y-1.5 max-h-[50vh] overflow-y-auto pr-1">
                {selectedJob.steps && selectedJob.steps.length > 0 ? (
                  selectedJob.steps.map((step, sIdx) => {
                    const isSelected = selectedStep?.name === step.name
                    const isFailed = step.conclusion === 'failure'
                    
                    return (
                      <button
                        key={sIdx}
                        onClick={() => handleStepSelect(step)}
                        className={`w-full flex items-center justify-between p-3 rounded-lg border text-left transition-all ${
                          isSelected
                            ? isFailed
                              ? 'border-red-500 bg-red-500/15 text-white'
                              : 'border-brand-500 bg-brand-500/5 text-white'
                            : 'border-transparent bg-white/2 hover:bg-white/5 text-slate-400'
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="text-[10px] font-mono text-slate-600 w-4">{step.number}</span>
                          {stepStatusIcon(step.conclusion, step.status)}
                          <span className={`text-[11px] truncate ${isSelected ? 'font-semibold' : ''}`}>
                            {step.name}
                          </span>
                        </div>
                        
                        {isFailed && (
                          <span className="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)] animate-pulse" />
                        )}
                      </button>
                    )
                  })
                ) : (
                  <p className="text-xs text-slate-600 py-4 text-center">No steps logged for this job.</p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right Main Content Panel: Toggle Tab Panel (Parsed Issues OR Raw Logs) */}
        <div className="lg:col-span-2 flex flex-col border border-white/5 rounded-2xl bg-surface-900/50 shadow-2xl overflow-hidden min-h-[70vh]">
          
          {/* 1. Header showing Active Step Info */}
          <div className="p-4 flex items-center justify-between border-b border-white/5 bg-surface-800/60">
            <div>
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Active Step</span>
              <h2 className="text-base font-bold text-white mt-0.5">{selectedStep?.name || 'Select a step'}</h2>
            </div>
            
            {selectedStep && (
              <span className={`text-xs font-semibold px-3 py-1 rounded-full ${
                selectedStep.conclusion === 'success' ? 'bg-green-500/10 text-green-400' :
                selectedStep.conclusion === 'failure' ? 'bg-red-500/10 text-red-400' :
                'bg-yellow-500/10 text-yellow-400 animate-pulse'
              }`}>
                {selectedStep.status === 'in_progress' ? 'Running' : (selectedStep.conclusion || 'Pending')}
              </span>
            )}
          </div>

          {/* 2. Sleek Tab Selection Bar */}
          <div className="flex bg-surface-900 border-b border-white/5">
            <button
              onClick={() => setActiveTab('issues')}
              className={`flex items-center gap-2 px-6 py-3.5 text-xs font-bold transition-all border-b-2 ${
                activeTab === 'issues'
                  ? 'border-brand-500 text-brand-400 bg-brand-500/3 shadow-[inset_0_-2px_0_#6366f1]'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/2'
              }`}
            >
              <Bug size={14} className={activeTab === 'issues' ? 'text-brand-400' : 'text-slate-500'} />
              Parsed Issues ({stepFindings.length})
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`flex items-center gap-2 px-6 py-3.5 text-xs font-bold transition-all border-b-2 ${
                activeTab === 'logs'
                  ? 'border-brand-500 text-brand-400 bg-brand-500/3 shadow-[inset_0_-2px_0_#6366f1]'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/2'
              }`}
            >
              <Terminal size={14} className={activeTab === 'logs' ? 'text-brand-400' : 'text-slate-500'} />
              Raw Terminal Output
            </button>
          </div>

          {/* 3. Tab Contents */}
          <div className="flex-1 p-5 overflow-y-auto bg-surface-900/10 flex flex-col">
            {activeTab === 'issues' ? (
              <div className="space-y-4 flex-1">
                {stepFindings.length > 0 ? (
                  <div className="space-y-4">
                    {stepFindings.map((finding) => (
                      <div 
                        key={finding.id} 
                        className={`card p-5 border rounded-xl space-y-4 transition-all hover:border-white/10 ${
                          finding.severity === 'critical' ? 'border-red-500/30 bg-red-500/5' :
                          finding.severity === 'high' ? 'border-orange-500/30 bg-orange-500/5' :
                          'border-yellow-500/20 bg-yellow-500/3'
                        }`}
                      >
                        {/* Finding Info Header */}
                        <div className="flex items-center justify-between gap-3 border-b border-white/5 pb-3">
                          <div className="flex items-center gap-3">
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded tracking-wide uppercase ${
                              finding.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                              finding.severity === 'high' ? 'bg-orange-500/20 text-orange-400' :
                              'bg-yellow-500/20 text-yellow-400'
                            }`}>
                              {finding.severity.toUpperCase()}
                            </span>
                            <span className="font-mono text-xs text-slate-400 font-semibold">{finding.rule_id}</span>
                          </div>
                          
                          <span className="font-mono text-[11px] text-slate-400">
                            {finding.file_path.split('/').pop()}:{finding.line_number}
                          </span>
                        </div>

                        {/* Message & Suggestion */}
                        <div className="space-y-3 text-sm leading-relaxed">
                          <div className="text-slate-200">
                            <span className="font-semibold text-slate-400 block text-xs uppercase tracking-wide mb-1">Issue Details</span>
                            {finding.message}
                          </div>
                          
                          {finding.suggestion && (
                            <div className="text-emerald-300 bg-emerald-500/5 border border-emerald-500/10 p-3 rounded-lg">
                              <span className="font-semibold text-emerald-400 block text-xs uppercase tracking-wide mb-1">Suggested Fix</span>
                              {finding.suggestion}
                            </div>
                          )}
                        </div>

                        {/* Code Snippet Box */}
                        {finding.code_snippet && finding.code_snippet !== 'N/A' && (
                          <div className="space-y-1">
                            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Context Snippet</span>
                            <pre className="rounded-lg border border-white/5 bg-black p-4 font-mono text-[11px] text-zinc-300 overflow-x-auto whitespace-pre shadow-inner">
                              {finding.code_snippet}
                            </pre>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  selectedStep?.conclusion === 'failure' ? (
                    <div className="my-auto py-12 text-center space-y-3">
                      <XCircle className="text-red-400 mx-auto" size={32} />
                      <p className="text-sm font-semibold text-red-300">Step Failed with no parsed code issues</p>
                      <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                        This step exited with error codes. Click on the <strong>Raw Terminal Output</strong> tab above to view logs and troubleshoot setup or dependency errors.
                      </p>
                    </div>
                  ) : (
                    <div className="my-auto py-12 text-center space-y-2">
                      <CheckCircle2 className="text-green-400 mx-auto" size={32} />
                      <p className="text-sm text-slate-300 font-medium">No issues identified in this step.</p>
                      <p className="text-xs text-slate-500">Everything compiles and runs cleanly.</p>
                    </div>
                  )
                )}
              </div>
            ) : (
              /* Full Height Terminal logs inside its own tab */
              <div className="flex-1 flex flex-col border border-white/5 rounded-xl bg-black overflow-hidden shadow-2xl h-[55vh]">
                <div className="flex items-center justify-between bg-zinc-950 px-4 py-2 border-b border-zinc-900 select-none">
                  <span className="text-[10px] font-mono text-slate-500">
                    LOGS FOR: {selectedStep?.name} ({activeLogs.split('\n').length} lines)
                  </span>
                  <div className="flex gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-zinc-800" />
                    <div className="w-1.5 h-1.5 rounded-full bg-zinc-800" />
                    <div className="w-1.5 h-1.5 rounded-full bg-zinc-800" />
                  </div>
                </div>
                
                <div className="flex-1 p-4 overflow-auto font-mono text-xs leading-relaxed custom-scrollbar bg-black select-text">
                  <div className="space-y-0.5 bg-black">
                    {activeLogs.split('\n').map((line, lIdx) => formatLogLine(line, lIdx))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
