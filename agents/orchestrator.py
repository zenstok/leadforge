"""
LeadForge Orchestrator — Coordinates the agent swarm.
Manages the full pipeline: Scout → Research → Qualify → Outreach.
"""

import asyncio
from typing import Optional
from pydantic import BaseModel

from .scout import ScoutAgent, ICPCriteria, CompanyLead
from .researcher import ResearchAgent, CompanyResearch
from .qualifier import QualifierAgent, LeadScore
from .outreach import OutreachAgent, OutreachSequence
from memory.evermind import EvermindMemory


class PipelineConfig(BaseModel):
    """Configuration for a LeadForge pipeline run."""
    icp: ICPCriteria
    product_description: str
    max_leads: int = 10
    min_score: float = 30.0
    emails_per_lead: int = 3


class PipelineStatus(BaseModel):
    """Current status of a pipeline run."""
    status: str = "idle"  # idle, scouting, researching, qualifying, generating_outreach, complete, error
    progress: float = 0.0
    message: str = ""
    leads_found: int = 0
    leads_researched: int = 0
    leads_qualified: int = 0
    outreach_generated: int = 0


class PipelineResult(BaseModel):
    """Final result of a pipeline run."""
    config: PipelineConfig
    leads: list[CompanyLead] = []
    research: list[CompanyResearch] = []
    scores: list[LeadScore] = []
    outreach: list[OutreachSequence] = []
    status: PipelineStatus = PipelineStatus()


class LeadForgeOrchestrator:
    """
    Orchestrator: Coordinates the full LeadForge agent pipeline.

    Flow:
    1. Scout Agent discovers companies from ICP
    2. Research Agent enriches each lead
    3. Qualifier Agent scores and ranks leads
    4. Outreach Agent generates personalized emails
    5. All data persisted to Evermind memory
    """

    def __init__(self):
        self.scout = ScoutAgent()
        self.researcher = ResearchAgent()
        self.qualifier = QualifierAgent()
        self.outreach = OutreachAgent()
        self.memory = EvermindMemory()
        self._current_status = PipelineStatus()
        self._current_result: Optional[PipelineResult] = None

    @property
    def status(self) -> PipelineStatus:
        return self._current_status

    @property
    def result(self) -> Optional[PipelineResult]:
        return self._current_result

    def _update_status(self, status: str, progress: float, message: str, **kwargs):
        self._current_status.status = status
        self._current_status.progress = progress
        self._current_status.message = message
        for k, v in kwargs.items():
            if hasattr(self._current_status, k):
                setattr(self._current_status, k, v)

    async def run_pipeline(self, config: PipelineConfig) -> PipelineResult:
        """
        Execute the full LeadForge pipeline.

        This is the main entry point for running the agent swarm.
        """
        result = PipelineResult(config=config)
        self._current_result = result

        try:
            # Store ICP in memory
            await self.memory.store_icp(config.icp.model_dump())

            # === Phase 1: Scout ===
            self._update_status("scouting", 0.1, "Discovering companies matching your ICP...")
            leads = await self.scout.discover(config.icp)
            leads = leads[:config.max_leads]
            result.leads = leads
            self._update_status("scouting", 0.25, f"Found {len(leads)} potential leads",
                              leads_found=len(leads))

            if not leads:
                self._update_status("complete", 1.0, "No leads found. Try broadening your ICP criteria.")
                result.status = self._current_status
                return result

            # === Phase 2: Research ===
            self._update_status("researching", 0.3, f"Researching {len(leads)} companies...")
            researched = []
            for i, lead in enumerate(leads):
                progress = 0.3 + (0.25 * (i + 1) / len(leads))
                self._update_status(
                    "researching", progress,
                    f"Researching {lead.name} ({i+1}/{len(leads)})",
                    leads_researched=i + 1,
                )
                research = await self.researcher.research(lead)
                researched.append(research)

                # Store in memory
                await self.memory.store_lead(research.model_dump())

            result.research = researched

            # === Phase 3: Qualify ===
            self._update_status("qualifying", 0.6, f"Scoring {len(researched)} leads...")
            scores = await self.qualifier.qualify_batch(researched, config.icp)

            # Filter by minimum score
            qualified = [s for s in scores if s.score >= config.min_score]
            result.scores = scores  # Keep all scores for visibility
            self._update_status(
                "qualifying", 0.75,
                f"Qualified {len(qualified)} leads (min score: {config.min_score})",
                leads_qualified=len(qualified),
            )

            # === Phase 4: Outreach ===
            if qualified:
                self._update_status("generating_outreach", 0.8,
                                  f"Generating outreach for {len(qualified)} leads...")
                sequences = []
                for i, lead in enumerate(qualified):
                    progress = 0.8 + (0.18 * (i + 1) / len(qualified))
                    self._update_status(
                        "generating_outreach", progress,
                        f"Writing emails for {lead.name} ({i+1}/{len(qualified)})",
                        outreach_generated=i + 1,
                    )
                    seq = await self.outreach.generate_sequence(
                        lead=lead,
                        product_description=config.product_description,
                        num_emails=config.emails_per_lead,
                    )
                    sequences.append(seq)

                    # Store in memory
                    await self.memory.store_outreach(lead.name, seq.model_dump())

                result.outreach = sequences

            # === Complete ===
            self._update_status(
                "complete", 1.0,
                f"Pipeline complete! {len(leads)} leads → {len(qualified)} qualified → {len(result.outreach)} with outreach",
                leads_found=len(leads),
                leads_researched=len(researched),
                leads_qualified=len(qualified),
                outreach_generated=len(result.outreach),
            )

        except Exception as e:
            self._update_status("error", self._current_status.progress,
                              f"Pipeline error: {str(e)}")
            print(f"[Orchestrator] Pipeline error: {e}")
            import traceback
            traceback.print_exc()

        result.status = self._current_status
        return result

    async def close(self):
        """Clean up all agent resources."""
        await self.scout.close()
        await self.researcher.close()
        await self.memory.close()
