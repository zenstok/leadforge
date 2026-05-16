# LeadForge — AI Sales Intelligence Agent Swarm

An autonomous multi-agent system that discovers, researches, qualifies, and crafts personalized outreach for sales leads — powered by real-time web data.

## Architecture

**4-Agent Swarm:**

1. **Scout Agent** — Discovers companies matching your ICP via Bright Data SERP + page scraping. Targets Crunchbase, LinkedIn, and startup directories to find actual companies (not just listicle articles).
2. **Research Agent** — Deep-dives on each lead: scrapes their website, searches for recent news and hiring signals via Bright Data.
3. **Qualifier Agent** — Scores and ranks leads (0–100) using LLM reasoning via TokenRouter, with retry logic for reliability.
4. **Outreach Agent** — Generates personalized multi-touch email sequences via LLM, tailored to each lead's specific situation.

**Memory Layer**: Evermind EverOS integration for persistent lead memory (falls back to in-memory store when Evermind is not configured).

## Tech Stack (Sponsor Usage)

| Sponsor | Usage |
|---------|-------|
| Bright Data | Web scraping + SERP for company discovery and research |
| Evermind | Long-term memory for leads, outreach patterns |
| Qwen Cloud | LLM for scoring, analysis, and email generation |
| TokenRouter | Unified LLM routing with caching and retries |
| Zeabur | Live cloud deployment |

## Quick Start (Docker)

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd leadforge

# 2. Create your .env file
cp .env.example .env
# Edit .env and add your API keys:
#   BRIGHTDATA_API_TOKEN=...
#   TOKENROUTER_API_KEY=...
#   TOKENROUTER_BASE_URL=https://api.tokenrouter.com/v1
#   QWEN_MODEL=deepseek/deepseek-v4-pro

# 3. Build and run with Docker
docker build -t leadforge .
docker run -p 8000:8000 --env-file .env leadforge

# 4. Open http://localhost:8000
```

## Deploy to Zeabur

1. Push to GitHub
2. Connect the repo at [zeabur.com](https://zeabur.com)
3. Set environment variables in the Zeabur dashboard
4. Deploy — your app is live

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Dashboard UI |
| `GET` | `/health` | Health check |
| `POST` | `/api/pipeline/start` | Start a new pipeline run |
| `GET` | `/api/pipeline/{run_id}/status` | Check pipeline progress |
| `GET` | `/api/pipeline/{run_id}/results` | Get full results |
| `GET` | `/api/pipeline/runs` | List all runs |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BRIGHTDATA_API_TOKEN` | Yes | Bright Data API token for web scraping |
| `TOKENROUTER_API_KEY` | Yes | TokenRouter API key for LLM access |
| `TOKENROUTER_BASE_URL` | Yes | TokenRouter endpoint (`https://api.tokenrouter.com/v1`) |
| `QWEN_MODEL` | No | Model to use (default: `deepseek/deepseek-v4-pro`) |
| `EVERMIND_API_URL` | No | Evermind EverOS API URL (optional) |
| `EVERMIND_API_KEY` | No | Evermind API key (optional) |

## Built for Agent Forge AI Hackathon 2025
