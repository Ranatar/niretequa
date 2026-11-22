"""rev. 0.10: the code is read from the shuttle.

Every shuttle position carries a code comb on the inner face of the ring. For each of its eight cells (rows) the comb
has three tabs -- W, B and C -- whose faces stand at r = READ_R0 + READ_C0 + READ_K v from the shuttle axis
(v = w - 4, b, c). The reading head hangs from a post on the U-frame into the ring, in front of the shaft; once the
shuttle is fixed, its three feelers go out along the strike ray until each meets its tab. Every feeler pulls the inner
wire of a Bowden cable: W pulls the W frame down (the escapement stop and sector W follow it as before; a latch holds
the frame till the feed), B and C pull two short slides under the followers of sectors B and C. The B and C gauge
frames are gone; the code plates keep only R (reset and cycle trip), O and N, and the spaces their W.
A font is then the eleven type blocks and the eleven combs; nothing under the keys depends on it."""
import math
import numpy as np
import params as P
import data as D
import geo
import typeblocks as TB
from geo import box, cyl, zcyl, rotz, union

# ---------------------------------------------------------------------------------------------- geometry
Z_READ = P.BLOCK_TOP - (P.HOME_ROW + 0.5) * P.RH      # centre of the printed row at the line (= ZP - 0.04)
CH = P.READ_CH
FEELER = (1.6, 2.0)            # steel strip, width (x) and height (z)
FEELER_L = 22.0
HEAD_Y = (13.0, 34.5)          # head block, radii along the strike ray (inside the tab tips at 36.5)
HEAD_X = 3.4
HEAD_Z = (Z_READ - 6.0, Z_READ + 6.5)
STEM_XY = (12.0, P.AXIS_Y + 22.0)                     # vertical stem inside the ring, right of the strike ray
STEM_R = 3.5
ARM_Z = (325.0, 331.0)                                # over the ring top at the highest lift (321.7)
POST_X = (72.0, 78.0)
POST_Y = (STEM_XY[1] - 3.5, STEM_XY[1] + 3.5)


def code_v(item):
    """(vW, vB, vC) of an advancing item, or None for dead marks and empty cells."""
    if item is None:
        return None
    it = D.ITEMS[item]
    if it['kind'] not in D.ADV:
        return None
    return (it['w'] - P.W_OFFSET, it['b'], it['c'])


def face_r(v):
    return P.READ_R0 + P.READ_C0 + P.READ_K * v


def cells(m):
    """[(row index 0..7, (vW, vB, vC))] for position m (only advancing items carry tabs)."""
    rows = D.shuttle_layout()
    out = []
    for r in range(P.NROWS):
        v = code_v(rows[r][m])
        if v is not None:
            out.append((r, v))
    return out


def row_zc(r):
    return P.BLOCK_TOP - (r + 0.5) * P.RH


PIN_Z = (P.BLOCK_TOP + 0.6, P.BLOCK_BOT - 1.0)   # comb pins: in the solid band over the top window and under the bottom
PIN_ROWS = (0, 1)              # (index into PIN_Z)
PIN_R = 1.0


def comb_print_frame(m):
    """Comb of position m in the print frame (its cells on the +Y ray), lift 0."""
    r_in = P.RING_R0 - P.COMB_T
    half_sp = math.degrees(P.COMB_W / 2 / P.RING_R0)
    z0, z1 = P.BLOCK_BOT - 2.3, P.BLOCK_TOP + 1.8
    spine = geo.sector_xy(0, P.AXIS_Y, r_in, P.RING_R0 - 0.05, -half_sp, half_sp, z0, z1)
    tabs = []
    for r, v in cells(m):
        for ch, vv in zip(CH, v):
            rf = face_r(vv)
            ha = math.degrees(P.TAB_W / 2 / rf)
            zc = row_zc(r) + P.READ_DZ[ch]
            tabs.append(geo.sector_xy(0, P.AXIS_Y, rf, r_in + 0.3, -ha, ha, zc - P.TAB_H / 2, zc + P.TAB_H / 2, n=8))
    # pin bosses (the pins go radially into the ring band between two windows)
    for k in PIN_ROWS:
        zp = PIN_Z[k]
        tabs.append(geo.sector_xy(0, P.AXIS_Y, r_in - 1.2, r_in + 0.3, -half_sp, half_sp, zp - 1.1, zp + 1.1))
    m_ = spine + union(tabs) if tabs else spine
    for k in PIN_ROWS:
        zp = PIN_Z[k]
        m_ = m_ - cyl((0, P.AXIS_Y + r_in - 1.5, zp), (0, P.AXIS_Y + P.RING_R0 + 0.1, zp), PIN_R + 0.03, 12)
    return m_


def comb_home(m):
    return rotz(comb_print_frame(m), TB.home_angle(m), 0, P.AXIS_Y)


