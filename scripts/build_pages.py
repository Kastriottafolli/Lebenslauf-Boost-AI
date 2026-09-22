"""Stage the functional browser app for GitHub Pages (no Python server required)."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
shutil.copytree(ROOT / 'frontend/css', OUT / 'assets/css')
shutil.copytree(ROOT / 'static', OUT / 'static')
html = (ROOT / 'frontend/index.html').read_text()
html = html.replace('"/assets/', '"./assets/').replace('"/static/', '"./static/')
html = html.replace('./assets/js/main.js', './assets/js/pages-main.js')
notice = '''
  <aside class="pages-notice" aria-label="Browser-App">
    <div><strong data-browser-de="Direkt ausprobieren — ohne Anmeldung" data-browser-en="Try it now — no sign-up">Direkt ausprobieren — ohne Anmeldung</strong>
    <p data-browser-de="Ohne API-Key: regelbasierter Demo-Modus mit echtem Datei-Import, Bearbeitung und PDF-/Word-Download. Mit eigenem Key: KI-Anfragen direkt an den gewählten Anbieter."
       data-browser-en="Without an API key: a rule-based demo with file import, editing and PDF/Word downloads. With your own key: AI requests go directly to the selected provider.">Ohne API-Key: regelbasierter Demo-Modus mit echtem Datei-Import, Bearbeitung und PDF-/Word-Download. Mit eigenem Key: KI-Anfragen direkt an den gewählten Anbieter.</p></div>
    <button type="button" id="loadExample" class="btn primary" data-browser-de="Beispiel laden" data-browser-en="Load example">Beispiel laden</button>
    <p id="exampleStatus" role="status" aria-live="polite"></p>
  </aside>
'''
html = html.replace('  <!-- ── Hero:', notice + '\n  <!-- ── Hero:')
html = html.replace('</head>', '<link rel="stylesheet" href="./assets/css/browser.css" /></head>')
(OUT / 'index.html').write_text(html)
(OUT / '.nojekyll').touch()
print(f'Staged GitHub Pages app: {OUT}')
