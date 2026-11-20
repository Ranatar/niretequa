"""Thicken hairlines of a glyph to a minimum stroke width (mm at a given em), keeping thick parts as drawn.
Raster method: ink | dilate(skeleton, r_min); vectorised back with marching squares.
Also usable as a module: slug_geometry(glyphset, name, em_mm, pmin_mm) -> shapely geometry (font units)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import ndimage
from skimage.morphology import skeletonize, disk
from skimage import measure
from shapely.geometry import Polygon
from shapely.ops import unary_union
from PIL import Image, ImageDraw
from glyphgeom import glyph_geom

S = 2.0  # px per font unit


def _raster(geom, bounds, pad):
    minx, miny, maxx, maxy = bounds
    W = int((maxx - minx + 2 * pad) * S) + 1; H = int((maxy - miny + 2 * pad) * S) + 1
    im = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(im)
    polys = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
    tr = lambda xy: [((x - minx + pad) * S, (maxy - y + pad) * S) for x, y in xy]
    for p in polys:
        dr.polygon(tr(p.exterior.coords), fill=255)
        for h in p.interiors:
            dr.polygon(tr(h.coords), fill=0)
    return np.array(im) > 127


def prune(sk, n):
    """Shorten every skeleton branch by n pixels from its free end. Short spurs (forks at thin tips) vanish,
    and the disk of radius n around the new end reaches exactly to where the branch ended, so tips keep their
    length without a bulb."""
    orig = sk.copy()
    sk = sk.copy()
    kern = np.ones((3, 3), int); kern[1, 1] = 0
    for _ in range(n):
        nb = ndimage.convolve(sk.astype(int), kern, mode='constant')
        ends = sk & (nb <= 1)
        if not ends.any():
            break
        sk &= ~ends
    # a component pruned away completely (a dot) keeps one pixel near its middle
    lab, n_lab = ndimage.label(orig, structure=np.ones((3, 3)))
    for i in range(1, n_lab + 1):
        comp = lab == i
        if not (sk & comp).any():
            ys, xs = np.nonzero(comp)
            cy, cx = ys.mean(), xs.mean()
            k = np.argmin((ys - cy) ** 2 + (xs - cx) ** 2)
            sk[ys[k], xs[k]] = True
    return sk


def slug_geometry(glyphset, name, em_mm, pmin_mm):
    g = glyph_geom(glyphset, name)
    rmin = pmin_mm / 2 * 1000.0 / em_mm          # font units
    pad = rmin + 20
    b = g.bounds
    m = _raster(g, b, pad)
    sk = skeletonize(m)
    rad = max(1, int(round(rmin * S)))
    sk = prune(sk, rad)
    thick = m | (ndimage.distance_transform_edt(~sk) <= rad)
    cs = measure.find_contours(np.pad(thick, 1).astype(float), 0.5)
    minx, miny, maxx, maxy = b
    geom = None
    for c in cs:
        pts = [((col - 1) / S + minx - pad, maxy + pad - (row - 1) / S) for row, col in c]
        if len(pts) < 4:
            continue
        p = Polygon(pts).buffer(0)
        geom = p if geom is None else geom.symmetric_difference(p)
    return geom.simplify(0.6), g
