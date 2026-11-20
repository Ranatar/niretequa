"""Panel: original / thickened / simulated print of the thickened glyph."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont
from thicken import slug_geometry

font, outp = sys.argv[1:3]
F = TTFont(font); GS = F.getGlyphSet(); cmap = F.getBestCmap()
INCH = 25.4
CASES = [('0,4 мм · 1/3 дюйма', 0.45, INCH / 3), ('0,25 мм · 1/4 дюйма', 0.30, INCH / 4)]
GL = [cmap[0xE000], cmap[0xE004], cmap[0xE022], cmap[0xE02E], 'uniE046', 'uniE04A', 'uniE040', 'uniE043', 'uniE051.lambe', 'uniE050', cmap[0xE073], 'uniE07D']
CELL, SC = 140, 0.12
rows = []
for lbl, pos, em in CASES:
    rows += [(lbl + ': утолщено', pos, em, 'thick'), (lbl + ': печать', pos, em, 'print')]
img = Image.new('RGB', (CELL * len(GL) + 230, CELL * (len(rows) + 1) + 10), 'white'); dr = ImageDraw.Draw(img)
fnt = ImageFont.truetype(os.path.join(os.path.dirname(font), 'PT_Sans-Web-Regular.ttf'), 14)


def draw(geom, ci, ri, ref):
    cx = 230 + ci * CELL + CELL / 2; cy = ri * CELL + CELL * 0.6
    b = ref.bounds; ox = (b[0] + b[2]) / 2; oy = (b[1] + b[3]) / 2
    polys = [] if geom.is_empty else ([geom] if geom.geom_type == 'Polygon' else list(geom.geoms))
    T = lambda xy: [(cx + (x - ox) * SC, cy - (y - oy) * SC) for x, y in xy]
    for p in polys:
        dr.polygon(T(p.exterior.coords), fill=(20, 20, 20))
        for h in p.interiors:
            dr.polygon(T(h.coords), fill=(255, 255, 255))
    dr.rectangle([230 + ci * CELL + 3, ri * CELL + 3, 230 + (ci + 1) * CELL - 3, (ri + 1) * CELL - 3], outline=(200, 200, 200))


dr.text((6, CELL / 2 - 8), 'исходник', fill=(30, 30, 30), font=fnt)
cache = {}
for ci, g in enumerate(GL):
    th, orig = slug_geometry(GS, g, INCH / 3, 0.45); draw(orig, ci, 0, orig)
for ri, (lbl, pos, em, kind) in enumerate(rows, start=1):
    dr.text((6, ri * CELL + CELL / 2 - 8), lbl, fill=(30, 30, 30), font=fnt)
    for ci, g in enumerate(GL):
        th, orig = slug_geometry(GS, g, em, pos)
        geom = th
        if kind == 'print':
            r = pos / 2 * 1000 / em
            geom = th.buffer(-r * 0.98, 16).buffer(r * 0.98, 16)
        draw(geom, ci, ri, orig)
img.save(outp)
