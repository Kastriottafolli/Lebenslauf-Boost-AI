"""Build a static preview; the Python app continues to use its original frontend."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
shutil.copytree(ROOT / 'frontend', OUT / 'assets')
shutil.copytree(ROOT / 'static', OUT / 'static')
html = (ROOT / 'frontend/index.html').read_text()
html = html.replace('"/assets/', '"./assets/').replace('"/static/', '"./static/')
html = html.replace('./assets/js/main.js', './assets/js/pages-preview.js')
notice = '''
  <aside class="pages-notice" role="note">
    <strong data-preview-de="Oberflächen-Vorschau" data-preview-en="Interface preview">Oberflächen-Vorschau</strong>
    <p data-preview-de="Diese GitHub-Pages-Version zeigt die Oberfläche. Upload, KI, Demo-Modus und Export benötigen den Python-Server und sind hier deaktiviert."
       data-preview-en="This GitHub Pages version previews the interface. Upload, AI, demo mode and export require the Python server and are disabled here.">Diese GitHub-Pages-Version zeigt die Oberfläche. Upload, KI, Demo-Modus und Export benötigen den Python-Server und sind hier deaktiviert.</p>
    <a href="https://github.com/Kastriottafolli/Lebenslauf-Boost-AI# getting-started" data-preview-de="App lokal starten: Anleitung auf GitHub →" data-preview-en="Run locally: instructions on GitHub →">App lokal starten: Anleitung auf GitHub →</a>
    <nav aria-label="Vorschau / Preview">
      <button type="button" data-preview-step="1">1 · Eingabe / Input</button>
      <button type="button" data-preview-step="2">2 · Bearbeiten / Edit</button>
      <button type="button" data-preview-step="3">3 · Design / Design</button>
    </nav>
  </aside>
'''.replace('# getting-started', '#getting-started')
html = html.replace('  <!-- ── Hero:', notice + '\n  <!-- ── Hero:')
# Native disabled controls also protect the preview before JavaScript loads.
html = html.replace('<main>', '<main><fieldset disabled class="pages-fields">')
html = html.replace('</main>', '</fieldset></main>')
html = html.replace('</head>', '''<style>
.pages-notice { position:relative; z-index:2; margin:24px auto; padding:20px; width:calc(100% - 32px); max-width:1100px; border:1px solid #6298d8; border-radius:16px; background:#edf5ff; color:#173450; }
.pages-notice p { margin:8px 0; }
.pages-notice a { color:#164f90; text-decoration:underline; }
.pages-notice nav { display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }
.pages-notice button { padding:8px 14px; border:1px solid #6298d8; border-radius:8px; background:white; color:#173450; cursor:pointer; }
.pages-notice button[aria-pressed="true"] { background:#173450; color:white; }
.pages-fields { border:0; padding:0; margin:0; min-width:0; }
#mascot, #providerBadges { display:none !important; }
</style></head>''')
(OUT / 'index.html').write_text(html)
(OUT / '.nojekyll').touch()
print(f'Built GitHub Pages preview: {OUT}')
