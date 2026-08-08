# AI Multi-Agent Code Review Platform

> **Hackathon MVP v2.0** — Hybrid rule-based + AI multi-agent code review platform.
> Supports **OpenAI** (gpt-4o, gpt-4o-mini, gpt-3.5-turbo) and **Google Gemini** (gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash).
> Switch models **live from the sidebar** — no server restart needed.

A pull request is automatically analysed the moment it opens. High-confidence findings (≥ 95%) are published instantly as inline PR comments by the rule engine. Ambiguous findings are routed through a LangGraph supervisor to GPT-3.5 specialist agents (Security / Code Review) for deeper reasoning before being posted.

---

## Architecture

```
GitHub PR → Webhook → Rule Engine (AST) → Confidence Split
                                                ↓
                              ≥95% → Direct PR Comment (⚙️ Rule Engine)
                              <95% → LangGraph Supervisor
                                        ├── Security Agent (GPT-3.5)
                                        └── Code Review Agent (GPT-3.5)
                                                ↓
                                       PR Comment (🤖 AI Review)
                                       + PR Summary
```

---

## Quick Start

### Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11+ |
| Node.js | 20+ |
| Smee Client (for webhook) | any |

---

### 1. Clone and Configure

```bash
# Navigate to the project directory
cd "Version 1"

# Copy the example env file and fill in your credentials
cp .env.example .env
```

Open `.env` and set:

```env
GITHUB_APP_ID=your_app_id_here
GITHUB_APP_INSTALLATION_ID=your_installation_id_here
GITHUB_APP_PRIVATE_KEY_PATH=path/to/private-key.pem

# Choose ONE provider (or configure both for easy switching)
OPENAI_API_KEY=sk-your_openai_key_here    # From https://platform.openai.com/api-keys
GOOGLE_API_KEY=your_google_api_key_here   # From https://aistudio.google.com/app/apikey

MODEL_PROVIDER=openai                     # "openai" or "google"
MODEL_NAME=gpt-4o-mini                    # See available models in README
```

#### Getting GitHub App Credentials
1. Create a GitHub App in your organization settings.
2. Grant read/write permissions for **Pull Requests** and **Contents**.
3. Install the app on your repository.
4. Download the private key and set the IDs in `.env`.

#### Getting an OpenAI API Key
1. Go to **https://platform.openai.com/api-keys**
2. Create a new secret key, copy it into `.env` as `OPENAI_API_KEY`

#### Getting a Google Gemini API Key
1. Go to **https://aistudio.google.com/app/apikey**
2. Create a new API key, copy it into `.env` as `GOOGLE_API_KEY`

#### Switching Models (Live, No Restart)
Use the **model selector panel in the sidebar** of the dashboard — pick any provider and model and click **Apply Model**. It hot-swaps the backend LLM instantly.

---

### 2. Backend Setup

```bash
cd "Version 1/backend"

# Create a virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server using uvicorn directly
uvicorn app.main:app --reload
# Server runs at http://localhost:8000
```

> **Checkpoint:** Visit http://localhost:8000/health → should return `{"status":"ok"}`

---

### 3. Frontend Setup

```bash
cd "Version 1/frontend"

# Install dependencies
npm install

# Start the dev server
npm run dev
# Dashboard at http://localhost:5173
```

---

### 4. Expose Webhook with Smee.io

GitHub needs a public URL to send webhook events. Use Smee.io to forward webhook payloads:

1. Go to **https://smee.io/** and click **Start a new channel**.
2. Copy your unique Smee URL (e.g. `https://smee.io/abc123XYZ`).
3. Install and run the Smee client locally to forward payloads to your local FastAPI server:

```bash
# Install Smee client globally
npm install --global smee-client

# Forward Smee payloads to local port 8000
smee --url https://smee.io/ReviewGen --path /webhook/github --port 8000
```

---

### 5. Configure GitHub Webhook

1. Go to your GitHub repo → **Settings → Webhooks → Add webhook**
2. Set:
   - **Payload URL**: paste your Smee channel URL (e.g. `https://smee.io/abc123XYZ`)
   - **Content type**: `application/json`
   - **Secret**: same value as `GITHUB_WEBHOOK_SECRET` in `.env`
   - **Events**: Select "Pull requests"
3. Click **Add webhook**

---

### 6. Test the Pipeline

Open a PR against your repo (or push to a branch). The bot will:
1. ⚙️ Instantly comment on high-confidence issues (hardcoded secrets, SQL injection)
2. 🤖 Post AI-reasoned comments for ambiguous findings after GPT-3.5 analysis
3. Post a summary comment with an overall risk score

