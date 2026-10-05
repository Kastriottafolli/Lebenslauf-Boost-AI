"""Render native launch assets from the shared Boosty mascot."""
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
    # Same document character as static/boosti.svg, with a safe margin for maskable icons.
    def box(x1,y1,x2,y2): return (*point(x1,y1),*point(x2,y2))
    stroke = max(1,round(size*factor*scale*0.014))
    draw.ellipse(box(152,427,360,456),fill='#162d2e')
    draw.line([point(165,302),point(107,325),point(96,357)],fill='#d7ebe2',width=stroke)
    draw.line([point(346,301),point(407,275),point(427,237)],fill='#d7ebe2',width=stroke)
    draw.ellipse(box(83,345,111,373),fill='#f4dcc4')
    draw.ellipse(box(414,224,442,252),fill='#f4dcc4')
    draw.rounded_rectangle(box(156,168,354,415),radius=size*factor*scale*0.05,fill='white',outline='#142f30',width=stroke)
    draw.rounded_rectangle(box(162,174,348,218),radius=size*factor*scale*0.035,fill='#0474c4')
    for y,end in [(263,314),(302,295),(341,275)]: draw.line([point(194,y),point(end,y)],fill='#dce6f5',width=stroke)
    for x in (217,293):
        draw.ellipse(box(x-13,118,x+13,144),fill='#d7ebe2')
        draw.ellipse(box(x-2,120,x+4,126),fill='white')
    draw.arc(box(225,143,283,175),0,180,fill='#d7ebe2',width=stroke)
    draw.rounded_rectangle(box(217,414,294,446),radius=size*factor*scale*0.018,fill='#0474c4')
    return canvas.resize((size, size), Image.Resampling.LANCZOS)

res = ROOT / 'android/app/src/main/res'
for path in res.glob('mipmap-*/*.png'):
    size = Image.open(path).width
    foreground = 'foreground' in path.name
    mark(size, not foreground, 0.64 if foreground else 1).save(path)
(res / 'values/ic_launcher_background.xml').write_text('<?xml version="1.0" encoding="utf-8"?>\n<resources><color name="ic_launcher_background">#22393a</color></resources>\n')
(res / 'drawable-v24/ic_launcher_foreground.xml').write_text('''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="108dp" android:height="108dp" android:viewportWidth="108" android:viewportHeight="108"><path android:fillColor="#ffffff" android:pathData="M34,36 L74,36 L74,83 L34,83 Z"/><path android:fillColor="#0474c4" android:pathData="M34,36 L74,36 L74,46 L34,46 Z"/><path android:fillColor="#262b40" android:pathData="M43,25 A3,3 0,1 0,43 31 A3,3 0,1 0,43 25 M62,25 A3,3 0,1 0,62 31 A3,3 0,1 0,62 25"/><path android:strokeColor="#d7ebe2" android:strokeWidth="3" android:strokeLineCap="round" android:fillColor="@android:color/transparent" android:pathData="M33,64 L24,74 M75,64 L86,52 M44,58 L66,58 M44,66 L62,66 M44,74 L58,74 M48,32 Q54,36 60,32"/></vector>\n''')
for icon_size in (192,512): mark(icon_size).convert('RGB').save(ROOT / f'static/icon-{icon_size}.png')

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
