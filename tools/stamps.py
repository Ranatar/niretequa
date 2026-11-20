"""Printable test stamps (STL) for stage E1: relief type plates with thickened Alcarin glyphs.
Usage: python3 -I stamps.py FONT DATA_DIR GEN_DIR OUT_DIR"""
import sys, os, json, runpy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import trimesh
from shapely.geometry import Polygon, MultiPolygon, box
from shapely import affinity
from shapely.ops import unary_union
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw
from thicken import slug_geometry

font, data_dir, gen_dir, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
sys.argv = ['gen_shuttle.py', font, data_dir, gen_dir]
G = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen_shuttle.py'))
ITEMS, U, MARK_AX = G['ITEMS'], G['U'], G['MARK_AX']
F = TTFont(font); GS = F.getGlyphSet()
INCH = 25.4
SIZES = [('em13_nozzle04', INCH / 3, 0.45), ('em14_nozzle025', INCH / 4, 0.30)]
RELIEF, BASE, MARGIN = 1.2, 2.5, 4.0     # mm
LINE = 1700                              # font units between lines
cache = {}


def slug(name, em, pmin):
    key = (name, em, pmin)
    if key not in cache:
        cache[key] = slug_geometry(GS, name, em, pmin)[0]
    return cache[key]


def placed_glyphs(placed, y0=0):
    """(glyph name, origin x, origin y) in font units from a simulate_mech placement list."""
    out_ = []
    for kind, k, X in placed:
        it = ITEMS[k]
        out_.append((it['glyph'], X * U - it['ax'], y0))
        if kind == 'base' and it['kind'] == 'C':
            out_.append((it['mark'], X * U - MARK_AX[it['mark']], y0))
    return out_


def sheet_glyphs():
    """All 88 shuttle positions as 8 rows x 11 cells, as on the shuttle (rev. 0.6)."""
    P = G['PITCH'] * U; res = []
    for ri, rw in enumerate(G['shuttle_rows']()):
        for half in (0,):
            y = -ri * 1350
            for pi in range(11):
                k = rw[pi]
                if k is None:
                    continue
                it = ITEMS[k]; x0 = pi * P
                if it['kind'] in G['ADV']:
                    x = x0 + (P - it['w'] * U) / 2
                    res.append((it['glyph'], x + it['a'] * U - it['ax'], y))
                    if it['kind'] == 'C':
                        res.append((it['mark'], x + it['a'] * U - MARK_AX[it['mark']], y))
                else:
                    res.append((it['glyph'], x0 + P / 2 - it['ax'], y))
    return res


def compose(glyphs, em, pmin):
    s = em / 1000.0
    geoms = []
    for name, x, y in glyphs:
        g = slug(name, em, pmin)
        geoms.append(affinity.translate(g, x, y))
    u = unary_union(geoms)
    u = affinity.scale(u, s, s, origin=(0, 0))
    return u


def plate(geom, fname):
    # mirror for a stamp: the print must read correctly
    m = affinity.scale(geom, -1, 1, origin=(0, 0))
    minx, miny, maxx, maxy = m.bounds
    m = affinity.translate(m, -minx + MARGIN, -miny + MARGIN)
    W, H = maxx - minx + 2 * MARGIN, maxy - miny + 2 * MARGIN
    base = trimesh.creation.box(extents=(W, H, BASE)); base.apply_translation((W / 2, H / 2, BASE / 2))
    # orientation mark: small triangle in the corner that is top-left on the print (top-right on the stamp)
    tri = Polygon([(W - 1.5, H - 1.5), (W - 4.5, H - 1.5), (W - 1.5, H - 4.5)])
    polys = list(m.geoms) if isinstance(m, MultiPolygon) else [m]
    parts = [base]
    skipped = 0
    for p in polys + [tri]:
        p = p.buffer(0).simplify(0.004)
        for q in ([p] if p.geom_type == 'Polygon' else list(getattr(p, 'geoms', []))):
            if q.area < 0.02:
                skipped += 1; continue
            ex = trimesh.creation.extrude_polygon(q, RELIEF); ex.apply_translation((0, 0, BASE))
            if not ex.is_volume:
                ex = trimesh.creation.extrude_polygon(q.buffer(0.002).buffer(-0.002), RELIEF); ex.apply_translation((0, 0, BASE))
            if ex.is_volume:
                parts.append(ex)
            else:
                skipped += 1
    if skipped:
        print('  skipped tiny/invalid polygons:', skipped)
    mesh = trimesh.boolean.union(parts, engine='manifold')
    mesh.export(os.path.join(out, fname + '.stl'))
    return W, H, mesh.is_watertight, len(polys)


def preview(geom, fname, px_per_mm=12):
    minx, miny, maxx, maxy = geom.bounds
    W = int((maxx - minx + 2 * MARGIN) * px_per_mm); H = int((maxy - miny + 2 * MARGIN) * px_per_mm)
    im = Image.new('L', (W, H), 255); dr = ImageDraw.Draw(im)
    T = lambda xy: [((x - minx + MARGIN) * px_per_mm, (maxy - y + MARGIN) * px_per_mm) for x, y in xy]
    for p in (list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]):
        dr.polygon(T(p.exterior.coords), fill=0)
        for h in p.interiors:
            dr.polygon(T(h.coords), fill=255)
    im.save(os.path.join(out, fname + '.png'))


report = []
_, placed_q, _ = G['simulate_mech'](G['QUENYA'])
_, placed_s, _ = G['simulate_mech'](G['SINDARIN'])
test_lines = []
for li, w in enumerate(G['twords']):
    _, pl, _ = G['simulate_mech']([w]); test_lines += placed_glyphs(pl, -li * LINE)
for tag, em, pmin in SIZES:
    jobs = {
        'sample': placed_glyphs(placed_q, 0) + placed_glyphs(placed_s, -LINE),
        'control': test_lines,
        'sheet': sheet_glyphs(),
    }
    for jn, gl in jobs.items():
        geom = compose(gl, em, pmin)
        name = f"tpm2_{tag}_{jn}"
        W, H, wt, n = plate(geom, name)
        preview(geom, name)
        report.append(dict(file=name + '.stl', em_mm=round(em, 3), pmin=pmin, W=round(W, 1), H=round(H, 1),
                           watertight=bool(wt), polygons=n))
        print(report[-1])
json.dump(report, open(os.path.join(out, 'stamps.json'), 'w'), ensure_ascii=False, indent=1)
