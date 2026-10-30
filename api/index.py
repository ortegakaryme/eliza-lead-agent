"""Vercel entry point: Vercel runs Python files in api/ as serverless functions and
serves the ASGI `app` they expose.

vercel.json rewrites every request to this function, and a rewrite hands the app
/api/index as the path. The rewrite therefore carries the original path in the
`__path` query parameter, and RestoreOriginalPath puts it back before routing, so
/health and /leads reach their FastAPI routes.

If the app cannot even be imported (for example a missing dependency), serve a
minimal app that names the error instead of Vercel's opaque FUNCTION_INVOCATION_FAILED.
"""
from urllib.parse import parse_qsl, urlencode


class RestoreOriginalPath:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            params = parse_qsl(scope.get("query_string", b"").decode(), keep_blank_values=True)
            original = [value for key, value in params if key == "__path"]
            if original:
                path = "/" + original[0].lstrip("/")
                rest = urlencode([(k, v) for k, v in params if k != "__path"])
                scope = dict(scope, path=path, raw_path=path.encode(), query_string=rest.encode())
        await self.app(scope, receive, send)


try:
    from app.main import app
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

# Added as middleware so `app` stays a FastAPI instance, which Vercel recognizes as ASGI.
app.add_middleware(RestoreOriginalPath)
