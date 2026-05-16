"""
Scout Agent — Finds companies matching an Ideal Customer Profile (ICP).
Uses Bright Data Python SDK for SERP searches, then scrapes listicle pages
to extract actual company names and websites.
"""

import os
import sys
import json
import re
import traceback
from typing import Optional
from pydantic import BaseModel


class ICPCriteria(BaseModel):
    """Ideal Customer Profile definition."""
    industry: str = ""
    company_size: str = ""
    funding_stage: str = ""
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
    Scout Agent: Discovers companies matching an ICP using Bright Data SDK.

    Two-phase approach:
    1. SERP search to find listicle/directory pages
    2. Scrape those pages and extract actual company names + URLs
    """

    def __init__(self):
        self.brightdata_token = os.getenv("BRIGHTDATA_API_TOKEN", "")

        print(f"[Scout] ========== INIT ==========", flush=True)
        print(f"[Scout] BRIGHTDATA_API_TOKEN set: {bool(self.brightdata_token)}", flush=True)
        if self.brightdata_token:
            print(f"[Scout] Token prefix: {self.brightdata_token[:12]}...", flush=True)

        try:
            import brightdata
            print(f"[Scout] brightdata-sdk version: {brightdata.__version__}", flush=True)
        except ImportError:
            print(f"[Scout] ERROR: brightdata-sdk NOT INSTALLED", flush=True)

    def _build_search_queries(self, icp: ICPCriteria) -> list[str]:
        """Build search queries targeting directory/listing pages with actual company names."""
        queries = []

        # Use site: operators to target directories that list actual companies
        base_terms = []
        if icp.industry:
            base_terms.append(icp.industry)
        if icp.location:
            base_terms.append(icp.location)
        if icp.raw_description:
            # Extract key terms from the description
            base_terms.append(icp.raw_description)

        base = " ".join(base_terms).strip() or "B2B SaaS"

        # Target Crunchbase — returns actual company pages
        queries.append(f"site:crunchbase.com {base} startup")

        # Target Y Combinator directory
        queries.append(f"site:ycombinator.com {icp.industry or 'SaaS'} company")

        # Target general startup lists with company names in results
        if icp.funding_stage:
            queries.append(f"{base} {icp.funding_stage} funded startups 2025 2026")
        else:
            queries.append(f"{base} startups funded 2025 2026")

        # Target LinkedIn company pages
        queries.append(f"site:linkedin.com/company {icp.industry or 'SaaS'} {icp.location or ''} startup".strip())

        return queries[:4]

    async def _search_serp(self, query: str) -> list[dict]:
        """Use Bright Data SDK for Google SERP search."""
        print(f"\n[Scout] SERP: '{query}'", flush=True)

        try:
            from brightdata import BrightDataClient

            async with BrightDataClient() as client:
                result = await client.search.google(query=query, num_results=10)

                if hasattr(result, 'data') and result.data:
                    data = result.data
                    if isinstance(data, list):
                        print(f"[Scout] SERP got {len(data)} results", flush=True)
                        return data
                    elif isinstance(data, dict):
                        organic = data.get("organic", data.get("results", []))
                        print(f"[Scout] SERP got {len(organic)} organic results", flush=True)
                        return organic if isinstance(organic, list) else []
                return []

        except Exception as e:
            print(f"[Scout] SERP error: {type(e).__name__}: {e}", flush=True)
            return []

    async def _scrape_page(self, url: str) -> str:
        """Scrape a page using Bright Data SDK to extract company info."""
        try:
            from brightdata import BrightDataClient

            async with BrightDataClient() as client:
                result = await client.scrape_url(url)
                if hasattr(result, 'data'):
                    return str(result.data)[:15000]
                return str(result)[:15000]
        except Exception as e:
            print(f"[Scout] Scrape error for {url}: {e}", flush=True)
            return ""

    def _extract_companies_from_serp(self, results: list[dict]) -> list[CompanyLead]:
        """Extract company leads directly from SERP results.
        Handles Crunchbase, LinkedIn, and direct company pages."""
        leads = []

        for result in results:
            title = result.get("title", "") or result.get("name", "") or ""
            url = result.get("url", "") or result.get("link", "") or ""
            description = result.get("description", "") or result.get("snippet", "") or ""

            if not title or not url:
                continue

            url_lower = url.lower()

            # Skip pure article/blog sites
            skip_domains = [
                "wikipedia.org", "youtube.com", "reddit.com", "quora.com",
                "facebook.com", "twitter.com", "x.com", "instagram.com",
                "medium.com", "google.com", "pinterest.com",
            ]
            if any(d in url_lower for d in skip_domains):
                continue

            # Crunchbase company pages → extract company name
            if "crunchbase.com/organization/" in url_lower:
                # URL like: crunchbase.com/organization/company-name
                slug = url.split("/organization/")[-1].split("/")[0].split("?")[0]
                name = slug.replace("-", " ").title()
                leads.append(CompanyLead(
                    name=name,
                    website=url,
                    description=description[:500],
                    source_url=url,
                ))
                continue

            # LinkedIn company pages → extract company name
            if "linkedin.com/company/" in url_lower:
                slug = url.split("/company/")[-1].split("/")[0].split("?")[0]
                name = slug.replace("-", " ").title()
                leads.append(CompanyLead(
                    name=name,
                    website=url,
                    description=description[:500],
                    source_url=url,
                ))
                continue

            # Direct company websites (not listicle articles)
            # Filter out known listicle/blog domains
            listicle_domains = [
                "builtin.com", "getlatka.com", "tracxn.com", "seedtable.com",
                "founderconnects.com", "mikesonders.com", "ensun.io",
                "ventureradar.com", "dealroom.co", "hicronsoftware.com",
                "themindstudios.com", "ascendixtech.com", "landbase.com",
                "g2.com/categories", "capterra.com/directory",
                "theresanaiforthat.com", "toptal.com", "clutch.co",
            ]
            if any(d in url_lower for d in listicle_domains):
                # These are listicle pages — skip as direct leads
                # but we could scrape them later for company extraction
                continue

            # Looks like a direct company website
            name = title.split(" - ")[0].split(" | ")[0].split(" — ")[0].strip()
            if len(name) > 80:
                name = name[:80]

            # Skip if name looks like an article title (contains numbers like "Top 50...")
            if re.match(r'^(top\s+)?\d+\s+', name, re.I):
                continue

            leads.append(CompanyLead(
                name=name,
                website=url,
                description=description[:500],
                source_url=url,
            ))

        return leads

    def _extract_companies_from_html(self, html: str, source_url: str) -> list[CompanyLead]:
        """Extract company names and URLs from a scraped listicle/directory page."""
        leads = []

        # Extract all links with text that look like company names
        # Pattern: <a href="https://company.com">Company Name</a>
        link_pattern = re.compile(
            r'<a[^>]+href=["\']?(https?://[^"\'>\s]+)["\']?[^>]*>([^<]{2,60})</a>',
            re.I
        )

        seen_domains = set()
        for match in link_pattern.finditer(html):
            url = match.group(1).strip()
            text = match.group(2).strip()

            # Skip internal/nav links
            url_lower = url.lower()
            skip = [
                "javascript:", "#", "mailto:", "tel:",
                "facebook.com", "twitter.com", "linkedin.com",
                "instagram.com", "youtube.com", "google.com",
                "github.com", "apple.com/app", "play.google.com",
                ".css", ".js", ".png", ".jpg", ".svg",
            ]
            if any(s in url_lower for s in skip):
                continue

            # Skip if text looks like navigation
            nav_words = [
                "read more", "learn more", "click here", "sign up",
                "log in", "subscribe", "download", "view all",
                "home", "about", "contact", "privacy", "terms",
                "cookie", "menu", "close", "share", "tweet",
            ]
            if text.lower().strip() in nav_words or len(text) < 3:
                continue

            # Skip if the same domain as source page
            try:
                source_domain = source_url.split("//")[-1].split("/")[0].lower()
                link_domain = url.split("//")[-1].split("/")[0].lower()
                if link_domain == source_domain:
                    continue
                if link_domain in seen_domains:
                    continue
                seen_domains.add(link_domain)
            except Exception:
                continue

            # Clean company name
            name = text.split(" - ")[0].split(" | ")[0].strip()
            if re.match(r'^\d+[\.\)]?\s*', name):
                name = re.sub(r'^\d+[\.\)]?\s*', '', name)

            if len(name) < 2 or len(name) > 60:
                continue

            leads.append(CompanyLead(
                name=name,
                website=url,
                description="",
                source_url=source_url,
            ))

        return leads[:10]  # Cap per source page

    async def discover(self, icp: ICPCriteria) -> list[CompanyLead]:
        """Main entry: Discover companies matching the ICP."""
        print(f"\n[Scout] ========== DISCOVERY START ==========", flush=True)
        print(f"[Scout] ICP: {icp.raw_description or icp.industry}", flush=True)

        queries = self._build_search_queries(icp)
        print(f"[Scout] Queries: {queries}", flush=True)

        all_leads: list[CompanyLead] = []
        seen_domains: set[str] = set()

        for i, query in enumerate(queries):
            print(f"\n[Scout] --- Query {i+1}/{len(queries)} ---", flush=True)

            results = await self._search_serp(query)

            # Phase 1: Extract companies directly from SERP results
            direct_leads = self._extract_companies_from_serp(results)
            print(f"[Scout] Direct company leads: {len(direct_leads)}", flush=True)

            for lead in direct_leads:
                domain = lead.website.split("//")[-1].split("/")[0].lower()
                if domain not in seen_domains:
                    seen_domains.add(domain)
                    all_leads.append(lead)

            # Phase 2: If we have listicle URLs, scrape one to extract companies
            if len(all_leads) < 10:
                for result in results[:2]:  # Only scrape top 2 listicle pages
                    url = result.get("url", "") or result.get("link", "")
                    if not url:
                        continue
                    # Only scrape pages that look like company lists
                    title = (result.get("title", "") or "").lower()
                    if any(kw in title for kw in ["top", "best", "list", "companies", "startups"]):
                        print(f"[Scout] Scraping listicle: {url[:80]}", flush=True)
                        html = await self._scrape_page(url)
                        if html:
                            extracted = self._extract_companies_from_html(html, url)
                            print(f"[Scout] Extracted {len(extracted)} companies from page", flush=True)
                            for lead in extracted:
                                domain = lead.website.split("//")[-1].split("/")[0].lower()
                                if domain not in seen_domains:
                                    seen_domains.add(domain)
                                    all_leads.append(lead)
                        if len(all_leads) >= 15:
                            break

        print(f"\n[Scout] ========== DISCOVERY DONE ==========", flush=True)
        print(f"[Scout] Total unique leads: {len(all_leads)}", flush=True)
        for lead in all_leads[:10]:
            print(f"[Scout]   - {lead.name}: {lead.website}", flush=True)

        return all_leads[:20]

    async def close(self):
        pass
