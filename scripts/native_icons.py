"""Render native launch assets from the shared Boosty AI arrow mark."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BACKGROUND = '#22393a'
INK = '#d7ebe2'

def mark(size, background=True, scale=1.0):
    factor = 3
    canvas = Image.new('RGBA', (size * factor, size * factor), BACKGROUND if background else (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    def point(x, y):
        return ((0.5 + (x / 512 - 0.5) * scale) * size * factor, (0.5 + (y / 512 - 0.5) * scale) * size * factor)
    width = max(1, round(44 / 512 * size * factor * scale))
    draw.line([point(144, 356), point(356, 144)], fill=INK, width=width)
    draw.line([point(169, 144), point(356, 144), point(356, 331)], fill=INK, width=width, joint='curve')
    return canvas.resize((size, size), Image.Resampling.LANCZOS)

res = ROOT / 'android/app/src/main/res'
for path in res.glob('mipmap-*/*.png'):
    size = Image.open(path).width
    foreground = 'foreground' in path.name
    mark(size, not foreground, 0.64 if foreground else 1).save(path)
(res / 'values/ic_launcher_background.xml').write_text('<?xml version="1.0" encoding="utf-8"?>\n<resources><color name="ic_launcher_background">#22393a</color></resources>\n')
(res / 'drawable-v24/ic_launcher_foreground.xml').write_text('''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="108dp" android:height="108dp" android:viewportWidth="108" android:viewportHeight="108"><path android:strokeColor="#d7ebe2" android:strokeWidth="6" android:strokeLineCap="round" android:strokeLineJoin="round" android:fillColor="@android:color/transparent" android:pathData="M39,69 L69,39 M43,39 L69,39 L69,65"/></vector>\n''')
assets = ROOT / 'ios/App/App/Assets.xcassets'
mark(1024).convert('RGB').save(assets / 'AppIcon.appiconset/AppIcon-512@2x.png')
for path in list(res.glob('drawable*/splash.png')) + list((assets / 'Splash.imageset').glob('*.png')):
    with Image.open(path) as old:
        width, height = old.size
    splash = Image.new('RGB', (width, height), BACKGROUND)
    symbol_size = max(48, round(min(width, height) * 0.23))
    symbol = mark(symbol_size, False)
    splash.paste(symbol, ((width-symbol_size)//2, (height-symbol_size)//2), symbol)
    splash.save(path, optimize=True)
print('Native icons and launch screens updated.')
