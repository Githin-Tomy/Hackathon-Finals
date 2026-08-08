# Build Plan — AI Multi-Agent Code Review & Suggestion Platform

## How to execute the design in `AI_Code_Review_Suggestion_Agent_Design_v2.md`

> **Assumption:** this is being built for a hackathon with roughly
> **48 hours** of build time. If your window is different, the phase
> *order* stays the same — only the hour numbers on the left move.
> The plan is structured so that at the end of **every** phase you
> have something demoable, even if the clock runs out early.

---

# 0. Priority Tiers (read this first)

Everything below is tagged so you always know what to cut if you're
behind schedule.

- **P0 — Demo-breaking.** Without this, there is no demo. Build these
  first, in order, no exceptions.
- **P1 — Demo-strengthening.** Makes the platform look like a real
  product instead of a script. Build after all P0 is working end-to-end.
- **P2 — Stretch.** Build only if P0+P1 are done with time to spare.

Rule of thumb: get one **thin vertical slice** through P0 working
(one PR, one rule, one agent, one comment posted) before building any
component out wide. A narrow end-to-end demo beats a wide half-built
system every time judges look at a clock.

---

# 1. Tech Stack Decisions

Locking these now avoids debate later.

| Layer | Choice | Why |
|---|---|---|
| Backend | Python, FastAPI | Fast to scaffold, native AST module, async webhook handling |
| AST parsing | `ast` (Python), `tree-sitter` (JS/TS) | Both have mature Python bindings; skip Java parsing for MVP |
| Rule engine | Plain Python classes, no external framework | Keeps the "no SonarQube dependency" story clean and demo-explainable |
| Agent orchestration | LangGraph | Matches the design doc; supervisor + specialist agents |
| LLM | Claude API (Anthropic) | Tool use for structured findings, good at code reasoning |
| Git integration | GitHub MCP / GitHub REST API + PyGithub | MCP if available in your environment, REST as fallback — don't block on MCP setup |
| CI/CD adapter | GitHub Actions webhook only for MVP | Cover GitLab/Jenkins only as P2 — one provider is enough to prove the concept |
| Database | SQLite for MVP → Postgres if time allows | Zero setup time; swap later is a one-line connection string change |
| Frontend | React + Vite, Tailwind, Monaco Editor | Monaco gives you a real diff viewer for free |
| Dependency graph | NetworkX | As per design doc |
| Hosting for demo | Local + `ngrok` (or similar) for webhook exposure | No deployment risk on demo day |

**Explicitly deferred to P2/post-hackathon:** Java support, GitLab/Jenkins
adapters, self-hosted LLM mode, Postgres migration, auth/multi-tenant,
rule marketplace.

---

# 2. Build Order & Dependency Graph

Build in this order — each step only depends on the ones above it.

```
1. Repo scaffold + FastAPI skeleton + React skeleton         [P0]
2. Synthetic PR fixtures (3–5 PRs with known injected bugs)   [P0]
3. AST Parser (Python only first)                             [P0]
4. Rule Engine core + 5 security rules + 5 code-smell rules   [P0]
5. Finding Aggregator + Confidence Scorer (static thresholds) [P0]
6. GitHub webhook receiver → PR Collector                     [P0]
7. Publish findings ≥95% confidence as GitHub PR comments      [P0]
   ── At this point you have a working non-AI review bot. Demo-safe. ──
8. Context Compression + Privacy Redaction (basic regex)       [P0]
9. LangGraph Supervisor + Security Agent + Code Review Agent   [P0]
10. Publish AI-reasoned comments alongside rule-based ones     [P0]
   ── At this point the hybrid pipeline is real end-to-end. ──
11. React dashboard: PR list, diff viewer, inline comments      [P1]
12. Remaining rule categories (maintainability, perf, arch)     [P1]
13. Architecture Agent + Suggestion Agent + Summary Agent       [P1]
14. Eval harness (`eval/scoring.py`) against synthetic PRs      [P1]
15. Eval panel in dashboard (precision/recall live)             [P1]
16. CI/CD webhook (GitHub Actions) + status-check gate           [P1]
17. Feedback capture (accept/reject buttons → feedback_store)   [P2]
18. Historical comment ingestion into Repository Context Agent  [P2]
19. Confidence recalibration from feedback                       [P2]
20. GitLab/Jenkins adapters, self-hosted LLM mode                [P2]
```

Steps 1–10 are the entire P0 tier. If you build nothing else, you
still have a legitimate, working hybrid AI code review bot to show.

---

# 3. Hour-by-Hour Plan (48h window)

Adjust proportionally if your actual window differs — the ratio
matters more than the absolute hours.

## Hours 0–4: Foundation
- Scaffold `backend/` (FastAPI) and `frontend/` (React + Vite).
- Set up SQLite + models: `repositories`, `pull_requests`,
  `review_issues`.
- Write 3 synthetic PR fixtures by hand (a hardcoded secret, a SQL
  string-concat, a long method with high cyclomatic complexity) —
  these become your test data for everything downstream.
- Get GitHub API auth working (personal access token is fine for demo).

## Hours 4–12: Deterministic Core
- AST Parser for Python.
- Rule Engine base class + registry + 8–10 rules across security and
  code-smell categories (the highest-signal, easiest-to-explain ones:
  hardcoded secrets, `eval()`/`exec()`, SQL string concat, long
  method, unused imports, empty catch block).
