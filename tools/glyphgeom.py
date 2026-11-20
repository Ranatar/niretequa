"""Glyph outlines of Alcarin as shapely geometry (font units, y up).
Even-odd combination of flattened contours; works for CFF and TrueType outlines."""
from fontTools.pens.basePen import BasePen
from shapely.geometry import Polygon
from shapely.ops import unary_union


class FlattenPen(BasePen):
    def __init__(self, glyphSet, steps=24):
        super().__init__(glyphSet); self.contours = []; self.cur = []; self.steps = steps

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps; mt = 1 - t
            self.cur.append((mt**3*p0[0] + 3*mt*mt*t*p1[0] + 3*mt*t*t*p2[0] + t**3*p3[0],
                             mt**3*p0[1] + 3*mt*mt*t*p1[1] + 3*mt*t*t*p2[1] + t**3*p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps; mt = 1 - t
            self.cur.append((mt*mt*p0[0] + 2*mt*t*p1[0] + t*t*p2[0], mt*mt*p0[1] + 2*mt*t*p1[1] + t*t*p2[1]))

    def _closePath(self):
        if len(self.cur) >= 3:
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


def glyph_geom(glyphset, name):
    pen = FlattenPen(glyphset); glyphset[name].draw(pen)
    geom = None
    for c in pen.contours:
        p = Polygon(c).buffer(0)
        geom = p if geom is None else geom.symmetric_difference(p)
    return geom
