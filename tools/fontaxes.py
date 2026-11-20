"""rev. 0.11: a sheet of every tengwa of a font with the axes the machine will use: the tehta 'a' placed over the top
axis and the dot below under the bottom axis, as the shuttle's blocks will print them (for checking fonts without
anchors, e.g. Dan Smith's layout, whose axes are estimated).
Usage: python3 -I fontaxes.py FONT OUT_PNG"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
import fontprof as FP
from glyphgeom import glyph_geom

font, out = sys.argv[1], sys.argv[2]
R, D = FP.fit(font)
gs = FP.glyphset(R, D)
marks = {m['key']: m for m in D['marks'] if not m.get('missing')}
S = 0.12                      # px per unit (1000 per em)
cw, ch, cols = 160, 190, 8
T = [t for t in D['tengwar'] if not t.get('missing')]
rows = (len(T) + cols - 1) // cols
im = Image.new('RGB', (cols * cw, rows * ch + 40), 'white'); d = ImageDraw.Draw(im)
try:
    L = ImageFont.truetype('/home/claude/tpm2/fonts/PT_Sans-Web-Regular.ttf', 13)
except Exception:
    L = ImageFont.load_default()
d.text((8, 8), f"{R['name']}: s = {D['scale']:.3f}; красная — ось техт, синяя — нижняя ось", font=L, fill='black')


def poly(g, ox, oy, fill):
    if g is None or g.is_empty:
        return
    for p in (g.geoms if hasattr(g, 'geoms') else [g]):
        d.polygon([(ox + x * S, oy - y * S) for x, y in p.exterior.coords], fill=fill)
        for h in p.interiors:
            d.polygon([(ox + x * S, oy - y * S) for x, y in h.coords], fill='white')


from shapely import affinity
for i, t in enumerate(T):
    x0 = (i % cols) * cw + 20; y0 = 40 + (i // cols) * ch + 125
    g = glyph_geom(gs, t['glyph'])
    poly(g, x0, y0, (30, 30, 30))
    ax, bx = t['top'][0], t['bot'][0]
    d.line([(x0 + ax * S, y0 - 100), (x0 + ax * S, y0 - 20)], fill=(220, 40, 40))
    d.line([(x0 + bx * S, y0 - 10), (x0 + bx * S, y0 + 40)], fill=(40, 90, 220))
    for key, xx, col in (('a', ax, (220, 40, 40)), ('dotb', bx, (40, 90, 220))):
        m = marks.get(key)
        if m:
            mg = affinity.translate(glyph_geom(gs, m['glyph']), xx - m['anchor'][0], 0)
            poly(mg, x0, y0, col)
    d.line([(x0 - 5, y0), (x0 + t['adv'] * S + 5, y0)], fill=(200, 200, 200))
    d.text((x0 - 12, y0 + 45), t['name'][:22], font=L, fill='black')
im.save(out)
print(out, len(T))
