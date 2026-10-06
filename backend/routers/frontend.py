"""Frontend-Endpunkt: liefert die Single-Page-App aus dem Ordner frontend/."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter(tags=["Frontend"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STATIC_DIR = PROJECT_ROOT / "static"


def asset_revision():
    import hashlib

    bundle = FRONTEND_DIR / "build/app.js"
    return hashlib.sha256(
        (bundle.read_bytes() if bundle.exists() else b"unbuilt")
        + (FRONTEND_DIR / "css/professional.css").read_bytes()
    ).hexdigest()[:12]


@router.get("/index.html", include_in_schema=False)
@router.get("/", include_in_schema=False)
def index():
    import html
    import json

    from backend.config import get_settings

    brand = json.loads((STATIC_DIR / "branding.json").read_text())["name"]
    source = (FRONTEND_DIR / "index.html").read_text().replace("Boosty AI", html.escape(brand))
    site = get_settings().site_url.rstrip("/")
    if site.startswith("https://"):
        source = source.replace(
            "</head>",
            f'<link rel="canonical" href="{html.escape(site, quote=True)}/">'
            f'<meta property="og:url" content="{html.escape(site, quote=True)}/"></head>',
        )
    # The shell lives at /; API and generated documents are never cached.
    return HTMLResponse(
        source.replace("__BUILD_ID__", asset_revision()).replace(
            "</head>", '<meta name="app-base" content="/"></head>'
        ),
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/admin", include_in_schema=False)
@router.get("/admin/", include_in_schema=False)
def admin_page():
    return HTMLResponse(
        (FRONTEND_DIR / "admin.html").read_text().replace("__BUILD_ID__", asset_revision()),
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
    )


@router.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(
        FRONTEND_DIR / "public/manifest.webmanifest",
        media_type="application/manifest+json",
    )


@router.get("/sw.js", include_in_schema=False)
def worker():
    import json

    revision = asset_revision()
    value = (
        (FRONTEND_DIR / "public/sw.js")
        .read_text()
        .replace("assets/js/app.js", "assets/build/app.js")
        .replace("__BUILD_ID__", revision)
        .replace(
            "__PRECACHE_CHUNKS__",
            json.dumps(
                [
                    "assets/build/" + p.name
                    for p in (FRONTEND_DIR / "build").glob("*.js")
                    if p.name != "app.js"
                ]
            ),
        )
    )
    return HTMLResponse(
        value,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/robots.txt", include_in_schema=False)
def robots():
    from fastapi.responses import PlainTextResponse

    from backend.config import get_settings

    base = get_settings().site_url.rstrip("/")
    return PlainTextResponse(
        "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /admin\n"
        + (f"Sitemap: {base}/sitemap.xml\n" if base else "")
    )


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    path = PROJECT_ROOT / "_site/sitemap.xml"
    if not path.exists():
        raise HTTPException(404, "Configure SITE_URL and rebuild first")
    return FileResponse(path, media_type="application/xml")


@router.get("/impressum", include_in_schema=False)
@router.get("/impressum/", include_in_schema=False)
@router.get("/datenschutz", include_in_schema=False)
@router.get("/datenschutz/", include_in_schema=False)
@router.get("/agb", include_in_schema=False)
@router.get("/agb/", include_in_schema=False)
@router.get("/widerruf", include_in_schema=False)
@router.get("/widerruf/", include_in_schema=False)
def legal_notice(request: Request, lang: str = "de"):
    from backend.config import get_settings
    from backend.services.legal_service import render

    settings = get_settings()
    kind = {"datenschutz": "privacy", "agb": "terms", "widerruf": "withdrawal"}.get(request.url.path.strip("/"), "legal")
    return HTMLResponse(render(kind, lang, {
        "operator_name":settings.operator_name,
        "operator_address":settings.operator_address,
        "operator_email":settings.operator_email,
    }, settings.site_url, retention_days=settings.retention_days), headers={"Cache-Control":"no-cache"})


@router.get("/agb.txt", include_in_schema=False)
@router.get("/widerruf.txt", include_in_schema=False)
def contract_text(request: Request, lang: str = "de"):
    from fastapi.responses import PlainTextResponse

    from backend.config import get_settings
    from backend.services.legal_service import render_text

    settings = get_settings()
    kind = "withdrawal" if "widerruf" in request.url.path else "terms"
    return PlainTextResponse(render_text(kind, lang, {
        "operator_name": settings.operator_name,
        "operator_address": settings.operator_address,
        "operator_email": settings.operator_email,
    }, settings.retention_days), headers={"Cache-Control": "no-cache", "Content-Disposition": f'attachment; filename="tafolliboost-{kind}-{lang if lang in ("de", "en", "sq") else "de"}.txt"'})


@router.get("/{language}/{slug}/", include_in_schema=False)
def guide(language: str, slug: str):
    allowed = {
        ("de", "lebenslauf-mit-ki"),
        ("en", "ai-resume-builder"),
        ("de", "anschreiben-mit-ki"),
        ("en", "ai-cover-letter"),
        ("sq", "cv-me-ia"),
        ("sq", "leter-aplikimi-me-ia"),
    }
    if (language, slug) not in allowed:
        raise HTTPException(404)
    path = PROJECT_ROOT / "_site" / language / slug / "index.html"
    if not path.exists():
        raise HTTPException(503, "Run npm run build")
    return HTMLResponse(
        path.read_text().replace('assets/js/analytics-app.js', 'assets/build/analytics-app.js'),
        headers={'Cache-Control': 'no-cache'},
    )