- Metrics Engine: cyclomatic complexity, method length, LOC.
- Finding Aggregator with dedup.
- Confidence Scorer with the static threshold table from the design
  doc (no learning yet — that's P2).
- **Checkpoint:** run the rule engine against your synthetic PRs from
  a script and confirm findings match ground truth. Don't move on
  until this checkpoint passes.

## Hours 12–20: Git Integration
- Webhook receiver for PR opened/synchronize events.
- PR Collector pulls diff + changed files via GitHub API.
- Wire deterministic pipeline to run automatically on webhook.
- Publisher posts ≥95%-confidence findings as inline PR comments.
- **Checkpoint:** open a real PR against a scratch repo with an
  injected hardcoded secret and watch the bot comment on it
  automatically. This is your fallback demo if AI agents run late.

## Hours 20–30: AI Layer
- Privacy Redaction pass (regex-based secret/PII stripping — keep it
  simple, it just needs to demonstrably run before compression).
- Context Compression builder (structured JSON per design doc).
- LangGraph Supervisor + Security Agent + Code Review Agent (start
  with these two; they cover the widest range of findings).
- Wire <95%-confidence findings through this path, publish agent
  output as PR comments distinct from rule-based ones (e.g. prefix
  `🤖 AI Review:` vs `⚙️ Rule Engine:` so the demo visibly shows the
  hybrid split).
- **Checkpoint:** the same test PR now shows both instant rule-based
  comments and slower, reasoned AI comments on the ambiguous finding.

## Hours 30–38: Dashboard
- PR list page, pulling from the DB.
- Diff viewer (Monaco) with inline comment overlay.
- Risk score + summary panel (wire up Summary Agent here).
- Basic styling pass — this is what judges actually look at first,
  don't skip polish here even under time pressure.

## Hours 38–44: Eval + CI/CD (P1)
- `eval/scoring.py`: run pipeline against all synthetic fixtures,
  compute precision/recall/F1.
- Eval panel in dashboard showing these numbers live.
- GitHub Actions webhook adapter + status check that fails on
  critical findings — even a minimal version (one workflow file, one
  status check) sells the "CI/CD integration" requirement.

## Hours 44–48: Demo Prep
- Reset synthetic repo to a clean state.
- Rehearse the demo script from the design doc's Evaluation section
  end-to-end at least twice, timed.
- Prepare a fallback recording/screenshots in case live webhooks fail
  on venue wifi.
- Write the 3–5 line README explaining what's real vs. what's
  scoped-out for time (judges respect honesty about MVP boundaries
  more than overclaiming).

---

# 4. What to Explicitly Cut If Behind Schedule

In order — cut from the bottom up:

1. GitLab/Jenkins adapters (keep GitHub Actions only, or even skip
   CI/CD gating entirely and just show the webhook firing).
2. Feedback loop / confidence recalibration — hardcode the thresholds
   and say so.
3. Architecture Agent + Suggestion Agent — Security Agent + Code
   Review Agent alone still tell the hybrid-AI story.
4. Historical comment ingestion — mention it as next-step in the demo.
5. Eval dashboard panel — keep the `eval/scoring.py` script and show
   its console output instead of a UI panel.
6. Dashboard polish — a working diff viewer with plain inline comments
   is enough; skip the analytics/architecture-graph pages entirely.

Never cut: the rule engine, the confidence-based routing split, and
at least one working end-to-end PR demo. That routing split is the
entire thesis of the project ("LLM is never the first step") — if
that doesn't visibly work in the demo, the pitch falls apart.

---

# 5. Synthetic PR Fixture Plan

You need these early (Hour 0–4) because everything downstream tests
against them.

| Fixture | Injected issue | Expected finding | Confidence tier |
|---|---|---|---|
| `pr_001_hardcoded_secret` | `API_KEY = "sk-live-..."` | SEC001, Critical | ≥95% (direct publish) |
| `pr_002_sql_injection` | f-string built SQL query | SEC00X, High | ≥95% |
| `pr_003_long_method` | 80-line method, cyclomatic complexity 18 | Maintainability finding | <95% (AI review) |
| `pr_004_n_plus_one` | loop with a DB call inside | Performance finding | <95% (AI review, ambiguous without full context) |
| `pr_005_layer_violation` | controller importing DB layer directly | Architecture finding | <95% (needs Architecture Agent) |

Keep each fixture to one or two files — small, readable, and fast to
narrate live during the demo.

---

# 6. Risk Register

| Risk | Mitigation |
|---|---|
| Webhook delivery fails on venue wifi | Have `ngrok` pre-tested; fallback to a "replay webhook" button that re-POSTs a saved payload |
| LLM latency makes demo feel slow | Pre-warm one call before going on stage; have a cached response ready as fallback narration |
| AST parser chokes on an edge case in the fixture | Freeze fixture files early (Hour 4) and never edit them again without re-running the checkpoint |
| Running out of time before AI layer works | Hours 12–20 checkpoint (rule-engine-only bot) is a legitimate standalone demo — treat it as your floor, not just a milestone |
| Judges ask about production readiness | Have the "What's Cut" section (§4) memorized — scoping honesty reads as engineering maturity |

---

# 7. Post-Hackathon Roadmap (if this continues past the event)

1. Postgres migration + proper auth/multi-tenancy.
2. Java support via JavaParser; GitLab/Jenkins adapters.
3. Full feedback-driven confidence recalibration (currently P2/stubbed).
4. Self-hosted LLM deployment option for privacy-sensitive orgs.
5. Rule Marketplace and org-custom rule packs.
6. Auto-fix generation with direct commit-back.

This section exists so the README doesn't read as "finished" — it
signals the team knows the difference between a hackathon MVP and a
production system, which is worth stating explicitly to judges.
