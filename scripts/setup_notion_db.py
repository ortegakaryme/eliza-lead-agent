"""Create the "Leads" database in Notion with the exact schema the backend expects.

Usage:
    python scripts/setup_notion_db.py <PARENT_PAGE_ID>

Before running:
  1. Create an internal integration at https://www.notion.so/my-integrations
     and put its secret in NOTION_API_KEY (in .env).
  2. Create (or pick) a Notion page that will hold the database, open "..." >
     "Connections" and add your integration so it can write there.
  3. Copy that page's ID: the 32-character hex string at the end of its URL.

The script prints the new database ID; put it in NOTION_DATABASE_ID.
"""
import os
import re
import sys

import httpx
from dotenv import load_dotenv

NOTION_VERSION = "2022-06-28"


def select(*options):
    colors = ["blue", "green", "yellow", "orange", "red", "purple", "pink", "brown", "gray"]
    return {"select": {"options": [{"name": n, "color": colors[i % len(colors)]} for i, n in enumerate(options)]}}


SCHEMA = {
    "Name": {"title": {}},
    "Status": select("New", "Contacted", "Visit scheduled", "Proposal sent", "Won", "Lost"),
    "Score": {"select": {"options": [
        {"name": "Hot", "color": "red"},
        {"name": "Warm", "color": "orange"},
        {"name": "Cold", "color": "blue"},
    ]}},
    "Score reason": {"rich_text": {}},
    "Phone": {"phone_number": {}},
    "Email": {"email": {}},
    "Company": {"rich_text": {}},
    "Business type": select("Restaurant", "Clinic", "Retail store", "Office", "Industrial/Logistics", "Other"),
    "Property type": select("Retail unit", "Office", "Warehouse", "Land"),
    "Operation": select("Lease", "Purchase"),
    "Space (m²)": {"number": {"format": "number_with_commas"}},
    "Zone": {"rich_text": {}},
    "Budget min (MXN)": {"number": {"format": "mexican_peso"}},
    "Budget max (MXN)": {"number": {"format": "mexican_peso"}},
    "Timeframe": select("Immediate (<1 mo)", "1–3 months", "3–6 months", "6+ months", "Undefined"),
    "Decision role": select("Decision maker", "Influencer", "Researching for someone else"),
    "Notes": {"rich_text": {}},
    "Follow-up by": {"date": {}},
    "Source": select("Voice agent – phone", "Voice agent – web"),
    "Conversation ID": {"rich_text": {}},
    "Created": {"created_time": {}},
}


def main() -> None:
    load_dotenv()
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        sys.exit("NOTION_API_KEY is not set. Add it to .env first.")

    # Accept a raw ID, a dashed UUID or a full page URL; keep the 32 hex characters.
    # The ID is always the last 32 hex characters of the path (titles can contain hex letters).
    runs = re.findall(r"[0-9a-f]{32,}", sys.argv[1].split("?")[0].replace("-", ""))
    if not runs:
        sys.exit("Could not find a 32-character page ID in the argument.")
    parent_page_id = runs[-1][-32:]

    response = httpx.post(
        "https://api.notion.com/v1/databases",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        json={
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": "Leads"}}],
            "is_inline": False,
            "properties": SCHEMA,
        },
        timeout=20,
    )
    if response.status_code >= 400:
        sys.exit(f"Notion returned {response.status_code}: {response.json().get('message', response.text)}")

    db = response.json()
    print("Database created:", db.get("url"))
    print(f"\nAdd this line to your .env and to Render:\nNOTION_DATABASE_ID={db['id']}")


if __name__ == "__main__":
    main()
