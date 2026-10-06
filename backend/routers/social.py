"""Server-side social login. Disabled until operator credentials and callbacks exist."""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from backend.config import get_settings
from backend.database import get_db
from backend.models import Account, AdminAccess, OAuthState, SocialIdentity
from backend.services import account_service, session_service

router = APIRouter(tags=["Social login"])
PROVIDERS = {
    "google": (
        "Google",
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "openid email",
    ),
    "apple": (
        "Apple",
        "https://appleid.apple.com/auth/authorize",
        "https://appleid.apple.com/auth/token",
        "email",
    ),
    "facebook": (
        "Facebook",
        "https://www.facebook.com/{version}/dialog/oauth",
        "https://graph.facebook.com/{version}/oauth/access_token",
        "email,public_profile",
    ),
    "x": (
        "X",
        "https://x.com/i/oauth2/authorize",
        "https://api.x.com/2/oauth2/token",
        "tweet.read users.read",
    ),
}


def configuration(provider):
    s = get_settings()
    if provider not in PROVIDERS:
        raise HTTPException(404, "Anmeldedienst unbekannt")
    base = s.oauth_base_url.rstrip("/")
    parsed = urlparse(base)
    safe = (
        (
            parsed.scheme == "https"
            or (
                provider != "apple"
                and parsed.scheme == "http"
                and parsed.hostname in {"127.0.0.1", "localhost"}
            )
        )
        and not parsed.query
        and not parsed.fragment
        and not parsed.username
        and not parsed.password
        and parsed.path in {"", "/"}
    )
    cid, secret = (
        getattr(s, f"oauth_{provider}_client_id"),
        getattr(s, f"oauth_{provider}_client_secret"),
    )
    if not safe or not cid or not secret:
        raise HTTPException(
            503, "Dieser Anmeldedienst ist noch nicht eingerichtet. Bitte E-Mail-Anmeldung nutzen."
        )
    if not re.fullmatch(r"v\d+\.\d+", s.oauth_facebook_version):
        raise HTTPException(503, "OAuth-Konfiguration ungültig")
    return base, cid, secret


@router.get("/api/oauth/providers")
def available():
    result = []
    for provider, (name, *_rest) in PROVIDERS.items():
        try:
            configuration(provider)
            enabled = True
        except HTTPException:
            enabled = False
        result.append({"id": provider, "name": name, "enabled": enabled})
    return result


