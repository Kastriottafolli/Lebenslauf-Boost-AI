"""HTTP boundaries, configurable origins and bounded abuse protection.
Rate limits are per process; deploy one worker or add shared edge limits.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from backend.config import get_settings

_buckets = defaultdict(deque)
_lock = threading.Lock()
MAX_REQUEST_BYTES = 12 * 1024 * 1024


class BodyLimitMiddleware:
    """Bound streamed bodies before JSON/multipart parsing, even without Content-Length."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > MAX_REQUEST_BYTES:
                    raise HTTPException(status_code=413, detail="Request too large")
            return message

        return await self.app(scope, limited_receive, send)


def install_security(app):
    settings = get_settings()
    origins = {o.strip() for o in settings.allowed_origins.split(",")}
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts.split(","))
    app.add_middleware(BodyLimitMiddleware)

    @app.middleware("http")
    async def boundaries(request, call_next):
        origin = request.headers.get("origin")
        if request.url.path.startswith("/api/") and request.method not in (
            "GET",
            "HEAD",
            "OPTIONS",
        ):
            if origin and origin not in origins and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site" and not origin:
                return JSONResponse({"detail": "Cross-site request denied"}, status_code=403)
            try:
                if int(request.headers.get("content-length", "0")) > MAX_REQUEST_BYTES:
                    return JSONResponse({"detail": "Request too large"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid content length"}, status_code=400)
            category = (
                "auth"
                if "/account/" in request.url.path
                else "ai"
                if request.url.path
                in (
                    "/api/generate",
                    "/api/refine",
                    "/api/package",
                    "/api/package/refine",
                    "/api/provider/test",
                )
                else "other"
            )
            limit = 10 if category == "auth" else 12 if category == "ai" else 60
            # Do not trust user-controlled forwarding headers.
            key = (request.client.host if request.client else "unknown", category)
            now = time.monotonic()
            with _lock:
                for old in list(_buckets):
                    if not _buckets[old] or _buckets[old][-1] < now - 60:
                        del _buckets[old]
                bucket = _buckets[key]
                while bucket and bucket[0] < now - 60:
                    bucket.popleft()
                if len(bucket) >= limit:
                    return JSONResponse(
                        {"detail": "Zu viele Anfragen / too many requests. Try again in a minute."},
                        status_code=429,
                        headers={"Retry-After": "60"},
                    )
                bucket.append(now)
            if settings.allow_server_keys and category == "ai":
                from backend.database import SessionLocal
                from backend.services.account_service import current_account

                with SessionLocal() as db:
                    if not current_account(db, request):
                        return JSONResponse(
                            {"detail": "Server-KI benötigt Anmeldung / server AI requires sign-in"},
                            status_code=401,
                        )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' https://api.openai.com https://api.anthropic.com https://api.x.ai https://generativelanguage.googleapis.com; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response
