"""Parts of the TPM-2 layout model. Every builder returns Part objects in world coordinates for a State.
kind: 'print' (FDM), 'buy' (purchased), 'cut' (cut from stock), 'ref' (paper, ribbon: not made)."""
import math
from dataclasses import dataclass, field
import numpy as np
from manifold3d import OpType, CrossSection, Manifold, JoinType
import links as LK
import params as P
import data as D
import geo
import typeblocks as TB
import relief as RL
import reader as RD
from geo import box, cbox, cyl, zcyl, union, rotz, rotx

COL = {
    'frame': (175, 180, 188), 'buy': (120, 126, 136), 'steel': (150, 155, 165), 'key': (60, 62, 70),
    'lever': (214, 160, 72), 'plate': (232, 196, 120), 'bail': (96, 150, 200), 'sector': (90, 170, 150),
    'pin': (200, 90, 80), 'uframe': (130, 160, 210), 'shuttle': (210, 180, 130), 'type': (190, 150, 95),
    'drum': (160, 200, 220), 'hammer': (200, 110, 90), 'carriage': (150, 190, 140), 'paper': (248, 248, 240),
    'ribbon': (40, 40, 60), 'esc': (180, 140, 200), 'grub': (70, 70, 80),
}


@dataclass
class State:
    theta: float = None          # shuttle rotation, deg CCW; None -> from 'pos'
    pos: float = (P.NPOS - 1) / 2   # shuttle position (0..10); home = 5
    row: float = P.REST_ROW      # shuttle row at the print line (0..7); rev. 0.8: rests at -1, under the line
    slide_u: float = 0.0         # retraction of the print unit, u (unit moves -X)
    car: float = P.CAR_X_START   # carriage x offset
    pressed: dict = field(default_factory=dict)   # lever n -> fraction 0..1
    frames: dict = field(default_factory=dict)    # bail name -> travel mm (down)
    tier: int = 0
    hammer: float = 0.0          # 0 cocked, 1 striking
    cycle: float = 0.0           # cycle shaft angle, deg
    detent: float = 0.0          # 0 out, 1 engaged
    bits: tuple = ()             # raised selector bars: ('r1','r2','r4','r8','l1','l2','l4')
    ribbon: float = None         # 0 ribbon down (rest), 1 raised for the blow; None -> follows the detent cam
    cock: float = 0.0            # hammer spring cocking (cam), 0..1
    lock: float = 0.0            # lock bail (0 out, 1 in while the cycle runs)
    mem: dict = field(default_factory=dict)       # rev. 0.8b: memory held by sectors B, C, W (units; W as w - 4)
    esc_mem: int = 0             # rev. 0.9c: width of the last letter held by the memory arm M (units)
    pm_u: int = 0                # rev. 0.9c: +-u lever (-1, 0, +1)
    u_in: bool = False           # rev. 0.9c: U's finger in the teeth (for the release)
    m_couple: bool = False       # rev. 0.9c: M coupled to the wheel (during a release)
    feel: dict = field(default_factory=dict)      # rev. 0.10: feeler travels W, B, C (mm from rest)
    lock_read: float = 0.0       # rev. 0.11: read lock pin in (dead marks, spaces): the read rocker stays up, no reading
    lock_hammer: float = 0.0     # rev. 0.11: hammer lock pin in (spaces): the idle cycle does not strike
    car_release: float = 0.0     # rev. 0.11: carriage release key pressed (0..1): the holding dog drawn out of the wheel
    margin_l: float = P.CAR_X_START   # rev. 0.11: carriage x where the line starts (left margin stop on the abutment)
    margin_r: float = P.CAR_X_END     # rev. 0.11: carriage x where the line ends (right margin stop on the abutment)

    def th(self):
        if self.theta is not None:
            return self.theta
        return (self.pos - (P.NPOS - 1) / 2) * P.STEP_DEG

    def slide(self):
        return self.slide_u * P.U

    def lift(self):
        return (self.row - P.HOME_ROW) * P.RH


@dataclass
class Part:
    name: str
    group: str
    kind: str
    mesh: object
    color: tuple
    bom: str = None          # part type id for the bill of materials
    mat: str = ''
    note: str = ''
    mov: str = 'fixed'       # motion group for checks
    printable: object = None  # callable -> Manifold laid out for printing (print parts)


def lever_x(n):
    return P.X0_KEYS + n * P.LEVER_PITCH


def pin_x(m):
    return P.X0_KEYS + P.PIN_PITCH * m + P.LEVER_PITCH / 2


# ----------------------------------------------------------------------------------------------- keys
def key_list():
    """(id, label, x_key, y_key, keytop_z, lever_n_or_x, kind) for all keys."""
    keys = []
    for r in range(4):
        for c in range(11):
            n, m = D.key_slot(r, c)
            keys.append(dict(id=f'k{r}{c}', label=D.LEGENDS[r][c], x=lever_x(n), y=P.KEY_ROW_Y[r],
                             top=P.KEYTOP_Z[r], lx=lever_x(n), n=n, r=r, c=c, kind='char', w=P.KEYCAP))
    keys.append(dict(id='space4', label='пробел 4u', x=-50, y=P.SPACE_Y, top=93, lx=lever_x(-1), n=-1, r=4, c=0,
                     kind='space', w=90))
    keys.append(dict(id='space6', label='пробел 6u', x=50, y=P.SPACE_Y, top=93, lx=lever_x(44), n=44, r=4, c=1,
                     kind='space', w=90))
    keys.append(dict(id='shift', label='регистр', x=-127, y=P.KEY_ROW_Y[3], top=P.KEYTOP_Z[3], lx=-127, n=-5, r=3,
                     c=-1, kind='service', w=P.KEYCAP))
    keys.append(dict(id='bksp', label='забой', x=127, y=P.KEY_ROW_Y[0], top=P.KEYTOP_Z[0], lx=124, n=46, r=0, c=11,
                     kind='service', w=P.KEYCAP))
    keys.append(dict(id='back', label='назад на литеру', x=127, y=P.KEY_ROW_Y[1], top=P.KEYTOP_Z[1], lx=130, n=47,
                     r=1, c=11, kind='service', w=P.KEYCAP))
    return keys


def lever_angle(k, frac):
    L = P.LEVER_PIVOT_Y - k['y']
    return math.degrees(math.atan2(P.KEY_TRAVEL * frac, L))


def lever_move(mesh, k, frac):
    """Rotate about the pivot (axis X): front goes down, tail goes up."""
    a = lever_angle(k, frac)
    return rotx(mesh, a, P.LEVER_PIVOT_Y, (P.LEVER_Z0 + P.LEVER_Z1) / 2)


def keyboard(st):
    parts = []
    for k in key_list():
        frac = st.pressed.get(k['n'], 0.0)
        dz = -P.KEY_TRAVEL * frac
        w = k['w']
        # rev. 0.9c: the legend is debossed 0.6 mm into the cap top (relief.key_legend)
        cap = cached(f"cap_{k['id']}", lambda k=k, w=w: RL.cut_top(cbox(k['x'], k['y'], k['top'] - 4, w, 14 if k['kind'] == 'space' else w, 8),
                                                              RL.key_legend(k, k['top']), k['top'])).translate((0, 0, dz))
        parts.append(Part(f"cap {k['id']}", 'keys', 'print', cap, COL['key'], 'keycap' if k['kind'] != 'space' else 'spacebar',
                          'PETG', mov=f"key{k['n']}"))
        sx = k['lx']
        stem = (zcyl(sx, k['y'], RISER_TOP + 2.0, k['top'] - 8, 2.0, 16) + Manifold.sphere(2.0, 16).translate((sx, k['y'], RISER_TOP + 2.0))).translate((0, 0, dz))
        if abs(sx - k['x']) > 0.1:
            stem = stem + box(min(sx, k['x']) - 2, max(sx, k['x']) + 2, k['y'] - 2, k['y'] + 2, k['top'] - 11, k['top'] - 8).translate((0, 0, dz))
        parts.append(Part(f"stem {k['id']}", 'keys', 'print', stem, COL['key'], 'keystem', 'PETG', mov=f"key{k['n']}"))
    # key comb: guides the stems
    comb = box(-138, 140, P.KEY_ROW_Y[3] - 10, P.KEY_ROW_Y[0] + 9, *P.COMB_Z)
    holes = [zcyl(k['lx'], k['y'], P.COMB_Z[0] - 1, P.COMB_Z[1] + 1, 2.7, 16) for k in key_list() if k['kind'] != 'space']
    comb = comb - union(holes)
    parts.append(Part('key comb', 'keys', 'print', comb, (110, 112, 120), 'comb', 'PETG',
                      note='печатается двумя частями, стыкуется на накладке', printable=lambda comb=comb: split_planes(comb, 0, [0.0])))
    # space bar guide: a second, short comb under the space bars
    sc = box(-120, 120, P.SPACE_Y - 9, P.SPACE_Y + 9, *P.COMB_Z) - union(
        [zcyl(k['lx'], k['y'], P.COMB_Z[0] - 1, P.COMB_Z[1] + 1, 2.7, 16) for k in key_list() if k['kind'] == 'space'])
    parts.append(Part('space comb', 'keys', 'print', sc, (110, 112, 120), 'comb_space', 'PETG',
                      printable=lambda sc=sc: split_planes(sc, 0, [0.0])))
    return parts


# --------------------------------------------------------------------------------------------- levers
RISER_TOP = 70.0
LOCK_Y = -200.0                     # rev. 0.8: lock comb under the levers
LOCK_Z = (40.5, 42.5)               # comb plane: under the tabs of the levers at rest, over the tab of a pressed lever
LOCK_TAB = (LOCK_Z[1] + 0.5, P.LEVER_Z0)      # tab under each lever (full width)
LOCK_NECK = (P.LEVER_Z0, P.LEVER_Z0 + 6.5)    # neck above the tab: only the right 1 mm of the lever is left
LOCK_SHIFT = 1.55                   # the comb shifts 1.55 mm along X while the cycle runs: teeth under the tabs, the neck in a slot
RACE_Y, FIN_H = -180.0, 5.0         # ball race
# selector bars along X above the lever tails: lift bits l1, l2 (rows), l4 (shift); rotate bits r1..r8 (column)
BIT_Y = {'l1': -5.0, 'l2': -1.0, 'l4': 3.0, 'r1': 7.0, 'r2': 11.0, 'r4': 15.0, 'r8': 19.0}   # rev. 0.8: under the latch lanes
BIT_Z = P.LEVER_Z1 + 3.0          # underside of the lift-bit bails at rest


def lever_mesh(k):
    x = k['lx']; t = P.LEVER_T / 2
    y_front = k['y'] - 4
    zc = (P.LEVER_Z0 + P.LEVER_Z1) / 2
    body = box(x - t, x + t, y_front, P.LEVER_TAIL_Y, P.LEVER_Z0, P.LEVER_Z1)
    body = body + box(x - t, x + t, k['y'] - 2, k['y'] + 2, P.LEVER_Z1, RISER_TOP)    # riser through the comb
    body = body - cyl((x - 3, P.LEVER_PIVOT_Y, zc), (x + 3, P.LEVER_PIVOT_Y, zc), 2.15, 16)
    if k['kind'] == 'char' or k['id'] == 'shift':
        # notch under the row-bit bails; lugs only where the key's row (or shift) sets the bit
        body = body - box(x - 3, x + 3, -10, P.LEVER_TAIL_Y + 1, P.LEVER_Z1 - 7, P.LEVER_Z1 + 1)
        r = P.ROW_CODE[k['r']]          # rev. 0.8: row code by frequency, not the keyboard row itself
        for bit, yb in ((1, BIT_Y['l1']), (2, BIT_Y['l2'])):
            if k['kind'] == 'char' and (r & bit):
                body = body + box(x - t, x + t, yb - 1.2, yb + 1.2, P.LEVER_Z1 - 7, BIT_Z - lug_gap(k, yb + 1.2))
        if k['id'] == 'shift':
            yb = BIT_Y['l4']
            body = body + box(x - t, x + t, yb - 1.2, yb + 1.2, P.LEVER_Z1 - 7, BIT_Z - lug_gap(k, yb + 1.2))
        if k['kind'] == 'char':          # lug under the column pusher
            body = body + box(x - t, x + t, TAIL_LUG[0], TAIL_LUG[1], P.LEVER_Z1 - 7, PUSH_Z0 - lug_gap(k, TAIL_LUG[1]))
    if k['kind'] not in ('char',) and k['id'] != 'shift':
        body = body - box(x - 3, x + 3, -10, P.LEVER_TAIL_Y + 1, P.LEVER_Z1 - 7, P.LEVER_Z1 + 1)   # no selector work
    if k['kind'] == 'space':             # rev. 0.11: the spaces set r1 + r4 (position 5: the shuttle stays in the middle)
        body = body + box(x - t, x + t, TAIL_LUG[0], TAIL_LUG[1], P.LEVER_Z1 - 7, PUSH_Z0 - lug_gap(k, TAIL_LUG[1]))
    # rev. 0.8 interlocks: a tab under the lever for the lock bail and a fin into the ball race (code keys only)
    if k['kind'] in ('char', 'space') or k['id'] == 'shift':
        body = body + box(x - t, x + t, LOCK_Y - 1.5, LOCK_Y + 1.5, *LOCK_TAB)
        body = body - box(x - t - 0.1, x + t - 1.0, LOCK_Y - 4.2, LOCK_Y + 4.2, *LOCK_NECK)
        body = body + box(x - 1.0, x + 1.0, RACE_Y - 1.0, RACE_Y + 1.0, P.LEVER_Z0 - FIN_H, P.LEVER_Z0)
    return body


def levers(st):
    parts = []
    for k in key_list():
        frac = st.pressed.get(k['n'], 0.0)
        m = lever_move(lever_mesh(k), k, frac)
        parts.append(Part(f"lever {k['id']}", 'levers', 'print', m, COL['lever'], 'lever', 'PETG',
                          mov=f"key{k['n']}", printable=lambda k=k: lever_pieces(k)))
    zc = (P.LEVER_Z0 + P.LEVER_Z1) / 2
    parts.append(Part('lever pivot rod', 'levers', 'buy', cyl((-140, P.LEVER_PIVOT_Y, zc), (140, P.LEVER_PIVOT_Y, zc), 2.0, 16),
                      COL['steel'], 'rod4x280', 'сталь', 'пруток 4 мм, 280 мм'))
    # rev. 0.8 interlocks: the lock bail slides 6 mm under the tabs while the cycle runs (the pressed lever cannot rise,
    # the others cannot go down); the ball race lets one fin in at a time; R or O at 15.5 mm trips the cycle.
    xl0, xl1 = lever_x(-1) - 3, lever_x(44) + 3
    dl = LOCK_SHIFT * st.lock
    lb = box(xl0 - 4, xl1 + 4, LOCK_Y - 3.0, LOCK_Y + 3.0, *LOCK_Z)
    lb = lb - union([box(lever_x(n) - 1.7, lever_x(n) + 1.7, LOCK_Y - 4, LOCK_Y + 4, LOCK_Z[0] - 1, LOCK_Z[1] + 1)
                     for n in range(-1, 45)])
    parts.append(Part('lock bail', 'levers', 'cut', lb.translate((dl, 0, 0)), COL['steel'], 'comb_plate', 'сталь',
                      'запорная гребёнка 2 мм: прорези под рычаги, сдвиг на полшага на время цикла', mov='lock'))
    for sx in (-1, 1):
        g0, g1 = sorted((sx * (xl1 + 5), sx * (xl1 + 9)))
        g = box(g0, g1, LOCK_Y - 6, LOCK_Y + 6, 0, LOCK_Z[1] + 2)
        g = g - box(-200, 200, LOCK_Y - 3.3, LOCK_Y + 3.3, LOCK_Z[0] - 0.3, LOCK_Z[1] + 0.3)
        parts.append(Part(f'lock bail guide {sx:+d}', 'levers', 'print', g, (110, 112, 120), 'lock_guide', 'PETG'))
    # lock link: from the bail end to the cycle stop latch (it is pushed in by the latch while the cycle runs)
    # route: along X to x = 121 (between lane O and the backspace lever), down to z 22 (over the cross member), along Y to
    # y = -24 (clear of the cams), along X to the stop latch, up under it
    zl = (22.0, 24.5)
    xr = 119.0
    ll = box(xl1 + 3, xr + 1.5, LOCK_Y - 2.5, LOCK_Y + 0.5, LOCK_Z[0], LOCK_Z[1]) + \
        box(xr - 1.0, xr + 1.5, LOCK_Y - 2.5, LOCK_Y + 0.5, zl[0], LOCK_Z[1]) + \
        box(xr - 1.0, xr + 1.5, LOCK_Y - 2.5, CAM_Y - 35.0, *zl) + box(xr - 1.0, 175.0, CAM_Y - 38.0, CAM_Y - 35.0, *zl) + \
        box(172.0, 175.0, CAM_Y - 38.0, CAM_Y - 35.0, zl[0], 32.0) + box(172.0, 175.0, CAM_Y - 38.0, CAM_Y - 21.0, 29.5, 32.0)
    parts.append(Part('lock link', 'levers', 'cut', ll.translate((dl, 0, 0)), COL['steel'], 'strip3x2_5', 'сталь', mov='lock'))
    # cycle trip: a rocker under the R and O beams (just behind zone A); either frame at 15.5 mm trips the cycle latch
    yt = P.ZONE_A[1] - 1.0
    trip = box(LK.LANES['R'] - 3, LK.LANES['O'] + 4, yt - 1.5, yt + 1.5, 21.0, 23.0) + \
        box(LK.LANES['O'] + 2, LK.LANES['O'] + 5, yt - 3.0, yt + 3.0, 15.0, 23.0)
    parts.append(Part('cycle trip lever', 'levers', 'print', trip, COL['pin'], 'trip_lever', 'PETG',
                      note='спуск цикла: рамка R или O на 15,5 мм; храповая собачка полного хода на тех же рамках'))
    tl = box(124.5, 126.3, yt - 1.5, CAM_Y - 42.0, 26.0, 28.5) + box(124.5, 182.0, CAM_Y - 45.0, CAM_Y - 42.0, 26.0, 28.5) + \
        box(179.0, 182.0, CAM_Y - 45.0, CAM_Y - 42.0, 26.0, 32.0) + box(179.0, 182.0, CAM_Y - 45.0, CAM_Y - 21.0, 29.5, 32.0) + \
        box(LK.LANES['O'] + 5, 126.3, yt - 1.5, yt + 1.5, 23.0, 28.5)
    parts.append(Part('cycle trip link', 'levers', 'cut', tl, COL['steel'], 'strip2x2_5', 'сталь', 'тяга спуска цикла к защёлке'))
    race = box(xl0 - 2, xl1 + 2, RACE_Y - 4, RACE_Y + 4, P.LEVER_Z0 - FIN_H - 14, P.LEVER_Z0 - FIN_H - 0.5)
    race = race - box(xl0 - 1, xl1 + 1, RACE_Y - 3, RACE_Y + 3, P.LEVER_Z0 - FIN_H - 13, P.LEVER_Z0 - FIN_H - 1.5)
    race = race - box(xl0 - 1, xl1 + 1, RACE_Y - 1.2, RACE_Y + 1.2, P.LEVER_Z0 - FIN_H - 2, P.LEVER_Z0)
    for sx in (-1, 1):
        race = race + box(sx * (xl1 + 2) - 2, sx * (xl1 + 2) + 2, RACE_Y - 4, RACE_Y + 4, 0, P.LEVER_Z0 - FIN_H - 0.5)
    parts.append(Part('ball race', 'levers', 'print', race, (110, 112, 120), 'ball_race', 'PETG',
                      note='шариковый замок: шарики 4,75 мм, свободный ход на одно перо 2 мм'))
    for sx in (-148, 148):
        parts.append(Part(f'pivot bracket {sx:+.0f}', 'levers', 'print',
                          box(sx - 6, sx + 6, P.LEVER_PIVOT_Y - 8, P.LEVER_PIVOT_Y + 8, 20, zc + 6) -
                          cyl((sx - 7, P.LEVER_PIVOT_Y, zc), (sx + 7, P.LEVER_PIVOT_Y, zc), 2.05, 16),
                          (110, 112, 120), 'pivot_bracket', 'PETG'))
    return parts


def split_planes(m, axis, cuts):
    """Cut a mesh into pieces by planes normal to axis (0, 1, 2) at the given coordinates."""
    b = m.bounding_box(); lo = list(b[:3]); hi = list(b[3:])
    edges = [lo[axis] - 1] + list(cuts) + [hi[axis] + 1]
    out = []
    for a, c in zip(edges[:-1], edges[1:]):
        l2 = [v - 1 for v in lo]; h2 = [v + 1 for v in hi]; l2[axis] = a; h2[axis] = c
        piece = m ^ box(l2[0], h2[0], l2[1], h2[1], l2[2], h2[2])
        if not piece.is_empty():
            out.append(piece)
    return out


def lever_pieces(k):
    """Long levers are printed in two pieces with a lap joint 20 mm long (glued and two M2 screws)."""
    m = lever_mesh(k); x = k['lx']
    if P.LEVER_TAIL_Y - (k['y'] - 4) <= 205:
        return [lay_flat_x(m)]
    y0, y1 = -150.0, -130.0
    big = 1000
    front = (m ^ box(x - 5, x + 5, -big, y0, -big, big)) + (m ^ box(x - 5, x, y0, y1, -big, big))
    rear = (m ^ box(x - 5, x + 5, y1, big, -big, big)) + (m ^ box(x, x + 5, y0, y1, -big, big))
    return [lay_flat_x(front), lay_flat_x(rear)]


def lay_flat_x(m):
    """Lay a part whose thin direction is X onto the bed (X -> Z)."""
    m = m.rotate((0, 90, 0))
    b = m.bounding_box()
    return m.translate((-b[0], -b[1], -b[2]))


# --------------------------------------------------------------------------------------- code plates
def bar_y(zone, k, tier=0):
    return zone[0] + 4 + P.BAIL_PITCH * k + P.TIER_SHIFT * tier


def plate_lugs(k):
    """[(bail name, tier, gap mm)] for the code plate of key k."""
    if k['kind'] == 'space':
        w = 4 if k['id'] == 'space4' else 6
        return [('R', t, 0.0) for t in (0, 1)] + [('W', t, P.TP - P.K_STEP * (w - P.W_OFFSET)) for t in (0, 1)]
    if k['kind'] != 'char':
        return []
    out = []
    for tier in (0, 1):
        item = D.ROWS[k['r']][k['c']][tier]
        if item is None:
            continue
        it = D.ITEMS[item]
        if it['kind'] in D.ADV:
            # rev. 0.10: W, B and C are read from the shuttle; the plate only resets the memory and trips the cycle
            out += [('R', tier, 0.0)]
        else:
            out.append(('O', tier, 0.0))
            if it.get('below'):
                out.append(('N', tier, 0.0))
    return out


GRUBS = [3, 4, 5, 6, 8, 10, 12, 16, 20, 25]


def grub_length(gap):
    prot = P.BOSS_Z[0] - P.BAIL_Z - gap        # visible length below the boss
    for L in GRUBS:
        if prot + 4 <= L <= prot + (P.BOSS_Z[1] - P.BOSS_Z[0]):
            return L, prot
    return None, prot


def plate_zone(k):
    return P.ZONE_A if k['n'] % 2 == 0 else P.ZONE_B


