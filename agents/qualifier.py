"""
Qualifier Agent — Scores and ranks leads based on ICP fit.
Uses Qwen via TokenRouter for intelligent scoring.
"""

import os
import json
from typing import Optional
from pydantic import BaseModel
from openai import AsyncOpenAI

from .scout import ICPCriteria
from .researcher import CompanyResearch


class LeadScore(BaseModel):
    """Scored and qualified lead."""
    name: str
    website: str = ""
    score: float = 0.0  # 0-100
    grade: str = "C"  # A, B, C, D
    fit_reasons: list[str] = []
    concerns: list[str] = []
    priority: str = "low"  # high, medium, low
    recommended_approach: str = ""
    research: Optional[CompanyResearch] = None


class QualifierAgent:
    """
    Qualifier Agent: Scores leads against ICP using LLM reasoning.

    Workflow:
    1. Takes CompanyResearch + ICP criteria
    2. Sends structured prompt to Qwen via TokenRouter
    3. LLM evaluates fit across multiple dimensions
    4. Returns scored LeadScore with reasoning
    """

    def __init__(self):
        api_key = os.getenv("TOKENROUTER_API_KEY", "")
        base_url = os.getenv("TOKENROUTER_BASE_URL", "https://api.tokenrouter.com/v1")
        model = os.getenv("QWEN_MODEL", "qwen-plus")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model

    async def _score_with_llm(self, research: CompanyResearch, icp: ICPCriteria) -> dict:
        """Use Qwen via TokenRouter to score a lead."""

        system_prompt = """You are an expert B2B sales analyst. Your job is to evaluate whether a company
is a good fit for a product/service based on the Ideal Customer Profile (ICP).

Score the company from 0-100 based on:
- Industry fit (25 points)
- Company size fit (20 points)
- Technology alignment (20 points)
- Buying signals (hiring, funding, growth) (20 points)
- Accessibility (can we reach decision makers) (15 points)

Respond ONLY with valid JSON in this exact format:
{
    "score": <number 0-100>,
    "grade": "<A|B|C|D>",
    "fit_reasons": ["reason1", "reason2", "reason3"],
    "concerns": ["concern1", "concern2"],
    "priority": "<high|medium|low>",
    "recommended_approach": "one sentence on best outreach strategy"
}"""

        user_prompt = f"""## Ideal Customer Profile (ICP)
- Industry: {icp.industry}
- Company size: {icp.company_size}
- Funding stage: {icp.funding_stage}
- Location: {icp.location}
- Tech stack preference: {', '.join(icp.tech_stack)}
- Keywords: {', '.join(icp.keywords)}
- Description: {icp.raw_description}

## Company to Evaluate
- Name: {research.name}
- Website: {research.website}
- Description: {research.description}
- Industry: {research.industry}
- Size: {research.size}
- Location: {research.location}
- Funding: {research.funding}
- Tech stack: {', '.join(research.tech_stack)}
- Recent news: {'; '.join(research.recent_news[:3])}
- Hiring signals: {'; '.join(research.hiring_signals[:3])}

Evaluate this company against the ICP and provide your scoring."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON from response (handle markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return json.loads(content)

        except Exception as e:
            print(f"[Qualifier] LLM scoring error for {research.name}: {e}")
            return {
                "score": 50,
                "grade": "C",
                "fit_reasons": ["Unable to fully evaluate"],
                "concerns": ["Scoring error — manual review needed"],
                "priority": "low",
                "recommended_approach": "Manual review recommended",
            }

    async def qualify(self, research: CompanyResearch, icp: ICPCriteria) -> LeadScore:
        """
        Main entry: Score a single researched lead against ICP.
        """
        print(f"[Qualifier] Scoring: {research.name}")

        scoring = await self._score_with_llm(research, icp)

        lead_score = LeadScore(
            name=research.name,
            website=research.website,
            score=scoring.get("score", 50),
            grade=scoring.get("grade", "C"),
            fit_reasons=scoring.get("fit_reasons", []),
            concerns=scoring.get("concerns", []),
            priority=scoring.get("priority", "low"),
            recommended_approach=scoring.get("recommended_approach", ""),
            research=research,
        )

        print(f"[Qualifier] {research.name}: Score={lead_score.score}, Grade={lead_score.grade}")
        return lead_score

    async def qualify_batch(self, researched: list[CompanyResearch], icp: ICPCriteria) -> list[LeadScore]:
        """Score multiple leads and return sorted by score (highest first)."""
        scores = []
        for r in researched:
            score = await self.qualify(r, icp)
            scores.append(score)

        scores.sort(key=lambda x: x.score, reverse=True)
        return scores
