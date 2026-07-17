"""Frische Screenshots der aktualisierten UI fuer Video/Praesentation."""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs" / "video" / "assets"
SHOTS = ROOT / "docs" / "screenshots"
DEMO_CV = ASSETS / "demo-cv.txt"
BASE = "http://127.0.0.1:8000"

JOB = """Senior Software Engineer (Python / FastAPI)

Wir suchen eine erfahrene Software-Entwicklerin / einen erfahrenen Software-Entwickler
fuer den Ausbau unserer Backend-Plattform.

Must-haves:
- Mehrjaehrige Erfahrung mit Python und FastAPI
- Kenntnisse in PostgreSQL / SQLAlchemy
- REST-APIs, Git, agile Zusammenarbeit
- Sehr gute Deutsch- und Englischkenntnisse

Nice-to-haves:
- Docker, CI/CD, Cloud-Grundlagen
- Frontend-Kenntnisse in JavaScript/HTML/CSS
"""

WISHES = "Modern und kompakt, Fokus auf Backend und Wirkung, max. 1–2 Seiten."


async def dismiss_mascot(page) -> None:
    for _ in range(10):
        btn = page.locator("#mascotSubmit:visible")
        if await btn.count() == 0:
            break
        try:
            await btn.click(timeout=1000)
            await page.wait_for_timeout(300)
        except Exception:
            break


async def shot(page, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(path), full_page=False)
    print(f"Saved {path.relative_to(ROOT)}")


async def run() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_timeout(800)
        await dismiss_mascot(page)

        # Hero / Start
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(400)
        await shot(page, ASSETS / "01-hero.png")
        await shot(page, SHOTS / "01-start.png")

        # Input + API key links visible
        await page.locator("#jobDescription").fill(JOB)
        await page.locator("#wishes").fill(WISHES)
        await page.set_input_files("#fileInput", str(DEMO_CV))
        await page.wait_for_timeout(1200)
        await page.locator("#providerSelect").scroll_into_view_if_needed()
        await page.locator("#providerSelect label.prov", has_text="Vergleich").click()
        await page.wait_for_timeout(400)
        await page.locator("#apiKeys").scroll_into_view_if_needed()
        await page.wait_for_timeout(400)
        await shot(page, ASSETS / "02-input-upload.png")

        # Generate (demo mode) — overlay ~5s then step 2
        await page.locator("#generateBtn").click()
        # Capture loading overlay mid-sequence
        await page.wait_for_timeout(1800)
        await shot(page, ASSETS / "02b-loading.png")
        await page.wait_for_selector("#panel-2.active", timeout=20000)
        await page.wait_for_timeout(800)
        await dismiss_mascot(page)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(400)
        await shot(page, ASSETS / "03-compare-output.png")
        await shot(page, SHOTS / "02-bearbeiten.png")

        # Refine area
        await page.locator("#refineInput").scroll_into_view_if_needed()
        await page.wait_for_timeout(300)
        await shot(page, ASSETS / "04-refine.png")

        # Design & Download
        await page.locator("#toStep3").click()
        await page.wait_for_timeout(1800)
        await shot(page, ASSETS / "05b-loading-design.png")
        await page.wait_for_selector("#panel-3.active", timeout=20000)
        await page.wait_for_timeout(800)
        await dismiss_mascot(page)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(400)
        await shot(page, ASSETS / "05-design-export.png")
        await shot(page, SHOTS / "03-design.png")

        await browser.close()
        print("Screenshots fertig.")


if __name__ == "__main__":
    asyncio.run(run())
