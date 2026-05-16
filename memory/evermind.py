"""
Evermind Memory Integration — Persistent long-term memory for LeadForge agents.
Stores lead research, outreach patterns, and scoring history.
"""

import os
import json
import httpx
from typing import Optional
from datetime import datetime, timezone


class EvermindMemory:
    """
    Evermind integration for persistent agent memory.

    Stores:
    - Lead research data (so we don't re-scrape)
    - Scoring history (learn what makes good leads)
    - Outreach patterns (what email styles work)
    - ICP evolution (refine ICP over time)
    """

    def __init__(self):
        self.api_url = os.getenv("EVERMIND_API_URL", "http://localhost:1995/api/v1")
        self.api_key = os.getenv("EVERMIND_API_KEY", "")
        self.http_client: Optional[httpx.AsyncClient] = None
        # In-memory fallback when Evermind is unavailable
        self._local_store: dict[str, dict] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self.http_client is None or self.http_client.is_closed:
            self.http_client = httpx.AsyncClient(timeout=30.0)
        return self.http_client

    async def store(self, category: str, key: str, data: dict, user_id: str = "leadforge") -> bool:
        """Store a memory in Evermind."""
        client = await self._get_client()

        memory_content = json.dumps({
            "category": category,
            "key": key,
            "data": data,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        })

        try:
            response = await client.post(
                f"{self.api_url}/memories",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "message_id": f"{category}_{key}_{datetime.now(timezone.utc).timestamp()}",
                    "create_time": datetime.now(timezone.utc).isoformat(),
                    "sender": user_id,
                    "content": memory_content,
                },
            )

            if response.status_code in (200, 201):
                print(f"[Evermind] Stored: {category}/{key}")
                return True
        except Exception as e:
            print(f"[Evermind] Store error (falling back to local): {e}")

        # Fallback to local store
        store_key = f"{category}:{key}"
        self._local_store[store_key] = {
            "data": data,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        return True

    async def recall(self, query: str, user_id: str = "leadforge", category: str = "") -> list[dict]:
        """Search memories in Evermind."""
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.api_url}/memories/search",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                params={
                    "query": query,
                    "user_id": user_id,
                    "retrieve_method": "hybrid",
                },
            )

            if response.status_code == 200:
                result = response.json().get("result", {})
                memories = result.get("memories", [])
                print(f"[Evermind] Recalled {len(memories)} memories for: {query}")
                return memories
        except Exception as e:
            print(f"[Evermind] Recall error (searching local): {e}")

        # Fallback: search local store
        results = []
        query_lower = query.lower()
        for store_key, value in self._local_store.items():
            if category and not store_key.startswith(category):
                continue
            data_str = json.dumps(value.get("data", {})).lower()
            if query_lower in data_str or any(word in data_str for word in query_lower.split()):
                results.append(value["data"])

        return results

    async def store_lead(self, lead_data: dict) -> bool:
        """Store a researched lead."""
        return await self.store(
            category="leads",
            key=lead_data.get("name", "unknown").lower().replace(" ", "_"),
            data=lead_data,
        )

    async def store_outreach(self, lead_name: str, sequence_data: dict) -> bool:
        """Store an outreach sequence."""
        return await self.store(
            category="outreach",
            key=lead_name.lower().replace(" ", "_"),
            data=sequence_data,
        )

    async def store_icp(self, icp_data: dict) -> bool:
        """Store an ICP for future reference."""
        return await self.store(
            category="icp",
            key=f"icp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            data=icp_data,
        )

    async def recall_similar_leads(self, company_name: str) -> list[dict]:
        """Recall similar leads from memory."""
        return await self.recall(
            query=f"company similar to {company_name}",
            category="leads",
        )

    async def recall_successful_outreach(self, industry: str) -> list[dict]:
        """Recall successful outreach patterns for an industry."""
        return await self.recall(
            query=f"successful outreach {industry}",
            category="outreach",
        )

    async def close(self):
        if self.http_client and not self.http_client.is_closed:
            await self.http_client.aclose()
