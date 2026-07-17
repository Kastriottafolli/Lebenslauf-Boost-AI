"""Frische Full-HD-Screenshots der aktuellen Sapphire-Nightfall-UI."""

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


async def hide_ui_chrome(page) -> None:
    await page.evaluate(
        """() => {
          const mascot = document.querySelector('#mascot');
          if (mascot) mascot.style.display = 'none';
          const toast = document.querySelector('#toast');
          if (toast) toast.classList.add('hidden');
        }"""
    )


async def shot(page, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(path), full_page=False, type="png")
    print(f"Saved {path.relative_to(ROOT)}")


async def run() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )
        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await hide_ui_chrome(page)

        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(500)
        await shot(page, ASSETS / "01-hero.png")
        await shot(page, SHOTS / "01-start.png")

        await page.locator("#jobDescription").fill(JOB)
        await page.locator("#wishes").fill(WISHES)
        await page.set_input_files("#fileInput", str(DEMO_CV))
        await page.wait_for_timeout(1500)
        await page.locator("#providerSelect").scroll_into_view_if_needed()
        await page.locator("#providerSelect label.prov", has_text="Vergleich").click()
        await page.wait_for_timeout(400)
        await page.locator("#apiKeys").scroll_into_view_if_needed()
        await page.wait_for_timeout(500)
        await hide_ui_chrome(page)
        await shot(page, ASSETS / "02-input-upload.png")

        await page.locator("#generateBtn").scroll_into_view_if_needed()
        await page.locator("#generateBtn").click()
        await page.wait_for_timeout(2200)
        await shot(page, ASSETS / "02b-loading.png")
        await page.wait_for_selector("#panel-2.active", timeout=25000)
        await page.wait_for_timeout(900)
        await hide_ui_chrome(page)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(400)
        await shot(page, ASSETS / "03-compare-output.png")
        await shot(page, SHOTS / "02-bearbeiten.png")

        await page.locator("#refineInput").scroll_into_view_if_needed()
        await page.wait_for_timeout(400)
        await hide_ui_chrome(page)
        await shot(page, ASSETS / "04-refine.png")

        await page.locator("#toStep3").click()
        await page.wait_for_timeout(2200)
        await shot(page, ASSETS / "05b-loading-design.png")
        await page.wait_for_selector("#panel-3.active", timeout=25000)
        await page.wait_for_timeout(900)
        await hide_ui_chrome(page)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(400)
        await shot(page, ASSETS / "05-design-export.png")
        await shot(page, SHOTS / "03-design.png")

        await browser.close()
        print("Screenshots fertig.")


if __name__ == "__main__":
    asyncio.run(run())