@router.get("/api/oauth/{provider}/start")
def start(provider: str, db=Depends(get_db)):
    base, cid, _secret = configuration(provider)
    state, browser = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    verifier, nonce = secrets.token_urlsafe(64), secrets.token_urlsafe(32)
    now = datetime.now(UTC).replace(tzinfo=None)
    db.query(OAuthState).filter(OAuthState.expires_at < now).delete()
    if db.query(OAuthState).count() >= 500:
        raise HTTPException(429, "Zu viele laufende Anmeldungen. Bitte später versuchen.")
    db.add(
        OAuthState(
            state_hash=session_service.token_hash(state),
            browser_hash=session_service.token_hash(browser),
            provider=provider,
            verifier=verifier,
            nonce=nonce,
            expires_at=now + timedelta(minutes=10),
        )
    )
    db.commit()
    params = {
        "client_id": cid,
        "redirect_uri": base + f"/api/oauth/{provider}/callback",
        "response_type": "code",
        "scope": PROVIDERS[provider][3],
        "state": state,
    }
    if provider in {"google", "apple"}:
        params["nonce"] = nonce
    if provider in {"google", "x"}:
        params.update(
            code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("="),
            code_challenge_method="S256",
        )
    if provider == "apple":
        params["response_mode"] = "form_post"
    url = PROVIDERS[provider][1].format(version=get_settings().oauth_facebook_version)
    response = RedirectResponse(url + "?" + urlencode(params), status_code=303)
    response.set_cookie(
        "tafolli_oauth",
        browser,
        max_age=600,
        httponly=True,
        secure=base.startswith("https:"),
        samesite="none" if provider == "apple" else "lax",
        path="/api/oauth/",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def decode64(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_identity(token, provider, cid, nonce, client):
    if not isinstance(token, str) or len(token) > 20000:
        raise ValueError("invalid token")
    head, payload, signature = token.split(".")
    header, claims = json.loads(decode64(head)), json.loads(decode64(payload))
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise ValueError("algorithm")
    keys_url = (
        "https://www.googleapis.com/oauth2/v3/certs"
        if provider == "google"
        else "https://appleid.apple.com/auth/keys"
    )
    response = client.get(keys_url)
    response.raise_for_status()
    key = next(
        k for k in response.json()["keys"] if k["kid"] == header["kid"] and k.get("kty") == "RSA"
    )
    public = rsa.RSAPublicNumbers(
        int.from_bytes(decode64(key["e"]), "big"), int.from_bytes(decode64(key["n"]), "big")
    ).public_key()
    public.verify(
        decode64(signature), (head + "." + payload).encode(), padding.PKCS1v15(), hashes.SHA256()
    )
    issuers = (
        {"https://accounts.google.com", "accounts.google.com"}
        if provider == "google"
        else {"https://appleid.apple.com"}
    )
    if (
        claims.get("iss") not in issuers
        or claims.get("aud") != cid
        or claims.get("exp", 0) < time.time()
        or claims.get("iat", 0) > time.time() + 60
        or claims.get("nonce") != nonce
    ):
        raise ValueError("claims")
    if claims.get("email_verified") not in {True, "true"}:
        raise ValueError("unverified email")
    return claims["sub"], claims["email"]


def exchange(provider, code, flow):
    base, cid, secret = configuration(provider)
    endpoint = PROVIDERS[provider][2].format(version=get_settings().oauth_facebook_version)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": base + f"/api/oauth/{provider}/callback",
        "client_id": cid,
    }
    if provider in {"google", "x"}:
        data["code_verifier"] = flow.verifier
    if provider != "x":
        data["client_secret"] = secret
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
        response = client.post(endpoint, data=data, auth=(cid, secret) if provider == "x" else None)
        response.raise_for_status()
        tokens = response.json()
        if provider in {"google", "apple"}:
            return verify_identity(tokens.get("id_token"), provider, cid, flow.nonce, client)
        token = tokens["access_token"]
        if provider == "x":
            response = client.get(
                "https://api.x.com/2/users/me", headers={"Authorization": "Bearer " + token}
            )
            response.raise_for_status()
            subject = response.json()["data"]["id"]
            return subject, f"x-{subject}@social.tafolliboost.com"
        version = get_settings().oauth_facebook_version
        response = client.get(
            f"https://graph.facebook.com/{version}/debug_token",
            params={"input_token": token, "access_token": cid + "|" + secret},
        )
        response.raise_for_status()
        checked = response.json()["data"]
        if (
            not checked.get("is_valid")
            or str(checked.get("app_id")) != cid
            or checked.get("expires_at", 0) < time.time()
        ):
            raise ValueError("invalid facebook token")
        proof = hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()
        response = client.get(
            f"https://graph.facebook.com/{version}/me",
            params={"fields": "id,email", "appsecret_proof": proof},
            headers={"Authorization": "Bearer " + token},
        )
        response.raise_for_status()
        profile = response.json()
        if str(profile["id"]) != str(checked["user_id"]):
            raise ValueError("subject mismatch")
        return str(profile["id"]), profile.get(
            "email"
        ) or f"facebook-{profile['id']}@social.tafolliboost.com"


def social_account(db, provider, subject, email):
    if (
        not isinstance(subject, str)
        or not 1 <= len(subject) <= 255
        or not isinstance(email, str)
        or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
        or len(email) > 254
    ):
        raise ValueError("identity")
    identity = db.get(SocialIdentity, (provider, subject))
    if identity:
        account = db.get(Account, identity.account_id)
        if not account or db.get(AdminAccess, account.id):
            raise ValueError("account")
        return account
    email = email.lower()
    # Never silently link accounts by email: an existing password account must log in first.
    if db.query(Account).filter_by(email=email).first():
        raise HTTPException(
            409, "E-Mail bereits registriert. Bitte mit deinem bestehenden Konto anmelden."
        )
    account = Account(
        email=email,
        password_hash=account_service.password_hash(secrets.token_urlsafe(48)),
        recovery_hash=session_service.token_hash(secrets.token_urlsafe(48)),
    )
    db.add(account)
    db.flush()
    from backend.account_models import AccountProfile, AccountSecurity

    db.add(AccountSecurity(
        account_id=account.id, verified_at=datetime.now(UTC).replace(tzinfo=None),
        verification_source="social_verified", credential_version=1,
    ))
    db.add(AccountProfile(account_id=account.id))
    db.add(SocialIdentity(provider=provider, subject=subject, account_id=account.id))
    db.commit()
    return account


@router.api_route("/api/oauth/{provider}/callback", methods=["GET", "POST"])
async def callback(provider: str, request: Request, db=Depends(get_db)):
    base, _cid, _secret = configuration(provider)
    if request.method == "POST" and provider != "apple":
        raise HTTPException(405, "GET required")
    values = await request.form() if request.method == "POST" else request.query_params
    state, code = values.get("state", ""), values.get("code", "")
    if (
        not isinstance(state, str)
        or not 20 <= len(state) <= 200
        or not isinstance(code, str)
        or len(code) > 4096
    ):
        raise HTTPException(400, "OAuth-Antwort ungültig")
    if db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    flow = db.get(OAuthState, session_service.token_hash(state))
    if (
        not flow
        or flow.provider != provider
        or flow.expires_at < datetime.now(UTC).replace(tzinfo=None)
        or not secrets.compare_digest(
            flow.browser_hash, session_service.token_hash(request.cookies.get("tafolli_oauth", ""))
        )
    ):
        db.rollback()
        raise HTTPException(400, "Anmeldung abgelaufen oder nicht in diesem Browser gestartet")
    # One-time state is consumed before network activity, including provider denial.
    db.delete(flow)
    db.commit()
    response = RedirectResponse(base + "/?auth=success", status_code=303)
    try:
        if values.get("error") or not code:
            raise ValueError("denied")
        from starlette.concurrency import run_in_threadpool

        subject, email = await run_in_threadpool(exchange, provider, code, flow)
        account = social_account(db, provider, subject, email)
        account_service.login_cookie(db, account, response)
        request.state.metric_account = account.id
    except Exception:
        # Never disclose provider tokens, credentials or error responses to the browser.
        db.rollback()
        response = RedirectResponse(base + "/?auth=failed", status_code=303)
    response.delete_cookie("tafolli_oauth", path="/api/oauth/")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
