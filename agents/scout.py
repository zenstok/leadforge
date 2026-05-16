"""
Scout Agent — Finds companies matching an Ideal Customer Profile (ICP).
Uses Bright Data for web scraping and search.
"""

import os
import json
import httpx
from typing import Optional
from pydantic import BaseModel


class ICPCriteria(BaseModel):
    """Ideal Customer Profile definition."""
    industry: str = ""
    company_size: str = ""  # e.g., "20-100 employees"
    funding_stage: str = ""  # e.g., "Series A", "Seed"
    location: str = ""
    tech_stack: list[str] = []
    keywords: list[str] = []
    raw_description: str = ""


class CompanyLead(BaseModel):
    """A discovered company lead."""
    name: str
    website: str = ""
    description: str = ""
    industry: str = ""
    size: str = ""
    location: str = ""
    funding: str = ""
    source_url: str = ""


class ScoutAgent:
    """
    Scout Agent: Discovers companies matching an ICP using Bright Data.

    Workflow:
    1. Takes ICP criteria as input
    2. Builds search queries from the ICP
    3. Uses Bright Data SERP API to find matching companies
    4. Extracts and structures company info from results
    5. Returns a list of CompanyLead objects
    """

    def __init__(self):
        self.brightdata_token = os.getenv("BRIGHTDATA_API_TOKEN", "")
        self.http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.http_client is None or self.http_client.is_closed:
            self.http_client = httpx.AsyncClient(timeout=60.0)
        return self.http_client

    def _build_search_queries(self, icp: ICPCriteria) -> list[str]:
        """Build targeted search queries from ICP criteria."""
        queries = []

        # Primary query from raw description
        if icp.raw_description:
            queries.append(icp.raw_description + " companies list")

        # Structured queries
        parts = []
        if icp.industry:
            parts.append(icp.industry)
        if icp.funding_stage:
            parts.append(icp.funding_stage)
        if icp.company_size:
            parts.append(icp.company_size)
        if icp.location:
            parts.append(icp.location)

        if parts:
            queries.append(" ".join(parts) + " startups companies")

        # Keyword-based queries
        for kw in icp.keywords[:3]:
            queries.append(f"{kw} {icp.industry} companies {icp.location}".strip())

        # Tech stack queries
        if icp.tech_stack:
            tech_str = " ".join(icp.tech_stack[:3])
            queries.append(f"companies using {tech_str} {icp.industry}".strip())

        return queries[:5]  # Cap at 5 queries

    async def _search_brightdata(self, query: str) -> list[dict]:
        """Use Bright Data SERP API to search for companies."""
        client = await self._get_client()

        try:
            # Bright Data Web Scraper API — SERP collection
            response = await client.post(
                "https://api.brightdata.com/datasets/v3/trigger",
                headers={
                    "Authorization": f"Bearer {self.brightdata_token}",
                    "Content-Type": "application/json",
                },
                json=[{
                    "keyword": query,
                    "search_engine": "google",
                    "num_results": 10,
                }],
                params={"dataset_id": "gd_se708sdt1684345hjkg", "format": "json"},
            )

            if response.status_code == 200:
                return response.json() if isinstance(response.json(), list) else []
        except Exception as e:
            print(f"[Scout] Bright Data search error: {e}")

        return []

    async def _search_google_serp(self, query: str) -> list[dict]:
        """Fallback: Use Bright Data's Google SERP scraping."""
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
                    "url": f"https://www.google.com/search?q={query}&num=10",
                    "format": "json",
                },
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("organic", []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"[Scout] SERP fallback error: {e}")

        return []

    async def _scrape_url(self, url: str) -> str:
        """Scrape a URL using Bright Data for company info."""
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
                return response.text[:5000]  # Cap response size
        except Exception as e:
            print(f"[Scout] Scrape error for {url}: {e}")

        return ""

    def _parse_search_results(self, results: list[dict]) -> list[CompanyLead]:
        """Parse search results into CompanyLead objects."""
        leads = []

        for result in results:
            title = result.get("title", "") or result.get("name", "")
            url = result.get("url", "") or result.get("link", "")
            description = result.get("description", "") or result.get("snippet", "")

            if not title or not url:
                continue

            # Skip non-company results
            skip_domains = ["wikipedia.org", "youtube.com", "reddit.com", "quora.com"]
            if any(d in url for d in skip_domains):
                continue

            leads.append(CompanyLead(
                name=title.split(" - ")[0].split(" | ")[0].strip(),
                website=url,
                description=description,
                source_url=url,
            ))

        return leads

    async def discover(self, icp: ICPCriteria) -> list[CompanyLead]:
        """
        Main entry: Discover companies matching the ICP.

        Returns a deduplicated list of CompanyLead objects.
        """
        print(f"[Scout] Starting discovery for ICP: {icp.raw_description or icp.industry}")

        queries = self._build_search_queries(icp)
        print(f"[Scout] Generated {len(queries)} search queries")

        all_leads: list[CompanyLead] = []
        seen_domains: set[str] = set()

        for query in queries:
            print(f"[Scout] Searching: {query}")
            results = await self._search_brightdata(query)

            if not results:
                results = await self._search_google_serp(query)

            parsed = self._parse_search_results(results)

            for lead in parsed:
                domain = lead.website.split("//")[-1].split("/")[0].lower()
                if domain not in seen_domains:
                    seen_domains.add(domain)
                    all_leads.append(lead)

        print(f"[Scout] Discovered {len(all_leads)} unique leads")
        return all_leads[:20]  # Cap at 20 leads

    async def close(self):
        if self.http_client and not self.http_client.is_closed:
            await self.http_client.aclose()
