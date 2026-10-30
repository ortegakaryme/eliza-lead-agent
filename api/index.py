"""Vercel entry point: Vercel runs Python files in api/ as serverless functions and
serves the ASGI `app` they expose. vercel.json routes every path here.

If the app cannot even be imported (for example a missing dependency), serve a
minimal app that names the error instead of Vercel's opaque FUNCTION_INVOCATION_FAILED.
"""
try:
    from app.main import app  # noqa: F401
except Exception as exc:  # pragma: no cover - only hit on a broken deploy
    import traceback

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    traceback.print_exc()  # full details in Vercel's runtime logs
    # Import errors are safe to show; other messages could echo configuration values.
    _detail = str(exc) if isinstance(exc, ImportError) else ""
    _error = {"status": "import_failed", "error": type(exc).__name__, "detail": _detail}

    app = FastAPI()

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def _broken(path: str):
        return JSONResponse(status_code=503, content=_error)
