"""
LeadForge — AI Sales Intelligence Agent Swarm
Main FastAPI application serving the API and dashboard.
"""

import os
import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from agents.orchestrator import LeadForgeOrchestrator, PipelineConfig, PipelineResult, PipelineStatus
from agents.scout import ICPCriteria


# === State ===
orchestrator: LeadForgeOrchestrator | None = None
pipeline_runs: dict[str, PipelineResult] = {}
pipeline_tasks: dict[str, asyncio.Task] = {}
pipeline_orchestrators: dict[str, LeadForgeOrchestrator] = {}
pipeline_statuses: dict[str, PipelineStatus] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator
    orchestrator = LeadForgeOrchestrator()
    print("[LeadForge] Agent swarm initialized")
    yield
    if orchestrator:
        await orchestrator.close()
    print("[LeadForge] Shutdown complete")


app = FastAPI(
    title="LeadForge",
    description="AI Sales Intelligence Agent Swarm — Discover, research, qualify, and engage leads automatically.",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# === Request/Response Models ===

class PipelineRequest(BaseModel):
    """Request to start a new pipeline run."""
    industry: str = ""
    company_size: str = ""
    funding_stage: str = ""
    location: str = ""
    tech_stack: list[str] = []
    keywords: list[str] = []
    icp_description: str = ""
    product_description: str = "Our AI-powered solution helps companies automate their workflows and increase productivity."
    max_leads: int = 10
    min_score: float = 30.0


class PipelineResponse(BaseModel):
    """Response with pipeline run ID."""
    run_id: str
    status: str
    message: str


# === API Endpoints ===

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the main dashboard."""
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "leadforge", "agents": 4}


@app.post("/api/pipeline/start", response_model=PipelineResponse)
async def start_pipeline(request: PipelineRequest):
    """Start a new LeadForge pipeline run."""
    global orchestrator

    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")

    run_id = str(uuid.uuid4())[:8]

    config = PipelineConfig(
        icp=ICPCriteria(
            industry=request.industry,
            company_size=request.company_size,
            funding_stage=request.funding_stage,
            location=request.location,
            tech_stack=request.tech_stack,
            keywords=request.keywords,
            raw_description=request.icp_description,
        ),
        product_description=request.product_description,
        max_leads=request.max_leads,
        min_score=request.min_score,
    )

    # Each run gets its own orchestrator to avoid shared state
    run_orchestrator = LeadForgeOrchestrator()

    # Run pipeline in background
    async def _run():
        result = await run_orchestrator.run_pipeline(config)
        pipeline_runs[run_id] = result
        # Store status for polling
        pipeline_statuses[run_id] = run_orchestrator.status

    task = asyncio.create_task(_run())
    pipeline_tasks[run_id] = task
    pipeline_orchestrators[run_id] = run_orchestrator

    return PipelineResponse(
        run_id=run_id,
        status="started",
        message="Pipeline started. Poll /api/pipeline/{run_id}/status for updates.",
    )


@app.get("/api/pipeline/{run_id}/status")
async def get_pipeline_status(run_id: str):
    """Get the current status of a pipeline run."""
    # Check completed runs first
    if run_id in pipeline_runs:
        return pipeline_runs[run_id].status.model_dump()

    # Check running orchestrators
    if run_id in pipeline_orchestrators:
        return pipeline_orchestrators[run_id].status.model_dump()

    return PipelineStatus(status="unknown", message="Run not found").model_dump()


@app.get("/api/pipeline/{run_id}/results")
async def get_pipeline_results(run_id: str):
    """Get the full results of a completed pipeline run."""
    if run_id not in pipeline_runs:
        # Check if still running
        if run_id in pipeline_tasks and not pipeline_tasks[run_id].done():
            raise HTTPException(status_code=202, detail="Pipeline still running")
        raise HTTPException(status_code=404, detail="Run not found")

    result = pipeline_runs[run_id]

    # Serialize results
    return {
        "status": result.status.model_dump(),
        "leads": [l.model_dump() for l in result.leads],
        "scores": [
            {
                "name": s.name,
                "website": s.website,
                "score": s.score,
                "grade": s.grade,
                "fit_reasons": s.fit_reasons,
                "concerns": s.concerns,
                "priority": s.priority,
                "recommended_approach": s.recommended_approach,
                "research": s.research.model_dump() if s.research else None,
            }
            for s in result.scores
        ],
        "outreach": [
            {
                "lead_name": seq.lead_name,
                "lead_score": seq.lead_score,
                "emails": [e.model_dump() for e in seq.emails],
            }
            for seq in result.outreach
        ],
    }


@app.get("/api/pipeline/runs")
async def list_runs():
    """List all pipeline runs."""
    runs = []
    for run_id, result in pipeline_runs.items():
        runs.append({
            "run_id": run_id,
            "status": result.status.status,
            "leads_found": result.status.leads_found,
            "leads_qualified": result.status.leads_qualified,
        })

    # Include running tasks
    for run_id, task in pipeline_tasks.items():
        if run_id not in pipeline_runs and not task.done():
            runs.append({
                "run_id": run_id,
                "status": "running",
                "leads_found": 0,
                "leads_qualified": 0,
            })

    return {"runs": runs}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
