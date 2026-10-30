"""Thin wrapper over the official Notion REST API (https://developers.notion.com).

We call the API directly with httpx so every request is visible and easy to debug.
The API version is pinned so Notion changes cannot silently break the integration.
"""
import logging
from enum import Enum
from typing import Optional

import httpx

from .followup import FollowUp
from .models import LeadIn, notion_label
from .scoring import ScoreResult

log = logging.getLogger("lead_agent.notion")

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
TEXT_LIMIT = 2000  # Notion's max length for a single rich-text block
DEFAULT_STATUS = "New"


class NotionError(Exception):
    """Raised when Notion rejects a request; carries Notion's own error message."""


def _text(value: Optional[str]) -> dict:
    if not value:
        return {"rich_text": []}
    return {"rich_text": [{"text": {"content": value[:TEXT_LIMIT]}}]}


def _select(value) -> dict:
    if not value:
        return {"select": None}
    name = notion_label(value) if isinstance(value, Enum) else value
    return {"select": {"name": name}}


def build_properties(lead: LeadIn, score: ScoreResult, follow_up: FollowUp) -> dict:
    """Map a validated lead to Notion page properties. Status is set separately."""
    return {
        "Name": {"title": [{"text": {"content": lead.full_name}}]},
        "Score": _select(score.score),
        "Score reason": _text(score.reason),
        "Phone": {"phone_number": lead.best_phone},
        "Email": {"email": lead.email},
        "Company": _text(lead.company),
        "Business type": _select(lead.business_type),
        "Property type": _select(lead.property_type),
        "Operation": _select(lead.operation),
        "Space (m²)": {"number": lead.space_m2},
        "Zone": _text(lead.zone),
        "Budget min (MXN)": {"number": lead.budget_min_mxn},
        "Budget max (MXN)": {"number": lead.budget_max_mxn},
        "Timeframe": _select(lead.timeframe),
        "Decision role": _select(lead.decision_role),
        "Notes": _text(lead.notes),
        "Follow-up by": {"date": {"start": follow_up.deadline.isoformat()}},
        "Source": _select(lead.source),
        "Conversation ID": _text(lead.conversation_id),
    }


class NotionClient:
    def __init__(self, api_key: str, database_id: str, http: Optional[httpx.AsyncClient] = None):
        self.database_id = database_id
        self.http = http or httpx.AsyncClient(
            base_url=NOTION_API,
            timeout=10.0,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self.http.aclose()

    async def _request(self, method: str, path: str, json: dict) -> dict:
        try:
            response = await self.http.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise NotionError(f"Could not reach Notion: {exc}") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("message", response.text)
            except ValueError:
                detail = response.text
            raise NotionError(f"Notion API {response.status_code}: {detail}")
        return response.json()

    async def find_by_conversation(self, conversation_id: str) -> Optional[str]:
        data = await self._request(
            "POST",
            f"/databases/{self.database_id}/query",
            {
                "filter": {"property": "Conversation ID", "rich_text": {"equals": conversation_id}},
                "page_size": 1,
            },
        )
        results = data.get("results", [])
        return results[0]["id"] if results else None

    async def upsert_lead(self, lead: LeadIn, score: ScoreResult, follow_up: FollowUp) -> tuple:
        """Create the lead page, or update it if this conversation was already saved.

        Returns (page_id, "created" | "updated"). On update, Status is left untouched
        so a re-sent lead never resets the pipeline stage you already set by hand.
        """
        properties = build_properties(lead, score, follow_up)

        existing = None
        if lead.conversation_id:
            existing = await self.find_by_conversation(lead.conversation_id)

        if existing:
            await self._request("PATCH", f"/pages/{existing}", {"properties": properties})
            log.info("Updated Notion page %s for conversation %s", existing, lead.conversation_id)
            return existing, "updated"

        properties["Status"] = {"select": {"name": DEFAULT_STATUS}}
        page = await self._request(
            "POST",
            "/pages",
            {"parent": {"database_id": self.database_id}, "properties": properties},
        )
        log.info("Created Notion page %s", page["id"])
        return page["id"], "created"
