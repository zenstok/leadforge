"""
Research Agent — Deep-dives on each company lead.
Uses Bright Data Python SDK for web scraping and SERP searches.
"""

import os
import re
import json
import traceback
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
    Research Agent: Enriches company leads with detailed intelligence
    using Bright Data SDK for scraping and SERP.
    """

    def __init__(self):
        self.brightdata_token = os.getenv("BRIGHTDATA_API_TOKEN", "")

    async def _scrape_website(self, url: str) -> str:
        """Scrape a company website using Bright Data SDK."""
        print(f"[Research] BD scrape_url: {url}", flush=True)
        try:
            from brightdata import BrightDataClient

            async with BrightDataClient() as client:
                result = await client.scrape_url(url)
                print(f"[Research] BD scrape result type: {type(result).__name__}", flush=True)
                if hasattr(result, 'error') and result.error:
                    print(f"[Research] BD scrape ERROR: {result.error}", flush=True)
                if hasattr(result, 'data'):
                    data_str = str(result.data)[:8000]
                    print(f"[Research] BD scrape got {len(data_str)} chars", flush=True)
                    return data_str
                return str(result)[:8000]
        except Exception as e:
            print(f"[Research] BD scrape EXCEPTION: {type(e).__name__}: {e}", flush=True)
            import traceback; traceback.print_exc()
            return ""

    async def _search_serp(self, query: str) -> list[str]:
        """Search via Bright Data SDK SERP and return titles."""
        print(f"[Research] BD SERP: '{query}'", flush=True)
        try:
            from brightdata import BrightDataClient

            async with BrightDataClient() as client:
                result = await client.search.google(query=query, num_results=5)

                print(f"[Research] BD SERP result type: {type(result).__name__}", flush=True)
                if hasattr(result, 'error') and result.error:
                    print(f"[Research] BD SERP ERROR: {result.error}", flush=True)

                titles = []
                if hasattr(result, 'data'):
                    data = result.data
                    print(f"[Research] BD SERP data type: {type(data).__name__}, is None: {data is None}", flush=True)
                    if data is None:
                        return []
                    items = data if isinstance(data, list) else data.get("organic", [])
                    for item in items[:5]:
                        title = item.get("title", "") if isinstance(item, dict) else ""
                        if title:
                            titles.append(title)
                    print(f"[Research] BD SERP got {len(titles)} titles", flush=True)
                return titles
        except Exception as e:
            print(f"[Research] BD SERP EXCEPTION: {type(e).__name__}: {e}", flush=True)
            import traceback; traceback.print_exc()
            return []

    async def _search_company_news(self, company_name: str) -> list[str]:
        """Search for recent news about a company."""
        return await self._search_serp(f"{company_name} news funding announcement 2024 2025")

    async def _search_hiring_signals(self, company_name: str) -> list[str]:
        """Search for hiring signals."""
        return await self._search_serp(f"{company_name} hiring jobs careers engineering")

    def _extract_info_from_html(self, html: str) -> dict:
        """Extract structured info from raw HTML content."""
        info = {"tech_stack": [], "description": ""}

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

        meta_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html, re.I)
        if meta_match:
            info["description"] = meta_match.group(1)

        if not info["description"]:
            og_match = re.search(r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"', html, re.I)
            if og_match:
                info["description"] = og_match.group(1)

        return info

    async def research(self, lead: CompanyLead) -> CompanyResearch:
        """Research a single company lead in depth."""
        print(f"[Research] Researching: {lead.name} ({lead.website})")

        # 1. Scrape main website
        website_content = ""
        extracted_info = {}
        if lead.website:
            website_content = await self._scrape_website(lead.website)
            if website_content:
                extracted_info = self._extract_info_from_html(website_content)

        # 2. Search for recent news
        news = await self._search_company_news(lead.name)

        # 3. Search for hiring signals
        hiring = await self._search_hiring_signals(lead.name)

        research = CompanyResearch(
            name=lead.name,
            website=lead.website,
            description=extracted_info.get("description") or lead.description,
            industry=lead.industry,
            size=lead.size,
            location=lead.location,
            funding=lead.funding,
            tech_stack=extracted_info.get("tech_stack", []),
            recent_news=news,
            hiring_signals=hiring,
            source_url=lead.source_url,
            raw_content=website_content[:2000],
        )

        print(f"[Research] Done: {lead.name} — "
              f"{len(research.tech_stack)} techs, {len(research.recent_news)} news")

        return research

    async def research_batch(self, leads: list[CompanyLead]) -> list[CompanyResearch]:
        """Research multiple leads."""
        results = []
        for lead in leads:
            result = await self.research(lead)
            results.append(result)
        return results

    async def close(self):
        pass