**For demo/testing without a live webhook:**
```bash
# Run the local script to manually trigger a review for a specific repo/PR
cd "Version 1/backend"
python demo_trigger.py
```

---

### 7. Run the Eval Harness

```bash
cd "Version 1/backend"
python eval/scoring.py
```

Or from the dashboard → **Eval Harness** → **Run Eval**.

---

## Project Structure

```
Version 1/
├── backend/
│   ├── app/                  # Application Core
│   │   ├── main.py           # FastAPI entrypoint
│   │   ├── config.py         # App configuration
│   │   ├── db/               # SQLAlchemy models & engine
│   │   └── routers/          # API routes (webhook, reviews, eval)
│   ├── analysis/             # Static Analysis Engine
│   │   ├── engine/           # Aggregator & confidence scoring
│   │   ├── parser/           # AST & Diff parsers
│   │   └── rules/            # Custom rules (SEC001-SEC005, CS001-CS005)
│   ├── ai/                   # AI Orchestration
│   │   ├── llm.py            # Central LLM client
│   │   └── agents/           # LangGraph supervisor & specialist agents
│   └── integrations/         # External APIs
│       └── github/           # PR collector & publisher
├── frontend/
│   └── src/
│       ├── App.tsx           # Main app with sidebar + routing
│       ├── components/
│       │   ├── PRList.tsx    # PR list with live polling
│       │   ├── DiffViewer.tsx# PR detail + finding cards
│       │   └── EvalPanel.tsx # Eval charts + table
│       └── api/client.ts     # Typed API client
├── fixtures/                 # 5 synthetic PRs with injected bugs
├── .env.example              # Environment variable template
└── README.md
```

---

## Implemented Rules

| ID | Name | Severity | Confidence | Path |
|---|---|---|---|---|
| SEC001 | Hardcoded Secret | Critical | 100% → Direct | `rules/security.py` |
| SEC002 | Dangerous eval/exec | High | 100% → Direct | `rules/security.py` |
| SEC003 | SQL Injection Risk | Critical | 97% → Direct | `rules/security.py` |
| SEC004 | Subprocess shell=True | High | 100% → Direct | `rules/security.py` |
| SEC005 | Open Redirect | Medium | 80% → AI | `rules/security.py` |
| CS001 | Long Method | Medium | 90% → AI | `rules/code_smell.py` |
| CS002 | Too Many Arguments | Low | 95% → Direct | `rules/code_smell.py` |
| CS003 | Empty Except Block | High | 100% → Direct | `rules/code_smell.py` |
| CS004 | Unused Import | Low | 85% → AI | `rules/code_smell.py` |
| CS005 | Bare Raise | Low | 80% → AI | `rules/code_smell.py` |

---

## What's Real vs. Scoped Out (MVP Boundaries)

### ✅ What's built
- Full hybrid pipeline: rule engine → confidence split → AI agents → PR comments
- LangGraph supervisor routing Security and Code Review agents
- GPT-3.5 for analysis, validation, and PR summaries
- React dashboard with live polling, Monaco code snippets, risk scores
- Eval harness with precision/recall/F1

### 🔲 Explicitly out of scope (post-hackathon)
- GitLab / Jenkins adapters (GitHub Actions webhook only)
- Java/TypeScript AST parsing (Python only)
- Feedback-driven confidence recalibration (thresholds are static)
- Multi-tenancy / auth
- Postgres migration (SQLite is fine for demo scale)
- Self-hosted LLM mode

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/webhook/github` | GitHub webhook receiver |
| `POST` | `/webhook/replay/{pr_id}` | Re-trigger pipeline (demo fallback) |
| `GET`  | `/api/prs` | List all pull requests |
| `GET`  | `/api/prs/{id}` | PR detail with all findings |
| `GET`  | `/api/prs/{id}/findings` | Findings (filterable) |
| `GET`  | `/api/stats` | Dashboard summary stats |
| `POST` | `/api/eval/run` | Run eval harness |
| `GET`  | `/api/eval/results` | Stored eval results |
| `GET`  | `/api/settings/model` | Get active LLM config + available models |
| `POST` | `/api/settings/model` | Switch LLM provider/model at runtime |
| `GET`  | `/health` | Health check + active model info |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `GITHUB_TOKEN` errors | Ensure PAT has `repo` scope; check it hasn't expired |
| Webhook not firing | Confirm Smee client is running; check GitHub webhook "Recent Deliveries" tab |
| OpenAI rate limit | Low-confidence findings will be skipped gracefully; rule-based comments still post |
| SQLite locked | Restart the FastAPI server; only one process should write to the DB |
| Frontend 404 on `/api` | Ensure the FastAPI server is running on port 8000 |
