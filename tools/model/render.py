"""Tiny software renderer (z-buffer, flat shading, outlines) for assembly pictures without a GPU."""
import numpy as np
from numba import njit
from PIL import Image


@njit(cache=True)
def _raster(px, py, pz, tris, cols, W, H, zbuf, img, ids, tid0):
    for t in range(tris.shape[0]):
        i0, i1, i2 = tris[t, 0], tris[t, 1], tris[t, 2]
        x0, y0, z0 = px[i0], py[i0], pz[i0]
        x1, y1, z1 = px[i1], py[i1], pz[i1]
        x2, y2, z2 = px[i2], py[i2], pz[i2]
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12:
            continue
        xmin = max(int(min(x0, x1, x2)), 0); xmax = min(int(max(x0, x1, x2)) + 1, W - 1)
        ymin = max(int(min(y0, y1, y2)), 0); ymax = min(int(max(y0, y1, y2)) + 1, H - 1)
        for yy in range(ymin, ymax + 1):
            for xx in range(xmin, xmax + 1):
                fx = xx + 0.5; fy = yy + 0.5
                w0 = ((y1 - y2) * (fx - x2) + (x2 - x1) * (fy - y2)) / den
                w1 = ((y2 - y0) * (fx - x2) + (x0 - x2) * (fy - y2)) / den
                w2 = 1.0 - w0 - w1
                if w0 < -1e-6 or w1 < -1e-6 or w2 < -1e-6:
                    continue
                z = w0 * z0 + w1 * z1 + w2 * z2
                if z < zbuf[yy, xx]:
                    zbuf[yy, xx] = z
                    img[yy, xx, 0] = cols[t, 0]; img[yy, xx, 1] = cols[t, 1]; img[yy, xx, 2] = cols[t, 2]
                    ids[yy, xx] = tid0[t]


def look(eye, target, up=(0, 0, 1)):
    eye = np.asarray(eye, float); target = np.asarray(target, float)
    f = target - eye; f /= np.linalg.norm(f)
    r = np.cross(f, up); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return eye, r, u, f


def render(objs, view, W=1600, H=1100, scale=None, persp=None, light=(-0.4, -0.7, 0.9), bg=(255, 255, 255),
           outline=True, margin=0.04, return_ids=False):
    """objs: list of (V, F, rgb, id). view: (eye, target[, up]). Orthographic unless persp=fov_deg."""
    eye, r, u, f = look(*view)
    L = np.asarray(light, float); L /= np.linalg.norm(L)
    allp = []
    for V, F, c, oid in objs:
        d = V - eye
        allp.append(np.stack([d @ r, d @ u, d @ f], 1))
    cat = np.concatenate(allp)
    if persp:
        k = 1 / np.tan(np.radians(persp) / 2)
        proj = lambda P: np.stack([P[:, 0] / P[:, 2] * k, P[:, 1] / P[:, 2] * k, P[:, 2]], 1)
    else:
        proj = lambda P: P
    cp = proj(cat)
    lo = cp[:, :2].min(0); hi = cp[:, :2].max(0)
    s = scale or min(W * (1 - 2 * margin) / (hi[0] - lo[0]), H * (1 - 2 * margin) / (hi[1] - lo[1]))
    off = np.array([W / 2, H / 2]) - s * (lo + hi) / 2 * np.array([1, 1])
    zbuf = np.full((H, W), np.inf); img = np.zeros((H, W, 3), np.uint8); img[:] = bg
    ids = np.full((H, W), -1, np.int64)
    for (V, F, c, oid), P in zip(objs, allp):
        if len(F) == 0:
            continue
        Q = proj(P)
        px = Q[:, 0] * s + off[0]; py = H - (Q[:, 1] * s + off[1]); pz = Q[:, 2]
        a = V[F[:, 1]] - V[F[:, 0]]; b = V[F[:, 2]] - V[F[:, 0]]
        n = np.cross(a, b); nn = np.linalg.norm(n, axis=1); nn[nn == 0] = 1; n = n / nn[:, None]
        # two-sided lighting (toward viewer)
        sgn = np.sign(-(n @ f)); sgn[sgn == 0] = 1; n = n * sgn[:, None]
        lam = 0.45 + 0.55 * np.clip(n @ L, 0, 1)
        cols = np.clip(np.asarray(c, float)[None, :] * lam[:, None], 0, 255).astype(np.uint8)
        _raster(px, py, pz, F.astype(np.int64), cols, W, H, zbuf, img, ids, np.full(len(F), oid, np.int64))
    if outline:
        e = np.zeros((H, W), bool)
        e[:, 1:] |= ids[:, 1:] != ids[:, :-1]; e[1:, :] |= ids[1:, :] != ids[:-1, :]
        zz = np.where(np.isfinite(zbuf), zbuf, 1e9)
        dz = np.zeros((H, W)); dz[:, 1:] = np.abs(zz[:, 1:] - zz[:, :-1]); dz[1:, :] = np.maximum(dz[1:, :], np.abs(zz[1:, :] - zz[:-1, :]))
        e |= dz > 3.0
        img[e] = (img[e] * 0.35).astype(np.uint8)
    if return_ids:
        return Image.fromarray(img), s, ids
    return Image.fromarray(img), s
