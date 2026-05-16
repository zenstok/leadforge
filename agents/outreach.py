"""
Outreach Agent — Generates personalized sales emails.
Uses Qwen via TokenRouter for copywriting.
"""

import os
import json
from typing import Optional
from pydantic import BaseModel
from openai import AsyncOpenAI

from .qualifier import LeadScore


class OutreachEmail(BaseModel):
    """Generated personalized outreach email."""
    lead_name: str
    subject: str
    body: str
    personalization_hooks: list[str] = []
    call_to_action: str = ""
    tone: str = "professional"


class OutreachSequence(BaseModel):
    """Multi-touch email sequence for a lead."""
    lead_name: str
    lead_score: float
    emails: list[OutreachEmail] = []


class OutreachAgent:
    """
    Outreach Agent: Creates personalized email sequences.

    Workflow:
    1. Takes scored leads from the Qualifier Agent
    2. Analyzes research data for personalization angles
    3. Generates multi-touch email sequences via Qwen/TokenRouter
    4. Returns ready-to-send OutreachSequence objects
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

    async def _generate_email(
        self,
        lead: LeadScore,
        product_description: str,
        email_number: int = 1,
        total_emails: int = 3,
    ) -> dict:
        """Generate a single personalized email using Qwen."""

        research = lead.research
        research_context = ""
        if research:
            research_context = f"""
Company details:
- Description: {research.description}
- Tech stack: {', '.join(research.tech_stack)}
- Recent news: {'; '.join(research.recent_news[:3])}
- Hiring signals: {'; '.join(research.hiring_signals[:3])}
- Key people: {', '.join(research.key_people[:3])}"""

        tone_map = {
            1: "warm introduction — establish relevance, mention something specific about their company",
            2: "value-driven follow-up — share a specific insight or case study relevant to their industry",
            3: "gentle close — create urgency with a specific offer or limited-time value",
        }

        system_prompt = """You are an elite B2B sales copywriter. You write emails that get opened and replied to.

Rules:
- Keep subject lines under 50 characters, curiosity-driven
- Keep emails under 150 words
- Always personalize based on the company's specific situation
- Use conversational tone, not corporate speak
- Include exactly ONE clear call-to-action
- Never use "I hope this email finds you well" or similar clichés
- Reference specific details about their company

Respond ONLY with valid JSON:
{
    "subject": "email subject line",
    "body": "email body text",
    "personalization_hooks": ["what makes this email specific to them"],
    "call_to_action": "the specific CTA"
}"""

        user_prompt = f"""Write email #{email_number} of {total_emails} in a sales sequence.

Tone for this email: {tone_map.get(email_number, tone_map[1])}

## Our Product
{product_description}

## Target Lead
- Company: {lead.name}
- Website: {lead.website}
- Score: {lead.score}/100 (Grade: {lead.grade})
- Why they're a fit: {'; '.join(lead.fit_reasons)}
- Recommended approach: {lead.recommended_approach}
{research_context}

Write a compelling, personalized email."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=600,
            )

            content = response.choices[0].message.content.strip()

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return json.loads(content)

        except Exception as e:
            print(f"[Outreach] Email generation error for {lead.name}: {e}")
            return {
                "subject": f"Quick question about {lead.name}",
                "body": f"Hi,\n\nI noticed {lead.name} and thought our solution might be relevant.\n\nWould you be open to a quick chat?\n\nBest",
                "personalization_hooks": [],
                "call_to_action": "Book a call",
            }

    async def generate_sequence(
        self,
        lead: LeadScore,
        product_description: str,
        num_emails: int = 3,
    ) -> OutreachSequence:
        """
        Main entry: Generate a full email sequence for a scored lead.
        """
        print(f"[Outreach] Generating {num_emails}-email sequence for {lead.name}")

        # Only generate sequences for decent leads
        actual_emails = num_emails
        if lead.score < 40:
            actual_emails = 1  # Just one email for low-scoring leads
        elif lead.score < 70:
            actual_emails = 2

        emails = []
        for i in range(1, actual_emails + 1):
            email_data = await self._generate_email(
                lead=lead,
                product_description=product_description,
                email_number=i,
                total_emails=actual_emails,
            )

            emails.append(OutreachEmail(
                lead_name=lead.name,
                subject=email_data.get("subject", ""),
                body=email_data.get("body", ""),
                personalization_hooks=email_data.get("personalization_hooks", []),
                call_to_action=email_data.get("call_to_action", ""),
            ))

        sequence = OutreachSequence(
            lead_name=lead.name,
            lead_score=lead.score,
            emails=emails,
        )

        print(f"[Outreach] Generated {len(emails)} emails for {lead.name}")
        return sequence

    async def generate_batch(
        self,
        leads: list[LeadScore],
        product_description: str,
    ) -> list[OutreachSequence]:
        """Generate sequences for multiple scored leads."""
        sequences = []
        for lead in leads:
            seq = await self.generate_sequence(lead, product_description)
            sequences.append(seq)
        return sequences