def pin_home(m, k):
    zp = PIN_Z[k]
    r_in = P.RING_R0 - P.COMB_T
    p = cyl((0, P.AXIS_Y + r_in - 1.2, zp), (0, P.AXIS_Y + P.RING_R0 + 3.0, zp), PIN_R, 12)
    return rotz(p, TB.home_angle(m), 0, P.AXIS_Y)


def ring_pin_holes():
    return union([pin_home(m, k) for m in range(P.NPOS) for k in PIN_ROWS])


def comb_print_bed(m):
    """Laid on its edge: the tabs' radial faces lie in the bed plane (in-plane accuracy of the printer)."""
    c = comb_print_frame(m).rotate((0, 90, 0))
    b = c.bounding_box()
    return c.translate((-b[0], -b[1], -b[2]))


# ---------------------------------------------------------------------------------------------- the head
def feeler_mesh(ch, t):
    """Feeler ch with its tip t mm beyond rest (rest tip at READ_R0 on the strike ray)."""
    zc = Z_READ + P.READ_DZ[ch]
    y1 = P.AXIS_Y + P.READ_R0 + t
    w, h = FEELER
    m = box(-w / 2, w / 2, y1 - FEELER_L, y1, zc - h / 2, zc + h / 2)
    # tail lug: the retract bar hooks it, the wire of the channel is clamped in it
    m = m + box(-2.2, w / 2, y1 - FEELER_L, y1 - FEELER_L + 2.0, zc - h / 2, zc + h / 2 + 1.0)
    return m


def head_mesh():
    y0, y1 = P.AXIS_Y + HEAD_Y[0], P.AXIS_Y + HEAD_Y[1]
    hb = box(-HEAD_X, HEAD_X, y0, y1, *HEAD_Z)
    # bridge to the stem, over the block
    hb = hb + box(-HEAD_X, STEM_XY[0] + 2.0, STEM_XY[1] - 3.0, STEM_XY[1] + 3.0, HEAD_Z[1] - 3.0, HEAD_Z[1])
    # slots for the feelers (0.1 mm clearance) and the room for their tails, springs and the retract bar
    w, h = FEELER
    for ch in CH:
        zc = Z_READ + P.READ_DZ[ch]
        hb = hb - box(-w / 2 - 0.1, w / 2 + 0.1, y0 - 1, y1 + 1, zc - h / 2 - 0.1, zc + h / 2 + 0.1)
        hb = hb - box(-w / 2 - 0.1, w / 2 + 0.1, y0 - 1.0, y0 + 16.5, zc - h / 2 - 0.1, zc + h / 2 + 1.2)   # the tail lug's lane
    hb = hb - box(-HEAD_X + 1.0, -0.8, y0 - 1.0, y0 + 18.5, HEAD_Z[0] + 1.0, HEAD_Z[1] - 1.0)   # retract bar lane
    return hb


def retract_bar_mesh(t):
    """The bar that pulls all three feelers back by their tail lugs. At home it holds the lugs; while the feelers read,
    the cam lets it go out by the full stroke, so no feeler is held by it (t = bar travel)."""
    yl = P.AXIS_Y + P.READ_R0 - FEELER_L + 2.0          # front face of the lugs at rest
    return box(-HEAD_X + 1.2, -1.2, yl, yl + 1.5, HEAD_Z[0] + 1.3, HEAD_Z[1] - 1.3).translate((0, t, 0))


def stem_mesh():
    x, y = STEM_XY
    s = geo.tube(x, y, HEAD_Z[1] - 3.0, ARM_Z[1], STEM_R, STEM_R - 1.0)
    arm = box(x - 3.0, POST_X[1], y - 3.0, y + 3.0, *ARM_Z)
    return s + arm


def post_mesh():
    z0 = P.UF_Z + P.UF_T
    p = box(*POST_X, *POST_Y, z0, ARM_Z[1])
    p = p - box(POST_X[0] + 1.5, POST_X[1] - 1.5, POST_Y[0] + 1.5, POST_Y[1] - 1.5, z0 + 8.0, ARM_Z[1] + 1.0)   # hollow: the cables
    p = p - box(POST_X[0] - 1.0, POST_X[0] + 2.0, POST_Y[0] + 1.5, POST_Y[1] - 1.5, z0 + 8.0, z0 + 20.0)       # their window at the foot
    foot = box(POST_X[0] - 8.0, POST_X[1] + 8.0, POST_Y[0] - 6.0, POST_Y[1] + 6.0, z0, z0 + 4.0)
    return p + foot


def travels(st):
    """Feeler travels (mm from rest) in a state; st.feel holds them (0 at rest)."""
    return {ch: st.feel.get(ch, 0.0) for ch in CH}


