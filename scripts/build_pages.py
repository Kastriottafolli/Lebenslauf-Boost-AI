"""Build public HTML, locale guides and an offline-safe application shell."""
from pathlib import Path
import html
import json
import os
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
shutil.copytree(ROOT / 'frontend/css', OUT / 'assets/css')
shutil.copytree(ROOT / 'static', OUT / 'static')
css = OUT / 'assets/css/professional.css'
css.write_text(css.read_text().replace("url('/static/", "url('../../static/"))
brand = json.loads((ROOT / 'static/branding.json').read_text())['name']
base = os.environ.get('PUBLIC_BASE_PATH', '/Lebenslauf-Boost-AI/').strip('/')
base = '/' + base + '/' if base else '/'
site = os.environ.get('SITE_URL', '').rstrip('/')
if site and not re.fullmatch(r'https://[a-zA-Z0-9.-]+(?::[0-9]+)?(?:/[a-zA-Z0-9._/-]*)?', site):
    raise ValueError('SITE_URL must be a public HTTPS origin/base URL')
source = (ROOT / 'frontend/index.html').read_text().replace('Lebenslauf Boost AI', html.escape(brand))
source = source.replace('"/assets/build/app.js"', '"./assets/js/app.js"').replace('"/assets/', '"./assets/').replace('"/static/', '"./static/')
source = source.replace('"/manifest.webmanifest"', '"./manifest.webmanifest"').replace('href="/de/', 'href="./de/')
source = source.replace('</head>', '<meta name="app-base" content="./"></head>')
if site:
    source = source.replace('</head>', f'<link rel="canonical" href="{site}/"></head>')
(OUT / 'index.html').write_text(source)
(OUT / '.nojekyll').touch()
manifest = {'id': '.', 'name': brand, 'short_name': brand, 'description': 'Resume and application studio / Bewerbungswerkstatt', 'start_url': './', 'scope': './', 'display': 'standalone', 'background_color': '#f6f7f3', 'theme_color': '#22393a', 'icons': [{'src': 'static/icon-192.png', 'sizes': '192x192', 'type': 'image/png'}, {'src': 'static/icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'}]}
(OUT / 'manifest.webmanifest').write_text(json.dumps(manifest, ensure_ascii=False))
(ROOT / 'frontend/public/manifest.webmanifest').write_text(json.dumps(manifest, ensure_ascii=False))
shutil.copy(ROOT / 'frontend/public/sw.js', OUT / 'sw.js')
urls = []
for path in sorted((ROOT / 'frontend/content').rglob('*.json')):
    page = json.loads(path.read_text())
    route = page['route'].strip('/')
    target = OUT / route
    target.mkdir(parents=True, exist_ok=True)
    depth = len(route.split('/'))
    prefix = '../' * depth
    canonical = f'<link rel="canonical" href="{site}/{route}/">' if site else ''
    alt = ''.join(f'<link rel="alternate" hreflang="{lang}" href="{site}/{value}/">' for lang, value in page['alternates'].items()) if site else ''
    paragraphs = ''.join(f'<section><h2>{html.escape(s["heading"])}</h2>{s["html"]}</section>' for s in page['sections'])
    # No JSON-LD until a real site URL/operator has been configured; no invented ratings.
    value = f'''<!doctype html><html lang="{page['language']}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(page['title'])} | {html.escape(brand)}</title><meta name="description" content="{html.escape(page['description'], quote=True)}">{canonical}{alt}<link rel="stylesheet" href="{prefix}assets/css/professional.css"><link rel="icon" href="{prefix}static/icon.svg"></head><body><header class="topbar"><a class="brand" href="{prefix}"><span class="brand-symbol">↗</span>{html.escape(brand)}</a><a href="{prefix}{page['alternates']['en' if page['language']=='de' else 'de']}/">{'English' if page['language']=='de' else 'Deutsch'}</a></header><main class="guide"><p class="eyebrow">{page['eyebrow']}</p><h1>{html.escape(page['heading'])}</h1><p>{html.escape(page['description'])}</p><a class="button primary" href="{prefix}?lang={page['language']}#workspace">{page['cta']}</a>{paragraphs}<p><a href="{prefix}">{page['back']}</a></p></main></body></html>'''
    (target / 'index.html').write_text(value)
    urls.append(route)
robots = 'User-agent: *\nAllow: /\nDisallow: ' + base + 'api/\n'
if site:
    robots += f'Sitemap: {site}/sitemap.xml\n'
(OUT / 'robots.txt').write_text(robots)
if site:
    items = ''.join(f'<url><loc>{site}/{u}/</loc></url>' for u in urls)
    (OUT / 'sitemap.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>')
(ROOT / 'frontend/public/routes.json').write_text(json.dumps(urls))
print('Built public pages and PWA shell; canonical URLs require SITE_URL.')
