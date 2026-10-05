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
        path = request.url.path
        if (
            settings.hosted_ai_enabled
            and path.startswith("/api/")
            and not path.startswith("/api/admin/")
        ):
            public = {
                "/api/session",
                "/api/status",
                "/api/public-config",
                "/api/hosted-config",
                "/api/account",
                "/api/account/register",
                "/api/account/login",
                "/api/account/recover",
                "/api/assistant/config",
                "/api/oauth/providers",
                "/api/usage",
                "/api/billing/pricing",
            }
            # Only these exact callback endpoints bypass user login. They reject
            # disabled payments and authenticate the provider signature themselves.
            payment_webhook = (
                path in {"/api/billing/webhooks/stripe", "/api/billing/webhooks/paypal"}
                and request.method == "POST"
            )
            allowed_public = path in public and not (
                path == "/api/account" and request.method == "DELETE"
            )
            if not allowed_public and not payment_webhook and not path.startswith("/api/oauth/"):
                from backend.database import SessionLocal
                from backend.services.account_service import current_account

                with SessionLocal() as db:
                    if not current_account(db, request):
                        return JSONResponse(
                            {"detail": "Bitte zuerst anmelden / sign in first"}, status_code=401
                        )
            if path in {"/api/generate", "/api/refine", "/api/provider/test"}:
                return JSONResponse(
                    {"detail": "Diese alte Anbieter-Funktion ist deaktiviert"}, status_code=410
                )
        origin = request.headers.get("origin")
        is_admin = request.url.path.startswith("/api/admin/")
        if (
            is_admin
            and request.method != "OPTIONS"
            and request.headers.get("X-Boosty-Request") != "1"
        ):
            return JSONResponse({"detail": "Admin request header required"}, status_code=403)
        admin_origins = {str(request.base_url).rstrip("/")} | (
            origins & {"capacitor://localhost", "http://localhost", "https://localhost"}
        )
        if is_admin and origin and origin not in admin_origins:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        if (
            request.url.path.startswith("/api/")
            and not (path == "/api/oauth/apple/callback" and request.method == "POST")
            and request.method
            not in (
                "GET",
                "HEAD",
                "OPTIONS",
            )
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
                if "/account/" in request.url.path or is_admin
                else "ai"
                if request.url.path
                in (
                    "/api/generate",
                    "/api/refine",
                    "/api/package",
                    "/api/package/refine",
                    "/api/provider/test",
                    "/api/assistant",
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
        from backend.database import SessionLocal
        from backend.services.account_service import current_account
        from backend.services.activity_service import EVENTS, record

        path = request.url.path
        event = EVENTS.get((request.method, path))
        if path.startswith("/api/projects/"):
            event = {
                "GET": "project.open",
                "PUT": "project.update",
                "DELETE": "project.delete",
            }.get(request.method)
        account_id = None
        if event and event != "account.delete":
            with SessionLocal() as db:
                account = current_account(db, request)
                account_id = account.id if account else None
        response = await call_next(request)
        if event or (request.method == "GET" and path in ("/", "/index.html")):
            import asyncio

            await asyncio.to_thread(
                record,
                event,
                response.status_code,
                getattr(request.state, "metric_account", account_id),
                request.method == "GET" and path in ("/", "/index.html"),
                event == "session.start" and response.status_code < 400,
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
        if request.url.path.startswith("/api/") or path.rstrip("/") == "/admin":
            response.headers["Cache-Control"] = "no-store"
        if path.rstrip("/") == "/admin" or is_admin:
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        if settings.secure_cookies:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' https://api.openai.com https://api.anthropic.com https://api.x.ai https://generativelanguage.googleapis.com; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response
