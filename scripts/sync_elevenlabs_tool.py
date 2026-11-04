"""Sync the ElevenLabs `save_lead` tool with agent/save_lead_tool.json.

The JSON file is the source of truth for the tool's URL, description and body
parameters. Configuring 16 parameters by hand in the dashboard is error-prone, so
this script pushes the file to ElevenLabs through the API instead.

Usage:
    python scripts/sync_elevenlabs_tool.py           # dry run: compare, change nothing
    python scripts/sync_elevenlabs_tool.py --apply   # update the tool in ElevenLabs

Needs ELEVENLABS_API_KEY in .env (an API key with Agents write access only).
The X-Webhook-Secret header keeps the secret already configured in ElevenLabs,
so the secret value never passes through this script.
"""
import copy
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

API = "https://api.elevenlabs.io/v1/convai"
TOOL_FILE = Path(__file__).resolve().parent.parent / "agent" / "save_lead_tool.json"
SECRET_HEADER = "X-Webhook-Secret"


def fail(message: str) -> None:
    sys.exit(f"ERROR: {message}")


def check(response: httpx.Response, action: str) -> dict:
    if response.status_code >= 400:
        fail(f"{action} failed with HTTP {response.status_code}: {response.text[:500]}")
    return response.json()


def body_properties(tool_config: dict) -> dict:
    schema = (tool_config.get("api_schema") or {}).get("request_body_schema") or {}
    return schema.get("properties") or {}


def main() -> None:
    load_dotenv()
    apply = "--apply" in sys.argv
    api_key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    if not api_key:
        fail("ELEVENLABS_API_KEY is empty in .env")

    desired = json.loads(TOOL_FILE.read_text(encoding="utf-8"))
    client = httpx.Client(base_url=API, headers={"xi-api-key": api_key}, timeout=30)

    tools = check(client.get("/tools"), "Listing tools").get("tools", [])
    matches = [t for t in tools if (t.get("tool_config") or {}).get("name") == desired["name"]]
    if not matches:
        names = [(t.get("tool_config") or {}).get("name") for t in tools]
        fail(f"No workspace tool named '{desired['name']}'. Tools found: {names}")
    if len(matches) > 1:
        fail(f"Found {len(matches)} tools named '{desired['name']}'; delete the extras first.")
    tool = matches[0]
    current = tool["tool_config"]

    # Keep the secret header exactly as configured in ElevenLabs.
    current_headers = (current.get("api_schema") or {}).get("request_headers") or {}
    secret = current_headers.get(SECRET_HEADER)
    if not secret:
        fail(f"The tool has no '{SECRET_HEADER}' header. Add it in the dashboard (value: your secret) and rerun.")

    new_config = copy.deepcopy(desired)
    new_config["api_schema"]["request_headers"] = {SECRET_HEADER: secret}

    have, want = set(body_properties(current)), set(body_properties(new_config))
    print(f"Tool: {current.get('name')} (id {tool['id']})")
    print(f"URL now: {(current.get('api_schema') or {}).get('url')}")
    print(f"URL in file: {new_config['api_schema']['url']}")
    print(f"Body parameters now ({len(have)}): {sorted(have)}")
    print(f"Missing, will be added ({len(want - have)}): {sorted(want - have)}")
    print(f"Extra, will be removed ({len(have - want)}): {sorted(have - want)}")
    print(f"Secret header kept: {'secret_id' in secret if isinstance(secret, dict) else 'plain value'}")

    if not apply:
        print("\nDry run only. Rerun with --apply to update the tool.")
        return

    updated = check(client.patch(f"/tools/{tool['id']}", json={"tool_config": new_config}), "Updating tool")
    final = body_properties(updated.get("tool_config", {}))
    print(f"\nUpdated. The tool now has {len(final)} body parameters: {sorted(final)}")


if __name__ == "__main__":
    main()