def reader_parts(st, Part, COL):
    """The combs ride the shuttle; the head, stem, arm and post ride the U-frame."""
    parts = []
    th = st.th(); dx = -st.slide(); lz = st.lift()
    TS = lambda m: rotz(m, th, 0, P.AXIS_Y).translate((dx, 0, lz))
    TU = lambda m: m.translate((dx, 0, 0))
    for m in range(P.NPOS):
        parts.append(Part(f'code comb {m}', 'shuttle', 'print', TS(_cached(f'comb{m}', lambda m=m: comb_home(m))), (200, 120, 160),
                          f'code_comb_{m:02d}', 'PETG', note='кодовая гребёнка позиции: 8 клеток по три зубца W, B, C; печатается на ребре',
                          mov='shuttle', printable=lambda m=m: comb_print_bed(m)))
        for k in PIN_ROWS:
            parts.append(Part(f'comb pin {m} {k}', 'shuttle', 'buy', TS(_cached(f'cpin{m}{k}', lambda m=m, k=k: pin_home(m, k))), COL['steel'],
                              'pin2x5', 'сталь', 'штифт 2×5 мм (гребёнка на кольце)', mov='shuttle'))
    parts.append(Part('reading head', 'reader', 'print', TU(_cached('head', head_mesh)), (120, 140, 190), 'read_head', 'PETG',
                      note='головка чтения: три паза щупов, пружины, тяга отвода', mov='uframe'))
    t = travels(st)
    for ch in CH:
        parts.append(Part(f'feeler {ch}', 'reader', 'buy', TU(feeler_mesh(ch, t[ch])), COL['steel'], 'feeler_strip', 'сталь',
                          'щуп: полоса 1,6×2×22 мм, лапка с зажимом троса; на носу эластомерный наконечник 0,5 мм (ред. 0.14, ступень 2б: отскок от зубца ≤ 0,3 мм)', mov=f'feel{ch}'))
    parts.append(Part('reading retract bar', 'reader', 'buy', TU(retract_bar_mesh(P.READ_TRAVEL if max(t.values()) > 0 else 0.0)), COL['steel'], 'strip_retract', 'сталь',
                      'тяга отвода щупов (полоса 1,5 мм)', mov='feelbar'))
    parts.append(Part('reading stem and arm', 'reader', 'print', TU(_cached('stem', stem_mesh)), (120, 140, 190), 'read_stem', 'PETG',
                      note='стойка головки внутри кольца и кронштейн над челноком; внутри — четыре троса', mov='uframe'))
    parts.append(Part('reading post', 'reader', 'print', TU(_cached('post', post_mesh)), (120, 140, 190), 'read_post', 'PETG',
                      note='стойка на плите узла, справа от точки печати; внутри — оболочки тросов', mov='uframe'))
    return parts


_cache = {}


def _cached(name, fn):
    if name not in _cache:
        _cache[name] = fn()
    return _cache[name]


# ---------------------------------------------------------------------------------------------- audit
def audit():
    """For every advancing item: put its cell on the strike ray, send each feeler out along the ray and find where it
    first meets the comb (ray cast against the comb mesh); the travel must equal READ_C0 + READ_K v, and every other
    comb and tab must stay clear of the feeler path."""
    import trimesh
    rows = D.shuttle_layout()
    res = []
    for m in range(P.NPOS):
        th = (m - (P.NPOS - 1) / 2) * P.STEP_DEG
        combs = [rotz(comb_home(mm), th, 0, P.AXIS_Y) for mm in range(P.NPOS)]
        V, F = geo.to_arrays(union(combs))
        tm = trimesh.Trimesh(V, F, process=False)
        for r in range(P.NROWS):
            item = rows[r][m]
            v = code_v(item)
            if v is None:
                continue
            lz = (r - P.HOME_ROW) * P.RH
            out = dict(item=item, label=D.ITEMS[item]['label'], pos=m, row=r + 1, v=list(v), t=[], ok=True)
            for ch, vv in zip(CH, v):
                z = Z_READ + P.READ_DZ[ch] - lz
                hits = []
                for xo in (-FEELER[0] / 2 + 0.05, 0.0, FEELER[0] / 2 - 0.05):
                    for zo in (-FEELER[1] / 2 + 0.05, 0.0, FEELER[1] / 2 - 0.05):
                        loc, _, _ = tm.ray.intersects_location([[xo, P.AXIS_Y + P.READ_R0, z + zo]], [[0, 1, 0]])
                        hits.append(min(loc[:, 1]) - (P.AXIS_Y + P.READ_R0) if len(loc) else np.inf)
                t_read = min(hits)
                want = P.READ_C0 + P.READ_K * vv
                # the whole tip face must land on the tab (no corner of the feeler on another face)
                ok = abs(t_read - want) < 0.02 and max(hits) - min(hits) < 0.05
                out['t'].append(round(float(t_read), 3))
                out['ok'] = out['ok'] and ok
            res.append(out)
    return res


