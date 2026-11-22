"""rev. 0.14: marks raised into the bowl of lambe (and alda).

Lambe's bowl goes below the line, so a mark set under it (the two dots of y, the doubling bar) lies on its stroke.
Alcarin has a doubling bar drawn inside the bowl (uniE051.lambe); the other marks and the other fonts have none.
This module makes such glyphs by raising the plain mark: a synthetic glyph '<mark>.inlambe' is the mark moved up so
that its middle stands in the middle of the bowl, on lambe's bottom axis. The glyph set is wrapped (VarGlyphSet), so
every consumer of glyph names (thickening, type blocks, the page, the document) draws it as any other glyph.

Where the bowl's middle is: on a vertical line through lambe's bottom axis, the gap between the bowl's lowest stroke
and the stroke above it (Alcarin: its own uniE051.lambe gives the height, and the dots follow it)."""
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

SUFFIX = '.inlambe'


class _Shifted:
    def __init__(self, g, dx, dy):
        self.g, self.dx, self.dy = g, dx, dy
        self.width = getattr(g, 'width', 0)

    def draw(self, pen):
        self.g.draw(TransformPen(pen, (1, 0, 0, 1, self.dx, self.dy)))


class VarGlyphSet:
    """A glyph set plus synthetic glyphs: name -> (base name, dx, dy)."""
    def __init__(self, gs, extra=None):
        self.gs = gs
        self.extra = dict(extra or {})

    def add(self, name, base, dx, dy):
        self.extra[name] = (base, dx, dy)

    def __getitem__(self, name):
        if name in self.extra:
            b, dx, dy = self.extra[name]
            return _Shifted(self[b], dx, dy)          # a synthetic glyph may stand on another one
        return self.gs[name]

    def __contains__(self, name):
        return name in self.extra or name in self.gs

    def keys(self):
        return list(self.gs.keys()) + list(self.extra)

    def get(self, name, default=None):
        return self[name] if name in self else default


def bounds(gs, name):
    p = BoundsPen(gs)
    gs[name].draw(p)
    return p.bounds


def bowl_middle(gs, lambe, x):
    """y of the middle of lambe's bowl on the vertical through x (font units), or None."""
    from glyphgeom import glyph_geom
    from shapely.geometry import LineString
    g = glyph_geom(gs, lambe)
    b = g.bounds
    cut = g.intersection(LineString([(x, b[1] - 10), (x, b[3] + 10)]))
    segs = []
    for s in getattr(cut, 'geoms', [cut]):
        if s.is_empty or s.length == 0:
            continue
        ys = [p[1] for p in s.coords]
        segs.append((min(ys), max(ys)))
    segs.sort()
    if len(segs) < 2:
        return None
    return 0.5 * (segs[0][1] + segs[1][0])


def bowl_centre(gs, lambe, res=4.0):
    """(x, y) of the middle of lambe's bowl: the background point farthest from the ink among those that have ink
    above, below and to the left (the bowl opens to the lower right); font units, or None."""
    import numpy as np
    from scipy import ndimage
    from PIL import Image, ImageDraw
    from glyphgeom import glyph_geom
    g = glyph_geom(gs, lambe)
    x0, y0, x1, y1 = g.bounds
    W, H = int((x1 - x0) / res) + 3, int((y1 - y0) / res) + 3
    im = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(im)
    tr = lambda xy: [((x - x0) / res + 1, (y1 - y) / res + 1) for x, y in xy]
    for p in getattr(g, 'geoms', [g]):
        if p.geom_type != 'Polygon':
            continue
        dr.polygon(tr(p.exterior.coords), fill=255)
        for h in p.interiors:
            dr.polygon(tr(h.coords), fill=0)
    ink = np.array(im) > 127
    above = np.maximum.accumulate(ink, axis=0)                 # ink somewhere above (rows grow downward)
    below = np.maximum.accumulate(ink[::-1], axis=0)[::-1]
    left = np.maximum.accumulate(ink, axis=1)
    ok = ~ink & above & below & left
    if not ok.any():
        return None
    d = ndimage.distance_transform_edt(~ink) * ok
    r, c = np.unravel_index(np.argmax(d), d.shape)
    return x0 + (c - 1) * res, y1 - (r - 1) * res


def place_in(gs, mark, anchor_x, lambe, axis_x, centre=None):
    """(dx, dy) that put the middle of `mark` (set with its anchor on lambe's bottom axis) on the bowl's middle."""
    c = centre or bowl_centre(gs, lambe)
    if c is None:
        return None
    b = bounds(gs, mark)
    return c[0] - (axis_x + 0.5 * (b[0] + b[2]) - anchor_x), c[1] - 0.5 * (b[1] + b[3])


def overlap(gs, mark, dx, dy, anchor_x, lambe, axis_x):
    """Share of the moved mark's ink that lies on lambe's ink."""
    from glyphgeom import glyph_geom
    from shapely import affinity
    m = affinity.translate(glyph_geom(gs, mark), axis_x - anchor_x + dx, dy)
    a = m.area
    return m.intersection(glyph_geom(gs, lambe)).area / a if a else 0.0


def raise_into(gs, mark, lambe, x, y_mid=None):
    """dy that puts the middle of `mark` at the middle of lambe's bowl (or at y_mid)."""
    y = bowl_middle(gs, lambe, x) if y_mid is None else y_mid
    if y is None:
        return None
    b = bounds(gs, mark)
    return y - 0.5 * (b[1] + b[3])
