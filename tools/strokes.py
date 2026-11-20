"""Measure stroke thickness and gap width of slugs (font units).
Usage: python3 -I strokes.py FONT DATA_DIR OUT_JSON"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from fontTools.ttLib import TTFont
from scipy import ndimage
from skimage.morphology import skeletonize
from shapely.geometry import box
from PIL import Image, ImageDraw
from glyphgeom import glyph_geom

font, data_dir, out = sys.argv[1:4]
F = TTFont(font); GS = F.getGlyphSet()
D = json.load(open(os.path.join(data_dir, 'codes.json')))
S = 2.0  # px per font unit


def raster(geom, pad=40):
    minx, miny, maxx, maxy = geom.bounds
    W = int((maxx - minx + 2 * pad) * S) + 1; H = int((maxy - miny + 2 * pad) * S) + 1
    im = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(im)
    polys = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
    tr = lambda xy: [((x - minx + pad) * S, (maxy - y + pad) * S) for x, y in xy]
    for p in polys:
        dr.polygon(tr(p.exterior.coords), fill=255)
        for h in p.interiors:
            dr.polygon(tr(h.coords), fill=0)
    return np.array(im) > 127


def thickness(mask):
    dist = ndimage.distance_transform_edt(mask)
    sk = skeletonize(mask)
    v = 2 * dist[sk] / S
    # drop skeleton tips that run into tapered terminals: keep values above the 2nd percentile
    return v


def measure(name):
    g = glyph_geom(GS, name)
    m = raster(g)
    t = thickness(m)
    # gaps: background inside the convex hull of the ink
    hull = g.convex_hull.buffer(-1)
    hm = raster_hull(g, hull, m.shape)
    bg = (~m) & hm
    gv = thickness(bg) if bg.any() else np.array([])
    return dict(t5=float(np.percentile(t, 5)), t50=float(np.median(t)), tmin=float(t.min()),
                g5=float(np.percentile(gv, 5)) if gv.size else None, gmin=float(gv.min()) if gv.size else None,
                area=g.area)


def raster_hull(g, hull, shape, pad=40):
    minx, miny, maxx, maxy = g.bounds
    im = Image.new('L', (shape[1], shape[0]), 0); dr = ImageDraw.Draw(im)
    if hull.is_empty:
        return np.zeros(shape, bool)
    polys = [hull] if hull.geom_type == 'Polygon' else list(hull.geoms)
    for p in polys:
        dr.polygon([((x - minx + pad) * S, (maxy - y + pad) * S) for x, y in p.exterior.coords], fill=255)
    return np.array(im) > 127


res = {}
names = [(t['name'], t['glyph']) for t in D['tengwar']] + [(m['key'], m['glyph']) for m in D['marks']] \
    + [(n['name'], n['glyph']) for n in D['numerals'] + D['punct']]
for lbl, g in names:
    res[lbl] = dict(glyph=g, **measure(g))
json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)
vals = sorted(res.items(), key=lambda kv: kv[1]['t5'])
print('thinnest strokes (t5, font units):')
for k, v in vals[:8]:
    print(f"  {k:28s} t5={v['t5']:.0f} tmin={v['tmin']:.0f} t50={v['t50']:.0f}")
gv = sorted([kv for kv in res.items() if kv[1]['g5'] is not None], key=lambda kv: kv[1]['g5'])
print('narrowest gaps (g5):')
for k, v in gv[:8]:
    print(f"  {k:28s} g5={v['g5']:.0f} gmin={v['gmin']:.0f}")
allt = np.array([v['t5'] for v in res.values()]); allg = np.array([v['g5'] for v in res.values() if v['g5'] is not None])
print('median of per-glyph t5:', np.median(allt), ' 10th pct:', np.percentile(allt, 10))
print('median of per-glyph g5:', np.median(allg), ' 10th pct:', np.percentile(allg, 10))
