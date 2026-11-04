"""Sync Eliza's system prompt and first message with the files in agent/.

agent/system_prompt.es.md and agent/first_message.es.txt are the source of truth.
This pushes them to the ElevenLabs agent through the API and leaves every other
setting (voice, LLM, tools, limits) untouched.

Usage:
    python scripts/sync_elevenlabs_agent.py           # dry run: compare, change nothing
    python scripts/sync_elevenlabs_agent.py --apply   # update the agent in ElevenLabs

Needs ELEVENLABS_API_KEY in .env (Agents write access) and the agent ID below.
"""
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

API = "https://api.elevenlabs.io/v1/convai"
AGENT_ID = "agent_6701m65p3x45fb59cqr5hwnr5ns5"
AGENT_DIR = Path(__file__).resolve().parent.parent / "agent"


def fail(message: str) -> None:
    sys.exit(f"ERROR: {message}")


def check(response: httpx.Response, action: str) -> dict:
    if response.status_code >= 400:
        fail(f"{action} failed with HTTP {response.status_code}: {response.text[:500]}")
    return response.json()


def main() -> None:
    load_dotenv()
    apply = "--apply" in sys.argv
    api_key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    if not api_key:
        fail("ELEVENLABS_API_KEY is empty in .env")

    prompt_text = (AGENT_DIR / "system_prompt.es.md").read_text(encoding="utf-8").strip()
    first_message = (AGENT_DIR / "first_message.es.txt").read_text(encoding="utf-8").strip()
    client = httpx.Client(base_url=API, headers={"xi-api-key": api_key}, timeout=30)

    agent = check(client.get(f"/agents/{AGENT_ID}"), "Reading agent")["conversation_config"]["agent"]
    current_prompt = agent["prompt"]
    print(f"Agent: {AGENT_ID}")
    print(f"Prompt changes: {current_prompt.get('prompt', '').strip() != prompt_text} "
          f"({len(current_prompt.get('prompt', ''))} -> {len(prompt_text)} chars)")
    print(f"First message now:  {agent.get('first_message', '').strip()}")
    print(f"First message file: {first_message}")

    if not apply:
        print("\nDry run only. Rerun with --apply to update the agent.")
        return

    # Send the whole prompt object back so tools, LLM and other prompt settings are kept.
    # The API returns tools both expanded (`tools`) and by ID (`tool_ids`) but accepts
    # only one on update, so keep the IDs.
    new_prompt = {key: value for key, value in current_prompt.items() if key != "tools"}
    new_prompt["prompt"] = prompt_text
    body = {"conversation_config": {"agent": {"first_message": first_message, "prompt": new_prompt}}}
    check(client.patch(f"/agents/{AGENT_ID}", json=body), "Updating agent")

    after = check(client.get(f"/agents/{AGENT_ID}"), "Re-reading agent")["conversation_config"]["agent"]
    ok = after["prompt"]["prompt"].strip() == prompt_text and after["first_message"].strip() == first_message
    print(f"\nUpdated: {ok}. Tools still linked: {after['prompt'].get('tool_ids')}")


if __name__ == "__main__":
    main()
