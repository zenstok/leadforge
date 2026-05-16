"""
Research Agent — Deep-dives on each company lead.
Uses Bright Data for web scraping and Actionbook for browser automation.
"""

import os
import json
import httpx
from typing import Optional
from pydantic import BaseModel

from .scout import CompanyLead


class CompanyResearch(BaseModel):
    """Enriched company data from research."""
    name: str
    website: str = ""
    description: str = ""
    industry: str = ""
    size: str = ""
    location: str = ""
    funding: str = ""
    tech_stack: list[str] = []
    recent_news: list[str] = []
    hiring_signals: list[str] = []
    key_people: list[str] = []
    pain_points: list[str] = []
    source_url: str = ""
    raw_content: str = ""


class ResearchAgent:
    """
    Research Agent: Enriches company leads with detailed intelligence.

    Workflow:
    1. Takes a CompanyLead from the Scout Agent
    2. Scrapes the company website using Bright Data
    3. Uses Actionbook for structured browser navigation
    4. Extracts key data points: funding, tech stack, hiring, news
    5. Returns enriched CompanyResearch objects
    """

    def __init__(self):
        self.brightdata_token = os.getenv("BRIGHTDATA_API_TOKEN", "")
        self.actionbook_key = os.getenv("ACTIONBOOK_API_KEY", "")
        self.http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.http_client is None or self.http_client.is_closed:
            self.http_client = httpx.AsyncClient(timeout=60.0)
        return self.http_client

    async def _scrape_website(self, url: str) -> str:
        """Scrape a company website using Bright Data."""
        client = await self._get_client()

        try:
            response = await client.post(
                "https://api.brightdata.com/request",
                headers={
                    "Authorization": f"Bearer {self.brightdata_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "zone": "web_unlocker",
                    "url": url,
                    "format": "raw",
                },
            )

            if response.status_code == 200:
                return response.text[:8000]
        except Exception as e:
            print(f"[Research] Scrape error for {url}: {e}")

        return ""

    async def _scrape_with_actionbook(self, url: str, action: str = "extract_company_info") -> dict:
        """Use Actionbook to navigate and extract structured data."""
        client = await self._get_client()

        try:
            # Actionbook API — get action manual for a website
            response = await client.post(
                "https://api.actionbook.dev/v1/actions/execute",
                headers={
                    "Authorization": f"Bearer {self.actionbook_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "action": action,
                    "extract_fields": [
                        "company_name", "description", "team_size",
                        "location", "tech_stack", "pricing",
                        "about_us", "careers_page",
                    ],
                },
            )

            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"[Research] Actionbook error for {url}: {e}")

        return {}

    async def _search_company_news(self, company_name: str) -> list[str]:
        """Search for recent news about a company using Bright Data SERP."""
        client = await self._get_client()

        try:
            response = await client.post(
                "https://api.brightdata.com/request",
                headers={
                    "Authorization": f"Bearer {self.brightdata_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "zone": "serp",
                    "url": f"https://www.google.com/search?q={company_name}+news+funding+announcement&tbs=qdr:m3&num=5",
                    "format": "json",
                },
            )

            if response.status_code == 200:
                data = response.json()
                organic = data.get("organic", []) if isinstance(data, dict) else []
                return [r.get("title", "") for r in organic[:5] if r.get("title")]
        except Exception as e:
            print(f"[Research] News search error: {e}")

        return []

    async def _search_hiring_signals(self, company_name: str) -> list[str]:
        """Search for hiring signals using Bright Data."""
        client = await self._get_client()

        try:
            response = await client.post(
                "https://api.brightdata.com/request",
                headers={
                    "Authorization": f"Bearer {self.brightdata_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "zone": "serp",
                    "url": f"https://www.google.com/search?q={company_name}+hiring+jobs+careers&num=5",
                    "format": "json",
                },
            )

            if response.status_code == 200:
                data = response.json()
                organic = data.get("organic", []) if isinstance(data, dict) else []
                return [r.get("title", "") for r in organic[:5] if r.get("title")]
        except Exception as e:
            print(f"[Research] Hiring search error: {e}")

        return []

    def _extract_info_from_html(self, html: str) -> dict:
        """Extract structured info from raw HTML content."""
        info = {
            "tech_stack": [],
            "description": "",
            "key_signals": [],
        }

        # Simple keyword extraction for tech stack
        tech_keywords = [
            "react", "vue", "angular", "python", "node.js", "typescript",
            "aws", "gcp", "azure", "kubernetes", "docker", "postgresql",
            "mongodb", "redis", "graphql", "rust", "go", "java",
            "terraform", "datadog", "snowflake", "stripe", "twilio",
        ]

        html_lower = html.lower()
        for tech in tech_keywords:
            if tech in html_lower:
                info["tech_stack"].append(tech)

        # Extract meta description if present
        import re
        meta_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html, re.I)
        if meta_match:
            info["description"] = meta_match.group(1)

        return info

    async def research(self, lead: CompanyLead) -> CompanyResearch:
        """
        Main entry: Research a single company lead in depth.

        Combines multiple data sources for a comprehensive profile.
        """
        print(f"[Research] Researching: {lead.name} ({lead.website})")

        # 1. Scrape website
        website_content = ""
        extracted_info = {}
        if lead.website:
            website_content = await self._scrape_website(lead.website)
            extracted_info = self._extract_info_from_html(website_content)

        # 2. Try Actionbook for structured extraction
        actionbook_data = {}
        if lead.website:
            actionbook_data = await self._scrape_with_actionbook(lead.website)

        # 3. Search for news
        news = await self._search_company_news(lead.name)

        # 4. Search for hiring signals
        hiring = await self._search_hiring_signals(lead.name)

        # Merge all data
        research = CompanyResearch(
            name=lead.name,
            website=lead.website,
            description=(
                actionbook_data.get("description")
                or extracted_info.get("description")
                or lead.description
            ),
            industry=actionbook_data.get("industry", lead.industry),
            size=actionbook_data.get("team_size", lead.size),
            location=actionbook_data.get("location", lead.location),
            funding=lead.funding,
            tech_stack=extracted_info.get("tech_stack", []),
            recent_news=news,
            hiring_signals=hiring,
            key_people=actionbook_data.get("key_people", []),
            pain_points=[],
            source_url=lead.source_url,
            raw_content=website_content[:2000],
        )

        print(f"[Research] Completed research for {lead.name}: "
              f"{len(research.tech_stack)} techs, {len(research.recent_news)} news items")

        return research

    async def research_batch(self, leads: list[CompanyLead]) -> list[CompanyResearch]:
        """Research multiple leads (sequential to respect rate limits)."""
        results = []
        for lead in leads:
            result = await self.research(lead)
            results.append(result)
        return results

    async def close(self):
        if self.http_client and not self.http_client.is_closed:
            await self.http_client.aclose()
