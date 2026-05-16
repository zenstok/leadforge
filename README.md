# LeadForge — AI Sales Intelligence Agent Swarm

An autonomous multi-agent system that discovers, researches, qualifies, and crafts personalized outreach for sales leads.

## Architecture

**4-Agent Swarm** orchestrated by AgentField:

1. **Scout Agent** — Discovers companies matching your ICP using Bright Data web scraping
2. **Research Agent** — Deep-dives on each lead using Actionbook browser automation + Bright Data
3. **Qualifier Agent** — Scores and ranks leads using Qwen LLM via TokenRouter
4. **Outreach Agent** — Generates personalized multi-touch email sequences via Qwen/TokenRouter

**Memory Layer**: Evermind EverOS for persistent lead memory and pattern learning

## Tech Stack (Sponsor Usage)

| Sponsor | Usage |
|---------|-------|
| AgentField | Agent orchestration and coordination |
| Bright Data | Web scraping for company discovery and research |
| Actionbook | Browser automation for structured data extraction |
| Evermind | Long-term memory for leads, outreach patterns |
| Qwen Cloud | LLM for scoring, analysis, and email generation |
| TokenRouter | Unified LLM routing with caching |
| Zeabur | Live cloud deployment |
| Butterbase | Backend API and data persistence |

## Quick Start

```bash
# Clone and install
cd leadforge
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run locally
python main.py
# Visit http://localhost:8000
```

## Deploy to Zeabur

Push to GitHub, then connect to Zeabur for one-click deployment.

## API Endpoints

- `GET /` — Dashboard
- `POST /api/pipeline/start` — Start a new pipeline run
- `GET /api/pipeline/{run_id}/status` — Check pipeline status
- `GET /api/pipeline/{run_id}/results` — Get results
- `GET /api/pipeline/runs` — List all runs
- `GET /health` — Health check

## Built for Agent Forge AI Hackathon 2025
