"""Small solid-geometry helpers on top of manifold3d (mm, right-handed: X along the line, Y back, Z up)."""
import math
import numpy as np
from manifold3d import Manifold, CrossSection

SEG = 48


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def cbox(cx, cy, cz, sx, sy, sz):
    return box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, cz - sz / 2, cz + sz / 2)


def _rot_to(v):
    """3x4 affine that maps +Z onto unit vector v."""
    v = np.asarray(v, float); v = v / np.linalg.norm(v)
    z = np.array([0, 0, 1.0])
    c = float(np.dot(z, v))
    if c > 1 - 1e-12:
        R = np.eye(3)
    elif c < -1 + 1e-12:
        R = np.diag([1, -1, -1.0])
    else:
        a = np.cross(z, v); s = np.linalg.norm(a); a = a / s
        K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
        R = np.eye(3) + s * K + (1 - c) * K @ K
    return R


def affine(R, t):
    M = np.zeros((3, 4)); M[:, :3] = R; M[:, 3] = t
    return M


def cyl(p0, p1, r, seg=SEG, r1=None):
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float)
    h = float(np.linalg.norm(p1 - p0))
    m = Manifold.cylinder(h, r, r if r1 is None else r1, seg)
    return m.transform(affine(_rot_to(p1 - p0), p0))


def zcyl(x, y, z0, z1, r, seg=SEG):
    return Manifold.cylinder(z1 - z0, r, r, seg).translate((x, y, z0))


def tube(x, y, z0, z1, r_out, r_in, seg=SEG):
    return zcyl(x, y, z0, z1, r_out, seg) - zcyl(x, y, z0 - 1, z1 + 1, r_in, seg)


def extrude_xy(polys, z0, z1):
    """polys: list of rings (lists of (x,y)); even-odd via CrossSection fill rule positive with orientation fix."""
    cs = CrossSection(polys, fillrule=__import__('manifold3d').FillRule.EvenOdd)
    return cs.extrude(z1 - z0).translate((0, 0, z0))


def shapely_to_cs(geom):
    from manifold3d import FillRule
    rings = []
    gs = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
    for p in gs:
        if p.is_empty:
            continue
        rings.append(list(p.exterior.coords)[:-1])
        for h in p.interiors:
            rings.append(list(h.coords)[:-1])
    return CrossSection(rings, fillrule=FillRule.EvenOdd)


def rotz(m, deg, cx=0.0, cy=0.0):
    return m.translate((-cx, -cy, 0)).rotate((0, 0, deg)).translate((cx, cy, 0))


def rotx(m, deg, cy=0.0, cz=0.0):
    return m.translate((0, -cy, -cz)).rotate((deg, 0, 0)).translate((0, cy, cz))


def roty(m, deg, cx=0.0, cz=0.0):
    return m.translate((-cx, 0, -cz)).rotate((0, deg, 0)).translate((cx, 0, cz))


def sector_xy(cx, cy, r0, r1, a0, a1, z0, z1, n=None):
    """Annular sector in XY, angles in degrees measured from +Y toward +X (clockwise seen from above)."""
    n = n or max(8, int(abs(a1 - a0) / 2) + 2)
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n); pts.append((cx + r1 * math.sin(a), cy + r1 * math.cos(a)))
    for i in range(n, -1, -1):
        a = math.radians(a0 + (a1 - a0) * i / n); pts.append((cx + r0 * math.sin(a), cy + r0 * math.cos(a)))
    if r0 <= 0:
        pts = pts[:n + 1] + [(cx, cy)]
    # make counter-clockwise
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    if area < 0:
        pts = pts[::-1]
    return CrossSection([pts]).extrude(z1 - z0).translate((0, 0, z0))


def union(parts):
    parts = [p for p in parts if p is not None and not p.is_empty()]
    if not parts:
        return Manifold()
    return Manifold.batch_boolean(parts, __import__('manifold3d').OpType.Add)


def gear_profile(z, m, cx=0, cy=0, add=1.0, ded=1.25, pts_per_tooth=10, phase=0.0):
    """Simple involute-ish spur gear outline (good enough for layout and printing sketches)."""
    rp = m * z / 2; ra = rp + add * m; rf = max(0.5, rp - ded * m)
    out = []
    for k in range(z):
        a0 = 2 * math.pi * k / z + phase
        tw = math.pi / z
        seq = [(rf, a0 - 0.62 * tw), (rp, a0 - 0.5 * tw), (ra, a0 - 0.28 * tw), (ra, a0 + 0.28 * tw),
               (rp, a0 + 0.5 * tw), (rf, a0 + 0.62 * tw)]
        for r, a in seq:
            out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return CrossSection([out])


def _ccw(pts):
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    return pts if area > 0 else pts[::-1]


def ratchet_profile(n, r_root, r_tip, cx=0, cy=0):
    out = []
    for k in range(n):
        a0 = 2 * math.pi * k / n; a1 = 2 * math.pi * (k + 1) / n
        out.append((cx + r_root * math.cos(a0), cy + r_root * math.sin(a0)))
        out.append((cx + r_tip * math.cos(a1 - 1e-3), cy + r_tip * math.sin(a1 - 1e-3)))
    return CrossSection([_ccw(out)])


def to_arrays(m):
    mesh = m.to_mesh()
    return np.asarray(mesh.vert_properties)[:, :3].astype(np.float64), np.asarray(mesh.tri_verts).astype(np.int64)