def plate_mesh(k):
    x = k['lx']; zone = plate_zone(k)
    y0, y1 = zone[0] - 1, zone[1] + 1
    ya = k['y']
    bw = P.BOSS_W / 2; st = P.STRAP_T / 2
    m = box(x - bw, x + bw, y0, y1, *P.BOSS_Z)
    # rev. 0.9b: a strap 3 mm wide under the lever (its full width) from the boss to the key; an M2 screw at the key
    # holds the plate to the lever. One solid body (earlier the hanger tongue could hang free of the strap).
    t = P.LEVER_T / 2
    ys0, ys1 = min(y0, ya - 4), max(y1, ya + 4)
    m = m + box(x - t, x + t, ys0, ys1, P.LEVER_Z0 - 3.0, P.LEVER_Z0)
    holes = [zcyl(x, ya, P.LEVER_Z0 - 4, P.LEVER_Z0 + 1, 0.8, 10)]
    for bail, tier, gap in plate_lugs(k):
        yb = bar_y(zone, P.BAIL_ORDER.index(bail), tier)
        holes.append(zcyl(x, yb, P.BOSS_Z[0] - 1, P.BOSS_Z[1] + 1, 1.25, 12))
    return m - union(holes)


def plates(st):
    parts = []
    for k in key_list():
        lugs = plate_lugs(k)
        if not lugs:
            continue
        dz = -P.TP * st.pressed.get(k['n'], 0.0)
        zone = plate_zone(k)
        parts.append(Part(f"plate {k['id']}", 'plates', 'print', plate_mesh(k).translate((0, 0, dz)), COL['plate'],
                          'code_plate', 'PETG', mov=f"key{k['n']}", printable=lambda k=k: lay_flat_x(plate_mesh(k))))
        for bail, tier, gap in lugs:
            L, prot = grub_length(gap)
            yb = bar_y(zone, P.BAIL_ORDER.index(bail), tier)
            ztip = P.BAIL_Z + gap
            g = zcyl(k['lx'], yb, ztip, ztip + L, 1.5, 12).translate((0, 0, dz))
            parts.append(Part(f"grub {k['id']} {bail}{tier}", 'plates', 'buy', g, COL['grub'], f'grubM3x{L}',
                              'сталь', f'установочный винт М3×{L}, плоский конец', mov=f"key{k['n']}"))
    return parts


# --------------------------------------------------------------------------------------------- bails
BAR_R = 2.5


# rev. 0.8: each gauge frame moves on four vertical guides (pure translation). Side plates sit in their own lanes
# (|x|), clear of the service levers at x = 124, 130 and -127 and of the space-key levers at 106.9; the beam that joins
# the two bars of a frame runs over every other frame's bars with 1 mm to spare when it is fully down.
LANES = LK.LANES
GUIDE_Y = {'front': (-386.0, -380.0), 'rear': (-241.0, -235.0)}   # sleeves of neighbouring lanes alternate in y
BEAM_Z = (P.BAIL_Z + 17.0, P.BAIL_Z + 20.0)                         # 39..42: 1 mm over the other bars at full travel
SLEEVE_Z = (BEAM_Z[0] - 2.0, BEAM_Z[1] + 6.0)
TIER_TOP_Z = (SLEEVE_Z[1] + 2.0, SLEEVE_Z[1] + 5.0)                 # front guide bracket (rods hang from it)
TIER_BOT_Z = (0.0, 4.0)                                             # rear guide strip (rods stand on it)


def lane_order():
    return sorted(LANES, key=lambda n: LANES[n])


def guide_y(name):
    k = lane_order().index(name) % 2
    return GUIDE_Y['front'][k], GUIDE_Y['rear'][k]


def bail_plate(name, sx):
    i = P.BAIL_ORDER.index(name)
    x = sx * LANES[name]
    ya = bar_y(P.ZONE_A, i); yb_ = bar_y(P.ZONE_B, i)
    zc = P.BAIL_Z - BAR_R
    yf, yr = guide_y(name)
    m = box(x - 2, x + 2, yf, yr, *BEAM_Z)
    for yy in (ya, yb_):
        m = m + box(x - 2, x + 2, yy - 4, yy + 4, zc - 4, BEAM_Z[1])
    for yy in (yf, yr):
        m = m + zcyl(x, yy, *SLEEVE_Z, 3.0, 24)
        m = m - zcyl(x, yy, SLEEVE_Z[0] - 1, SLEEVE_Z[1] + 1, 1.55, 16)
    for yy in (ya, yb_):
        m = m - cyl((x - 3, yy, zc), (x + 3, yy, zc), BAR_R + 0.05, 24)
    return m


FRAMES = ('R', 'W', 'O', 'N')      # rev. 0.10: the B and C frames are gone (slides under their followers, reader.py)


def bails(st):
    parts = []
    dy = P.TIER_SHIFT * st.tier
    for i, name in enumerate(P.BAIL_ORDER):
        if name not in FRAMES:
            continue
        dz = -st.frames.get(name, 0.0)
        xa = LANES[name]
        for zone, zn in ((P.ZONE_A, 'A'), (P.ZONE_B, 'B')):
            yb = bar_y(zone, i); zc = P.BAIL_Z - BAR_R
            parts.append(Part(f'bail {name} bar {zn}', 'bails', 'buy',
                              cyl((-xa - 2, yb, zc), (xa + 2, yb, zc), BAR_R, 24).translate((0, dy, dz)), COL['steel'],
                              f'rod5x{int(2 * xa + 4)}', 'сталь', f'пруток 5 мм, {int(2 * xa + 4)} мм', mov=f'bail{name}'))
        for sx in (-1, 1):
            parts.append(Part(f'bail {name} plate {sx:+d}', 'bails', 'print', bail_plate(name, sx).translate((0, dy, dz)), COL['bail'],
                              f'bail_plate_{name}', 'PETG', note='боковина рамки с двумя гильзами на направляющих 3 мм',
                              mov=f'bail{name}'))
        # four guide rods (front ones hang from the bracket, rear ones stand on the strip)
        yf, yr = guide_y(name)
        for sx in (-1, 1):
            x = sx * xa
            rods = zcyl(x, yf, P.FRAME_Y0 * 0 + 21.0, TIER_TOP_Z[0], 1.5, 16) + zcyl(x, yr, TIER_BOT_Z[1], SLEEVE_Z[1] + 1.5, 1.5, 16)
            parts.append(Part(f'bail {name} guides {sx:+d}', 'bails', 'buy', rods.translate((0, dy, 0)), COL['steel'], 'rod3x30',
                              'сталь', 'направляющие 3 мм', mov='tier'))
    # tier carriages: one per side, slide 4.5 mm in Y with the shift key; they carry all guide rods
    x0, x1 = min(LANES.values()) - 4, max(LANES.values()) + 4
    for sx in (-1, 1):
        lo, hi = sorted((sx * x0, sx * (x1 + 6)))
        fy0, fy1 = min(GUIDE_Y['front']) - 4, max(GUIDE_Y['front']) + 4
        ry0, ry1 = min(GUIDE_Y['rear']) - 4, max(GUIDE_Y['rear']) + 4
        xr0, xr1 = sorted((sx * (x1 + 2), sx * (x1 + 6)))
        yfr = P.FRAME_Y0 + P.EXT + 1.0                     # just behind the front frame member
        c = box(lo, hi, fy0, fy1, *TIER_TOP_Z) + box(lo, hi, ry0, ry1, *TIER_BOT_Z) + \
            box(xr0, xr1, yfr, ry1, *TIER_BOT_Z) + box(xr0, xr1, yfr, yfr + 4, TIER_BOT_Z[0], P.EXT + 4.5) + \
            box(xr0, xr1, fy0, yfr + 4, P.EXT + 0.5, P.EXT + 4.5) + box(xr0, xr1, fy0, fy0 + 4, P.EXT + 0.5, TIER_TOP_Z[1])
        parts.append(Part(f'tier carriage {sx:+d}', 'bails', 'print', c.translate((0, dy, 0)), (110, 112, 120), 'tier_carriage', 'PETG',
                          note='салазки регистра: несут направляющие рамок, ход 4,5 мм по Y', mov='tier'))
    return parts


# ------------------------------------------------------------------------------------ memory sectors
# rev. 0.8: the sectors ride on nested sleeves over the frames; a follower arm with a roller on the flat top of its
# frame's beam turns each sleeve (the shift key moves the frames in Y; a roller on a flat does not care).
SECT_SHAFT = LK.SLEEVE_AXIS          # (y, z), axis along X; fixed in the right motor cheek
# rev. 0.11: sector W removed (nobody read it since 0.9.1; the memory arm M of the escapement keeps the width): tubes 5/6/7
SLEEVE = {'R': (5.0, 110.0, 170.0), 'B': (6.0, 139.0, 162.0), 'C': (7.0, 144.0, 157.0)}  # OD, x0, x1
SECTOR_X = {'C': 155.5, 'B': 160.5}
TRIP_X = 168.5


def follower_delta(st, name):
    """Turn of a follower (deg, from rest) for the current travel of its frame."""
    s = max(st.frames.get(name, 0.0), st.mem.get(name, 0.0))   # a sector held by its pawl keeps its follower up
    s = min(s, 4.0) if name == 'R' else min(s, 12.0)      # the R arm meets its stop after 4 mm; the beam goes on alone
    return LK.follower_angle(s) - LK.THETA0


def follower_mesh(x, ys, zs):
    """Arm toward -Y with a roller at r, at its rest angle."""
    r = LK.FOLLOW_R
    arm = box(x - 1.5, x + 1.5, ys - r, ys, zs - 1.5, zs + 1.5) + cyl((x - 1.5, ys - r, zs), (x + 1.5, ys - r, zs), LK.ROLLER_R, 16)
    return rotx(arm, LK.THETA0, ys, zs)


def stair_profile(name, ys, zs):
    """rev. 0.8b: staircase lobe toward +Y; step k (radius R0 - (8 + k) u) sits at -theta_k and comes to the feeler
    finger (at the axis height, +Y side) when the sector holds k."""
    st_ = LK.stops()['stairs'][name]
    R, th = st_['R'], st_['theta']
    n = len(R)
    mids = [2.0] + [-(th[k] + th[k + 1]) / 2 for k in range(n - 1)] + [-th[-1] - 2.0]
    pol = lambda r, a: (ys + r * math.cos(math.radians(a)), zs + r * math.sin(math.radians(a)))
    pts = [pol(5.5, mids[0])]
    for k in range(n):
        a0, a1 = mids[k], mids[k + 1]
        for t in np.linspace(a0, a1, 4):
            pts.append(pol(R[k], t))
    pts.append(pol(5.5, mids[-1]))
    return pts


def sector_mesh(name, x, ys, zs):
    """Sector plate in the YZ plane, ratchet teeth at the angles where the pawl (straight above the axis) meets tooth k."""
    th = LK.sectors()[name]['theta']
    R = 42.0
    pts = []
    a_lo, a_hi = 90.0 - th[-1] - 4.0, 90.0 + 4.0
    n = 2 * len(th) + 2
    pts.append((ys + 6 * math.cos(math.radians(a_lo)), zs + 6 * math.sin(math.radians(a_lo))))
    for k, t in enumerate(reversed(th)):
        a = 90.0 - t
        for da, rr in ((-1.2, R - 1.8), (0.0, R)):          # saw teeth: the pawl drops behind each crest
            aa = math.radians(a + da)
            pts.append((ys + rr * math.cos(aa), zs + rr * math.sin(aa)))
    aa = math.radians(a_hi)
    pts.append((ys + R * math.cos(aa), zs + R * math.sin(aa)))
    pts.append((ys + 6 * math.cos(aa), zs + 6 * math.sin(aa)))
    polys = [geo._ccw(pts)]
    if name in ('B', 'C'):
        polys.append(geo._ccw(stair_profile(name, ys, zs)))
    prof = CrossSection(polys) if len(polys) == 1 else CrossSection([polys[0]]) + CrossSection([polys[1]])
    m = prof.extrude(3.0).transform(np.array([[0, 0, 1, x - 1.5], [1, 0, 0, 0], [0, 1, 0, 0]], float))
    m = m + cyl((x - 1.5, ys, zs), (x + 1.5, ys, zs), 6.0, 24)
    return m - cyl((x - 2, ys, zs), (x + 2, ys, zs), SLEEVE[name][0] / 2 - 0.5, 24)     # rev. 0.9b: one body with its tube


def sectors(st):
    parts = []
    ys, zs = SECT_SHAFT
    parts.append(Part('sector axis', 'sectors', 'buy', cyl((109.5, ys, zs), (176.0, ys, zs), 2.0, 16), COL['steel'],
                      'rod4x70', 'сталь', 'ось 4 мм, запрессована в правую щёку двигателя'))
    for name in ('R', 'B', 'C'):
        od, x0, x1 = SLEEVE[name]
        d = follower_delta(st, name)
        m = cyl((x0, ys, zs), (x1, ys, zs), od / 2, 24) - cyl((x0 - 1, ys, zs), (x1 + 1, ys, zs), od / 2 - 0.5, 24)
        m = m + follower_mesh(LK.LANES[name], ys, zs)
        if name in SECTOR_X:
            m = m + sector_mesh(name, SECTOR_X[name], ys, zs)
        else:   # R: trip finger that lifts the three pawls at the start of every advancing stroke
            m = m + box(TRIP_X - 1.5, TRIP_X + 1.5, ys - 2, ys + 2, zs, zs + 30) + cyl((TRIP_X - 2, ys, zs), (TRIP_X + 2, ys, zs), 4.0, 16)
        parts.append(Part(f'memory sleeve {name}', 'sectors', 'print', rotx(m, d, ys, zs), COL['sector'], f'sleeve_{name}', 'PETG',
                          note=('втулка-трубка с повторителем и сектором' if name != 'R' else 'втулка R с повторителем и пальцем сброса'),
                          mov=f'follow{name}'))
    # pawls on their own shaft above the sectors, held by a bracket on the motor cheek
    pz = zs + 42.0 + 3.0
    # rev. 0.9b: each sector has its own pawl (they hold different teeth); a lifter under all three, raised by the
    # trip finger of sleeve R, lifts them together
    ax_y, ax_z = ys + 9.0, pz + 3.0
    parts.append(Part('memory pawl shaft', 'sectors', 'buy', cyl((153.0, ax_y, ax_z), (172.9, ax_y, ax_z), 1.5, 12), COL['steel'],
                      'rod3x20', 'сталь', 'ось собачек памяти'))
    for name, x in SECTOR_X.items():
        paw = box(x - 1.5, x + 1.5, ys - 1.0, ax_y, pz - 1.0, pz + 1.0) + box(x - 1.5, x + 1.5, ys - 1.0, ys + 1.0, pz - 3.0, pz) + \
            cyl((x - 1.5, ax_y, ax_z), (x + 1.5, ax_y, ax_z), 2.8, 16)
        paw = paw - cyl((x - 2, ax_y, ax_z), (x + 2, ax_y, ax_z), 1.55, 12)
        parts.append(Part(f'memory pawl {name}', 'sectors', 'print', paw, COL['sector'], f'memory_pawl', 'PETG',
                          note='собачка храповика памяти, пружина 0,15 Н'))
    lif = box(153.0, 170.0, ys + 2.0, ys + 4.0, pz - 2.7, pz - 1.3) + box(TRIP_X - 1.5, TRIP_X + 1.5, ys + 2.0, ax_y, pz - 2.7, pz + 3.0) + \
        cyl((TRIP_X - 1.5, ax_y, ax_z), (TRIP_X + 1.5, ax_y, ax_z), 2.8, 16) + box(TRIP_X - 1.5, TRIP_X + 1.5, ys + 4.0, ax_y, pz + 1.0, pz + 3.0)
    lif = lif - cyl((TRIP_X - 2, ax_y, ax_z), (TRIP_X + 2, ax_y, ax_z), 1.55, 12)
    parts.append(Part('memory pawl lifter', 'sectors', 'print', lif, COL['sector'], 'pawl_lifter', 'PETG',
                      note='подъёмник собачек: сброс памяти пальцем втулки R'))
    br = box(171.0, 173.0, ys - 4, ys + 14, zs - 4, pz + 6) - cyl((170, ys, zs), (174, ys, zs), 2.05, 16) - \
        cyl((170, ys + 9.0, pz + 3.0), (174, ys + 9.0, pz + 3.0), 1.55, 12)
    parts.append(Part('sector bracket', 'sectors', 'print', br, (110, 112, 120), 'sector_bracket', 'PETG',
                      note='накладка на щёку двигателя: ось секторов и ось собачек'))
    parts += escape_link(st)
    return parts


ESC_ROD_X = -175.0


def esc_w(st):
    """rev. 0.10: travel of the escapement rods: the W frame (spaces) or the W wire (letters), whichever is further."""
    return max(st.frames.get('W', 0.0), st.frames.get('Wr', 0.0))
ESC_FOL_X = (-178.0, -132.0)


def escape_link(st):
    """W frame -> stop of the escapement: left follower (sine lever 1:1), rod along Y, bellcrank, rod along X, stop arm.
    rev. 0.10: the W wire of the reading head pulls rod Y forward too (frames['Wr']); the frame stays for the spaces."""
    parts = []
    ys, zs = SECT_SHAFT
    s_f = st.frames.get('W', 0.0)
    s = esc_w(st)
    th = LK.follower_angle(s_f)
    d = th - LK.THETA0
    r = LK.FOLLOW_R
    # bracket from the left frame side
    br = box(-230.0, -176.0, ys - 5, ys + 5, 20.0, 24.0) + box(-182.0, -178.0, ys - 5, ys + 5, 20.0, zs + 5) - \
        cyl((-183, ys, zs), (-177, ys, zs), 2.05, 16)
    parts.append(Part('W follower bracket', 'sectors', 'print', br, (110, 112, 120), 'wfol_bracket', 'PETG'))
    parts.append(Part('W follower axis', 'sectors', 'buy', cyl((-180.0, ys, zs), (-110.0, ys, zs), 2.0, 16), COL['steel'], 'rod4x70', 'сталь',
                      'ось 4 мм, 70 мм (повторители W и O слева)'))
    m = cyl((ESC_FOL_X[0], ys, zs), (ESC_FOL_X[1], ys, zs), 3.0, 24) - cyl((ESC_FOL_X[0] - 1, ys, zs), (ESC_FOL_X[1] + 1, ys, zs), 2.05, 16)
    m = m + follower_mesh(-LK.LANES['W'], ys, zs)
    xo = ESC_ROD_X + 3.0
    out = box(xo - 1.5, xo + 1.5, ys - 1.5, ys + 1.5, zs, zs + r) + cyl((xo - 1.5, ys, zs + r), (xo + 1.5, ys, zs + r), LK.ROLLER_R, 16)
    m = m + rotx(out, LK.THETA0, ys, zs)
    parts.append(Part('W follower', 'sectors', 'print', rotx(m, d, ys, zs), COL['sector'], 'w_follower', 'PETG',
                      note='синусный рычаг 1:1: ролик на балке W, ролик на упоре тяги', mov='followW'))
    # rod along Y: a flat plate in front of the output roller, pulled forward by s; tension spring at the escapement
    y_roll0 = ys - r * math.sin(math.radians(LK.THETA0))
    yf = y_roll0 - LK.ROLLER_R - 0.2
    z_r = zs + 0.5 * r + 3.0                     # 58: over the escapement bracket plate (z 54), under the wheel (66)
    E_ = LK.escape_link()
    ESCY = 116.05
    # rev. 0.9c: rod X runs along the bottom of U's drum (tape tangent at y = ESCY - R) and pulls toward -X, so the
    # drum turns CW, the way the wheel goes forward; the bellcrank turns CCW: input arm -X (rod Y), output arm +Y
    ra = 19.1
    yx = ESCY - E_['r_a']                    # rod X
    yb = yx - ra                             # rod Y end and the bellcrank's pivot
    flat = box(ESC_ROD_X - 1.0, ESC_ROD_X + 5.0, yf - 1.5, yf, zs + 2.0, zs + r + 2.0)
    rod1 = flat + cyl((ESC_ROD_X, yf, z_r), (ESC_ROD_X, yb, z_r), 1.0, 12)
    parts.append(Part('escapement rod Y', 'sectors', 'buy', rod1.translate((0, -s, 0)), COL['steel'], 'rod2x430', 'сталь',
                      'тяга 2 мм, 430 мм (работает на растяжение)', mov='followW'))
    # rev. 0.10: the W wire of the reading head is clamped to the front of the flat and leaves forward along the rod into
    # its housing, held by a bracket on the W follower's upright; a ratchet strip on the flat and a pawl hold the rod
    # from the reading to the feed (the pawl is lifted when the keyboard lock lets go, at 345 deg)
    zw = z_r
    clamp = box(ESC_ROD_X - 1.5, ESC_ROD_X + 3.5, yf - 4.0, yf - 1.5, zw - 2.5, zw + 2.5)
    parts.append(Part('W wire clamp', 'sectors', 'buy', clamp.translate((0, -s, 0)), COL['buy'], 'wire_clamp', 'латунь',
                      'зажим троса W на площадке тяги Y (винт нуля)', mov='followW'))
    yh = yf - 1.5 - P.K_STEP * 12 - 2.5 - 9.0          # housing end: the clamp stops 6 mm short of it at w = 16
    brk = box(-182.0, -178.0, yh - 6.0, ys - 5.0, zs + 1.0, zs + 5.0) + box(-182.0, ESC_ROD_X + 6.0, yh - 6.0, yh, zs + 1.0, zw + 5.0)
    brk = brk - cyl((ESC_ROD_X + 1.0, yh - 7.0, zw), (ESC_ROD_X + 1.0, yh + 1.0, zw), 1.8, 12)
    parts.append(Part('W wire bracket', 'sectors', 'print', brk, (110, 112, 120), 'w_wire_bracket', 'PETG',
                      note='кронштейн оболочки троса W и собачки тяги Y на стойке повторителя W'))
    rack = box(ESC_ROD_X - 1.0, ESC_ROD_X + 3.0, yf - 1.5 - 14.0, yf - 1.5, zs + P.K_STEP * 0 + 18.0, zs + 20.0)
    parts.append(Part('W latch rack', 'sectors', 'print', rack.translate((0, -s, 0)), COL['esc'], 'w_latch_rack', 'PETG',
                      note='храповая планка на площадке тяги Y, шаг 1 мм', mov='followW'))
    pawl = box(ESC_ROD_X - 1.0, ESC_ROD_X + 8.0, yh, yh + 3.0, zs + 20.0, zs + 22.0) + box(ESC_ROD_X + 6.0, ESC_ROD_X + 8.0, yh - 2.0, yh + 3.0, zs + 5.0, zs + 22.0)
    parts.append(Part('W latch pawl', 'sectors', 'print', pawl, COL['esc'], 'w_latch_pawl', 'PETG',
                      note='собачка тяги Y: держит считанную ширину до подачи'))
    # +-u: the bellcrank's pivot sits on an eccentric (e = 1 mm along X) turned by a small lever with three notches;
    # it moves rod X, so U's rest and every advance change by one unit
    pm = st.pm_u
    px, py = ESC_ROD_X + ra - pm * 1.0, yb
    ang = math.degrees(s / ra)
    z_x = 77.5                               # rev. 0.9c: rod X at the level of U's drum, over the wheel
    bc = box(px - ra, px, py - 1.5, py + 1.5, z_r - 1.5, z_r + 1.5) + box(px - 1.5, px + 1.5, py, py + ra, z_x - 1.5, z_x + 1.5) + \
        zcyl(px, py, z_r - 3, z_x + 1.5, 3.0, 16)
    bc = bc - zcyl(px, py, z_r - 4, z_x + 4, 2.05, 16)
    parts.append(Part('escapement bellcrank', 'sectors', 'print', rotz(bc, ang, px, py), COL['esc'], 'esc_bellcrank', 'PETG',
                      note='угловой рычаг 1:1 (кулисы) на эксцентрике ±u', mov='followW'))
    ex = zcyl(px, py, z_r - 6.5, z_r - 3.2, 2.0, 16) + zcyl(px, py, z_r - 3.2, z_r + 3.0, 2.0, 16)
    lev = box(px + pm * 1.0, px + pm * 1.0 + 16.0, py - 1.5, py + 1.5, z_r - 6.5, z_r - 4.5) + zcyl(px + pm * 1.0, py, z_r - 6.5, z_r - 4.5, 3.6, 24)
    lev = lev + geo.Manifold.sphere(1.3, 16).translate((px + pm * 1.0 + 16.0, py, z_r - 6.6))
    lev = rotz(lev, 30.0 * pm, px + pm * 1.0, py)
    parts.append(Part('pm-u eccentric', 'sectors', 'print', ex + lev, (200, 160, 60), 'pmu_eccentric', 'PETG',
                      note='рычажок ±u: эксцентрик 1 мм под осью углового рычага, три положения (−u, 0, +u)', mov='pmu'))
    cx0 = ESC_ROD_X + ra
    ntch = box(cx0 + 13.5, cx0 + 20.5, py - 10.0, py + 10.0, z_r - 9.5, z_r - 6.6)
    for k in (-1, 0, 1):
        c = (cx0 + 16.0 * math.cos(math.radians(30.0 * k)), py + 16.0 * math.sin(math.radians(30.0 * k)))
        ntch = ntch - zcyl(c[0], c[1], z_r - 10, z_r - 6, 1.3, 16)
    parts.append(Part('pm-u detent', 'sectors', 'print', ntch, (110, 112, 120), 'pmu_detent', 'PETG',
                      note='гребёнка рычажка ±u: три гнезда под шарик рычажка'))
    rod2 = cyl((px - 1.5, yx, z_x), (-6.0, yx, z_x), 1.0, 12)
    parts.append(Part('escapement rod X', 'sectors', 'buy', rod2.translate((-s, 0, 0)), COL['steel'], 'rod2x160', 'сталь',
                      'тяга 2 мм к упору спуска', mov='followW'))
    return parts


