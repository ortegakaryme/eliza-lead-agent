"""FastAPI webhook that the ElevenLabs agent calls (server tool `save_lead`).

Request flow for POST /leads:
  1. Auth      -> X-Webhook-Secret header must match WEBHOOK_SECRET (constant-time compare)
  2. Validate  -> Pydantic LeadIn model (FastAPI returns 422 with details on failure)
  3. Score     -> deterministic Hot / Warm / Cold rule in scoring.py
  4. Follow-up -> business-hours commitment in followup.py
  5. Persist   -> create or update the page in Notion
  6. Respond   -> the agent reads `follow_up_message` to the lead
"""
import hmac
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError

from .config import get_settings
from .followup import compute_follow_up
from .models import LeadIn, LeadOut
from .notion import NotionClient, NotionError
from .scoring import score_lead

# A missing or invalid environment variable must not crash the process silently:
# on serverless hosts that only shows up as an opaque 500. Instead the app starts,
# /health names the broken variables (never their values) and /leads returns 503.
try:
    settings = get_settings()
    CONFIG_PROBLEMS = []
except ValidationError as exc:
    settings = None
    CONFIG_PROBLEMS = [f"{str(e['loc'][0]).upper()}: {e['msg']}" for e in exc.errors()]

logging.basicConfig(
    level=settings.log_level.upper() if settings else "INFO",
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
log = logging.getLogger("lead_agent")
if CONFIG_PROBLEMS:
    log.error("Invalid configuration: %s", CONFIG_PROBLEMS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Lead agent backend started")
    yield
    notion = getattr(app.state, "notion", None)
    if notion:
        await notion.close()


def get_notion(app: FastAPI) -> NotionClient:
    # Created on first use rather than at startup: serverless hosts such as Vercel
    # do not always run the lifespan hook. The client is then reused while the
    # instance stays warm, which keeps tool calls fast.
    if getattr(app.state, "notion", None) is None:
        app.state.notion = NotionClient(settings.notion_api_key, settings.notion_database_id)
    return app.state.notion


app = FastAPI(title="Commercial Real Estate Lead Agent", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = uuid.uuid4().hex[:8]
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    log.info(
        "[%s] %s %s -> %s (%.0f ms)",
        request_id, request.method, request.url.path, response.status_code, elapsed_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Turn Pydantic's error list into short, readable messages for logs and the agent.
    problems = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"] if p != "body") or "payload"
        problems.append(f"{field}: {err['msg']}")
    log.warning("[%s] Invalid lead payload: %s", getattr(request.state, "request_id", "-"), problems)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "invalid_payload", "details": problems},
    )


def require_config() -> None:
    if CONFIG_PROBLEMS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server is misconfigured; see /health for the variables to fix.",
        )


def verify_secret(x_webhook_secret: Optional[str] = Header(default=None)) -> None:
    # compare_digest takes the same time whether the first or last character differs,
    # so an attacker cannot guess the secret by measuring response times.
    if not x_webhook_secret or not hmac.compare_digest(
        x_webhook_secret.encode(), settings.webhook_secret.encode()
    ):
        log.warning("Rejected request with missing or invalid X-Webhook-Secret")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


DEMO_PAGE = (Path(__file__).parent / "demo_page.html").read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def demo_page():
    """Public demo page with the ElevenLabs widget, so visitors can talk to Eliza."""
    return DEMO_PAGE


@app.get("/health")
async def health():
    """Liveness check for the host and uptime monitors; reports configuration problems."""
    if CONFIG_PROBLEMS:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "misconfigured", "problems": CONFIG_PROBLEMS},
        )
    return {"status": "ok"}


@app.post("/leads", response_model=LeadOut, dependencies=[Depends(require_config), Depends(verify_secret)])
async def create_lead(lead: LeadIn, request: Request) -> LeadOut:
    request_id = request.state.request_id
    score = score_lead(lead)
    follow_up = compute_follow_up(settings.timezone)
    log.info(
        "[%s] Lead '%s' scored %s (%s), conversation=%s",
        request_id, lead.full_name, score.score, score.reason, lead.conversation_id,
    )

    try:
        page_id, outcome = await get_notion(request.app).upsert_lead(lead, score, follow_up)
    except NotionError as exc:
        # Log the full payload so the lead can be recovered by hand from the logs.
        log.error("[%s] %s | lead payload: %s", request_id, exc, lead.model_dump_json())
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The lead could not be saved to Notion. It was logged for manual recovery.",
        )

    return LeadOut(
        status=outcome,
        score=score.score,
        follow_up_message=follow_up.message,
        notion_page_id=page_id,
    )
