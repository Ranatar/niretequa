"""Type blocks of the shuttle: one block per position, four glyph rows, thickened Alcarin relief."""
import math, os, pickle, hashlib
import numpy as np
from shapely import affinity
from shapely.ops import unary_union
from shapely.geometry import box as sbox
from manifold3d import Manifold
import params as P
import data as D
import geo
from thicken import slug_geometry

PMIN = 0.45
CACHE = D.CACHE
os.makedirs(CACHE, exist_ok=True)
_slugs = {}


def slug(name):
    if name not in _slugs:
        fn = os.path.join(CACHE, f'slug_{name}_{P.EM:.3f}_{PMIN}.pkl')        # rev. 0.11: CACHE is per font
        if os.path.exists(fn):
            _slugs[name] = pickle.load(open(fn, 'rb'))
        else:
            g = slug_geometry(D.GLYPHSET, name, P.EM, PMIN)[0]
            pickle.dump(g, open(fn, 'wb')); _slugs[name] = g
    return _slugs[name]


def item_glyphs(k):
    """(glyph, origin x in mm relative to the hammer axis) for an item on the shuttle."""
    it = D.ITEMS[k]; s = P.EM / 1000
    if it.get('missing') or it.get('glyph') is None:       # rev. 0.11: a sign the font lacks: an empty cell
        return []
    if it['kind'] in D.ADV:
        res = [(it['glyph'], it['a'] * P.U - it['ax'] * s)]
        if it['kind'] == 'C':
            res.append((it['mark'], it['a'] * P.U - D.MARK_AX[it['mark']] * s))
        return res
    return [(it['glyph'], P.MARK_REF_U * P.U - it['ax'] * s)]


def row_baseline(srow):
    return P.BASE1 - (srow - 1) * P.RH


def position_outline(m):
    """Shapely geometry (x, z) in mm of all glyphs of position m in print orientation (lift 0)."""
    L = D.shuttle_layout(); s = P.EM / 1000; geoms = []
    for srow in range(1, P.NROWS + 1):         # rev. 0.9.2: all eight rows (rows 5..8, the upper register, were missing)
        k = L[srow - 1][m]
        if k is None:
            continue
        for g, x0 in item_glyphs(k):
            gg = affinity.scale(slug(g), s, s, origin=(0, 0))
            geoms.append(affinity.translate(gg, x0, row_baseline(srow)))
    return unary_union(geoms) if geoms else None


def extents():
    """Per item: ink extent along the line in u relative to the hammer axis (for the hammer window check)."""
    out = {}
    s = P.EM / 1000
    for r in D.ROWS:
        for pair in r:
            for k in pair:
                if k is None:
                    continue
                gs = [affinity.translate(affinity.scale(slug(g), s, s, origin=(0, 0)), x0, 0) for g, x0 in item_glyphs(k)]
                if not gs:
                    continue
                b = unary_union(gs).bounds
                out[str(k)] = (b[0] / P.U, b[2] / P.U, b[1], b[3])
    return out


Y_FACE = P.AXIS_Y + P.R_FACE


def block_print(m, with_relief=True):
    """Block of position m in print orientation (its hammer axis on the +Y ray), lift 0."""
    x0, x1 = P.BLOCK_U0 * P.U, P.BLOCK_U1 * P.U
    yb = Y_FACE - P.RELIEF
    body = geo.box(x0 - 3, x1 + 3, yb - P.BLOCK_DEPTH, yb, P.BLOCK_BOT, P.BLOCK_TOP)
    a0 = math.degrees(math.atan2(x0, P.R_FACE)); a1 = math.degrees(math.atan2(x1, P.R_FACE))
    wedge = geo.sector_xy(0, P.AXIS_Y, 0, 200, a0, a1, P.BLOCK_BOT - 5, P.BLOCK_TOP + 5)
    body = body ^ wedge
    # rev. 0.9.2: the face is a cylinder about the shuttle axis (a flat face let the neighbour's far edge stand proud
    # of the face at print by up to 0.7 mm, right beside the hammer)
    body = body ^ geo.sector_xy(0, P.AXIS_Y, 0, P.R_FACE - P.RELIEF, a0 - 1, a1 + 1, P.BLOCK_BOT - 5, P.BLOCK_TOP + 5, n=96)
    # adjusting screw hole (radial M3) and seat groove handled by the ring
    body = body - geo.cyl((x1 / 2 + x0 / 2, yb - P.BLOCK_DEPTH - 1, (P.BLOCK_TOP + P.BLOCK_BOT) / 2),
                          (x1 / 2 + x0 / 2, yb - P.BLOCK_DEPTH + 6, (P.BLOCK_TOP + P.BLOCK_BOT) / 2), 1.25, 16)
    if not with_relief:
        return body
    g = position_outline(m)
    if g is None:
        return body
    g = g.buffer(0)
    cs = geo.shapely_to_cs(g)
    rel = cs.extrude(P.RELIEF + 1.5).rotate((90, 0, 0)).translate((0, yb + P.RELIEF + 1.0, 0))
    rel = rel ^ geo.sector_xy(0, P.AXIS_Y, 0, P.R_FACE, a0 - 1, a1 + 1, P.BLOCK_BOT - 5, P.BLOCK_TOP + 5, n=96)
    return body + rel


def home_angle(m):
    """CCW rotation (deg, seen from above) of block m in the shuttle frame. rev. 0.9.2: the sign is such that the
    shuttle turned to pos = m (th = (m - 5) STEP CCW) brings block m to print; before, it brought block 10 - m."""
    return -(m - (P.NPOS - 1) / 2) * P.STEP_DEG


def block_home(m, with_relief=True):
    return geo.rotz(block_print(m, with_relief), home_angle(m), 0, P.AXIS_Y)


def block_print_bed(m):
    """Block m laid face up for printing (relief toward +Z), at the origin."""
    b = block_print(m)
    b = b.rotate((-90, 0, 0))     # +Y (face) -> +Z
    lo, hi = b.bounding_box()[:3], b.bounding_box()[3:]
    return b.translate((-lo[0], -lo[1], -lo[2]))