# -------------------------------------------------------------------------------------------- frame
def frame(st):
    parts = []
    X, Y0, Y1, E = P.FRAME_X, P.FRAME_Y0, P.FRAME_Y1, P.EXT
    def ext(name, m, L):
        parts.append(Part(name, 'frame', 'cut', m, COL['frame'], f'2020x{int(round(L))}', 'алюминий',
                          f'профиль 2020, {int(round(L))} мм'))
    ext('frame front', box(-X, X, Y0, Y0 + E, 0, E), 2 * X)
    ext('frame back', box(-X, X, Y1 - E, Y1, 0, E), 2 * X)
    for sx in (-1, 1):
        ext(f'frame side {sx:+d}', box(sx * X - E if sx > 0 else -X, sx * X if sx > 0 else -X + E, Y0 + E, Y1 - E, 0, E), Y1 - Y0 - 2 * E)
    for yr in P.RAIL_Y:
        for sx in (-1, 1):
            x0 = X - E if sx > 0 else -X
            ext(f'beam post {yr:.0f} {sx:+d}', box(x0, x0 + E, yr - E / 2, yr + E / 2, E, P.RAIL_Z - E), P.RAIL_Z - 2 * E)
        ext(f'beam {yr:.0f}', box(-X + E, X - E, yr - E / 2, yr + E / 2, P.RAIL_Z - E, P.RAIL_Z), 2 * X - 2 * E)
        parts.append(Part(f'rail MGN12 {yr:.0f}', 'frame', 'buy', box(-150, 150, yr - 6, yr + 6, P.RAIL_Z, P.RAIL_Z + 8),
                          COL['buy'], 'MGN12_300', 'сталь', 'линейная направляющая MGN12, 300 мм'))
    for (yy, zz), nm in ((P.CAR_RAIL_LO, 'lo'), (P.CAR_RAIL_HI, 'hi')):
        for sx in (-1, 1):
            x0 = X - E if sx > 0 else -X
            ext(f'carriage post {nm} {sx:+d}', box(x0, x0 + E, yy - E / 2, yy + E / 2, E, zz + 10), zz + 10 - E)
        parts.append(Part(f'carriage rod {nm}', 'frame', 'buy', cyl((-X + E, yy, zz), (X - E, yy, zz), 4.0, 24),
                          COL['steel'], 'rod8x460', 'сталь', 'калиброванный пруток 8 мм, 460 мм'))
    # inner cross member under the lever pivot brackets
    ext('frame cross pivot', box(-X + E, X - E, P.LEVER_PIVOT_Y - E / 2, P.LEVER_PIVOT_Y + E / 2, 0, E), 2 * X - 2 * E)
    # ribbon spool posts on the rear beam, outside the MGN12 rail
    for sx in (-1, 1):
        parts.append(Part(f'ribbon post {sx:+d}', 'frame', 'print',
                          box(sx * 165 - 4, sx * 165 + 4, -24, -16, P.RAIL_Z, P.ZP - P.RIBBON_DROP - 12) +
                          box(min(sx * 152, sx * 165) - 4, max(sx * 152, sx * 165) + 4, -24, -16, P.ZP - P.RIBBON_DROP - 13, P.ZP - P.RIBBON_DROP - 9),
                          (110, 112, 120), 'ribbon_post', 'PETG'))
    return parts


# ------------------------------------------------------------------------- selectors (fixed, under the U-frame)
BAR_X1 = 138.0
ROD_OUT_X = 112.0                 # rev. 0.8: the bent selector rods leave the bars here, outside the lever field
ROD_ARM_Z = 77.5                  # their arm along X runs over the lever tails, under the selector comb
ROD_X = {'l1': -122.0, 'l2': -116.0, 'l4': -110.0, 'r1': 118.0, 'r2': 124.0, 'r4': 130.0, 'r8': 136.0}
SEL_RISE = 4.0


PUSH_Z0 = P.LEVER_Z1 + 0.3        # underside of a column pusher at rest (it rests on the guide by its tongue)
TAIL_LUG = (19.0, 23.0)            # rev. 0.9b: lug on each code lever's tail under its column pusher


def tail_rise(k, f, y):
    """Rise of the lever's top edge at y when the key is down by the fraction f."""
    return (y - P.LEVER_PIVOT_Y) * math.tan(math.radians(lever_angle(k, f)))


def lug_gap(k, y):
    """rev. 0.9b: rest gap of a tail lug so that the full stroke lifts its bar exactly SEL_RISE; the front rows
    (longer levers) need less, so every lever gets its own lug height."""
    return tail_rise(k, 1.0, y) - SEL_RISE


def lug_rise(k, f, y):
    return min(SEL_RISE, max(0.0, tail_rise(k, f, y) - lug_gap(k, y)))