def mass_inertia():
    """Mass (g) and moment of inertia about the shuttle axis (kg mm2) of all combs (PETG, solid)."""
    import trimesh
    rho = 1.27e-3
    M = I = 0.0
    for m in range(P.NPOS):
        V, F = geo.to_arrays(comb_home(m))
        tm = trimesh.Trimesh(V, F, process=False)
        tm.density = rho
        M += tm.mass
        c = tm.center_mass
        I += tm.moment_inertia[2, 2] + tm.mass * (c[0] ** 2 + (c[1] - P.AXIS_Y) ** 2)   # about the shuttle axis
    return M, I * 1e-3          # g, kg mm2 (g mm2 -> kg mm2)


# ---------------------------------------------------------------------------------------------- receivers
# B and C: short slides under the followers of sectors B and C (they replace the beams of the old B and C frames);
# W: the wire pulls the escapement rod Y forward, beside the W follower (which the spaces still drive through frame W).
SLIDE_X = {'B': 141.0, 'C': 146.0}
SLIDE_Y = (-341.0, -329.0)
SLIDE_Z = (13.0, 42.0)          # at rest (top = top of the old beams)
SLIDE_RODS_Y = (-338.8, -331.2)
STOP_Z = (0.0, 3.0)             # Bowden stops under the slides (C at its 9 units ends 1 mm over it)


def slide_mesh(name):
    x = SLIDE_X[name]
    m = box(x - 2.0, x + 2.0, *SLIDE_Y, *SLIDE_Z)
    for y in SLIDE_RODS_Y:
        m = m - zcyl(x, y, SLIDE_Z[0] - 1, SLIDE_Z[1] - 5.5, 1.05, 12)     # blind holes on the guide rods
    return m


def receivers(st, Part, COL, LK=None):
    parts = []
    for name in ('B', 'C'):
        s = st.frames.get(name, 0.0)
        x = SLIDE_X[name]
        parts.append(Part(f'read slide {name}', 'reader', 'print', slide_mesh(name).translate((0, 0, -s)), (120, 140, 190),
                          f'read_slide_{name}', 'PETG', note=f'ползунок {name}: под роликом повторителя сектора {name}, тянется тросом',
                          mov=f'slide{name}'))
        rods = union([zcyl(x, y, STOP_Z[1], SLIDE_Z[1] - 5.5 - 9.5, 1.0, 12) for y in SLIDE_RODS_Y])
        parts.append(Part(f'read slide {name} guides', 'reader', 'buy', rods, COL['steel'], 'rod2x25', 'сталь',
                          'направляющие ползунка 2 мм'))
        stop = box(x - 2.5, x + 2.5, SLIDE_Y[0] - 1.0, SLIDE_Y[1] + 1.0, *STOP_Z)
        parts.append(Part(f'read slide {name} stop', 'reader', 'print', stop, (110, 112, 120), 'read_slide_stop', 'PETG',
                          note='колодка: упор оболочки троса и основания направляющих'))
    return parts


def post_fittings(st, Part, COL):
    """Four Bowden housing ends on the post foot (retract, W, B, C)."""
    dx = -st.slide()
    z0 = P.UF_Z + P.UF_T + 4.0
    parts = []
    for i, ch in enumerate(('R',) + CH):
        x = POST_X[0] - 5.0 + i * 0.0
        y = POST_Y[0] - 4.0 + i * 0.0
        f = zcyl(POST_X[0] - 4.0 + 4.0 * i, POST_Y[0] - 3.0, z0, z0 + 6.0, 1.8, 12)
        parts.append(Part(f'read cable end {ch}', 'reader', 'buy', f.translate((dx, 0, 0)), COL['buy'], 'bowden_end', 'сталь',
                          'наконечник оболочки троса Ø3,5', mov='uframe'))
    return parts


def cell_code(pos, row):
    """(vW, vB, vC) of the item at shuttle position pos, row index row (0..7), or None."""
    if not (0 <= row < P.NROWS and 0 <= pos < P.NPOS):
        return None
    return code_v(D.shuttle_layout()[int(row)][int(pos)])


def read_state(v, f_free):
    """Feeler travels and receiver travels when the cam lets the feelers out by f_free (0..1 of the full stroke) over
    a cell with code v: each feeler stops on its tab; the receivers move once the lost motion C0 is taken up."""
    feel, frames = {}, {}
    for ch, vv in zip(CH, v):
        t = min(f_free * P.READ_TRAVEL, P.READ_C0 + P.READ_K * vv)
        feel[ch] = t
        frames['Wr' if ch == 'W' else ch] = max(0.0, t - P.READ_C0)
    return feel, frames
