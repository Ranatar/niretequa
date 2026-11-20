"""Render a panel: original glyph vs simulated FDM print for several (nozzle, em) cases.
Usage: python3 -I fdmpanel.py FONT OUT_PNG"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont
from glyphgeom import glyph_geom

font, outp = sys.argv[1:3]
F = TTFont(font); GS = F.getGlyphSet(); cmap = F.getBestCmap()
INCH = 25.4
CASES = [('исходник', None, None), ('0,4 мм · 1/3″', 0.45, INCH/3), ('0,4 мм · 1/2″', 0.45, INCH/2),
         ('0,25 мм · 1/4″', 0.30, INCH/4), ('0,25 мм · 1/3″', 0.30, INCH/3)]
GL = [cmap[0xE000], cmap[0xE004], cmap[0xE022], cmap[0xE02E], 'uniE046', 'uniE04A', 'uniE040', 'uniE043', 'uniE051.lambe', 'uniE050', cmap[0xE073], 'uniE07D']
CELL, SC = 150, 0.13   # px per cell, px per font unit
img = Image.new('RGB', (CELL * len(GL) + 170, CELL * len(CASES) + 10), 'white'); dr = ImageDraw.Draw(img)
try:
    fnt = ImageFont.truetype(os.path.join(os.path.dirname(font), 'PT_Sans-Web-Regular.ttf'), 15)
except Exception:
    fnt = None
for ri, (lbl, pos, em) in enumerate(CASES):
    dr.text((6, ri * CELL + CELL / 2 - 8), lbl, fill=(30, 30, 30), font=fnt)
    for ci, g in enumerate(GL):
        geom = glyph_geom(GS, g)
        if pos:
            r = pos / 2 * 1000 / em
            geom = geom.buffer(-r, 16).buffer(r, 16)
        cx = 170 + ci * CELL + CELL / 2; cy = ri * CELL + CELL * 0.62
        b = glyph_geom(GS, g).bounds; ox = (b[0] + b[2]) / 2; oy = (b[1] + b[3]) / 2
        polys = [] if geom.is_empty else ([geom] if geom.geom_type == 'Polygon' else list(geom.geoms))
        T = lambda xy: [(cx + (x - ox) * SC, cy - (y - oy) * SC) for x, y in xy]
        for p in polys:
            dr.polygon(T(p.exterior.coords), fill=(20, 20, 20))
            for h in p.interiors:
                dr.polygon(T(h.coords), fill=(255, 255, 255))
        dr.rectangle([170 + ci * CELL + 3, ri * CELL + 3, 170 + (ci + 1) * CELL - 3, (ri + 1) * CELL - 3], outline=(200, 200, 200))
img.save(outp)
