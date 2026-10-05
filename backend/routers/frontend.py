"""Frontend-Endpunkt: liefert die Single-Page-App aus dem Ordner frontend/."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter(tags=["Frontend"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STATIC_DIR = PROJECT_ROOT / "static"


@router.get("/index.html", include_in_schema=False)
@router.get("/", include_in_schema=False)
def index():
    import html
    import json

    from backend.config import get_settings

    brand = json.loads((STATIC_DIR / "branding.json").read_text())["name"]
    source = (
        (FRONTEND_DIR / "index.html").read_text().replace("Lebenslauf Boost AI", html.escape(brand))
    )
    site = get_settings().site_url.rstrip("/")
    if site.startswith("https://"):
        source = source.replace(
            "</head>", f'<link rel="canonical" href="{html.escape(site, quote=True)}/"></head>'
        )
    # The shell lives at /; API and generated documents are never cached.
    return HTMLResponse(source.replace("</head>", '<meta name="app-base" content="/"></head>'))


@router.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(
        FRONTEND_DIR / "public/manifest.webmanifest",
        media_type="application/manifest+json",
    )


@router.get("/sw.js", include_in_schema=False)
def worker():
    import hashlib
    import json

    bundle = FRONTEND_DIR / "build/app.js"
    revision = (
        hashlib.sha256(bundle.read_bytes()).hexdigest()[:12] if bundle.exists() else "unbuilt"
    )
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
        "User-agent: *\nAllow: /\nDisallow: /api/\n"
        + (f"Sitemap: {base}/sitemap.xml\n" if base else "")
    )


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    path = PROJECT_ROOT / "_site/sitemap.xml"
    if not path.exists():
        raise HTTPException(404, "Configure SITE_URL and rebuild first")
    return FileResponse(path, media_type="application/xml")


@router.get("/{language}/{slug}/", include_in_schema=False)
def guide(language: str, slug: str):
    allowed = {
        ("de", "lebenslauf-mit-ki"),
        ("en", "ai-resume-builder"),
        ("de", "anschreiben-mit-ki"),
        ("en", "ai-cover-letter"),
    }
    if (language, slug) not in allowed:
        raise HTTPException(404)
    path = PROJECT_ROOT / "_site" / language / slug / "index.html"
    if not path.exists():
        raise HTTPException(503, "Run npm run build")
    return FileResponse(path)
