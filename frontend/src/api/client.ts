import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface PRSummary {
  id: number
  github_pr_number: number
  title: string
  author: string
  html_url: string
  status: string
  risk_score: number
  finding_count: number
  created_at: string
  ai_summary?: string
}

export interface Finding {
  id: number
  pr_id: number
  rule_id: string
  rule_name: string
  category: string
  severity: string
  confidence: number
  file_path: string
  line_number: number
  code_snippet: string
  message: string
  suggestion: string
  source: string
  comment_posted: boolean
  created_at: string
}

export interface PRDetail extends PRSummary {
  repo_id: number
  base_branch: string
  head_branch: string
  ai_summary: string
  updated_at: string
  findings: Finding[]
}

export interface Stats {
  total_prs: number
  reviewed_prs: number
  total_findings: number
  critical_findings: number
  ai_findings: number
  rule_findings: number
}

export interface EvalResult {
  id: number
  fixture_name: string
  precision: number
  recall: number
  f1: number
  true_positives: number
  false_positives: number
  false_negatives: number
  run_at: string
}

export interface ModelOption {
  id: string
  label: string
  description: string
}

export interface ModelConfig {
  provider: string
  model: string
  temperature: number
  available_models: Record<string, ModelOption[]>
}

export interface CiStep {
  name: string
  status: string
  conclusion: string | null
  number: number
}

export interface CiCheck {
  name: string
  status: string        // "queued" | "in_progress" | "completed"
  conclusion: string | null  // "success" | "failure" | "neutral" | null
  details_url: string | null
  steps?: CiStep[]
}

// ── PR endpoints ──────────────────────────────────────────────────────────────
export const fetchPRs = (params?: Record<string, string>) =>
  api.get<PRSummary[]>('/prs', { params }).then(r => r.data)

export const fetchPR = (id: number) =>
  api.get<PRDetail>(`/prs/${id}`).then(r => r.data)

export const fetchFindings = (prId: number, params?: Record<string, string>) =>
  api.get<Finding[]>(`/prs/${prId}/findings`, { params }).then(r => r.data)

export const fetchChecks = (prId: number) =>
  api.get<CiCheck[]>(`/prs/${prId}/checks`).then(r => r.data)

export const fetchLogs = (prId: number) =>
  api.get<{ logs: string }>(`/prs/${prId}/logs`).then(r => r.data)

export const fetchStats = () =>
  api.get<Stats>('/stats').then(r => r.data)

// ── Eval endpoints ────────────────────────────────────────────────────────────
export const fetchEvalResults = () =>
  api.get<EvalResult[]>('/eval/results').then(r => r.data)

export const runEval = () =>
  api.post<EvalResult[]>('/eval/run').then(r => r.data)

// ── Webhook ───────────────────────────────────────────────────────────────────
export const replayWebhook = (prId: number) =>
  axios.post(`/webhook/replay/${prId}`).then(r => r.data)

export const syncGitHubPRs = () =>
  api.post<{ status: string; synced_new_prs: number }>('/sync').then(r => r.data)

// ── Model settings ────────────────────────────────────────────────────────────
export const fetchModelConfig = () =>
  api.get<ModelConfig>('/settings/model').then(r => r.data)

export const updateModelConfig = (provider: string, model: string, temperature = 0.1) =>
  api.post<ModelConfig>('/settings/model', { provider, model, temperature }).then(r => r.data)

// ── Repositories ──────────────────────────────────────────────────────────────
export const syncRepoContext = (repoId: number) =>
  api.post(`/repos/${repoId}/sync-context`).then(r => r.data)

// ── Approvals ─────────────────────────────────────────────────────────────────
export const approvePR = (prId: number, comment?: string) =>
  api.post<{status: string}>(`/prs/${prId}/approve`, { comment: comment || "" }).then(r => r.data)

export const rejectPR = (prId: number, comment?: string) =>
  api.post<{status: string}>(`/prs/${prId}/reject`, { comment: comment || "" }).then(r => r.data)