def bit_rises(st):
    """rev. 0.9b: rise of each selector bar (and its rod) from the levers pressed now."""
    ks = {k['n']: k for k in key_list()}
    out = {}
    for n, f in st.pressed.items():
        k = ks[n]
        if not f or k['kind'] not in ('char', 'space') and k['id'] != 'shift':
            continue
        if k['kind'] == 'space':
            for b in SPACE_BITS:
                out[b] = max(out.get(b, 0.0), lug_rise(k, f, TAIL_LUG[1]))
            continue
        if k['kind'] == 'char':
            for b in column_bits(k['n'] // 4):
                out[b] = max(out.get(b, 0.0), lug_rise(k, f, TAIL_LUG[1]))
            r = P.ROW_CODE[k['r']]
            for b, bit in (('l1', 1), ('l2', 2)):
                if r & bit:
                    out[b] = max(out.get(b, 0.0), lug_rise(k, f, BIT_Y[b] + 1.2))
        else:
            out['l4'] = max(out.get('l4', 0.0), lug_rise(k, f, BIT_Y['l4'] + 1.2))
    return out


def column_bits(c):
    return [b for b, v in (('r1', 1), ('r2', 2), ('r4', 4), ('r8', 8)) if c & v]


SPACE_POS = (P.NPOS - 1) // 2             # rev. 0.11: a space selects the middle position (the shuttle does not turn)
SPACE_BITS = column_bits(SPACE_POS)        # r1, r4


def selectors(st):
    """Column pushers on the lever tails set the rotate bits; row bails set the lift bits."""
    parts = []
    tail = P.LEVER_TAIL_Y
    ks = {k['n']: k for k in key_list()}
    bar_rise = {}
    for c in range(P.NPOS):
        x0 = lever_x(4 * c) - 2.0; x1 = lever_x(4 * c + 3) + 2.0
        rise = 0.0
        for n in range(4 * c, 4 * c + 4):
            f = st.pressed.get(n, 0.0)
            if f and ks[n]['kind'] == 'char':
                rise = max(rise, lug_rise(ks[n], f, TAIL_LUG[1]))
        for b in column_bits(c):
            bar_rise[b] = max(bar_rise.get(b, 0.0), rise)
        z0 = PUSH_Z0 + rise
        xc = (x0 + x1) / 2
        m = box(x0, x1, 6.5, tail - 0.5, z0, z0 + 2.0)
        for b in column_bits(c):
            m = m + box(x0 + 2, x1 - 2, BIT_Y[b] - 1.2, BIT_Y[b] + 1.2, z0 + 2.0, z0 + 4.0)
        # guide tongue (rev. 0.9b: joined to the body; at rest it sits on the floor of its slot in the guide)
        m = m + box(xc - 1.5, xc + 1.5, tail + 0.5, tail + 2.5, z0 - 3, z0 + 2.0) + box(xc - 1.5, xc + 1.5, tail - 0.5, tail + 0.5, z0, z0 + 2.0)
        parts.append(Part(f'column pusher {c}', 'select', 'print', m, COL['pin'], 'col_pusher', 'PETG', mov=f'sel{c}'))
    # rev. 0.11: a pusher over each space lever's tail with the lugs of r1 and r4 (beside the pushers of columns 0, 10)
    for k in key_list():
        if k['kind'] != 'space':
            continue
        x0, x1 = k['lx'] - 2.0, k['lx'] + 2.0
        f = st.pressed.get(k['n'], 0.0)
        rise = lug_rise(k, f, TAIL_LUG[1]) if f else 0.0
        for b in SPACE_BITS:
            bar_rise[b] = max(bar_rise.get(b, 0.0), rise)
        z0 = PUSH_Z0 + rise
        xc = k['lx']
        m = box(x0, x1, 6.5, tail - 0.5, z0, z0 + 2.0)
        for b in SPACE_BITS:
            m = m + box(x0 + 0.5, x1 - 0.5, BIT_Y[b] - 1.2, BIT_Y[b] + 1.2, z0 + 2.0, z0 + 4.0)
        m = m + box(xc - 1.5, xc + 1.5, tail + 0.5, tail + 2.5, z0 - 3, z0 + 2.0) + box(xc - 1.5, xc + 1.5, tail - 0.5, tail + 0.5, z0, z0 + 2.0)
        parts.append(Part(f"column pusher {k['id']}", 'select', 'print', m, COL['pin'], 'col_pusher_sp', 'PETG', mov=f"selS{k['n']}"))
    # rev. 0.9b: one piece: slots open to the front only, a back strip joins the blocks; slot floor = rest of the tongues
    guide = box(lever_x(-1) - 4, lever_x(44) + 4, tail + 0.3, tail + 5.0, P.LEVER_Z1 - 6, P.LEVER_Z1 + 9)
    guide = guide - union([box((lever_x(4 * c) + lever_x(4 * c + 3)) / 2 - 1.8, (lever_x(4 * c) + lever_x(4 * c + 3)) / 2 + 1.8,
                               tail, tail + 3.0, PUSH_Z0 - 3.0, P.LEVER_Z1 + 10) for c in range(P.NPOS)] +
                          [box(lever_x(n) - 1.8, lever_x(n) + 1.8, tail, tail + 3.0, PUSH_Z0 - 3.0, P.LEVER_Z1 + 10) for n in (-1, 44)])
    parts.append(Part('pusher guide', 'select', 'print', guide, (110, 112, 120), 'pusher_guide', 'PETG'))
    for sx in (-1, 1):
        parts.append(Part(f'selector post {sx:+d}', 'select', 'print',
                          box(sx * 164 - 3, sx * 164 + 3, 8, 25, 0, 84) if sx < 0 else box(163.0, 167.5, 8, 25, 0, 84),
                          (110, 112, 120), 'sel_post', 'PETG'))
    # bars: lift bits above the tails, rotate bits above the pushers
    bar_rise = bit_rises(st)
    for b, yb in BIT_Y.items():
        if b[0] == 'l':
            zb = BIT_Z
        else:
            zb = PUSH_Z0 + 4.0          # rev. 0.9b: r bars rest on the pushers' lugs
        up = SEL_RISE if b in st.bits else bar_rise.get(b, 0.0)
        bar = box(-140 if b[0] == 'l' else lever_x(-1) - 3, BAR_X1 if b[0] == 'r' else 125, yb - 1.4, yb + 1.4, zb, zb + 3.0)
        rx = ROD_X[b]
        # rev. 0.8: the latch pins lie over the lever field, so the rod is a bent wire: up from the bar end outside
        # the field, along X over the lever tails, up again under the pin to its finger
        xo = ROD_OUT_X if b[0] == 'r' else -ROD_OUT_X
        bar = bar + box(xo - 2, xo + 2, yb - 1.4, yb + 1.4, zb, zb + 3)
        rod = zcyl(xo, yb, zb + 3, ROD_ARM_Z + 1.5, 1.5, 12) + cyl((xo, yb, ROD_ARM_Z), (rx, yb, ROD_ARM_Z), 1.5, 12) + \
            zcyl(rx, yb, ROD_ARM_Z - 1.5, P.UF_Z - 2.0, 1.5, 12)
        fy = finger_y('rotate' if b[0] == 'r' else 'lift')          # finger under the latch pin lane
        rod = rod + box(rx + FINGER_X[0], rx + FINGER_X[1], fy[0], fy[1], P.UF_Z - 4.0, P.UF_Z - 2.0)
        rod = rod + zcyl(rx, yb, 87.0, 88.5, 2.4, 16)          # rev. 0.9b: collar resting on the comb (the rest stop of the bar)
        parts.append(Part(f'selector bar {b}', 'select', 'print', bar.translate((0, 0, up)), COL['bail'], f'sel_bar_{b[0]}', 'PETG',
                          note='планка выбора; печатается двумя частями', mov=f'bit{b}',
                          printable=lambda bar=bar: split_planes(bar, 0, [0.0])))
        parts.append(Part(f'selector rod {b}', 'select', 'buy', rod.translate((0, 0, up)), COL['steel'], 'rod3x40', 'сталь',
                          'пруток 3 мм', mov=f'bit{b}'))
    # comb guiding the selector rods (fixed, on the selector posts)
    comb = box(-164, 167, -9, 25, 84, 87) - union([zcyl(ROD_X[b], yb, 83, 88, 1.8, 12) for b, yb in BIT_Y.items()])
    comb = comb - union([box(-150, -140, -10, 26, 83, 88), box(138.5, 162.2, -10, 23, 83, 88),
                         box(-24, 14, 21, 26, 83, 88)])     # cam push rods and the U-frame arm pass here
    comb = comb + box(-154, -136, 25, 29, 84, 87) + box(134.5, 162, 25, 29, 84, 87)       # rev. 0.9b: bridges
    parts.append(Part('selector comb', 'select', 'print', comb, (110, 112, 120), 'sel_comb', 'PETG',
                      printable=lambda comb=comb: split_planes(comb, 0, [0.0])))
    return parts


# --------------------------------------------------------------------------------------- the U-frame
Z_B0 = P.UF_Z + P.UF_T                         # top of the U-frame base
CAM_X = {'lift': -145.0, 'rotate': 140.0, 'detent': 145.0, 'hammer': 150.0, 'ribbon': 160.0}
CAM_Y = 3.0
WT_Z = (Z_B0, Z_B0 + 8.0)                      # whiffletree layer on the base
SLIDER_X = P.PULLEY_R                          # tape leaves the pulley tangentially at x = +R, toward +Y
SLIDER_Y0 = -14.0                              # slider at home (rev. 0.8: off the pulley flange at position 0)


def tape_y(st):
    """rev. 0.8: the rotate tree moves its output toward -Y; the tape is wound the other way round the pulley."""
    return SLIDER_Y0 - (st.pos - (P.NPOS - 1) / 2) * P.TAPE_PER_POS


# ------------------------------------------------------------------- rev. 0.8: selection unit worked out
SEL = LK.selection()
S_STROKE = LK.S
SL_Z = (Z_B0 + 0.5, Z_B0 + 3.5)                 # bit and node sliders: steel strip 4 x 3 in grooves of a guide plate
LEV_Z = [(SL_Z[1] + 1.0 + 2.0 * k, SL_Z[1] + 2.5 + 2.0 * k) for k in range(3)]   # summing levers, one layer each
DB_Z = (Z_B0 + 9.6, Z_B0 + 13.0)                # drive bail (catches raised latch pins only)
AMP_Z = (Z_B0 + 13.5, Z_B0 + 15.0)              # amplifier lever, above the bail
FS_Z = (AMP_Z[1] + 0.5, AMP_Z[1] + 3.5)         # fulcrum slide, above the amplifier
PIN_LOW = (P.UF_Z - 1.5, Z_B0 + 9.0)            # latch pin at rest: bottom just over the rod finger, top under the bail
LIFT_BC_Z = SL_Z[1] - 25.5                      # pivot of the lift output bellcrank (under the base)
# each tree: the direction its sliders move (+1: +Y, -1: -Y), the latch lane (pin y at rest), the band of the levers.
# Everything stays in front of y = 28: behind that the carriage end plates sweep down to z = 84.
TREE = {
    'rotate': dict(bits=['r1', 'r2', 'r4', 'r8'], sel=SEL['rotate'], y_amp=None, cam='rotate', dir=-1, y_pin=19.0, y_tree=2.0),
    'lift': dict(bits=['l1', 'l2', 'l4'], sel=SEL['lift'], y_amp=-36.0, cam='lift', dir=+1, y_pin=-4.0, y_tree=13.0),
}
FINGER_X = (-P.SLIDE_MAX - 2.0, 2.0)            # rod finger along X (the U-frame slides up to 9 mm toward -X)
CAM_FINGER_Y = {'rotate': -8.0, 'detent': 3.0, 'hammer': 20.0, 'lift': -22.0, 'ribbon': -1.35}
# finger extent along X: wide under the narrow bellcrank arms; narrow under the long links (the links reach over the slide)
CAM_FINGER_X = {'rotate': FINGER_X, 'lift': FINGER_X, 'detent': (-2.0, 2.0), 'hammer': (-2.0, 2.0), 'rowdet': (-2.0, 2.0), 'ribbon': (-2.0, 2.0)}
ROD_X = {}
for _name, _t in TREE.items():
    for _b, _x in zip(_t['bits'], _t['sel']['tree']['b']):
        ROD_X[_b] = _x


def finger_y(name):
    t = TREE[name]
    return (t['y_pin'] - 2.0, t['y_pin'] + S_STROKE + 2.0) if t['dir'] > 0 else (t['y_pin'] - S_STROKE - 2.0, t['y_pin'] + 2.0)


def tree_pose(st, name):
    """Bits (0/1 per weight) and drive phase f of a whiffletree, consistent with the shuttle position in st."""
    t = TREE[name]; nb = len(t['bits'])
    raised = [1 if b in st.bits else 0 for b in t['bits']]
    c_bits = sum(v << i for i, v in enumerate(raised))
    if name == 'rotate':
        h = (P.NPOS - 1) / 2; d = st.pos - h
        if any(raised) and abs(c_bits - h) > 1e-9:
            c = c_bits
        elif abs(d) > 1e-9:
            c = P.NPOS - 1 if d > 0 else 0
        else:
            c = c_bits
        f = d / (c - h) if abs(c - h) > 1e-9 else (cam_lift('out', st.cycle) if st.cycle else 0.0)
    else:
        d = st.row - P.REST_ROW
        c = c_bits if any(raised) else (P.NROWS - 1 if d > 1e-9 else 0)
        f = d / (c - P.REST_ROW)
    f = min(max(f, 0.0), 1.0)
    return [(c >> i) & 1 for i in range(nb)], f


def tree_nodes(name, bits, f):
    sel = TREE[name]['sel']
    y, n = LK.node_y(sel['tree'], bits, f)
    amp = sel['amp']
    yF = amp['delta'] * f
    yo = amp['G'] * n[-1] + (1 - amp['G']) * yF
    return y, n, yF, yo


def _lever(x0, y0, x1, y1, z, w=5.0, pad=3.0):
    """Slotted lever between pins (x0, y0) and (x1, y1) at layer z (pins slide along the slots)."""
    L = math.hypot(x1 - x0, y1 - y0)
    m = box(-pad, L + pad, -w / 2, w / 2, *z)
    a = math.degrees(math.atan2(y1 - y0, x1 - x0))
    return rotz(m, a, 0, 0).translate((x0, y0, 0))


LIFT_BC_H = 22.0          # rev. 0.9b: arms of the lift bellcrank
SL_PIN_Z = 111.0          # height of the output slider's pin
DET_TIP = P.DETENT_R + 0.15                 # rev. 0.9c: pawl nose at rest; it goes in 3 mm
DET_WEDGE = (3.9, 2.5)                      # wedge length along X and half-width
DET_RISE = 3.0            # rev. 0.9c: rise of the detent link (incline 1:1 -> pawl 3 mm)
DET_INC_X = 86.0          # rev. 0.9b: foot of the pawl's incline (x at the bottom of the detent plane)


def row_incline_normal():
    """Normal (x, z) of the plane between the row link (moves -3 along X) and the wedge's roller (moves -5 along the
    wedge direction): equal normal speeds; it points from the link to the roller."""
    ux, uz = math.cos(math.radians(ROWDET_DIR)), math.sin(math.radians(ROWDET_DIR))
    # -3 nx = -5 (nx ux + nz uz)  ->  nz = nx (3 - 5 ux) / (5 uz)
    nx = 1.0; nz = nx * (3.0 - 5.0 * ux) / (5.0 * uz)
    n = math.hypot(nx, nz)
    nx, nz = nx / n, nz / n
    return (-nx, -nz) if nx > 0 else (nx, nz)


def drive_bc_geom(name):
    """rev. 0.9b: drive bellcrank of a tree: pivot, arm length, where the cam rod's pin and the bail's pin sit."""
    t = TREE[name]; s = t['dir']
    yP = t['y_pin']
    yb0 = yP - s * 5.5                     # the bail's edge touches a raised latch pin
    zp = Z_B0 + 3.0
    L = (DB_Z[0] + DB_Z[1]) / 2 - zp       # both arms: the bail's pin height over the pivot
    xc = CAM_X[t['cam']]
    xa = xc - 6.0                          # rev. 0.9c: output arm on the -X side (the slide moves away from the rod's riser)
    if s > 0:
        yp = yb0 + 2.0; ytip = yp - L
    else:
        ytip = CAM_FINGER_Y[t['cam']]; yp = ytip - L
    return dict(yb0=yb0, yp=yp, zp=zp, L=L, ytip=ytip, xc=xc, xa=xa)


def selection_unit(st, T):
    """Whiffletrees on the U-frame base: bit sliders with latch pins, node sliders, summing levers, the drive bail
    with its bellcrank, the amplifier with its fulcrum slide; for the lift, the output slider and the 1:1 bellcrank
    that pushes the fork yoke."""
    parts = []
    RISES = bit_rises(st)
    for name, t in TREE.items():
        sel = t['sel']; tr = sel['tree']; amp = sel['amp']; s = t['dir']
        y_amp = t['y_amp'] if t['y_amp'] is not None else SLIDER_Y0
        yP, yT = t['y_pin'], t['y_tree']
        bits, f = tree_pose(st, name)
        yb, yn, yF, yo = tree_nodes(name, bits, f)
        xs_b, xs_n = tr['b'], tr['n']
        nb = len(xs_b)
        allx = xs_b + xs_n[1:]
        x0g, x1g = min(allx) - 6, max(allx) + 6
        # guide plate with grooves (covers the latch lane and the lever band)
        ya0, ya1 = sorted((yP, yT))
        g = box(x0g, x1g, ya0 - 5, ya1 + 5, Z_B0, Z_B0 + 1.5)
        g = g - union([box(x - 2.15, x + 2.15, ya0 - 6, ya1 + 6, Z_B0 + 0.5, Z_B0 + 2) for x in allx])
        fy = finger_y(name)
        g = g - union([box(x - 2.2, x + 2.2, fy[0], fy[1], Z_B0 - 1, Z_B0 + 2) for x in xs_b])
        xc_ = CAM_X[t['cam']]
        yf_ = CAM_FINGER_Y[t['cam']]
        x_cut = xc_ + P.SLIDE_MAX + 3
        if t['cam'] in ('rotate', 'lift'):
            # rev. 0.11: these rods carry their finger at x + 2.6..4 out to the bellcrank's tip; with the unit retracted
            # the full 17 u (a mark under the line after a wide letter) the plate's end met the lifted finger -- found
            # by the idle-cycle scenario, which is the first to turn the shaft with the unit retracted
            yf_ = drive_bc_geom(t['cam'])['ytip']
            x_cut = max(x_cut, xc_ + 4.0 + P.SLIDE_MAX + 0.5)
        g = g - box(xc_ + CAM_FINGER_X[t['cam']][0] - 3, x_cut, min(CAM_Y, yf_) - 3, max(CAM_Y, yf_) + 3, Z_B0 - 1, Z_B0 + 2)
        parts.append(Part(f'{name} guide plate', 'uframe', 'print', T(g), (110, 112, 120), f'guide_{name}', 'PETG', mov='uframe'))
        # bit sliders with latch pins
        for i, (b, x) in enumerate(zip(t['bits'], xs_b)):
            dy = s * yb[i]
            sl = box(x - 2, x + 2, ya0 - 3, ya1 + 3, *SL_Z).translate((0, dy, 0))
            parts.append(Part(f'{name} bit slider {b}', 'uframe', 'buy', T(sl), COL['steel'], 'strip4x3x40', 'сталь',
                              'ползун разряда: полоса 4×3 мм', mov='wtree'))
            up = 3.5 if b in st.bits else max(0.0, RISES.get(b, 0.0) - 0.5)   # rev. 0.9b: the rod lifts the pin
            pin = zcyl(x, yP + dy, PIN_LOW[0] + up, PIN_LOW[1] + up, 1.5, 12)
            parts.append(Part(f'{name} latch pin {b}', 'uframe', 'buy', T(pin), COL['steel'], 'pin3x17', 'сталь',
                              'палец защёлки 3 мм с пружиной вниз', mov='wtree'))
        # node sliders (intermediate nodes and the tree output)
        for k in range(1, nb):
            x = xs_n[k]; dy = s * yn[k]
            if k == nb - 1:
                y0, y1 = sorted((y_amp, yT)); y0 -= 3; y1 += 3
            else:
                y0, y1 = yT - 4, yT + 4
            sl = box(x - 2, x + 2, y0, y1, *SL_Z).translate((0, dy, 0))
            parts.append(Part(f'{name} node slider {k}', 'uframe', 'buy', T(sl), COL['steel'], 'strip4x3x30', 'сталь', mov='wtree'))
        # summing levers: lever k joins node k-1 (node 0 = bit 0) and bit k; node k rides on it
        for k in range(1, nb):
            xa, ya = xs_n[k - 1], yT + s * yn[k - 1]
            xb, yb_ = xs_b[k], yT + s * yb[k]
            lv = _lever(xa, ya, xb, yb_, LEV_Z[k - 1])
            pins = union([zcyl(xx, yy, SL_Z[1], LEV_Z[k - 1][1] + 0.6, 1.0, 10) for xx, yy in
                          ((xa, ya), (xb, yb_), (xs_n[k], yT + s * yn[k]))])
            parts.append(Part(f'{name} summing lever {k}', 'uframe', 'print', T(lv + pins), COL['sector'], f'wlever_{name}_{k}', 'PETG',
                              note='рычаг с пазами под пальцы 2 мм', mov='wtree'))
        # amplifier: second-class lever, pins in slots: fulcrum (on its slide), input (tree output), output
        xF, xi, xo = amp['x_F'], amp['x_in'], amp['x_out']
        lv = _lever(xo, y_amp + s * yo, xF, y_amp + s * yF, AMP_Z, w=6.0)
        pins = zcyl(xi, y_amp + s * yn[-1], SL_Z[1], AMP_Z[1] + 0.6, 1.0, 10)
        # rev. 0.9b: the output pin goes down into the output slider (lift) or the tape slider (rotate)
        pins = pins + (zcyl(xo, y_amp + s * yo, SL_Z[1] - 0.5, AMP_Z[1] + 0.6, 1.0, 10) if name == 'lift' else
                       zcyl(xo - 0.5, y_amp + s * yo, Z_B0 + 7.5, AMP_Z[1] + 0.6, 1.0, 10))
        parts.append(Part(f'{name} amplifier', 'uframe', 'print', T(lv + pins), COL['sector'], f'amp_{name}', 'PETG',
                          note=f'усилитель {amp["G"]:.2f}: пальцы в пазах; винт нуля на опоре, винт передаточного числа на входе',
                          mov='wtree'))
        fs = box(xF - 2, xF + 2, y_amp - 6, y_amp + 6, *FS_Z).translate((0, s * yF, 0)) + \
            zcyl(xF, y_amp + s * yF, AMP_Z[0] - 0.6, FS_Z[0] + 0.5, 1.0, 10)
        parts.append(Part(f'{name} fulcrum slide', 'uframe', 'buy', T(fs), COL['steel'], 'strip4x3x12', 'сталь',
                          'ползун опоры: смещение нуля от ведущей планки', mov='wtree'))
        # drive bail: on the far side of the pins from the direction of motion... it pushes the raised pins along
        g = drive_bc_geom(name)
        yb0, yp, zp, L, ytip, xc, xa = g['yb0'], g['yp'], g['zp'], g['L'], g['ytip'], g['xc'], g['xa']
        lift_in = S_STROKE * f                              # rise of the cam rod's pin
        ylo, yhi = min(yb0, yb0 + s * 4), max(yb0, yb0 + s * 4)
        bar = box(x0g - 2, x1g + 2, ylo, yhi, *DB_Z)
        # rev. 0.9b: the bail's arm ends beside the bellcrank's output arm; its pin runs in the arm's slot
        if xc < 0:
            bar = bar + box(xa + 2.2, x0g, ylo, yhi, *DB_Z)
        if s > 0:
            bar = bar + cyl((xa - 3.0, yp, zp + L), (xa + 2.2, yp, zp + L), 1.2, 12)
        bar = bar.translate((0, s * S_STROKE * f, 0))
        parts.append(Part(f'{name} drive bail', 'uframe', 'cut', T(bar), COL['steel'],
                          'bail_plate', 'сталь', 'ведущая планка 3 мм, ход 12 мм', mov='wtree'))
        # rev. 0.9b: bellcrank with two radial slots; the pins sit on the parts that move straight (the cam rod's finger
        # and the bail or its link), so the bail travels exactly as far as the rod: L tan(phi) both sides
        ang = math.degrees(math.atan2(lift_in, L)) * (-1 if s > 0 else 1)
        rmax = math.hypot(L, S_STROKE) + 2.0                # the pins slide out to L / cos(phi_max)
        sy = -1 if s > 0 else 1
        r0 = L - 2.5
        yi0, yi1 = sorted((yp, yp + sy * (rmax + 1.5)))
        sl0, sl1 = sorted((yp + sy * r0, yp + sy * rmax))
        bc = box(xc - 2, xc + 2, yi0, yi1, zp - 2.5, zp + 2.5) - box(xc - 3, xc + 3, sl0, sl1, zp - 1.2, zp + 1.2)
        bc = bc + (box(xa - 2, xa + 2, yp - 2.5, yp + 2.5, zp, zp + rmax + 1.5) - box(xa - 3, xa + 3, yp - 1.2, yp + 1.2, zp + r0, zp + rmax))
        bc = bc + cyl((min(xc, xa) - 2.5, yp, zp), (max(xc, xa) + 2.5, yp, zp), 2.5, 16) - cyl((min(xc, xa) - 3, yp, zp), (max(xc, xa) + 3, yp, zp), 1.05, 12)
        parts.append(Part(f'{name} drive bellcrank', 'uframe', 'print', T(rotx(bc, ang, yp, zp)), COL['pin'], f'bellcrank_{name}', 'PETG',
                          note='качалка с двумя радиальными пазами от толкателя кулачка к ведущей планке', mov='wtree'))
        if s < 0:
            # rev. 0.9c: the link runs at x < xa - 6, outside the lane of the cam rod's long pin (x 128..144)
            link = box(xa - 8.0, xa - 6.2, yp - 3.0, yb0 + s * 2.0, zp + L - 0.3, zp + L + 2.7) + \
                cyl((xa - 8.0, yp, zp + L), (xa + 2.2, yp, zp + L), 1.2, 12)
            parts.append(Part(f'{name} drive link', 'uframe', 'cut', T(link.translate((0, -S_STROKE * f, 0))), COL['steel'], 'strip3x1_5', 'сталь',
                              'тяга от качалки к ведущей планке, палец в пазу качалки', mov='wtree'))
        if name == 'lift':
            # output slider at x_out moving along +Y, the 1:1 bellcrank (axis along X) and the push rod to the fork yoke
            os_ = box(xo - 2, xo + 2, y_amp - 4, y_amp + 8, *SL_Z).translate((0, yo, 0))
            parts.append(Part('lift output slider', 'uframe', 'buy', T(os_), COL['steel'], 'strip4x3x12', 'сталь', mov='wtree'))
            # rev. 0.9b: equal arms h = 22 (pin of the output slider) and 22 (pin of the push rod), both pins on the parts
            # that move straight, slots in the arms: the push rod rises exactly as far as the slider moves
            hb = LIFT_BC_H
            yb_p, zb_p = P.AXIS_Y + hb, SL_PIN_Z - hb
            angb = -math.degrees(math.atan2(yo, hb))
            xb0, xb1 = xo + 2.2, xo + 5.0
            # rev. 0.9c: the pins slide out along the arms to hypot(h, yo) (28.6 mm at row 7): slots to there plus 1 mm
            yo_max = tree_nodes('lift', [(P.NROWS - 1 >> i) & 1 for i in range(len(t['bits']))], 1.0)[3]
            rb = math.hypot(hb, yo_max) + 1.0
            bcl = box(xb0, xb1, yb_p - 2.5, yb_p + 2.5, zb_p, zb_p + rb + 2.0) - box(xb0 - 1, xb1 + 1, yb_p - 1.2, yb_p + 1.2, zb_p + hb - 2.0, zb_p + rb)
            bcl = bcl + box(xb0, xb1, yb_p - rb - 2.0, yb_p, zb_p - 2.5, zb_p + 2.5) - box(xb0 - 1, xb1 + 1, yb_p - rb, yb_p - hb + 2.0, zb_p - 1.2, zb_p + 1.2)
            bcl = bcl + cyl((xo - 3, yb_p, zb_p), (xb1, yb_p, zb_p), 2.5, 16) - cyl((xo - 4, yb_p, zb_p), (xb1 + 1, yb_p, zb_p), 1.05, 12)
            parts.append(Part('lift bellcrank', 'uframe', 'print', T(rotx(bcl, angb, yb_p, zb_p)), COL['pin'], 'bellcrank_lift_out', 'PETG',
                              note='угловая качалка 1:1 с пазами от выходного ползуна к толкателю вилки', mov='wtree'))
            spin = cyl((xo - 1.0, yb_p, SL_PIN_Z), (xb1 + 0.5, yb_p, SL_PIN_Z), 1.2, 12).translate((0, yo, 0))
            parts.append(Part('lift output pin', 'uframe', 'buy', T(spin), COL['steel'], 'pin2x8', 'сталь', 'палец выходного ползуна', mov='wtree'))
            zf = FORK_Z + 2.0
            push = zcyl(xo, P.AXIS_Y, zb_p - 2.5, FORK_Z - 2.5, 2.0, 16) + cyl((xo - 2.0, P.AXIS_Y, zb_p), (xb1 + 0.5, P.AXIS_Y, zb_p), 1.2, 12)
            push = push + box(xo - 2, xo + 2, P.AXIS_Y + 3.2, P.AXIS_Y + 5.2, FORK_Z - 4.0, zf + 2.5) + \
                box(xo - 2, xo + 2, P.AXIS_Y - 5.2, P.AXIS_Y - 3.2, FORK_Z - 4.0, zf + 2.5) + \
                box(xo - 2, xo + 2, P.AXIS_Y - 5.2, P.AXIS_Y + 5.2, FORK_Z - 4.0, FORK_Z - 2.5) + \
                cyl((xo, P.AXIS_Y - 5.2, zf), (xo, P.AXIS_Y + 5.2, zf), 1.2, 12)
            parts.append(Part('lift push rod', 'uframe', 'buy', T(push.translate((0, 0, yo))), COL['steel'], 'rod4x40', 'сталь',
                              'толкатель вилки с вилкой-серьгой и пальцем', mov='wtree'))
            hang = box(xo - 7, xo - 3, yb_p - 4, yb_p + 4, zb_p - 4, P.UF_Z) - cyl((xo - 8, yb_p, zb_p), (xo - 2, yb_p, zb_p), 1.05, 12)
            parts.append(Part('lift bellcrank bracket', 'uframe', 'print', T(hang), (110, 112, 120), 'bellcrank_bracket', 'PETG', mov='uframe'))
    return parts



def whiffletree(x0, x1, y0, y1, nbits, out_x, out_y, name):
    """Schematic whiffletree: input latches (one per bit), summing levers in a ladder, output link."""
    zl, zh = WT_Z
    parts = []
    span = x1 - x0
    for i in range(nbits):
        y = y0 + 3 + i * (y1 - y0 - 6) / max(1, nbits - 1)
        parts.append(box(x0, x1 - 6, y - 1.2, y + 1.2, zl + 1, zl + 3.5))          # bit link
    for i in range(nbits - 1):
        xm = x0 + 10 + i * (span - 30) / max(1, nbits - 2)
        parts.append(box(xm - 1.2, xm + 1.2, y0 + 2, y1 - 2, zl + 4, zl + 6.5))     # summing lever
    parts.append(box(min(out_x, x0), max(out_x, x0) + 2, out_y - 1.2, out_y + 1.2, zl + 4, zl + 6.5))  # output link
    return union(parts)


def uframe(st):
    parts = []; dx = -st.slide()
    T = lambda m: m.translate((dx, 0, 0))
    base = box(-130, 140, -165, 23, P.UF_Z, Z_B0)
    base = base + box(-160, -130, -16, 20, P.UF_Z, Z_B0) + box(140, 166, -10, 20, P.UF_Z, Z_B0)    # pads over the cam rods
    base = base - zcyl(0, P.AXIS_Y, P.UF_Z - 1, Z_B0 + 1, 11.05, 32)
    # slots for the fixed selector and cam rods (the base slides up to 9 mm toward -X)
    slots = []
    for name, t in TREE.items():                                   # latch pins and the rod fingers under them
        fy = finger_y(name)
        slots += [box(x - 2.2 + FINGER_X[0] + 2.0, x + 2.2 + P.SLIDE_MAX, fy[0] - 0.5, fy[1] + 0.5, P.UF_Z - 1, Z_B0 + 1)
                  for x in t['sel']['tree']['b']]
    xo_l = SEL['lift']['amp']['x_out']                              # lift output bellcrank and push rod pass the base
    slots.append(box(xo_l - 3, xo_l + 6, P.AXIS_Y - 12, TREE['lift']['y_amp'] + 21, P.UF_Z - 1, Z_B0 + 1))
    for kind, x in CAM_X.items():                                  # cam rod fingers reach the bellcranks and links
        yf = drive_bc_geom(kind)['ytip'] if kind in ('rotate', 'lift') else CAM_FINGER_Y[kind]
        x_hi = x + 4.2 + P.SLIDE_MAX if kind in ('rotate', 'lift') else x + P.SLIDE_MAX + 2.2   # rev. 0.9c: the riser lane
        slots.append(box(x + CAM_FINGER_X[kind][0] - 0.2, x_hi, min(CAM_Y, yf) - 2.2, max(CAM_Y, yf) + 2.2, P.UF_Z - 1, Z_B0 + 1))
    base = base - union(slots)
    arm = box(-12, 12, 23, 29, P.ARM_Z0, Z_B0) + box(-12, 12, 23, P.POST_Y[1], P.ARM_Z0, P.ARM_Z1)
    post = box(-8, 8, *P.POST_Y, P.ARM_Z1, P.HAMMER_PIVOT[1] + 7)
    post = post - cyl((-9, P.HAMMER_PIVOT[0], P.HAMMER_PIVOT[1]), (9, P.HAMMER_PIVOT[0], P.HAMMER_PIVOT[1]), 2.05, 16)
    post = post - box(-4.5, 4.5, P.POST_Y[0] - 1, P.POST_Y[1] + 1, P.HAMMER_PIVOT[1] - 8, P.HAMMER_PIVOT[1] + 8)
    parts.append(Part('U-frame base', 'uframe', 'cut', T(base), COL['uframe'], 'uframe_plate', 'Д16Т',
                      note='плита 326×188×6 мм из алюминиевого сплава, сверловка по шаблону', mov='uframe'))
    parts.append(Part('U-frame arm and hammer post', 'uframe', 'print', T(arm + post), COL['uframe'], 'uframe_arm', 'PETG',
                      mov='uframe'))
    for yr in P.RAIL_Y:
        for sx in (-60, 60):
            parts.append(Part(f'MGN12H block {yr:.0f} {sx:+d}', 'uframe', 'buy',
                              T(box(sx - 13.5, sx + 13.5, yr - 13.5, yr + 13.5, P.RAIL_Z + 3, P.UF_Z)), COL['buy'],
                              'MGN12H', 'сталь', 'каретка MGN12H', mov='uframe'))
    tower = zcyl(0, P.AXIS_Y, 76, P.UF_Z, 16, 48) - zcyl(0, P.AXIS_Y, 75, P.UF_Z + 1, 11.05, 32)
    tower = tower + zcyl(0, P.AXIS_Y, 76, 79, 16, 48) - zcyl(0, P.AXIS_Y, 75, 80, 4.5, 24)
    parts.append(Part('shaft tower', 'uframe', 'print', T(tower), COL['uframe'], 'tower', 'PETG', mov='uframe'))
    for z in (80.0, P.UF_Z - 1):
        parts.append(Part(f'bearing 608 z{z:.0f}', 'uframe', 'buy', T(zcyl(0, P.AXIS_Y, z, z + 7, 11, 32) - zcyl(0, P.AXIS_Y, z - 1, z + 8, 4.02, 24)),
                          COL['buy'], '608', 'сталь', 'подшипник 608 (8×22×7)', mov='uframe'))
    # rotate output: tape slider on a short MGN7 rail along Y, tangent to the pulley
    parts.append(Part('tape rail MGN7', 'uframe', 'buy', T(box(SLIDER_X + 2, SLIDER_X + 9, -52, 23, Z_B0, Z_B0 + 5)), COL['buy'],
                      'MGN7_75', 'сталь', 'линейная направляющая MGN7, 75 мм', mov='uframe'))
    ty = tape_y(st)
    sl = box(SLIDER_X + 0.5, SLIDER_X + 10.5, ty - 11, ty + 11, Z_B0 + 1.5, Z_B0 + 8)
    parts.append(Part('tape slider MGN7H', 'uframe', 'buy', T(sl), COL['buy'], 'MGN7H', 'сталь', 'каретка MGN7H', mov='tape'))
    clamp = box(SLIDER_X - 0.2, SLIDER_X + 0.5, ty - 8, ty + 8, P.Z_PULLEY[0], P.Z_PULLEY[1]) + \
        box(SLIDER_X + 0.5, SLIDER_X + 4, ty - 8, ty + 8, Z_B0 + 8, P.Z_PULLEY[1])
    parts.append(Part('tape clamp', 'uframe', 'print', T(clamp), COL['pin'], 'tape_clamp', 'PETG', mov='tape'))
    tape = box(SLIDER_X - 0.1, SLIDER_X, P.AXIS_Y, ty - 8, P.Z_PULLEY[0] + 0.5, P.Z_PULLEY[1] - 0.5)
    parts.append(Part('rotate tape', 'uframe', 'buy', T(tape), (60, 60, 70), 'tape', 'сталь',
                      'стальная лента 5×0,1 мм', mov='tape'))
    # rev. 0.8: the selection unit worked out (whiffletrees with latches, bails, amplifiers, output links)
    parts += selection_unit(st, T)
    # detent: notched wheel on the shaft, pawl from +X
    # rev. 0.9b: the cam lifts the detent link 6 mm; its tongue slides down a 2:1 incline on the pawl's end, so the pawl
    # (a rigid slider, with the row-detent link screwed to it) goes in 3 mm exactly; a spring returns it
    eng = st.detent
    zd0, zd1 = P.Z_DETENT
    zl = (zd1 + 4.0, zd1 + 7.0)
    inc = lambda z: DET_INC_X + (z - zd0) * 3.0 / DET_RISE   # the incline: x of the face at height z (rev. 0.9c: 1:1)
    yA = P.AXIS_Y
    xw = DET_TIP + DET_WEDGE[0]
    pts = [(xw - 0.01, zd0), (inc(zd0), zd0), (inc(zl[0] - 0.5), zl[0] - 0.5), (xw - 0.01, zl[0] - 0.5)]
    pawl = CrossSection([geo._ccw(pts)]).extrude(5.0).transform(np.array([[1, 0, 0, 0], [0, 0, 1, yA - 2.5], [0, 1, 0, 0]], float))
    # rev. 0.9c: the pawl's nose is a wedge that fits the wheel's V notches (tip 0.15 mm off the rim at rest)
    pawl = pawl + CrossSection([geo._ccw([(DET_TIP, yA), (xw, yA - DET_WEDGE[1]), (xw, yA + DET_WEDGE[1])])]).extrude(zl[0] - 0.5 - zd0).translate((0, 0, zd0))
    pawl = pawl + box(78, 84, yA - 6, yA + 6, Z_B0, zd0 + 0.01)
    parts.append(Part('detent pawl', 'uframe', 'print', T(pawl.translate((-3.0 * eng, 0, 0))), COL['pin'], 'detent_pawl', 'PETG',
                      note='клин из стали 3 мм в печатном ползуне; наклон 2:1 под язык тяги', mov='detent'))
    xtr = inc(zl[1]) + 3.0
    tpts = [(inc(zd0 + 0.5), zd0 + 0.5), (xtr, zd0 + 0.5), (xtr, zl[1]), (inc(zl[1]), zl[1])]
    tongue = CrossSection([geo._ccw(tpts)]).extrude(5.0).transform(np.array([[1, 0, 0, 0], [0, 0, 1, yA - 2.5], [0, 1, 0, 0]], float))
    xt = inc(zl[1]) + 1.0          # rev. 0.9c: over the tongue's top (the 1:1 incline moved it out)
    # rev. 0.9c: the post bridges over the ribbon link (y -2.6..-0.1, up to 137.5 when lifted) at z 138..141
    zb_ = (138.0, 141.0)
    link = tongue + box(xt - 2, xt + 2, yA - 2.5, -4.0, *zl) + box(xt - 2, xt + 2, -6.0, -4.0, zl[0], zb_[1]) + \
        box(xt - 2, xt + 2, -6.0, 2.0, *zb_) + box(xt - 2, xt + 2, 0.2, 2.0, zl[0], zb_[1]) + \
        box(xt - 2, xt + 2, 0.2, CAM_Y + 3, *zl) + box(xt - 2, CAM_X['detent'] + 4 + P.SLIDE_MAX, CAM_Y - 3, CAM_Y + 3, *zl)
    parts.append(Part('detent link', 'uframe', 'print', T(link.translate((0, 0, DET_RISE * eng))), COL['pin'], 'detent_link', 'PETG',
                      note='тяга фиксаторов: кулачок поднимает её на 3 мм', mov='detent'))
    # hammer trip link to the post
    # rev. 0.8: hammer cocking. The cam lifts the trip link 6 mm over 10..150 deg; a rod beside the post lifts the cocking
    # lever on the hammer axle (arm 19.1 mm, 18 deg), winding the hammer spring; at 160 deg the cam drops and the spring
    # throws the hammer (the lever's lip strikes its tail).
    zc_ = 6.0 * st.cock
    yp_, zp_ = P.HAMMER_PIVOT
    hl = box(10, CAM_X['hammer'] + 4 + P.SLIDE_MAX, 13, 22, P.Z_DETENT[1] + 0.5, P.Z_DETENT[1] + 3.5) + \
        box(10, 14, 13, yp_ + LK.hammer_geom()['r_cock'] + 2, P.Z_DETENT[1] + 0.5, P.Z_DETENT[1] + 3.5)
    parts.append(Part('hammer trip link', 'uframe', 'print', T(hl.translate((0, 0, zc_))), COL['hammer'], 'hammer_link', 'PETG',
                      note='тяга взвода от кулачка молотка', mov='cock'))
    rc = LK.hammer_geom()['r_cock']
    # rev. 0.9c: the rod carries a pin (on the part that moves straight) in a radial slot of the lever: exact rc tan(phi)
    rod = box(12.0, 13.5, yp_ + rc - 1.5, yp_ + rc + 1.5, P.Z_DETENT[1] + 3.5, zp_ + 1.5) + cyl((8.0, yp_ + rc, zp_), (13.5, yp_ + rc, zp_), 1.2, 12)
    parts.append(Part('hammer cocking rod', 'uframe', 'buy', T(rod.translate((0, 0, zc_))), COL['steel'], 'rod3x80', 'сталь',
                      'толкатель взвода', mov='cock'))
    r_sl = math.hypot(rc, 6.0) + 1.5
    lev = box(8.6, 11.9, yp_, yp_ + rc - 3.0, zp_ - 1.5, zp_ + 1.5) + box(8.6, 11.9, yp_ + rc - 3.0, yp_ + r_sl + 1.5, zp_ - 3.0, zp_ + 3.0) + \
        cyl((8.6, yp_, zp_), (11.9, yp_, zp_), 4.0, 16) - cyl((8, yp_, zp_), (12.5, yp_, zp_), 2.05, 16)
    lev = lev - box(8, 12.5, yp_ + rc - 2.0, yp_ + r_sl, zp_ - 1.2, zp_ + 1.2)
    a_c = math.degrees(math.atan2(zc_, rc))
    parts.append(Part('hammer cocking lever', 'uframe', 'print', T(rotx(lev, a_c, yp_, zp_)), COL['hammer'], 'cock_lever', 'PETG',
                      note='взводной рычаг на оси молотка', mov='cock'))
    spr = cyl((-11.9, yp_, zp_), (-8.6, yp_, zp_), 4.5, 24) - cyl((-12.5, yp_, zp_), (-8, yp_, zp_), 2.3, 16)
    parts.append(Part('hammer spring', 'uframe', 'buy', T(spr), COL['steel'], 'torsion_spring', 'сталь',
                      'пружина кручения 0,8 мм, 4 витка', mov='uframe'))
    # lift fork
    fork = fork_mesh()
    ang = math.degrees(math.atan2(st.lift() - LIFT_MIN, 150.0))
    fork = geo.roty(fork, -ang, -150, FORK_Z + 2)
    parts.append(Part('lift fork', 'uframe', 'print', T(fork), COL['uframe'], 'lift_fork', 'PETG', mov='lift'))
    parts.append(Part('lift collar', 'uframe', 'print', T(collar_mesh().translate((0, 0, st.lift() - LIFT_MIN))), COL['uframe'],
                      'lift_collar', 'PETG', note='муфта подъёма на упорной шайбе; пальцы 2 мм в пазах вилки', mov='collar'))
    # row detent: wedge on a post, moved along its fixed direction by the link from the fifth cam
    xp_, zp_ = -150.0, FORK_Z + 2
    ux, uz = math.cos(math.radians(ROWDET_DIR)), math.sin(math.radians(ROWDET_DIR))
    yw0, yw1 = P.AXIS_Y - ROWDET_Y - 1.5, P.AXIS_Y - ROWDET_Y + 1.5
    rw = 63.4 - 5.0 * st.detent         # tip stops 0.4 mm short of the notch bottom (r = 58)
    nx, nz = -uz, ux                       # across the wedge
    def at(r, w):
        return (xp_ + r * ux + w * nx, zp_ + r * uz + w * nz)
    poly = [at(rw, 0.0), at(rw + 6.0, -6.0 * math.tan(math.radians(30))), at(rw + 6.0, -1.2), at(rw + 20.0, -1.2),
            at(rw + 20.0, 1.2), at(rw + 6.0, 1.2), at(rw + 6.0, 6.0 * math.tan(math.radians(30)))]
    wedge = CrossSection([geo._ccw(poly)]).extrude(yw1 - yw0).transform(np.array([[1, 0, 0, 0], [0, 0, 1, yw0], [0, 1, 0, 0]], float))
    parts.append(Part('row detent wedge', 'uframe', 'cut', T(wedge), COL['pin'], 'row_wedge', 'сталь',
                      note='клин фиксатора ряда, 60°, ход 5 мм', mov='detent'))
    xg, zg = xp_ + 76 * ux, zp_ + 76 * uz
    post = box(xg - 4, xg + 4, yw0 - 5, yw0 - 1, Z_B0, zg + 6) + box(xg - 10, xg + 4, yw0 - 1, yw1 + 1, zg - 6, zg - 3)
    parts.append(Part('row detent post', 'uframe', 'print', T(post), (110, 112, 120), 'row_post', 'PETG',
                      note='стойка с направляющей клина', mov='uframe'))
    # rev. 0.9b: the row link is screwed to the detent pawl (it moves 3 mm toward -X with it) and runs round the
    # shuttle to an incline that pushes a roller on the wedge: two straight motions joined by a plane, so the wedge
    # goes in exactly 5/3 of the link's travel
    zr0, zr1 = P.Z_DETENT[0], P.Z_DETENT[0] + 3.0
    ux_, uz_ = math.cos(math.radians(ROWDET_DIR)), math.sin(math.radians(ROWDET_DIR))
    mx, mz = row_incline_normal()
    rr_ = 63.4 + 18.0
    cx0, cz0 = xp_ + rr_ * ux_, zp_ + rr_ * uz_               # roller centre at rest (wedge out)
    roller = cyl((cx0 - 5.0 * st.detent * ux_, yw1, cz0 - 5.0 * st.detent * uz_),
                 (cx0 - 5.0 * st.detent * ux_, yw1 + 3.5, cz0 - 5.0 * st.detent * uz_), 2.0, 16)
    parts.append(Part('row detent roller', 'uframe', 'buy', T(roller), COL['steel'], 'pin4x4', 'сталь',
                      'ролик на клине ряда', mov='detent'))
    p0x, p0z = cx0 - 2.0 * mx, cz0 - 2.0 * mz
    tx, tz = -mz, mx
    plate = [(p0x + 6 * tx, p0z + 6 * tz), (p0x - 6 * tx, p0z - 6 * tz), (p0x - 6 * tx - 4 * mx, p0z - 6 * tz - 4 * mz),
             (p0x + 6 * tx - 4 * mx, p0z + 6 * tz - 4 * mz)]
    pl = CrossSection([geo._ccw(plate)]).extrude(3.5).transform(np.array([[1, 0, 0, 0], [0, 0, 1, yw1 + 0.5], [0, 1, 0, 0]], float))
    xr_ = p0x - 4 * mx - 1.5
    zt_ = min(p0z + 6 * tz, p0z - 6 * tz)
    link = box(80, 84, -126, P.AXIS_Y - 1.5, zr0, zr1) + box(xr_ - 1.5, 84, -126, -122, zr0, zr1) + \
        box(xr_ - 1.5, xr_ + 1.5, -126, yw1 + 4.0, zr0, zr1) + box(xr_ - 1.5, xr_ + 1.5, yw1 + 0.5, yw1 + 4.0, zr0, zt_ + 1.0) + pl
    parts.append(Part('row detent link', 'uframe', 'print', T(link.translate((-3.0 * st.detent, 0, 0))), COL['pin'], 'row_link', 'PETG',
                      note='тяга фиксатора ряда: на ползуне фиксатора позиции, наклонная площадка давит на ролик клина', mov='detent'))
    parts.append(Part('lift fork bracket', 'uframe', 'print',
                      T(box(-156, -144, P.AXIS_Y + 6.2, P.AXIS_Y + 10, Z_B0, FORK_Z + 8) + box(-156, -144, P.AXIS_Y - 10, P.AXIS_Y - 6.2, Z_B0, FORK_Z + 8)
                        + box(-156, -144, P.AXIS_Y - 10, P.AXIS_Y + 10, P.UF_Z, Z_B0 + 0.01)
                        - cyl((-150, P.AXIS_Y - 11, FORK_Z + 2), (-150, P.AXIS_Y + 11, FORK_Z + 2), 2.05, 16)),
                      COL['uframe'], 'fork_bracket', 'PETG', mov='uframe'))
    parts.append(Part('lift fork pin', 'uframe', 'buy', T(cyl((-150, P.AXIS_Y - 10, FORK_Z + 2), (-150, P.AXIS_Y + 10, FORK_Z + 2), 2.0, 16)),
                      COL['steel'], 'rod4x24', 'сталь', 'ось вилки подъёма', mov='uframe'))
    parts += hammer(st, dx)
    parts += hammer_lock(st, dx)
    return parts


FORK_Z = P.BLOCK_BOT - 6.0 + (P.REST_ROW - P.HOME_ROW) * P.RH - 4.5     # fork under the hub at the lowest lift (rest)


FORK_Y = (12.0, 16.0)          # fork arms either side of the shaft axis (inside the guide rod's circle, r = 30 - 3)
FORK_SLOT = (-3.0, 29.0)        # slot along the arm for the collar pins; the pin slides out 150 (1/cos - 1) = 26 mm at 31 deg


def fork_mesh():
    """rev. 0.8: two arms with slots; pins of a non-rotating lift collar ride in the slots, so the lift is
    150 tan(angle) exactly and the shuttle axis stays put while the fork turns 31 deg."""
    z0, z1 = FORK_Z, FORK_Z + 4
    arms = []
    for s in (-1, 1):
        y0, y1 = sorted((P.AXIS_Y + s * FORK_Y[0], P.AXIS_Y + s * FORK_Y[1]))
        a = box(-140, FORK_SLOT[1] + 3, y0, y1, z0, z1) - box(FORK_SLOT[0], FORK_SLOT[1], y0 - 1, y1 + 1, z0 + 1.0, z1 - 1.0)
        arms.append(a)
    # rev. 0.9b: the arms are joined behind the bracket cheeks; the push rod's pin rides in a slot of a middle tongue
    # (its clevis straddles the tongue), at d = 30 from the pivot (fork ratio 5)
    yoke = box(-140, -132, P.AXIS_Y - FORK_Y[1], P.AXIS_Y + FORK_Y[1], z0, z1) + box(-112, -108, P.AXIS_Y - FORK_Y[1], P.AXIS_Y + FORK_Y[1], z0, z1)
    tg = box(-126, -108, P.AXIS_Y - 3.0, P.AXIS_Y + 3.0, FORK_Z - 1.0, FORK_Z + 5.0)
    tg = tg - box(-124.5, -111.0, P.AXIS_Y - 4.0, P.AXIS_Y + 4.0, FORK_Z + 2 - 1.2, FORK_Z + 2 + 1.2)
    yoke = yoke + tg
    # rev. 0.8: row detent comb at r = 60 from the pivot, in its own plane beside the arms; notch k faces the fixed wedge
    # (direction 40 deg above the arm) when the fork stands at row k
    yc0, yc1 = P.AXIS_Y - ROWDET_Y - 1.5, P.AXIS_Y - ROWDET_Y + 1.5
    comb = row_comb(yc0, yc1, -150.0, FORK_Z + 2)
    bridge = box(-122.0, -100.0, yc1, P.AXIS_Y - FORK_Y[1], z0, z1) + box(-122.0, -114.0, yc0, yc1, z0, FORK_Z + 2 + 12)
    # rev. 0.9b: a spoke from the bridge out to the comb's inner arc (earlier the comb only touched it)
    th = LK.row_detent()['theta']
    am = math.radians(ROWDET_DIR - (th[0] + th[-1]) / 2)
    xp_, zp_ = -150.0, FORK_Z + 2
    ux, uz = math.cos(am), math.sin(am); vx, vz = -uz, ux
    sp = [(xp_ + r * ux + w * vx, zp_ + r * uz + w * vz) for r, w in ((26.0, -3.0), (ROWDET_R[0] + 1.0, -3.0), (ROWDET_R[0] + 1.0, 3.0), (26.0, 3.0))]
    spoke = CrossSection([geo._ccw(sp)]).extrude(yc1 - yc0).transform(np.array([[1, 0, 0, 0], [0, 0, 1, yc0], [0, 1, 0, 0]], float))
    bridge = bridge + spoke + box(-130.0, -114.0, yc0, yc1, z0, FORK_Z + 2 + 12)
    piv = box(-154, -132, P.AXIS_Y - 6, P.AXIS_Y + 6, z0 - 2, z0 + 6) - cyl((-150, P.AXIS_Y - 7, z0 + 2), (-150, P.AXIS_Y + 7, z0 + 2), 2.05, 16)
    return union(arms) + yoke + piv + comb + bridge


ROWDET_Y = 22.0              # comb plane: 22 mm in front of the shaft axis
ROWDET_DIR = 40.0            # fixed direction of the wedge from the fork pivot (deg above the arm)
ROWDET_R = (52.0, 62.0)


def row_comb(y0, y1, xp, zp):
    th = LK.row_detent()['theta']
    a_lo, a_hi = ROWDET_DIR - th[-1] - 4.0, ROWDET_DIR - th[0] + 4.0
    pts = []
    r0, r1 = ROWDET_R
    for i in range(25):
        a = math.radians(a_lo + (a_hi - a_lo) * i / 24)
        pts.append((xp + r0 * math.cos(a), zp + r0 * math.sin(a)))
    outer = []
    for i in range(241):
        a = a_hi - (a_hi - a_lo) * i / 240
        outer.append(a)
    for a in outer:
        rr = r1
        for t in th:
            d = abs(a - (ROWDET_DIR - t))
            half = math.degrees(4.0 * math.tan(math.radians(30.0)) / r1)      # 60-degree V, 4 mm deep
            if d < half:
                rr = min(rr, r1 - 4.0 * (1 - d / half))
        pts.append((xp + rr * math.cos(math.radians(a)), zp + rr * math.sin(math.radians(a))))
    prof = CrossSection([geo._ccw(pts)])
    return prof.extrude(y1 - y0).transform(np.array([[1, 0, 0, 0], [0, 0, 1, y0], [0, 1, 0, 0]], float))


def collar_mesh():
    """Lift collar: a ring under the hub on a thrust washer; it lifts with the shuttle but does not turn."""
    zc = FORK_Z + 2
    c = zcyl(0, P.AXIS_Y, zc - 2.5, FORK_Z + 4.5, 11.0, 48) - zcyl(0, P.AXIS_Y, zc - 3.5, FORK_Z + 5.5, 4.6, 24)
    pins = cyl((0, P.AXIS_Y - FORK_Y[1] - 1.5, zc), (0, P.AXIS_Y + FORK_Y[1] + 1.5, zc), 0.6, 12)
    return c + cyl((0, P.AXIS_Y - FORK_Y[1] - 1.5, zc), (0, P.AXIS_Y - 10.9, zc), 1.0, 16) + \
        cyl((0, P.AXIS_Y + 10.9, zc), (0, P.AXIS_Y + FORK_Y[1] + 1.5, zc), 1.0, 16) + pins


PAPER_BACK = 0.1          # back face of the sheet at the line
PAPER_T = RIBBON_T = 0.1
R_STRIKE = P.R_FACE + RIBBON_T + PAPER_T   # rev. 0.9.2: radius of the hammer face at the blow, about the shuttle axis


HAMMER_EDGE = 0.1        # face beyond the ink of the widest glyphs, mm


def hammer_face():
    """rev. 0.9.2: the window of the hammer face (x0, x1, z0, z1): the ink of all items on the shuttle plus HAMMER_EDGE,
    no more -- the neighbouring positions' glyphs stay about 1 mm outside it.
    rev. 0.11: one hammer for every font set: the window is Alcarin's (fontprof.WIN_X, WIN_Z); another font's set is
    measured to fit inside it."""
    import fontprof as FPR
    base = P.ZP - 0.18 * P.EM
    if D.FONT_ID != 'alcarin':
        return (FPR.WIN_X[0] - 1e-4, FPR.WIN_X[1] + 1e-4, base + FPR.WIN_Z[0] - 1e-4, base + FPR.WIN_Z[1] + 1e-4)
    # rev. 0.11: the face spans fontprof.WIN_Z (-4.2..6.6 mm) for the long stems of other fonts
    def f():
        e = TB.extents(); base = P.ZP - 0.18 * P.EM
        return (min(v[0] for v in e.values()) * P.U - HAMMER_EDGE, max(v[1] for v in e.values()) * P.U + HAMMER_EDGE,
                min(base + min(v[2] for v in e.values()) - HAMMER_EDGE, base + FPR.WIN_Z[0]),
                max(base + max(v[3] for v in e.values()) + HAMMER_EDGE, base + FPR.WIN_Z[1]))
    return cached('hammer_face', f)


def hammer_mesh():
    """rev. 0.9.2: the face is concave, a cylinder R_STRIKE about the shuttle axis: at the blow it lays the sheet and
    the ribbon onto the cylindrical type face over the window of hammer_face()."""
    yp, zp = P.HAMMER_PIVOT
    x0, x1, z0, z1 = hammer_face()
    head = box(x0, x1, P.AXIS_Y + R_STRIKE - 2.0, 7, z0, z1)
    head = head - zcyl(0, P.AXIS_Y, P.ZP - 8, P.ZP + 8, R_STRIKE, 1440)
    hub = cyl((-4.2, yp, zp), (4.2, yp, zp), 6.5, 24) - cyl((-5, yp, zp), (5, yp, zp), 2.05, 16)
    arm = cyl((0, yp, zp), (4, 6, P.ZP), 3.0, 16)
    return head + arm + hub


def hammer_now(st, dx):
    yp, zp = P.HAMMER_PIVOT
    return rotx(cached('hammer_mesh', hammer_mesh), -18.0 * (1 - st.hammer), yp, zp).translate((dx, 0, 0))


def hammer(st, dx):
    yp, zp = P.HAMMER_PIVOT
    h = hammer_now(st, dx)
    return [Part('hammer', 'hammer', 'print', h, COL['hammer'], 'hammer', 'PETG',
                 note='боёк с накладкой из резины 1 мм', mov='hammer'),
            Part('hammer axle', 'hammer', 'buy', cyl((-12 + dx, yp, zp), (12 + dx, yp, zp), 2.0, 16), COL['steel'],
                 'rod4x24', 'сталь', mov='uframe')]


def pressed(sheet, pusher, t, y_back):
    """rev. 0.9.2: a thin sheet (thickness t, back face at y_back) where the pusher has gone past it: the part under
    the pusher is carried in front of it as a layer of the same thickness. Returns (new sheet, pusher + layer)."""
    lo = pusher.bounding_box()
    if lo[1] > y_back + 1e-6:
        return sheet, pusher
    swept = pusher + pusher.translate((0, -t, 0))
    layer = (swept - pusher) ^ box(lo[0] - 1, lo[3] + 1, y_back - 5, y_back, lo[2] - 1, lo[5] + 1)
    return (sheet - swept) + layer, swept


# ---------------------------------------------------------------------------------------- shuttle
HUB_Z0 = P.BLOCK_BOT - 6.0                    # hub bottom at home
# rev. 0.10: anti-rotation rod at GUIDE_ANG (CCW from +Y) in the shuttle frame; 180 = behind the shaft
GUIDE_XY = (-P.GUIDE_R * math.sin(math.radians(P.GUIDE_ANG)), P.AXIS_Y + P.GUIDE_R * math.cos(math.radians(P.GUIDE_ANG)))
LIFT_MIN = (P.REST_ROW - P.HOME_ROW) * P.RH      # rest, under the line
LIFT_MAX = (P.NROWS - 1 - P.HOME_ROW) * P.RH


def shaft_hub_mesh():
    """Tape pulley and detent wheel on the shaft (rotate with it, do not lift)."""
    pul = zcyl(0, P.AXIS_Y, P.Z_PULLEY[0], P.Z_PULLEY[1], P.PULLEY_R, 96)
    pul = pul + zcyl(0, P.AXIS_Y, P.Z_PULLEY[0] - 1, P.Z_PULLEY[0], P.PULLEY_R + 2, 96) + zcyl(0, P.AXIS_Y, P.Z_PULLEY[1], P.Z_PULLEY[1] + 1, P.PULLEY_R + 2, 96)
    wheel = zcyl(0, P.AXIS_Y, P.Z_DETENT[0], P.Z_DETENT[1], P.DETENT_R, 96)
    for m in range(P.NPOS):
        a = -TB.home_angle(m) + 90.0    # notch m faces the pawl (+X) when position m is at print
        # rev. 0.9c: the notch matches the pawl's wedge (half-angle 32.7 deg); its apex is where the wedge's tip lands
        v = geo.CrossSection([geo._ccw([(P.DETENT_R + 1, -DET_WEDGE[1] * (DET_WEDGE[0] + 1.0) / DET_WEDGE[0] - 0.0),
                                        (P.DETENT_R + 1, DET_WEDGE[1] * (DET_WEDGE[0] + 1.0) / DET_WEDGE[0]),
                                        (DET_TIP - 3.0 - 0.05, 0)])]).extrude(10).translate((0, 0, P.Z_DETENT[0] - 1))
        v = v.translate((0, P.AXIS_Y, 0))
        wheel = wheel - rotz(v, TB.home_angle(m), 0, P.AXIS_Y)     # notch m faces the pawl (+X) at print
    hub = zcyl(0, P.AXIS_Y, Z_B0 + 1, P.Z_DETENT[1], 12, 48)
    boss = zcyl(*GUIDE_XY, P.Z_DETENT[0], P.Z_DETENT[1] + 1.5, 5, 24)   # rev. 0.8: lower, under the fork arms
    m = pul + wheel + hub + boss
    m = m - zcyl(0, P.AXIS_Y, Z_B0, P.Z_DETENT[1] + 4, 4.02, 24) - zcyl(*GUIDE_XY, P.Z_DETENT[0] + 1, P.Z_DETENT[1] + 4, 3.0, 16)
    for a in (45, 135, 225, 315):      # rev. 0.10: windows between the rod's boss (180) and the front (0)
        m = m - geo.sector_xy(0, P.AXIS_Y, 16, P.PULLEY_R - 4, a - 30, a + 30, P.Z_PULLEY[0] - 2, P.Z_DETENT[1] + 1)
    return m


def ring_mesh():
    lo = min(-TB.home_angle(m) + math.degrees(math.atan2(P.BLOCK_U0 * P.U, P.R_FACE)) for m in range(P.NPOS))
    hi = max(-TB.home_angle(m) + math.degrees(math.atan2(P.BLOCK_U1 * P.U, P.R_FACE)) for m in range(P.NPOS))
    z0, z1 = P.BLOCK_BOT - 3, P.BLOCK_TOP + 2
    ring = geo.sector_xy(0, P.AXIS_Y, P.RING_R0, P.RING_R1, lo - 1.5, hi + 1.5, z0, z1)
    # lattice windows between the block rows keep the ring light
    for r in range(P.NROWS):
        zc = P.BLOCK_TOP - (r + 0.5) * P.RH
        ring = ring - geo.sector_xy(0, P.AXIS_Y, P.RING_R0 - 1, P.RING_R1 - 2.5, lo + 2, hi - 2, zc - 3.5, zc + 3.5)
    pockets = union([TB.block_home(m, with_relief=False) for m in range(P.NPOS)])
    ring = ring - pockets - RD.ring_pin_holes()          # rev. 0.10: holes for the code combs' pins
    # rev. 0.10: web and spokes hang under the band, so the reading head clears them at the highest lift
    web = zcyl(0, P.AXIS_Y, z0 - 3, z0, P.GUIDE_R + 8, 64)
    spokes = union([geo.sector_xy(0, P.AXIS_Y, P.GUIDE_R + 6, P.RING_R0 + 1, a - 5, a + 5, z0 - 3, z0 + 0.5) for a in (lo + 6, (lo + hi) / 2, hi - 6)])
    hub = zcyl(0, P.AXIS_Y, HUB_Z0, HUB_Z0 + 14, 11, 48)
    boss = zcyl(*GUIDE_XY, HUB_Z0, HUB_Z0 + 14, 6, 24)
    m = ring + web + spokes + hub + boss
    m = m - zcyl(0, P.AXIS_Y, HUB_Z0 - 1, HUB_Z0 + 15, 4.1, 24) - zcyl(*GUIDE_XY, HUB_Z0 - 1, HUB_Z0 + 15, 3.1, 16)
    return m


_cache = {}


def cached(name, fn):
    if name not in _cache:
        _cache[name] = fn()
    return _cache[name]


def shuttle(st):
    parts = []; th = st.th(); dx = -st.slide(); lz = st.lift()
    def T(m, lift=True):
        m = rotz(m, th, 0, P.AXIS_Y)
        return m.translate((dx, 0, lz if lift else 0))
    parts.append(Part('shuttle', 'shuttle', 'print', T(cached('ring', ring_mesh)), COL['shuttle'], 'shuttle', 'PETG',
                      note='кольцо 106°, R 60, с окнами между рядами', mov='shuttle',
                      printable=lambda: cached('ring', ring_mesh)))
    for m in range(P.NPOS):
        parts.append(Part(f'type block {m}', 'shuttle', 'print', T(cached(f'blk{m}', lambda m=m: TB.block_home(m))),
                          COL['type'], f'type_block_{m:02d}', 'PETG', note='литерный блок: 8 литер, лицом вверх, слой 0,1',
                          mov='shuttle', printable=lambda m=m: TB.block_print_bed(m)))
    parts.append(Part('pulley and detent wheel', 'shuttle', 'print', T(cached('shub', shaft_hub_mesh), lift=False), COL['drum'],
                      'shaft_hub', 'PETG', note='шкив ленты R 30 и колесо фиксатора с 11 вырезами', mov='drum',
                      printable=lambda: cached('shub', shaft_hub_mesh)))
    ztop = HUB_Z0 + 14 + LIFT_MAX + 4
    parts.append(Part('shaft', 'shuttle', 'buy', T(zcyl(0, P.AXIS_Y, 80, ztop, 4.0, 24), lift=False), COL['steel'],
                      f'shaft8x{int(round(ztop - 80, -1))}', 'сталь', f'вал 8 мм, {int(round(ztop - 80, -1))} мм', mov='drum'))
    parts.append(Part('guide rod', 'shuttle', 'buy',
                      T(zcyl(*GUIDE_XY, P.Z_DETENT[0] + 1, ztop + 2, 2.95, 16), lift=False), COL['steel'],
                      f'rod6x{int(round(ztop + 1 - P.Z_DETENT[0], -1))}', 'сталь', 'пруток 6 мм — поводок челнока', mov='drum'))
    parts.append(Part('shuttle bushing', 'shuttle', 'buy',
                      T(zcyl(*GUIDE_XY, HUB_Z0, HUB_Z0 + 14, 4.5, 24) - zcyl(*GUIDE_XY, HUB_Z0 - 1, HUB_Z0 + 15, 3.0, 16)),
                      COL['buy'], 'bushing6', 'бронза', 'втулка 6×9×14 с поджимом', mov='shuttle'))
    return parts


# --------------------------------------------------------------------------------------- carriage
def end_plate_profile():
    yl, zl = P.CAR_RAIL_LO; yh, zh = P.CAR_RAIL_HI
    return [(30, zl - 8), (yh + 12, zl - 8), (yh + 12, zh + 12), (30, P.ROLLER[1] + 12), (-6, P.ROLLER[1] + 12),
            (-6, P.ROLLER[1] - 8), (0, P.ROLLER[1] - 12), (0, P.ZP - 77), (30, P.ZP - 87)]


def carriage(st):
    parts = []; xc = st.car
    yl, zl = P.CAR_RAIL_LO; yh, zh = P.CAR_RAIL_HI
    prof = geo.CrossSection([geo._ccw(end_plate_profile())])
    for sx in (-1, 1):
        x = xc + sx * P.CAR_HALF
        m = prof.extrude(6).transform(np.array([[0, 0, 1, x - 3], [1, 0, 0, 0], [0, 1, 0, 0]], float))
        m = m - cyl((x - 4, yl, zl), (x + 4, yl, zl), 4.2, 24) - cyl((x - 4, yh, zh), (x + 4, yh, zh), 4.2, 24)
        parts.append(Part(f'carriage end plate {sx:+d}', 'carriage', 'print', m, COL['carriage'], 'car_end', 'PETG',
                          mov='carriage'))
        for (yy, zz) in ((yl, zl), (yh, zh)):
            bb = cyl((x - 15 * sx - 3 * sx, yy, zz), (x - 3 * sx, yy, zz), 7, 24) - cyl((x - 20 * sx, yy, zz), (x, yy, zz), 4.05, 24)
            parts.append(Part(f'carriage bushing {sx:+d} {zz:.0f}', 'carriage', 'buy', bb, COL['buy'], 'LM8UU', 'сталь',
                              'линейный подшипник LM8UU', mov='carriage'))
    ty, tz, tr = P.TUBE
    tube = cyl((xc - P.CAR_HALF + 3, ty, tz), (xc + P.CAR_HALF - 3, ty, tz), tr, 48) - \
        cyl((xc - P.CAR_HALF + 2, ty, tz), (xc + P.CAR_HALF - 2, ty, tz), tr - 1.5, 48)
    tube = tube - box(xc - 110, xc + 110, ty - 15, ty - 3, tz + 8, tz + 20)     # paper slot (front top)
    parts.append(Part('paper tube', 'carriage', 'cut', tube, COL['carriage'], 'pipe32x230', 'ПВХ',
                      'труба 30 мм (ПВХ или печать), 230 мм, с прорезью', mov='carriage'))
    guide = geo.Manifold.batch_hull([cyl((xc - 110, 24, 135), (xc + 110, 24, 135), 0.8, 8),
                                     cyl((xc - 110, 1.0, 150), (xc + 110, 1.0, 150), 0.8, 8)])
    parts.append(Part('paper guide', 'carriage', 'cut', guide, COL['carriage'], 'guide_sheet', 'жесть',
                      'направляющая бумаги — полоса 0,5 мм', mov='carriage'))
    ry, rz, rr = P.ROLLER
    parts.append(Part('feed roller', 'carriage', 'buy', cyl((xc - P.CAR_HALF + 3, ry, rz), (xc + P.CAR_HALF - 3, ry, rz), rr, 32),
                      (60, 60, 60), 'roller14', 'сталь+резина', 'вал 6 мм с резиновой трубкой 14 мм', mov='carriage'))
    for sx in (-1, 1):
        parts.append(Part(f'pinch roller {sx:+d}', 'carriage', 'buy',
                          cyl((xc + sx * 80 - 6, -3.6, rz), (xc + sx * 80 + 6, -3.6, rz), 3.5, 24), (60, 60, 60), 'pinch7', 'резина',
                          'прижимной ролик 7 мм', mov='carriage'))
    # rack along the back, teeth toward +Y
    rack_y = 110.0
    teeth = []
    pitch = math.pi * 1.0106
    for i in range(int(230 / pitch)):
        x = xc - 115 + i * pitch
        teeth.append(geo.CrossSection([geo._ccw([(x, rack_y - 1.25), (x + pitch * 0.5, rack_y - 1.25),
                                                 (x + pitch * 0.38, rack_y + 1.0), (x + pitch * 0.12, rack_y + 1.0)])]))
    rack = box(xc - 115, xc + 115, rack_y - 7, rack_y - 1.2, P.CAR_RAIL_LO[1] - 2, P.CAR_RAIL_LO[1] + 4)
    rack = rack + CrossSection.batch_boolean(teeth, OpType.Add).extrude(6).translate((0, 0, P.CAR_RAIL_LO[1] - 2))
    rack = rack + box(xc - P.CAR_HALF - 3, xc - 115, P.CAR_RAIL_HI[0] + 6, rack_y - 1.2, P.CAR_RAIL_LO[1] - 2, P.CAR_RAIL_LO[1] + 4)
    rack = rack + box(xc + 115, xc + P.CAR_HALF + 3, P.CAR_RAIL_HI[0] + 6, rack_y - 1.2, P.CAR_RAIL_LO[1] - 2, P.CAR_RAIL_LO[1] + 4)
    parts.append(Part('carriage rack', 'carriage', 'print', rack, COL['carriage'], 'rack', 'PETG',
                      note='модуль 1,0106 мм; печатается двумя частями', mov='carriage'))
    parts += margins(st, rack_y)
    # paper: from the guide up past the print line, over the roller onto the rest
    pap = box(xc - 108, xc + 108, 0.0, 0.1, 150, rz)
    pap = pap + box(xc - 108, xc + 108, ry - 0.05, ry + 0.05, rz + rr, rz + rr + 0.1)
    rest = rotx(box(xc - 108, xc + 108, ry, ry + 90, rz + rr, rz + rr + 0.1), 25, ry, rz + rr)
    parts.append(Part('paper', 'paper', 'ref', pap + rest, COL['paper'], None, mov='carriage'))
    parts.append(Part('paper rest', 'carriage', 'print', rotx(box(xc - 100, xc + 100, ry + 6, ry + 80, rz + rr - 2.5, rz + rr - 0.5), 25, ry, rz + rr),
                      COL['carriage'], 'paper_rest', 'PETG', mov='carriage', printable=lambda: box(0, 200, 0, 74, 0, 2)))
    return parts


# ------------------------------------------------------------------ rev. 0.11: margins and the print point indicator
# Two margin stops clip onto the carriage rack (one tooth = 6 u = 3.175 mm: the margins go in 6 u steps); a fixed
# abutment over the rack, on the escapement bracket, stands between them. On the return the left stop meets the
# abutment's left face: the line starts there. While typing the carriage goes -X and the right stop comes to the
# abutment's right face: the carriage cannot feed past the line's end.
MARGIN_W = 6.0                    # stop length along X
RACK_PITCH = math.pi * 1.0106
# abutment faces (x, fixed), put on the rack's tooth grid so that the stops at the default margins (the full line,
# CAR_X_START .. CAR_X_END) touch them exactly
MARGIN_AB = (MARGIN_W + P.CAR_X_START - 115.0 + round((18.0 - MARGIN_W - P.CAR_X_START + 115.0) / RACK_PITCH) * RACK_PITCH,
             P.CAR_X_END - 115.0 + round((23.0 - P.CAR_X_END + 115.0) / RACK_PITCH) * RACK_PITCH)


def margin_rel(st, side):
    """x of a stop's left end relative to the carriage (on a whole tooth of the rack)."""
    rel = MARGIN_AB[0] - MARGIN_W - st.margin_l if side == 'L' else MARGIN_AB[1] - st.margin_r
    k = round((rel + 115.0) / RACK_PITCH)
    return -115.0 + k * RACK_PITCH


def margins(st, rack_y):
    """rev. 0.11: a margin strip on top of the carriage rack (notches every rack tooth on its top), two stops that
    straddle it (a tongue in a notch, a leaf spring under the thumb tab), the abutment over the strip."""
    parts = []
    zt = P.CAR_RAIL_LO[1] + 4.0                       # top of the rack body (96)
    ys0, ys1 = rack_y - 5.5, rack_y - 2.0             # the strip (y 104.5..108), clear of the escapement's memory parts
    zs = zt + 4.0
    xc = st.car
    parts.append(Part('margin strip', 'carriage', 'print', box(xc - 112.0, xc + 112.0, ys0, ys1, zt, zs), COL['carriage'],
                      'margin_strip', 'PETG', note='планка полей на рейке каретки, пазы через зуб рейки (6u)', mov='carriage'))
    for side in ('L', 'R'):
        x0 = xc + margin_rel(st, side)
        x1 = x0 + MARGIN_W
        m = box(x0, x1, ys0 - 1.0, ys1 + 1.0, zs, zs + 3.5)                     # over the strip
        m = m + box(x0, x1, ys0 - 1.0, ys0, zt, zs + 0.01) + box(x0, x1, ys1, ys1 + 1.0, zt, zs + 0.01)   # cheeks
        parts.append(Part(f'margin stop {side}', 'carriage', 'print', m, (200, 60, 60), 'margin_stop', 'PETG',
                          note='упор поля: скоба на планке полей, язычок в пазу, шаг 6u', mov='carriage'))
    ab = box(MARGIN_AB[0], MARGIN_AB[1], ys0, 112.0, zs + 0.5, zs + 7.0)
    parts.append(Part('margin abutment', 'esc', 'print', ab, (110, 112, 120), 'margin_ab', 'PETG',
                      note='упор полей на кронштейне спуска, между упорами левого и правого поля'))
    return parts


POINTER_Y, POINTER_Z = -27.5, 243.0


def pointer(st):
    """rev. 0.11: the print point indicator: a red bead on a wire on top of the reading head, on the hammer axis. From
    the typist's seat it sits on the line just where the next letter's left edge will be; it rides the U-frame, so for
    a dead mark it shows the retracted point."""
    dx = -st.slide()
    w = zcyl(0.0, POINTER_Y, 240.0, POINTER_Z - 0.6, 0.4, 12)
    b = geo.Manifold.sphere(0.8, 16).translate((0.0, POINTER_Y, POINTER_Z))
    return [Part('print point indicator', 'reader', 'buy', (w + b).translate((dx, 0, 0)), (220, 30, 30), 'pointer', 'сталь',
                 'указатель точки печати: проволока 0,8 мм с красной бусиной 1,6 мм на головке чтения', mov='uframe')]


# ------------------------------------------------------------------ rev. 0.11: carriage release key
# A thumb key on the front frame, left: pressing it turns a small lever whose upright arm pulls a Bowden wire to the
# holding dog of the escapement; the dog leaves the wheel, and the carriage goes either way by hand. Let go, the dog's
# spring puts it back between two teeth: the carriage stands on a whole unit (1 u = one tooth of the wheel).
REL_KEY = dict(x=(-221.5, -208.5), y=-386.0, z=36.0, L=14.0, h=14.0)


def carriage_release(st):
    import escape
    g = REL_KEY; y, z = g['y'], g['z']
    phi = math.degrees(math.asin(min(1.0, escape.REL_LIFT * st.car_release / g['h'])))
    br = box(-224.0, -206.0, y - 6.0, y + 6.0, 20.0, 30.0)
    for x0, x1 in ((-224.0, -222.0), (-208.0, -206.0)):
        br = br + box(x0, x1, y - 3.5, y + 3.5, 30.0, z + 3.5)
    ys = y - g['h'] * 0.35 - 5.5                                                   # sheath stop: a bar over the key arm
    br = br + box(-224.0, -206.0, ys, ys + 2.0, z + 4.0, z + g['h'] + 1.5)
    for x0, x1 in ((-224.0, -222.0), (-208.0, -206.0)):
        br = br + box(x0, x1, ys, y - 3.5 + 0.01, z + 3.5 - 0.01, z + 6.0)
    br = br - cyl((-225.0, y, z), (-205.0, y, z), 1.05, 12)
    br = br - cyl((-215.0, y - 7.0, z + g['h']), (-215.0, y - 3.0, z + g['h']), 0.8, 12)
    parts = [Part('carriage release bracket', 'frame', 'print', br, (110, 112, 120), 'release_bracket', 'PETG',
                  note='кронштейн клавиши освобождения каретки на передней раме, с упором оболочки троса')]
    x0, x1 = g['x']
    lev = cyl((x0, y, z), (x1, y, z), 3.0, 20)
    lev = lev + box(x0, x1, y - g['L'] - 4.0, y, z - 1.5, z + 1.5)                    # the key arm, forward
    lev = lev + box(x0 - 1.0, x1 + 1.0, y - g['L'] - 12.0, y - g['L'] - 4.0, z - 1.5, z + 2.5)   # the pad
    lev = lev + box(-216.5, -213.5, y - 1.5, y + 1.5, z, z + g['h'] + 1.5)             # the upright arm (wire)
    lev = lev - cyl((x0 - 1, y, z), (x1 + 1, y, z), 1.05, 12)
    parts.append(Part('carriage release key', 'frame', 'print', geo.rotx(lev, phi, y, z), (200, 60, 60), 'release_key', 'PETG',
                      note='клавиша освобождения каретки: рычажок 14/14 мм, нажим 3 мм выводит собачку спуска', mov='release'))
    parts.append(Part('carriage release axle', 'frame', 'buy', cyl((-224.5, y, z), (-205.5, y, z), 1.0, 12), COL['steel'], 'rod2x20', 'сталь'))
    return parts


# ------------------------------------------------------------------------------------- escapement
ESC = (0.0, 116.05)       # pinion axis (x, y): rack pitch line at y = 110 (+ pitch radius 5.05)


def escapement(st):
    """rev. 0.9c: escapement.py -- two-tier wheel, dog, movable stop U, +-u lever, back arm B, memory arm M, rockers."""
    import escape
    return escape.parts(st, Part, COL, cached)


# ----------------------------------------------------------------------------------------- ribbon
RIB_LINK_Z = (P.Z_DETENT[1] + 0.8, P.Z_DETENT[1] + 3.8)   # rev. 0.9c: over the rotate amplifier's pins (124.6)
RIB_LINK_Y = (-2.6, -0.1)        # rev. 0.9c: beside the drive bellcrank's sweep (it reaches y -3.8 when high)
VIB_X = 34.0          # vibrator fingers, mm either side of the hammer axis (outside the shuttle: r > 60)
Z_RIB = P.ZP - P.RIBBON_DROP     # ribbon centre at rest


def ribbon_lift(st):
    return st.ribbon if st.ribbon is not None else cam_lift('ribbon', st.cycle % 360.0) if st.cycle else st.detent


def ribbon(st):
    """rev. 0.8: the ribbon rests 10 mm under the line; a vibrator on the print unit lifts it for the blow."""
    parts = []
    zs = Z_RIB - 10.0                  # spools sit lower still, the guides lead the ribbon up to the line of the vibrator
    for sx in (-1, 1):
        parts.append(Part(f'ribbon spool {sx:+d}', 'ribbon', 'buy', zcyl(sx * 165, -20, zs - 7, zs + 7, 16, 48), (50, 50, 60),
                          'spool', 'пластик', 'катушка ленты 13 мм'))
    dx = -st.slide(); lz = P.RIBBON_DROP * ribbon_lift(st)
    xl, xr = -VIB_X + dx, VIB_X + dx
    def seg(x0, z0, x1, z1):
        return geo.Manifold.batch_hull([box(x0 - 0.05, x0 + 0.05, P.RIBBON_Y - 0.05, P.RIBBON_Y + 0.05, z0 - 6.5, z0 + 6.5),
                                        box(x1 - 0.05, x1 + 0.05, P.RIBBON_Y - 0.05, P.RIBBON_Y + 0.05, z1 - 6.5, z1 + 6.5)])
    strip = union([seg(-150, Z_RIB, xl, Z_RIB + lz), seg(xl, Z_RIB + lz, xr, Z_RIB + lz), seg(xr, Z_RIB + lz, 150, Z_RIB)])
    parts.append(Part('ribbon', 'ribbon', 'ref', strip, COL['ribbon'], None, mov='ribbon'))
    for sx in (-1, 1):
        g = box(sx * 152 - 2, sx * 152 + 2, -20, -0.5, Z_RIB - 9, Z_RIB - 7) + box(sx * 152 - 2, sx * 152 + 2, -2.5, -0.5, Z_RIB - 9, Z_RIB + 9)
        parts.append(Part(f'ribbon guide {sx:+d}', 'ribbon', 'print', g, (110, 112, 120), 'ribbon_guide', 'PETG'))
    # vibrator: a steel fork on a vertical slide fixed to the U-frame arm; two fingers carry the ribbon
    fing = []
    for x in (xl, xr):
        fing.append(box(x - 2.0, x + 2.0, -4.0, P.RIBBON_Y + 0.15, Z_RIB - 8.5, Z_RIB - 6.5))      # lower lip under the ribbon
        fing.append(box(x - 2.0, x + 2.0, -4.0, -3.3, Z_RIB - 8.5, Z_RIB + 7.5))      # back of the finger
        fing.append(box(x - 2.0, x + 2.0, -4.0, P.RIBBON_Y + 0.15, Z_RIB + 6.5, Z_RIB + 7.5))      # upper lip
    # stems outside the shuttle (radius > 60 from its axis) down to a cross bar under the shuttle; rev. 0.9b: the bar
    # sits on the ribbon link, which its own cam (same profile as the detents, 10 mm) lifts
    zc0 = RIB_LINK_Z[1]
    stem = union([box(x - 2.0, x + 2.0, -4.0, -3.0, zc0, Z_RIB - 8.5) for x in (xl, xr)])
    stem = stem + box(xl - 2.0, xr + 2.0, -6.0, RIB_LINK_Y[1], zc0, zc0 + 2.5)
    lk = box(xr - 2.0, CAM_X['ribbon'] + 4 + P.SLIDE_MAX + dx, *RIB_LINK_Y, *RIB_LINK_Z)
    parts.append(Part('ribbon link', 'ribbon', 'cut', lk.translate((0, 0, lz)), COL['steel'], 'strip3x3', 'сталь',
                      'тяга вибратора: кулачок ленты поднимает её на 10 мм', mov='ribbon'))
    vib = (union(fing) + stem).translate((0, 0, lz))
    parts.append(Part('ribbon vibrator', 'ribbon', 'cut', vib, (90, 92, 100), 'vibrator', 'жесть',
                      'вибратор ленты: вилка из жести 0,5 мм на ползуне; ход 10 мм', mov='ribbon'))
    return parts


# ------------------------------------------------------------------------------ spring motor and cycle
CYC = (CAM_Y, 22.5)                       # cycle shaft axis along X: (y, z)
BARREL = dict(x0=188.0, x1=226.0, y=-265.0, z=65.0, r=60.0)
X_LAY = 214.0                             # lay shaft along Y
# gear train: barrel 80 (m 1.5) -> 12; int1 48 (m 1) -> 12; bevel 24 -> 12 on the lay shaft; lay -> cycle shaft bevel 1:1
ZG = dict(barrel=80, m1=1.5, int1=48, pin=12, bevel=24, bevpin=12, gov=32, govpin=8)


def train_axes():
    yb, zb = BARREL['y'], BARREL['z']
    d1 = ZG['m1'] * (ZG['barrel'] + ZG['pin']) / 2
    z1 = CYC[1] + 19.3
    y1 = yb + math.sqrt(d1 ** 2 - (zb - z1) ** 2)
    d2 = (ZG['int1'] + ZG['pin']) / 2
    z2 = CYC[1]
    y2 = y1 + math.sqrt(d2 ** 2 - (z1 - z2) ** 2)
    return dict(barrel=(yb, zb), int1=(y1, z1), int2=(y2, z2), C=CYC)


def train_ratio():
    return ZG['barrel'] / ZG['pin'] * ZG['int1'] / ZG['pin'] * ZG['bevel'] / ZG['bevpin']


CAM_PROFILE = {'lift': 'out', 'rotate': 'out', 'detent': 'detent', 'hammer': 'cock', 'rowdet': 'detent', 'ribbon': 'ribbon',
               'read': 'read'}
# top of each push rod (with its finger) at rest: just under the arm or link it lifts
CAM_TOP = {'rotate': Z_B0 + 0.3, 'lift': Z_B0 + 0.3, 'detent': P.Z_DETENT[1] + 4.0, 'hammer': P.Z_DETENT[1] + 0.5, 'ribbon': P.Z_DETENT[1] + 0.8,
           'rowdet': Z_B0 + 0.1}
CAM_LIFT = {'lift': 12.0, 'rotate': 12.0, 'detent': DET_RISE, 'hammer': 6.0, 'rowdet': 6.0, 'ribbon': 10.0}   # whiffletree input stroke S = 12 mm


RAMP = {'detent': 35.0, 'ribbon': 80.0}


def cam_lift(kind, a):
    """Follower lift (0..1) of a cam at cycle angle a (deg)."""
    c = P.CYCLE
    def cyc(t):
        t = min(max(t, 0.0), 1.0); return t - math.sin(2 * math.pi * t) / (2 * math.pi)
    if kind == 'out':
        if a < c['out'][0]: return 0.0
        if a < c['out'][1]: return cyc((a - c['out'][0]) / (c['out'][1] - c['out'][0]))
        if a < c['back'][0]: return 1.0
        if a < c['back'][1]: return 1.0 - cyc((a - c['back'][0]) / (c['back'][1] - c['back'][0]))
        return 0.0
    if kind in ('detent', 'ribbon'):
        # rev. 0.9c: ramps of 35 deg (detent) and 80 deg (ribbon) keep the cams' pressure angle under 45 deg
        d0, d1 = c[kind]; rp = RAMP[kind]
        if a < d0 - rp or a > d1 + rp: return 0.0
        if a < d0: return cyc((a - d0 + rp) / rp)
        if a > d1: return 1.0 - cyc((a - d1) / rp)
        return 1.0
    if kind == 'read':          # rev. 0.10: high at rest (feelers held in); low while the feelers read
        r0, r1 = c['read']; g0, g1 = P.READ_RAMP
        if a < r0 - g0 or a > r1 + g1: return 1.0
        if a < r0: return 1.0 - cyc((a - r0 + g0) / g0)
        if a <= r1: return 0.0
        return cyc((a - r1) / g1)
    if kind == 'cock':          # rev. 0.8: the hammer spring is cocked over 10..150 deg and released at the strike
        s0 = c['strike']
        if a < 10: return 0.0
        if a < 150: return cyc((a - 10) / 140)
        if a < s0: return 1.0
        if a < s0 + 2: return 1.0 - (a - s0) / 2
        return 0.0
    if kind == 'strike':        # the hammer itself: flies to the paper in about 8 deg (9 ms), rests on its stop by 190
        s0 = c['strike']
        if s0 <= a < s0 + 8: return cyc((a - s0) / 8)
        if s0 + 8 <= a < s0 + 11: return 1.0
        if s0 + 11 <= a < s0 + 30: return 1.0 - cyc((a - s0 - 11) / 19)
        return 0.0
    return 0.0


def cam_mesh(kind, x, base_r=9.0, lift=6.0, roller=2.0):
    """rev. 0.9b: the roller's centre follows the pitch curve r = base + roller + lift(phi) over the top; the cam is
    the pitch curve offset inward by the roller radius, so the roller touches it at every angle."""
    pts = []
    for i in range(720):
        a = 360.0 * i / 720
        r = base_r + roller + lift * cam_lift(CAM_PROFILE[kind], (90.0 - a) % 360.0)
        th = math.radians(a)
        pts.append((r * math.cos(th), r * math.sin(th)))
    cs = geo.CrossSection([geo._ccw(pts)]).offset(-roller, JoinType.Round, 2.0, 96)
    m = cs.extrude(5).transform(np.array([[0, 0, 1, x - 2.5], [1, 0, 0, CYC[0]], [0, 1, 0, CYC[1]]], float))
    return m - cyl((x - 3, CYC[0], CYC[1]), (x + 3, CYC[0], CYC[1]), 2.05, 16)


def gear_x(z, m, y0, z0, x, w=4.0, phase=0.0):
    g = geo.gear_profile(z, m, 0, 0, phase=phase).extrude(w)
    return g.transform(np.array([[0, 0, 1, x], [1, 0, 0, y0], [0, 1, 0, z0]], float))


def bevel(apex, axis, r_big, r_small, length, seg=48):
    """Bevel gear blank as a frustum along axis from the big end at 'apex' (schematic)."""
    apex = np.asarray(apex, float); axis = np.asarray(axis, float)
    return cyl(apex, apex + axis * length, r_big, seg, r1=r_small)


def drive(st):
    parts = []
    ax = train_axes()
    yb, zb = ax['barrel']; X0, X1, R = BARREL['x0'], BARREL['x1'], BARREL['r']
    bore = cyl((X0 - 1, yb, zb), (X1 + 1, yb, zb), 5.1, 32)
    barrel = cyl((X0, yb, zb), (X1 - 2.5, yb, zb), R, 96) - cyl((X0 + 2.5, yb, zb), (X1, yb, zb), R - 2.5, 96) - bore
    parts.append(Part('spring barrel', 'drive', 'print', barrel, (150, 120, 90), 'barrel', 'PETG',
                      note='барабан Ø120×38 мм: стакан с дном; крышка отдельно, на винтах'))
    lid = cyl((X1 - 2.5, yb, zb), (X1, yb, zb), R, 96) - bore
    parts.append(Part('spring barrel lid', 'drive', 'print', lid, (150, 120, 90), 'barrel_lid', 'PETG', note='крышка барабана, на шести винтах М3'))
    parts.append(Part('mainspring', 'drive', 'buy', cyl((X0 + 3, yb, zb), (X1 - 3, yb, zb), R - 3, 64) -
                      cyl((X0 + 2, yb, zb), (X1 - 2, yb, zb), 9, 32), (90, 90, 100), 'mainspring', 'сталь',
                      'заводная пружина 32×0,8 мм, около 6 м'))
    parts.append(Part('barrel arbor', 'drive', 'buy', cyl((X0 - 16, yb, zb), (P.FRAME_X + 14, yb, zb), 5.0, 24), COL['steel'],
                      'rod10x100', 'сталь', 'вал 10 мм — ось барабана'))
    # winding: crank on a pinion outside the frame, 1:3 to a gear on the arbor
    xc = P.FRAME_X + 4
    parts.append(Part('winding gear', 'drive', 'print', gear_x(54, 1.5, yb, zb, xc, 6), (150, 120, 90), 'wind_gear', 'PETG'))
    yw, zw = yb, zb + 1.5 * (54 + 18) / 2
    parts.append(Part('winding pinion', 'drive', 'print', gear_x(18, 1.5, yw, zw, xc, 6, 0.17), (150, 120, 90), 'wind_pinion', 'PETG'))
    crank = cyl((xc - 2, yw, zw), (xc + 20, yw, zw), 4, 24) + box(xc + 14, xc + 18, yw - 5, yw + 5, zw - 5, zw + 90) + \
        cyl((xc + 18, yw, zw + 85), (xc + 45, yw, zw + 85), 6, 24)
    parts.append(Part('winding crank', 'drive', 'print', crank, (60, 62, 70), 'crank', 'PETG',
                      note='ручка завода R 85 мм; храповик с собачкой на оси барабана'))
    # stage 1 (m 1.5) and stage 2 (m 1)
    y1, z1 = ax['int1']; y2, z2 = ax['int2']
    gx = X0 - 10.0
    parts.append(Part('barrel gear', 'drive', 'print', gear_x(ZG['barrel'], ZG['m1'], yb, zb, gx, 8), (150, 120, 90), 'gear_barrel', 'PETG',
                      note='m = 1,5; ширина 8 мм'))
    parts.append(Part('int1 shaft', 'drive', 'buy', cyl((gx - 22, y1, z1), (P.FRAME_X - 18, y1, z1), 3.0, 16), COL['steel'], 'rod6x60', 'сталь'))
    parts.append(Part('int1 pinion', 'drive', 'print', gear_x(ZG['pin'], ZG['m1'], y1, z1, gx, 8, 0.13), (150, 120, 90), 'pinion12_m15', 'PETG'))
    parts.append(Part('int1 gear', 'drive', 'print', gear_x(ZG['int1'], 1.0, y1, z1, gx - 14, 5), (150, 120, 90), 'gear_int1', 'PETG'))
    parts.append(Part('int2 shaft', 'drive', 'buy', cyl((gx - 20, y2, z2), (X_LAY - 4, y2, z2), 2.0, 16), COL['steel'], 'rod4x60', 'сталь'))
    parts.append(Part('int2 pinion', 'drive', 'print', gear_x(ZG['pin'], 1.0, y2, z2, gx - 14, 5, 0.13), (150, 120, 90), 'pinion12', 'PETG'))
    # bevel int2 -> lay shaft, lay shaft along Y, bevel lay -> cycle shaft
    rb, rp = ZG['bevel'] / 2, ZG['bevpin'] / 2
    parts.append(Part('bevel gear 24', 'drive', 'print', bevel((X_LAY - rp - 6, y2, z2), (1, 0, 0), rb, rb - 6, 6), (150, 120, 90), 'bevel24', 'PETG'))
    parts.append(Part('bevel pinion 12', 'drive', 'print', bevel((X_LAY, y2 + rb + 6, z2), (0, -1, 0), rp, rp - 3, 6), (150, 120, 90), 'bevel12', 'PETG'))
    parts.append(Part('lay shaft', 'drive', 'buy', cyl((X_LAY, y2 + rb - 2, z2), (X_LAY, CYC[0] - 8, z2), 2.0, 16), COL['steel'], 'rod4x200', 'сталь',
                      'пруток 4 мм, около 200 мм'))
    parts.append(Part('bevel lay 1:1', 'drive', 'print', bevel((X_LAY, CYC[0] - 10 - 6, z2), (0, 1, 0), 10, 6, 6), (150, 120, 90), 'bevel20', 'PETG'))
    parts.append(Part('bevel cycle 1:1', 'drive', 'print', bevel((X_LAY - 10 - 6, CYC[0], z2), (1, 0, 0), 10, 6, 6), (150, 120, 90), 'bevel20', 'PETG'))
    # governor on the cycle shaft 4:1, with a small flywheel
    yC, zC = CYC
    gxg = 184.0
    yD = yC + (ZG['gov'] + ZG['govpin']) / 2
    parts.append(Part('governor gear', 'drive', 'print', gear_x(ZG['gov'], 1.0, yC, zC, gxg), (150, 120, 90), 'gear_gov', 'PETG'))
    parts.append(Part('governor pinion', 'drive', 'print', gear_x(ZG['govpin'], 1.0, yD, zC, gxg, 4, 0.2), (150, 120, 90), 'pinion8', 'PETG'))
    fan = union([box(gxg + 6, gxg + 7.5, yD - 1, yD + 1, zC - 15, zC + 15), box(gxg + 6, gxg + 7.5, yD - 15, yD + 15, zC - 1, zC + 1),
                 cyl((gxg + 5, yD, zC), (gxg + 9, yD, zC), 4, 16)])
    parts.append(Part('governor fan', 'drive', 'print', fan, (180, 160, 120), 'governor', 'PETG',
                      note='воздушный регулятор: 4 лопасти 30 мм, раствор подгоняется'))
    parts.append(Part('governor arbor', 'drive', 'buy', cyl((gxg - 6, yD, zC), (gxg + 12, yD, zC), 1.5, 16), COL['steel'], 'rod3x20', 'сталь'))
    parts.append(Part('cycle shaft', 'drive', 'buy', cyl((-160, yC, zC), (X_LAY - 8, yC, zC), 4.0, 24), COL['steel'], 'rod8x380', 'сталь',
                      'вал 8 мм, 380 мм — цикловой вал'))
    rot = st.cycle
    for kind, x in CAM_X.items():
        cm = rotx(cam_mesh(kind, x, lift=CAM_LIFT[kind]), rot, yC, zC)
        parts.append(Part(f'cam {kind}', 'drive', 'print', cm, (200, 120, 60), f'cam_{kind}', 'PETG', mov='cycle'))
    gs = 178.5
    stop = rotx(box(gs - 2, gs + 2, yC - 3, yC + 3, zC, zC + 14), rot, yC, zC)
    parts.append(Part('cycle stop arm', 'drive', 'print', stop, (200, 120, 60), 'stop_arm', 'PETG', mov='cycle'))
    parts.append(Part('cycle stop latch', 'drive', 'print', box(gs - 3, gs + 3, yC - 18, yC - 10, zC + 10, zC + 22),
                      (110, 112, 120), 'stop_latch', 'PETG', note='защёлка цикла; спускается последней точкой хода клавиши'))
    for kind, x in CAM_X.items():
        lift = CAM_LIFT[kind] * cam_lift(CAM_PROFILE[kind], st.cycle % 360.0)
        h = 9.0 + lift
        # rev. 0.8: a rigid push rod with a finger at the top that reaches its own bellcrank or link (one Y lane each)
        top = CAM_TOP[kind] + lift
        yf = CAM_FINGER_Y[kind]
        fx = CAM_FINGER_X[kind]
        if kind in ('rotate', 'lift'):
            # rev. 0.9b: the finger carries a pin in the bellcrank's slot (long in X: the unit slides 9 mm over it)
            g = drive_bc_geom(kind)
            yf = g['ytip']
            zpin = g['zp'] + lift
            top = zpin - 2.8
            # rev. 0.9c: the finger runs low (under the bail and the arms' sweep) in a lane beside the input arm on +X,
            # then rises to the pin; the slide moves the bellcrank toward -X, away from that lane
            top = zpin - 11.5                 # over the U-frame rail (z 98) at rest, under the bail (118.6) at full lift
            xr0, xr1 = x + 2.6, x + 4.0
            rod = zcyl(x, yC, zC + h + 0.3, top, 1.5, 12) + box(x - 1.5, xr1, yC - 1.5, yC + 1.5, top - 2.0, top)
            rod = rod + box(xr0, xr1, min(yC, yf) - 1.5, max(yC, yf) + 1.5, top - 2.0, top)
            rod = rod + box(xr0, xr1, yf - 1.5, yf + 1.5, top - 2.0, zpin + 1.5) + \
                cyl((x - 3.0 - P.SLIDE_MAX, yf, zpin), (xr1, yf, zpin), 1.2, 12)
        else:
            rod = zcyl(x, yC, zC + h + 0.3, top, 1.5, 12)
            rod = rod + box(x + fx[0], x + fx[1], min(yC, yf) - 1.5, max(yC, yf) + 1.5, top - 2.0, top)
        roller = cyl((x - 2.5, yC, zC + h + 2.0), (x + 2.5, yC, zC + h + 2.0), 2.0, 16)
        parts.append(Part(f'cam rod {kind}', 'drive', 'buy', rod + roller, COL['steel'], 'rod3x80', 'сталь',
                          'толкатель с роликом', mov='cycle'))
    # bearing blocks and motor cheeks
    for x in (-153.0, 120.0, 171.0):
        parts.append(Part(f'cycle bearing block {x:.0f}', 'drive', 'print',
                          box(x - 3, x + 3, yC - 8, yC + 8, 0, zC + 8) - cyl((x - 4, yC, zC), (x + 4, yC, zC), 4.1, 24),
                          (110, 112, 120), 'cycle_bearing', 'PETG'))
    for xp in (175.0, X1 + 2):
        plate = box(xp - 2, xp + 2, yb - 63, y2 + 9, 0, zb + 64)
        plate = plate - cyl((xp - 3, yb, zb), (xp + 3, yb, zb), 5.1, 24) - cyl((xp - 3, y1, z1), (xp + 3, y1, z1), 3.1, 16)
        plate = plate - cyl((xp - 3, y2, z2), (xp + 3, y2, z2), 2.1, 16)
        parts.append(Part(f'motor cheek {xp:.0f}', 'drive', 'print', plate, (110, 112, 120), 'motor_cheek', 'PETG',
                          note='щёки двигателя; печатаются плашмя, двумя частями',
                          printable=lambda plate=plate: split_planes(plate, 1, [yb + 30])))
    parts.append(Part('lay shaft bearing', 'drive', 'print', box(X_LAY - 5, X_LAY + 5, -80, -70, 0, zC + 6) -
                      cyl((X_LAY, -81, zC), (X_LAY, -69, zC), 2.1, 16), (110, 112, 120), 'lay_bearing', 'PETG'))
    return parts


READ_CAM_X = 60.0           # rev. 0.10: the read cam on the cycle shaft (under the levers, between the bearings)
READ_CAM_LIFT = 4.5         # x 3 at the rocker: 13.5 mm of the retract wire
READ_PIV = (-8.0, 35.75)    # rocker pivot (y, z), axis along X; input arm 11 mm to the roller, output arm 33 mm down


def read_rocker_angle(st):
    """Rocker turn (deg from its middle position, + = roller up): the roller's centre, on its arc about the pivot, sits
    on the cam's pitch curve r = 9 + 2 + lift (the cam turned by st.cycle)."""
    if st.lock_read > 0.5 and st.cycle != 0.0:     # rev. 0.11: the lock pin holds the rocker where the cam leaves it at rest
        return read_rocker_angle(State())
    yC, zC = CYC
    py, pz = READ_PIV
    zr0 = zC + 9.0 + 2.0 + READ_CAM_LIFT * 0.5
    a0 = math.asin((zr0 - pz) / 11.0)

    def f(d):
        a = a0 + math.radians(d)
        cy, cz = py + 11.0 * math.cos(a), pz + 11.0 * math.sin(a)
        ag = math.degrees(math.atan2(cz - zC, cy - yC))          # from +Y toward +Z
        rp = 9.0 + 2.0 + READ_CAM_LIFT * cam_lift('read', (st.cycle + 90.0 - ag) % 360.0)
        return math.hypot(cy - yC, cz - zC) - rp
    lo, hi = -25.0, 25.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def reading(st):
    """rev. 0.10: code combs on the shuttle, the reading head on the U-frame, receivers, the read cam (reader.py)."""
    parts = RD.reader_parts(st, Part, COL) + RD.receivers(st, Part, COL) + RD.post_fittings(st, Part, COL)
    yC, zC = CYC
    cm = rotx(cam_mesh('read', READ_CAM_X, lift=READ_CAM_LIFT), st.cycle, yC, zC)
    parts.append(Part('cam read', 'drive', 'print', cm, (200, 120, 60), 'cam_read', 'PETG', mov='cycle'))
    py, pz = READ_PIV
    x0 = READ_CAM_X + 3.5
    zr0 = CYC[1] + 9.0 + 2.0 + READ_CAM_LIFT * 0.5
    a0 = math.asin((zr0 - pz) / 11.0)
    ry, rz = py + 11.0 * math.cos(a0), pz + 11.0 * math.sin(a0)
    rk = cyl((x0, py, pz), (x0 + 3.0, py, pz), 3.0, 16) + cyl((x0, py, pz), (x0 + 3.0, ry, rz), 1.5, 12) + \
        box(x0, x0 + 3.0, py - 1.5, py + 1.5, pz - 33.0, pz) + cyl((READ_CAM_X - 2.5, ry, rz), (x0 + 3.0, ry, rz), 0.8, 12)
    rk = rk + cyl((READ_CAM_X - 2.5, ry, rz), (READ_CAM_X + 2.5, ry, rz), 2.0, 16).translate((0, 0, 0))
    rk = rk - cyl((x0 - 1, py, pz), (x0 + 4, py, pz), 1.05, 12)
    parts.append(Part('read rocker', 'drive', 'print', rotx(rk, read_rocker_angle(st), py, pz), (200, 120, 60), 'read_rocker', 'PETG',
                      note='коромысло чтения 11/33 мм: ролик на кулачке, нижнее плечо тянет трос отвода щупов', mov='readrocker'))
    brk = box(x0 + 3.5, x0 + 6.5, py - 4.0, py + 4.0, 0.0, pz + 4.0) - cyl((x0 + 3, py, pz), (x0 + 7, py, pz), 1.05, 12)
    brk = brk - cyl((x0 + 3, READ_LOCK['y'], READ_LOCK['z']), (x0 + 7, READ_LOCK['y'], READ_LOCK['z']), 1.6, 16)   # rev. 0.11: bore of the read lock
    brk = brk + box(x0 - 2.0, x0 + 6.5, py - 36.0, py - 28.0, 0.0, 6.0) + box(x0 + 3.5, x0 + 6.5, py - 30.0, py - 3.0, 0.0, 6.0)
    parts.append(Part('read rocker bracket', 'drive', 'print', brk, (110, 112, 120), 'read_rocker_bracket', 'PETG',
                      note='стойка коромысла чтения и упор оболочки троса отвода'))
    parts.append(Part('read rocker axle', 'drive', 'buy', cyl((x0 - 0.5, py, pz), (x0 + 7.0, py, pz), 1.0, 12), COL['steel'], 'rod2x10',
                      'сталь', 'ось коромысла 2 мм'))
    parts += read_lock(st)
    parts += pointer(st)
    return parts


# ------------------------------------------------------------------ rev. 0.11: the idle cycle (read lock, hammer lock)
# A dead mark and a space must not read (a dead mark has no code; a space would read the cell its cycle sends the
# shuttle to), and a space must not strike. Two lock pins do it, each pushed in by a small lever that a Bowden wire
# pulls; the wires come from the followers of frames O (dead marks) and W (spaces), as the reading's wires do.
#  * read lock: a steel pin 3 mm along X in a guide on the read rocker's bracket; in, it stands 0.2 mm in front of
#    the rocker's lower arm while the cam keeps the rocker up (at rest), so when the cam drops at 118 deg the rocker
#    stays and the feelers stay in. Wires from O and W (a slot in the lever takes either pull).
#  * hammer lock: a pin 3 mm along X in a guide on the U-frame post, 0.3 mm in front of the hammer's arm at rest;
#    at the release (160 deg) the cocking lever's lip strikes the hammer's tail, the hammer cannot go, and the spring's
#    energy goes into the pin's rubber sleeve. The ribbon still lifts (no blow, no ink). Wire from W only.
READ_LOCK = dict(y=-6.06, z=10.75, x_in=63.0, L=14.0, travel=5.0, head=(7.0, 1.5))
HAM_LOCK = dict(y=55.2, z=220.4, x_in=-1.0, L=18.0, travel=6.2, head=(7.0, 1.5))
LOCK_LEVER_R = 9.0          # both levers: arms 9 mm (1:1), the wire pulls 1 mm per mm of pin travel


def lock_pin(x0, x1, y, z, head_left, head):
    d, t = head
    p = cyl((x0, y, z), (x1, y, z), 1.5, 16)
    hx = (x0, x0 + t) if head_left else (x1 - t, x1)
    return p + cyl((hx[0], y, z), (hx[1], y, z), d / 2, 24)


def read_lock(st):
    parts = []
    g = READ_LOCK; y, z = g['y'], g['z']
    t = g['travel'] * (1.0 - st.lock_read)                      # the pin moves -X to go in
    x0 = g['x_in'] + t; x1 = x0 + g['L']
    parts.append(Part('read lock pin', 'drive', 'buy', lock_pin(x0, x1, y, z, False, g['head']), COL['steel'], 'pin3x14', 'сталь',
                      'штырь запора чтения Ø3×14 с головкой Ø7; входит на 5 мм перед нижним плечом коромысла', mov='readlock'))
    # guide: a block on the rocker bracket's stand (x 67..70), bored for the pin, with a pad for the lever's axle
    gx1 = g['x_in'] + g['L'] - 1.5 - 0.5                        # 0.5 mm short of the head when the pin is in
    ax, ay = x1 - t + g['travel'] + 1.2, y + 1.0 - LOCK_LEVER_R     # lever axle: its arm's -X face on the head (pin out)
    ax = g['x_in'] + g['travel'] + g['L'] + 1.2
    gd = box(70.0, gx1, y - 3.5, y + 3.0, z - 4.0, z + 3.5) + box(70.0, gx1, y - 3.5, y + 3.0, 0.0, z - 4.0)
    gd = gd - cyl((66.0, y, z), (gx1 + 1.0, y, z), 1.6, 16)
    gd = gd + box(gx1 - 2.0, ax + 3.0, ay - 3.0, y - 3.0, 0.0, 4.0) + zcyl(ax, ay, 4.0, 6.0, 2.5, 16)
    gd = gd - zcyl(ax, ay, 0.0, 7.0, 1.05, 12)
    parts.append(Part('read lock guide', 'drive', 'print', gd, (110, 112, 120), 'read_lock_guide', 'PETG',
                      note='направляющая запора чтения на кронштейне коромысла'))
    phi = lock_phi(g['travel'] * st.lock_read)
    zl = (z - 1.2, z + 1.2)
    lev = zcyl(ax, ay, 6.2, zl[1], 2.5, 16) + box(ax - 1.2, ax + 1.2, ay - LOCK_LEVER_R - 1.0, ay + LOCK_LEVER_R + 1.0, *zl)
    lev = lev + box(ax - 1.2, ax + 1.2, ay - 1.5, ay + 1.5, 6.2, zl[0])
    lev = lev - zcyl(ax, ay, 6.0, zl[1] + 0.5, 1.05, 12)
    parts.append(Part('read lock lever', 'drive', 'print', rotz(lev, phi, ax, ay), (200, 120, 60), 'lock_lever', 'PETG',
                      note='рычажок запора 9/9 мм на вертикальной оси: плечо на головке штыря, плечо под тросы О и W', mov='readlock'))
    parts.append(Part('read lock axle', 'drive', 'buy', zcyl(ax, ay, 4.0, zl[1] + 0.3, 1.0, 12), COL['steel'], 'rod2x10', 'сталь'))
    return parts


def hammer_lock(st, dx):
    parts = []
    g = HAM_LOCK; y, z = g['y'], g['z']
    t = g['travel'] * (1.0 - st.lock_hammer)                    # the pin moves -X to go in (it sits right of the hammer:
    x0 = g['x_in'] + t; x1 = x0 + g['L']                        # left of x -17 the carriage's end plate passes)
    parts.append(Part('hammer lock pin', 'uframe', 'buy', lock_pin(x0, x1, y, z, False, g['head']).translate((dx, 0, 0)), COL['steel'],
                      'pin3x18', 'сталь', 'штырь запора удара Ø3×18 с головкой Ø7 и резиновой втулкой; входит на 6,2 мм перед плечом молотка',
                      mov='hammerlock'))
    gx0, gx1 = 9.0, g['x_in'] + g['L'] - 1.5 - 0.5               # 0.5 mm short of the head when the pin is in
    ax = g['x_in'] + g['travel'] + g['L'] + 1.2
    az = z - 1.0 - LOCK_LEVER_R
    # guide on a bar from the post's back plate (y 70..71, x -8..8), under the cocking lever's hub (y >= 71)
    gd = box(gx0, gx1, y - 4.0, y + 4.3, z - 4.0, z + 4.0) - cyl((gx0 - 1.0, y, z), (gx1 + 1.0, y, z), 1.6, 16)
    gd = gd + box(7.0, 10.5, y + 4.3, 70.6, z - 4.0, z + 2.0) + box(7.0, 8.5, 69.0, 70.6, 214.0, z + 2.0)
    # two cheeks down to the lever's axle (along Y), either side of the lever
    for y0, y1 in ((y - 4.2, y - 2.2), (y + 2.2, y + 4.2)):
        gd = gd + box(gx1 - 1.0, ax + 2.5, y0, y1, az - 2.5, z - 4.0 + 0.01)
    gd = gd - cyl((ax, y - 5.0, az), (ax, y + 5.0, az), 1.05, 12)
    parts.append(Part('hammer lock guide', 'uframe', 'print', gd.translate((dx, 0, 0)), (110, 112, 120), 'hammer_lock_guide', 'PETG',
                      note='направляющая запора удара на стойке молотка', mov='uframe'))
    phi = lock_phi(g['travel'] * st.lock_hammer)
    lev = cyl((ax, y - 1.8, az), (ax, y + 1.8, az), 2.5, 16) + box(ax - 1.2, ax + 1.2, y - 1.8, y + 1.8, az - LOCK_LEVER_R - 1.0, az + LOCK_LEVER_R + 1.0)
    lev = lev - cyl((ax, y - 3, az), (ax, y + 3, az), 1.05, 12)
    parts.append(Part('hammer lock lever', 'uframe', 'print', geo.roty(lev, -phi, ax, az).translate((dx, 0, 0)), (200, 120, 60), 'lock_lever', 'PETG',
                      note='рычажок запора удара 9/9 мм: верхнее плечо на головке штыря, нижнее под трос W', mov='hammerlock'))
    parts.append(Part('hammer lock axle', 'uframe', 'buy', cyl((ax, y - 4.5, az), (ax, y + 4.5, az), 1.0, 12).translate((dx, 0, 0)),
                      COL['steel'], 'rod2x10', 'сталь', mov='uframe'))
    return parts


def lock_phi(push):
    """Turn of a lock lever (deg) that moves the pin's head by push mm: the arm's face corner (radius R + 1, 1.2 off the
    centre line) is what touches the head, so R sin(phi) is not quite it; 0.05 mm of clearance kept."""
    if push <= 0:
        return 0.0
    R = LOCK_LEVER_R + 1.0
    lo, hi = 0.0, 80.0
    for _ in range(40):
        m = 0.5 * (lo + hi); a = math.radians(m)
        if R * math.sin(a) - 1.2 * (1 - math.cos(a)) > push - 0.05:
            hi = m
        else:
            lo = m
    return lo


def build(st):
    out = []
    for fn in (frame, keyboard, levers, plates, bails, frame_springs, sectors, mark_stops, selectors, uframe, shuttle, reading, carriage,
               escapement, carriage_release, ribbon, drive):
        out += fn(st)
    return press_all(out, st)


def press_all(out, st):
    """rev. 0.9.2: at the blow the hammer carries the sheet, and the sheet the ribbon, onto the type face."""
    by = {p.name: p for p in out}
    if st.hammer > 0.9 and all(n in by for n in ('hammer', 'paper', 'ribbon')):
        by['paper'].mesh, push = pressed(by['paper'].mesh, by['hammer'].mesh, PAPER_T, PAPER_BACK)
        if push is not by['hammer'].mesh:
            by['ribbon'].mesh, _ = pressed(by['ribbon'].mesh, push, RIBBON_T, P.RIBBON_Y + RIBBON_T / 2)
    return out


# ------------------------------------------------------------------------- rev. 0.8b: the stops of the print unit
# The slide (U-frame) rests on a zero stop; for a dead mark the O frame pushes it back through a compliant link until
# the feeler finger meets the step of sector B (or C, chosen by N) for the remembered value: retraction (8 + k) u.
FIN_X = {'B': 160.5, 'C': 155.5}           # planes of the sectors (SECTOR_X)
SBC = (154.0, -262.0)                       # sine bellcrank feeler -> carrier (vertical axis)
NSEL = (165.5, -282.0, 44.0)                # N lever pivot (axis along Y): x, y, z
OBC = (-135.0, -166.0)                      # bellcrank rod B -> post on the slide
OROCK = (-200.0, 60.0)                      # rocker behind the keys: y, z (axis along X)
O_X = -122.5                                # lane of the O link on the left


def mark_stops(st):
    parts = []
    d = st.slide()                                           # retraction, mm (the unit moves -X)
    ys, zs = SECT_SHAFT
    ret = P.SLIDE_MAX + 0.0
    # zero stop with an adjusting screw on the front beam, return spring
    blk = box(151, 160, -158, -142, 99, 112) + box(152, 160, -158, -142, 90, 99)
    parts.append(Part('zero stop', 'frame', 'print', blk - cyl((150, -150, 106), (161, -150, 106), 1.3, 12), (110, 112, 120), 'zero_stop', 'PETG',
                      note='нулевой упор узла: колодка на переднем брусе'))
    parts.append(Part('zero stop screw', 'frame', 'buy', cyl((140.05, -150, 106), (158, -150, 106), 1.5, 12), COL['steel'], 'grubM3x20', 'сталь'))
    parts.append(Part('slide return spring', 'frame', 'buy', cyl((141.5, -146, 101), (151, -146, 101), 2.0, 12), COL['steel'], 'spring_ret',
                      'сталь', 'пружина растяжения возврата узла, около 1 Н'))
    # feeler: a steel strip under the base, along the right side to the bellcrank (moves with the unit)
    fe = box(136, 140, -165, -161, 92, 103) + box(136, 160, -165, -161, 92, 96) + box(156, 160, -284, -161, 92, 96)
    parts.append(Part('stop feeler', 'uframe', 'cut', fe.translate((-d, 0, 0)), COL['steel'], 'strip4x4', 'сталь',
                      'щуп упоров: полоса 4×4 мм на плите узла', mov='uframe'))
    # sine bellcrank: input roller on the feeler's flat, output roller on the carrier's flat; exact 1:1
    r = LK.BC_R
    phi = math.degrees(math.asin(min(1.0, d / r)))
    bx, by = SBC
    bc = zcyl(bx, by, 97, 103, 3.5, 20) + box(bx - 1.5, bx + 1.5, by - r, by, 97, 101) + zcyl(bx, by - r, 92, 101, 2.0, 12) + \
        box(bx, bx + r, by - 1.5, by + 1.5, 97, 101) + zcyl(bx + r, by, 97, 101, 2.0, 12)
    bc = bc - zcyl(bx, by, 96, 104, 1.55, 12)
    parts.append(Part('stop bellcrank', 'sectors', 'print', rotz(bc, -phi, bx, by), COL['pin'], 'stop_bc', 'PETG',
                      note='синусный угловой рычаг 1:1 с роликами', mov='stopbc'))
    br = box(150, 173, -263.5, -258, 103.2, 106.2) + box(172, 173, -263.5, -256, 92, 106.2)
    parts.append(Part('stop bellcrank bracket', 'sectors', 'print', br, (110, 112, 120), 'stop_bc_br', 'PETG'))
    parts.append(Part('stop bellcrank pin', 'sectors', 'buy', zcyl(bx, by, 97, 106.2, 1.5, 12), COL['steel'], 'rod3x20', 'сталь'))
    # carrier: slides along -Y on a rod; carries the finger slider
    car = box(152, 164, -292, -267, 101.5, 104.5) - box(154, 162, -287.5, -284.5, 100, 106) - box(157.5, 165, -284, -271, 100, 106)
    car = car + box(164, 171.5, -270, -264, 97, 104.5) + box(167.5, 171.5, -292, -264, 97, 104.5)
    car = car - cyl((169.5, -300, 99), (169.5, -260, 99), 1.6, 12)
    parts.append(Part('stop carrier', 'sectors', 'print', car.translate((0, -d, 0)), COL['sector'], 'stop_carrier', 'PETG',
                      note='каретка щупа: ход до 9 мм по Y, пружина к ролику', mov='stopcar'))
    parts.append(Part('stop carrier rod', 'sectors', 'buy', cyl((169.5, -307, 99), (169.5, -280, 99), 1.5, 12), COL['steel'], 'rod3x30', 'сталь',
                      'направляющая каретки щупа'))
    parts.append(Part('stop carrier rod bracket', 'sectors', 'print',
                      box(167.5, 173, -308, -303, 92, 104) - cyl((169.5, -309, 99), (169.5, -302, 99), 1.55, 12), (110, 112, 120), 'stop_rod_br', 'PETG'))
    # finger slider: B plane by default, the N lever moves it 5 mm to the C plane
    nsh = LK.n_shift(st.frames.get('N', 0.0))
    xf = FIN_X['B']
    yf = ys + LK.FINGER_R0
    fin = box(xf - 3, xf + 3, -292, -280, 104.5, 108.5) + box(xf - 1, xf + 1, yf + 2, yf + 4, 47.7, 104.5) + \
        box(xf - 1, xf + 1, yf, yf + 4, 46.3, 47.7)
    parts.append(Part('stop finger', 'sectors', 'print', fin.translate((-nsh, -d, 0)), COL['pin'], 'stop_finger', 'PETG',
                      note='щуп: торец 2 мм на высоте оси секторов; ступень памяти останавливает его', mov='stopfin'))
    # N lever: roller on the N beam, upright arm, top bar pushing the slider
    nx, ny, nz = NSEL
    a = -math.degrees(math.asin(nsh / LK.N_OUT))
    lev = box(nx - LK.N_IN, nx, ny - 1, ny + 1, nz - 1, nz + 1) + cyl((nx - LK.N_IN, ny - 1.5, nz), (nx - LK.N_IN, ny + 1.5, nz), 2.0, 12) + \
        box(nx - 1, nx + 1, ny - 1, ny + 1, nz, nz + LK.N_OUT + 1.5) + box(163.5, nx + 1, ny - 1, ny + 1, nz + LK.N_OUT - 1.5, nz + LK.N_OUT + 1.5) + \
        box(163.5, 165.5, -301, ny, nz + LK.N_OUT - 1.5, nz + LK.N_OUT + 1.5) + cyl((nx, ny - 3, nz), (nx, ny + 3, nz), 3.0, 16)
    lev = lev - cyl((nx, ny - 4, nz), (nx, ny + 4, nz), 1.55, 12)
    parts.append(Part('stop selector lever', 'sectors', 'print', geo.roty(lev, a, nx, nz), COL['pin'], 'nsel_lever', 'PETG',
                      note='рычаг N: ролик на балке N, ход щупа 5 мм за первые 1,5 мм рамки', mov='nsel'))
    nb = box(167.5, 173, -290, -286, 38, 50) + box(167.5, 173, -278, -274, 38, 50) + box(171, 173, -290, -274, 38, 50)
    parts.append(Part('stop selector bracket', 'sectors', 'print', nb - cyl((nx, -292, nz), (nx, -272, nz), 1.55, 12) +
                      cyl((nx, -290, nz), (nx, -286, nz), 2.5, 12) + cyl((nx, -278, nz), (nx, -274, nz), 2.5, 12)
                      - cyl((nx, -292, nz), (nx, -272, nz), 1.55, 12), (110, 112, 120), 'nsel_br', 'PETG'))
    parts.append(Part('stop selector pin', 'sectors', 'buy', cyl((nx, -290, nz), (nx, -274, nz), 1.5, 12), COL['steel'], 'rod3x20', 'сталь'))
    parts += o_link(st)
    return parts


def o_link(st):
    """O frame -> slide: left follower (on the W follower axis), rod A with a spring section, rocker behind the keys,
    rod B, bellcrank, post on the slide."""
    parts = []
    ys, zs = SECT_SHAFT
    d = st.slide()
    s_o = st.frames.get('O', 0.0)
    dO = LK.follower_angle(min(s_o, LK.O_CLAMP)) - LK.THETA0
    p = LK.o_push(s_o)                                   # push of the arm pin, +Y
    q = d * LK.ROCKER[0] / LK.ROCKER[1]                  # the rocker follows the slide (rod B and the bellcrank 1:1)
    x = O_X
    tube = cyl((-128, ys, zs), (-113, ys, zs), 3.0, 24) - cyl((-129, ys, zs), (-112, ys, zs), 2.05, 16)
    m = tube + follower_mesh(-LK.LANES['O'], ys, zs) + box(x - 1.5, x + 1.5, ys - 1.5, ys + 1.5, zs - LK.O_ARM - 2, zs) + \
        cyl((x - 1.5, ys, zs - LK.O_ARM), (x + 1.5, ys, zs - LK.O_ARM), 1.2, 12)
    parts.append(Part('O follower', 'sectors', 'print', rotx(m, dO, ys, zs), COL['sector'], 'o_follower', 'PETG',
                      note='повторитель O: ролик на балке O, плечо 12 мм вниз к тяге A', mov='followO'))
    ry, rz = OROCK
    parts.append(Part('O rod A rear', 'sectors', 'buy', box(x - 1.5, x + 1.5, ys + p - 3, -262 + p, zs - LK.O_ARM - 2, zs - LK.O_ARM + 2),
                      COL['steel'], 'strip3x4', 'сталь', 'тяга A, задняя часть (паз под палец повторителя)', mov='orodA'))
    parts.append(Part('O rod A spring', 'sectors', 'buy', cyl((x, -262 + p, zs - LK.O_ARM), (x, -252 + q, zs - LK.O_ARM), 2.2, 12),
                      COL['steel'], 'spring_oA', 'сталь', 'пружина сжатия: поджатие 1,5 Н, до 2,3 Н', mov='orodS'))
    parts.append(Part('O rod A front', 'sectors', 'buy', box(x - 1.5, x + 1.5, -252 + q, ry + 2 + q, zs - LK.O_ARM - 2, zs - LK.O_ARM + 2),
                      COL['steel'], 'strip3x4', 'сталь', 'тяга A, передняя часть', mov='orodAf'))
    psi = math.degrees(math.asin(min(1.0, q / LK.ROCKER[0])))
    zl, zu = rz - LK.ROCKER[0], rz + LK.ROCKER[1]
    rk = cyl((x - 1.5, ry, rz), (-119.2, ry, rz), 3.5, 16) + box(x - 1.5, x + 1.5, ry - 1.5, ry + 1.5, zl, zu) + \
        cyl((x - 1.5, ry, zl), (x + 1.5, ry, zl), 1.2, 12) + cyl((x - 1.5, ry, zu), (x + 1.5, ry, zu), 1.2, 12)
    rk = rk - cyl((x - 5, ry, rz), (x + 5, ry, rz), 1.55, 12)
    parts.append(Part('O rocker', 'sectors', 'print', rotx(rk, psi, ry, rz), COL['sector'], 'o_rocker', 'PETG',
                      note='качалка за клавишами: 33/34 мм', mov='orock'))
    parts.append(Part('O rocker pin', 'sectors', 'buy', cyl((x - 1.5, ry, rz), (-116.0, ry, rz), 1.5, 12), COL['steel'], 'rod3x20', 'сталь',
                      'ось качалки, в стойке запорной гребёнки'))
    yB = ry - LK.ROCKER[1] * math.sin(math.radians(psi))
    bxo, byo = OBC
    rB = box(x - 1.5, x + 1.5, ry - 2, byo + 1, zu - 2, zu + 2).translate((0, -d, 0))
    parts.append(Part('O rod B', 'sectors', 'buy', rB, COL['steel'], 'strip3x4', 'сталь', 'тяга B: работает на растяжение', mov='orodB'))
    r = LK.O_BC_R
    phi = math.degrees(math.asin(min(1.0, d / r)))
    ob = zcyl(bxo, byo, 92, 96, 3.0, 16) + box(bxo, bxo + r, byo - 1.5, byo + 1.5, 92, 96) + zcyl(bxo + r, byo, 92, 96, 1.5, 12) + \
        box(bxo - 1.5, bxo + 1.5, byo - r, byo, 92, 96) + zcyl(bxo, byo - r, 92, 96, 2.0, 12)
    ob = ob - zcyl(bxo, byo, 91, 97, 1.55, 12)
    parts.append(Part('O bellcrank', 'sectors', 'print', rotz(ob, -phi, bxo, byo), COL['sector'], 'o_bc', 'PETG',
                      note='угловой рычаг 12/12 мм с роликом', mov='obc'))
    parts.append(Part('O bellcrank bracket', 'frame', 'print', box(bxo - 4, bxo + 4, byo - 4, P.RAIL_Y[0] - 10, 86, 90) +
                      zcyl(bxo, byo, 90, 91.8, 3.0, 16), (110, 112, 120), 'o_bc_br', 'PETG', note='кронштейн на переднем брусе'))
    parts.append(Part('O bellcrank pin', 'frame', 'buy', zcyl(bxo, byo, 86, 97, 1.5, 12), COL['steel'], 'rod3x20', 'сталь'))
    post = box(-143, -126, -181, -165, 99, P.UF_Z) + box(-143, -137, -181, -172, 92, 99)
    parts.append(Part('O post', 'uframe', 'print', post.translate((-d, 0, 0)), COL['uframe'], 'o_post', 'PETG',
                      note='упор на плите узла под рычагом отвода', mov='uframe'))
    return parts


def frame_springs(st):
    """rev. 0.8b: each frame stands on two compression springs around its rear guide rods (under the rear sleeves)."""
    parts = []
    dy = P.TIER_SHIFT * st.tier
    for name in FRAMES:
        yf, yr = guide_y(name)
        for sx in (-1, 1):
            xx = sx * LANES[name]
            sp = geo.tube(xx, yr, TIER_BOT_Z[1], SLEEVE_Z[0] - st.frames.get(name, 0.0), 2.6, 1.65)
            parts.append(Part(f'bail {name} spring {sx:+d}', 'bails', 'buy', sp.translate((0, dy, 0)), COL['steel'], 'spring_frame',
                              'сталь', 'пружина сжатия 5,2×0,5 мм на направляющей', mov=f'spring{name}'))
    return parts
