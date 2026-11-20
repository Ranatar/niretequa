"""rev. 0.9c: the escapement with backspace, back-a-letter and the +-u lever (section "Забой и назад на литеру").

Plan view, angles CCW from +X about the wheel axis ESC; the wheel's forward turn (carriage spring, carriage -X) is
CCW. The wheel is a ratchet of 60 teeth, 10 mm thick: lower tier z 66..71, upper tier 71..76. Every tooth has a radial
face that looks CCW (at angles 6k + rot) and a slope rising CCW from the root (r 18) to the tip (r 20.5).

* holding dog D: a radial slider at 90 deg (back); its tip sits in the gap CCW of a face and touches it, so the wheel
  cannot go forward; it rides up the slopes when the wheel goes back.
* movable stop U: a drum (r 9.55, steel tape from the W link: exactly 6 deg per unit) with an arm and a finger in the
  lower tier at 186 + 6 (w - 4 + pm) deg; the finger is a radial slider, 3 mm out of the teeth at rest.
* +-u: an eccentric under the W link's bellcrank moves rod X by one unit (parts.escape_link).
The parts are built in this design frame and mirrored (x -> -x) into the machine: there the wheel goes forward CW,
as the rack below the pinion turns it when the carriage moves -X.
* back arm B: above the wheel; a pawl in the upper tier, held out of the teeth at rest by a guard; two ball studs at
  r 13 for the links. Turning CW, the pawl drops in after 0.6 deg, meets a face at 1.2 deg and turns the wheel back.
* memory arm M: above B; it carries a coupling wedge (upper tier) and a holding pawl in a fixed ratchet sector. On a
  release the wedge couples M to the wheel, so M goes forward with it by 6 w; the holding pawl keeps it there. For
  back-a-letter the wedge couples M again and the holding pawl lets go: the wheel goes back with M until M meets its
  zero stop, that is by 6 w (plus 1.2 deg of the wedge's play, so the dog falls in; the wheel comes forward onto it).
* rockers: the tails of the backspace and back-a-letter levers carry pins in slots of two rockers on one shaft
  (y 30, z 50.5); their lower arms pull two links with ball ends to B's studs. The backspace rocker meets a stop after
  1.4 teeth of B; the back-a-letter link has a spring for the rest of the stroke."""
import math
import numpy as np
from shapely.geometry import Polygon
from shapely import affinity
import params as P
import geo
from geo import box, cyl, zcyl, union, rotz

ESC = (0.0, 116.05)
TEETH = 60
PITCH = 360.0 / TEETH
R_ROOT, R_TIP = 18.0, 20.5
Z_W = (66.0, 76.0)                 # wheel
Z_LO, Z_UP = (66.0, 71.0), (71.0, 76.0)
TH_D = 90.0                        # dog
REL_LIFT = 3.0                     # rev. 0.11: the carriage release draws the dog 3 mm out (teeth 2.5 mm deep)
TH_U0 = 162.0                      # U finger at w = 0 (the rest is at 4 teeth: 186 deg)
TH_B = 0.0                         # face that B's pawl meets
B_CATCH = 5.4                      # deg of B before its pawl meets the face
B_DROP = 4.6                       # deg of B before the guard pin lets the pawl in
TH_M = 300.0                       # M at zero (memory 0)
M_PLAY = 1.2                       # play of the coupling wedge (deg)
Z_B = (62.8, 65.6)                 # B under the wheel; its pawl reaches up into the lower tier
Z_M = (81.2, 84.0)                 # M over U; its wedge reaches down into the upper tier
Z_MH = (78.7, 80.9)                # M's holding pawl and the fixed sector (at U's arm level, away from its sweep)
Z_UD = (76.5, 78.5)                # U drum over the wheel (tape)
Z_UA = (78.7, 80.9)                # U arm; its finger reaches down into the upper tier
R_DRUM = 9.549                     # 6 deg per mm of the W link (1 unit = 1 mm)
STUD = {'bksp': (19.0, -60.0), 'back': (10.0, -11.0)}   # (r, deg, design frame) of the ball studs at rest: back on B,
                                                        # backspace on its own arm K that pushes B
STUD_Z = {'bksp': 56.6, 'back': 56.3}
Z_K = (59.6, 62.4)                 # backspace arm K, between the plate and B
# rockers on axes along Y behind the levers' tails; a pin along Y in each tail runs in a slot of the input arm
ROCK = dict(z=50.5, xa={'bksp': 116.0, 'back': 136.0}, xpin={'bksp': 124.0, 'back': 131.0},
            yin={'bksp': (25.0, 27.0), 'back': (28.0, 30.0)}, yout=(31.0, 33.0), yball={'bksp': 28.3, 'back': 35.5},
            r_out={'bksp': 9.0, 'back': 30.0}, up={'bksp': False, 'back': True})
TAIL_PIN = dict(y=(22.0, {'bksp': 27.4, 'back': 30.4}), z=50.5)
BKSP_DEG = B_CATCH + 1.2 * PITCH    # the wheel goes back 1.2 teeth, the dog falls in after one


def sec(r0, r1, a0, a1, z0, z1):
    """Annular sector about the wheel axis, angles CCW from +X."""
    return geo.sector_xy(ESC[0], ESC[1], r0, r1, 90.0 - a1, 90.0 - a0, z0, z1)


def slope_r(da):
    """Radius of the tooth surface da deg CCW of a face (0 <= da < 6)."""
    return R_ROOT + (R_TIP - R_ROOT) * (da % PITCH) / PITCH


def wheel_profile(rot):
    """The wheel's outline (shapely) at rotation rot (deg)."""
    pts = []
    for k in range(TEETH):
        a0 = math.radians(k * PITCH + rot); a1 = math.radians((k + 1) * PITCH + rot)
        pts.append((ESC[0] + R_ROOT * math.cos(a0), ESC[1] + R_ROOT * math.sin(a0)))
        pts.append((ESC[0] + R_TIP * math.cos(a1 - 1e-3), ESC[1] + R_TIP * math.sin(a1 - 1e-3)))
    return Polygon(pts)


def P2(r, a):
    a = math.radians(a)
    return (ESC[0] + r * math.cos(a), ESC[1] + r * math.sin(a))


def tip_shape(face, play=0.0, r_out=23.5, w_cw=4.0, w_ccw=6.0, slope_gap=0.2):
    """Tip that fills the gap CCW of the face at angle `face`: its CW edge on the face (touching), its underside
    0.2 mm over the slope, shifted CCW by `play` deg; above the tooth tips it widens."""
    pts = [P2(R_ROOT + 0.35, face), P2(20.75, face), P2(20.75, face - w_cw), P2(r_out, face - w_cw), P2(r_out, face + w_ccw),
           P2(20.75, face + w_ccw)]
    n = 24
    for i in range(n + 1):
        th = face + w_ccw - w_ccw * i / n
        r = slope_r(min(th - face + play, PITCH - 1e-6)) + slope_gap if th - face + play < PITCH else 20.75
        pts.append(P2(min(max(r, R_ROOT + 0.35), 20.75), th))
    return Polygon(pts).buffer(0)


def extrude(g, z0, z1):
    return geo.shapely_to_cs(g).extrude(z1 - z0).translate((0, 0, z0))


def wheel_rot(st):
    return -math.degrees((st.car - P.CAR_X_START) / 5.053)


def b_angle(st):
    """B's CW turn (deg) from the two keys: backspace 1.4 teeth; back-a-letter to M's zero stop (6 w + play)."""
    fb = st.pressed.get(46, 0.0); fk = st.pressed.get(47, 0.0)
    w = st.esc_mem
    return max(BKSP_DEG * fb, (B_CATCH + PITCH * w + M_PLAY) * fk)


def dog_lift(rot):
    """Radial lift of the dog so its tip clears the wheel at rotation rot (0 at a whole tooth)."""
    tip = tip_shape(TH_D)
    wp = wheel_profile(rot)
    lo, hi = 0.0, 3.0
    if tip.intersection(wp).area < 1e-5:
        return 0.0
    for _ in range(20):
        mid = (lo + hi) / 2
        if affinity.translate(tip, 0, mid).intersection(wp).area < 1e-5:
            hi = mid
        else:
            lo = mid
    return hi


def MIR(m):
    """Design frame -> machine (mirror about the plane x = ESC x = 0)."""
    return m.mirror((1, 0, 0))


def parts(st, Part, COL, cached):
    x, y = ESC
    zr = P.CAR_RAIL_LO[1]
    out = []
    rot = wheel_rot(st)
    def add(name, kind, mesh, color, bom, mat, note='', mov='fixed', design=True):
        out.append(Part(name, 'esc', kind, MIR(mesh) if design else mesh, color, bom, mat, note=note, mov=mov))
    # ---- wheel and pinion
    def wheel():
        pin = geo.gear_profile(10, 1.0106, x, y).extrude(6).translate((0, 0, zr - 2))
        w = geo.ratchet_profile(TEETH, R_ROOT, R_TIP, x, y).extrude(Z_W[1] - Z_W[0]).translate((0, 0, Z_W[0]))
        m = pin + w + zcyl(x, y, Z_W[0], zr - 2, 6, 24)
        return m - zcyl(x, y, 20, 120, 2.05, 16)
    add('escapement wheel and pinion', 'print', rotz(cached('escw', wheel), rot, x, y), COL['esc'], 'esc_wheel', 'PETG',
        'храповое колесо 60 зубьев толщиной 10 мм (два этажа) и шестерня z = 10 одной деталью', 'esc')
    add('escapement shaft', 'buy', zcyl(x, y, 20, zr + 8, 2.0, 16), COL['steel'], 'rod4x80', 'сталь')
    # ---- bracket
    def bracket():
        pp = P2(31.0, 160.0)                       # front post, clear of B, U, M and D
        br = box(pp[0] - 3, x + 34, y - 6, y + 34, 20, 24)
        br = br + box(pp[0] - 3, pp[0] + 3, pp[1] - 3, pp[1] + 3, 20, 102)
        br = br + box(pp[0] - 3, x + 34, y - 12, y + 34, 50, 54) - zcyl(x, y, 49, 55, 4.0, 32)
        br = br + box(pp[0] - 3, x + 34, y - 6, y + 34, 98, 102)
        br = br + box(x + 6, x + 12, y + 28, y + 34, 20, 102)                              # back post
        br = br + box(x - 6, x - 2.2, y + 24, y + 30, 64, 78) + box(x + 2.2, x + 6, y + 24, y + 30, 64, 78) + \
            box(x - 6, x + 12, y + 24, y + 30, 78, 80)                                      # the dog's channel
        return br - zcyl(x, y, 19, 121, 2.1, 16)
    add('escapement bracket', 'print', cached('escBR', bracket), (110, 112, 120), 'esc_bracket', 'PETG',
        'кронштейн спуска: передняя стойка слева, задняя стойка с направляющей собачки, плиты 50 и 98 мм')
    # ---- holding dog
    lift = dog_lift(rot % PITCH if abs((rot % PITCH) - PITCH) > 1e-6 else 0.0)
    lift = max(lift, REL_LIFT * st.car_release)     # rev. 0.11: the carriage release wire draws the dog out
    def dog():
        dg = extrude(tip_shape(TH_D, r_out=23.5, w_cw=1.6, w_ccw=2.0), Z_W[0] + 0.5, Z_W[1] - 0.5)
        return dg + box(x - 2.0, x + 2.0, y + 23.0, y + 27.6, Z_W[0] + 0.5, Z_W[1] - 0.5)
    add('escapement dog', 'print', cached('escD', dog).translate((0, lift, 0)), COL['esc'], 'esc_dog', 'PETG',
        'держащая собачка: ползун в направляющей за колесом, пружина 0,3 Н', 'escdog')
    # rev. 0.11: carriage release: a Bowden wire on the dog's tail, its sheath on a tab of the back post; the key that
    # pulls it is on the front frame (parts.carriage_release)
    add('dog release wire end', 'buy', cyl((x, y + 27.6, 71.0), (x, y + 29.6, 71.0), 1.0, 12).translate((0, lift, 0)), COL['steel'],
        'cable_end', 'сталь', 'наконечник троса освобождения каретки на хвосте собачки', 'escdog')
    tab = box(x - 3.0, x + 12.0, y + 33.0, y + 35.0, 67.0, 75.0) - cyl((x, y + 32.0, 71.0), (x, y + 36.0, 71.0), 0.8, 12)
    add('dog release sheath stop', 'print', tab, (110, 112, 120), 'release_stop', 'PETG',
        'упор оболочки троса освобождения на задней стойке кронштейна спуска')
    # ---- U: drum (tape), arm with a slot, finger slider
    s_w = max(st.frames.get('W', 0.0), st.frames.get('Wr', 0.0))     # rev. 0.10: frame W (spaces) or the W wire
    th_u = TH_U0 + PITCH * (4 + s_w + st.pm_u)
    def ustop():
        d = zcyl(x, y, *Z_UD, R_DRUM, 64) + zcyl(x, y, Z_UD[1], Z_UA[1], 9.0, 48)
        arm = box(x + 4.0, x + 34.0, y - 2.5, y + 2.5, *Z_UA) - box(x + 21.0, x + 32.5, y - 1.25, y + 1.25, Z_UA[0] - 1, Z_UA[1] + 1)
        return (d + arm) - zcyl(x, y, Z_UD[0] - 1, Z_UA[1] + 1, 6.1, 32)
    add('escapement stop', 'print', rotz(cached('escU', ustop), th_u, x, y), COL['esc'], 'esc_stop', 'PETG',
        'переставной упор U: барабан R 9,55 мм под ленту от тяги W (6° на единицу), рычаг с пазом под палец', 'followW')
    def ufinger():
        f = extrude(tip_shape(0.0, r_out=21.6, w_cw=1.2, w_ccw=2.2), Z_UP[0] + 0.3, Z_UD[0] - 0.2)
        return f + box(x + 21.2, x + 28.8, y - 1.2, y + 1.2, *Z_UA) + \
            box(x + 21.2, x + 22.4, y - 1.2, y + 1.2, Z_UP[0] + 0.3, Z_UA[1])
    rout = 0.0 if st.u_in else 3.0
    add('escapement stop finger', 'print', rotz(cached('escUF', ufinger).translate((rout, 0, 0)), th_u, x, y), COL['esc'],
        'esc_finger', 'PETG', 'палец U: ползун в пазу рычага; в покое выведен из зубьев на 3 мм, входит перед спуском', 'followW')
    # tape (machine frame): from rod X's end along the drum's bottom, wrapped CCW to its anchor; the drum turns CW
    a_anchor = 40.0 - PITCH * (s_w + st.pm_u)
    tp = box(-6.0, 0.0, y - R_DRUM - 0.1, y - R_DRUM, Z_UD[0] + 0.25, Z_UD[1] - 0.25) + \
        geo.sector_xy(x, y, R_DRUM, R_DRUM + 0.1, 90.0 - a_anchor, 180.0, Z_UD[0] + 0.25, Z_UD[1] - 0.25)
    add('escapement tape', 'buy', tp.translate((-s_w - st.pm_u, 0, 0)) ^ box(-60, 60, 0, 200, 0, 200) if False else tp, (60, 60, 70),
        'tape', 'сталь', 'лента 0,1 мм от тяги X к барабану U', 'followW', design=False)
    # ---- B (under the wheel), its pawl and guard
    beta = b_angle(st)
    pv = P2(25.0, 13.0)
    def barm():
        h = zcyl(x, y, *Z_B, 9.5, 48) - zcyl(x, y, Z_B[0] - 1, Z_B[1] + 1, 2.05, 16)
        m = h + sec(2.5, 19.0, -40.0, -3.0, *Z_B) + sec(2.5, 27.5, 8.0, 18.0, *Z_B)
        r, a = STUD['back']; c = P2(r, a)
        m = m + zcyl(c[0], c[1], STUD_Z['back'], Z_B[0] + 0.5, 0.9, 12) + geo.Manifold.sphere(1.6, 24).translate((c[0], c[1], STUD_Z['back']))
        m = m + zcyl(pv[0], pv[1], Z_B[1], Z_LO[1] - 0.5, 1.0, 12)
        return m - zcyl(x, y, Z_B[0] - 1, Z_B[1] + 1, 2.05, 16)
    add('back lever B', 'print', rotz(cached('escB', barm), -beta, x, y), COL['esc'], 'esc_back_lever', 'PETG',
        'рычаг B под колесом: собачка в нижнем этаже, шаровой палец R 10 мм', 'backB')
    def karm():
        h = zcyl(x, y, *Z_K, 6.0, 32)
        m = h + sec(2.5, 17.0, 30.0, 40.0, *Z_K) + sec(15.5, 22.0, -66.0, 40.0, *Z_K)
        # finger just CCW of B's back-stud neck (r 13): it pushes the neck, the back key turns B away from it
        a_n = STUD['back'][1] + math.degrees((0.9 + 0.02) / STUD['back'][0])
        rb_ = STUD['back'][0]
        m = m + sec(rb_ - 1.5, 15.6, a_n, a_n + 4.0, *Z_K)
        r, a = STUD['bksp']; c = P2(r, a)
        m = m + zcyl(c[0], c[1], STUD_Z['bksp'], Z_K[0] + 0.5, 0.9, 12) + geo.Manifold.sphere(1.6, 24).translate((c[0], c[1], STUD_Z['bksp']))
        return m - zcyl(x, y, Z_K[0] - 1, Z_K[1] + 1, 2.05, 16)
    kb = BKSP_DEG * st.pressed.get(46, 0.0)
    add('backspace arm K', 'print', rotz(cached('escK', karm), -kb, x, y), COL['esc'], 'esc_bksp_arm', 'PETG',
        'рычаг забоя K на оси спуска: толкает B на 12,6°; шаровой палец R 19 мм', 'backK')
    def bpawl():
        zz = (Z_LO[0] + 0.5, Z_LO[1] - 0.5)
        t = extrude(tip_shape(TH_B + B_CATCH, play=1.4, r_out=22.5, w_cw=1.0, w_ccw=2.0), *zz)
        body = geo.Manifold.batch_hull([zcyl(pv[0], pv[1], *zz, 2.2, 16), zcyl(*P2(21.6, TH_B + B_CATCH + 0.5), *zz, 1.0, 12)])
        tail = geo.Manifold.batch_hull([zcyl(pv[0], pv[1], *zz, 2.2, 16), zcyl(*P2(27.5, 21.0), *zz, 1.2, 12)])
        return (t + body + tail) - zcyl(pv[0], pv[1], Z_LO[0], Z_LO[1], 1.05, 12)
    bp = cached('escBP', bpawl)
    if beta < B_DROP:
        bp = rotz(bp, pawl_lift_angle(), pv[0], pv[1])      # held out by the guard: the tip clears the tooth tips
    add('back pawl', 'print', rotz(bp, -beta, x, y), COL['esc'], 'esc_back_pawl', 'PETG', 'собачка B на пальце рычага, пружина 0,2 Н', 'backB')
    def guard():
        gc, gd = guard_face()
        return zcyl(gc[0], gc[1], Z_LO[0] + 0.5, Z_LO[1] - 0.5, 0.8, 16) + zcyl(gc[0], gc[1], 54.0, Z_LO[0] + 0.5, 0.8, 16)
    add('back pawl guard', 'print', cached('escG', guard), (110, 112, 120), 'esc_guard', 'PETG',
        'штифт-щиток 1,6 мм: в покое хвост собачки B лежит на нём, и она вне зубьев; стоит в средней плите')
    # ---- M (over the wheel)
    fk = st.pressed.get(47, 0.0) > 0
    m_ang = TH_M + PITCH * st.esc_mem - (max(0.0, beta - B_CATCH - M_PLAY) if fk else 0.0)
    coupled = fk or st.m_couple
    def mwedge():
        return extrude(tip_shape(0.0, play=M_PLAY, r_out=22.5, w_cw=1.5, w_ccw=2.5, slope_gap=0.0), Z_UP[0] + 0.5, Z_M[0] + 3.8)
    def marm():
        h = zcyl(x, y, *Z_M, 9.5, 48) - zcyl(x, y, Z_M[0] - 1, Z_M[1] + 1, 6.1, 32)
        a = sec(8.0, 26.2, -5.0, 4.0, *Z_M) + zcyl(*P2(26.0, 2.5), Z_MH[0], Z_M[0], 1.0, 12)
        slot = geo.shapely_to_cs(tip_shape(0.0, play=M_PLAY, r_out=22.5, w_cw=1.5, w_ccw=2.5, slope_gap=0.0).buffer(0.15)).extrude(10).translate((0, 0, Z_M[0] - 2))
        return h + a - slot
    add('memory lever M', 'print', rotz(cached('escM', marm), m_ang, x, y), COL['esc'], 'esc_memory', 'PETG',
        'рычаг памяти M: помнит ширину последней литеры (6w°)', 'escM')
    wz = 0.0 if coupled else 4.6
    add('memory coupling wedge', 'print', rotz(cached('escMW', mwedge), m_ang, x, y).translate((0, 0, wz)), COL['esc'], 'esc_wedge', 'PETG',
        'клин сцепления M с колесом (люфт 1,2°) в пазу M', 'escM')
    def mpawl():
        tip = Polygon([P2(26.6, 2.0), P2(28.95, 2.0), P2(28.25, 3.9), P2(26.6, 3.9)])
        return extrude(tip, *Z_MH) + zcyl(*P2(26.0, 2.5), *Z_MH, 1.4, 12) - zcyl(*P2(26.0, 2.5), Z_MH[0] - 1, Z_MH[1] + 1, 1.05, 12)
    hp = cached('escMP', mpawl)
    if fk:                                           # back-a-letter: the holding pawl is let go (0.9 mm inward)
        hp = hp.translate((-0.9 * math.cos(math.radians(3.0)), -0.9 * math.sin(math.radians(3.0)), 0))
    add('memory holding pawl', 'print', rotz(hp, m_ang, x, y), COL['esc'], 'esc_mpawl', 'PETG',
        'собачка удержания M в неподвижном храповом секторе', 'escM')
    def msector():
        from shapely.ops import unary_union
        s_ = sec(28.3, 31.0, TH_M - 3.0, TH_M + 17 * PITCH + 8.0, *Z_MH)
        notches = [Polygon([P2(28.0, TH_M + PITCH * k + 2.0), P2(29.0, TH_M + PITCH * k + 2.0), P2(28.3, TH_M + PITCH * k + 4.0),
                            P2(28.0, TH_M + PITCH * k + 4.0)]) for k in range(18)]
        s_ = s_ - extrude(unary_union(notches), Z_MH[0] - 1, Z_MH[1] + 1)
        c = P2(29.6, TH_M + 17 * PITCH + 5.0)      # a stem up to the top plate, past the holding pawl's range
        s_ = s_ + box(c[0] - 1.4, c[0] + 1.4, c[1] - 1.4, c[1] + 1.4, Z_MH[1] - 0.5, 98.0)
        return s_
    add('memory ratchet sector', 'print', cached('escMS', msector), (110, 112, 120), 'esc_msector', 'PETG',
        'неподвижный храповой сектор M (шаг 6°), подвешен к верхней плите')
    za = TH_M - 5.0 - math.degrees(math.asin(1.5 / 16.0))
    zs = P2(16.0, za)
    add('memory zero stop', 'buy', zcyl(zs[0], zs[1], Z_M[0], 98.0, 1.5, 24), COL['steel'], 'rod3x20', 'сталь',
        'упор нуля M: стальной штифт 3 мм в верхней плите')
    # ---- rockers, tail pins, links (machine frame)
    for key, n in (('bksp', 46), ('back', 47)):
        f = st.pressed.get(n, 0.0)
        pc = tail_pin_centre(key, f)
        xp = ROCK['xpin'][key]
        out.append(Part(f'{key} tail pin', 'levers', 'buy', cyl((xp, TAIL_PIN['y'][0], pc[1]), (xp, TAIL_PIN['y'][1][key], pc[1]), 1.2, 12).translate((0, pc[0] - 24.75, 0)),
                        COL['steel'], 'pin2x8', 'сталь', 'палец в торце хвоста рычага', mov=f'key{n}'))
        phi = rocker_phi(key, f)
        def rocker(key=key):
            xa, z = ROCK['xa'][key], ROCK['z']; xp = ROCK['xpin'][key]
            y0, y1 = ROCK['yin'][key]; ro = ROCK['r_out'][key]; up = ROCK['up'][key]
            s_ = 1.0 if xp > xa else -1.0
            rk = cyl((xa, y0, z), (xa, ROCK['yout'][1], z), 3.0, 16)
            L = abs(xp - xa); Lmax = math.hypot(L, 8.45) + 1.3
            a0, a1 = sorted((xa, xa + s_ * (Lmax + 0.3)))
            rk = rk + box(a0, a1, y0, y1, z - 2.5, z + 2.5)
            r0, r1 = sorted((xa + s_ * (L - 1.5), xa + s_ * Lmax))
            rk = rk - box(r0, r1, y0 - 1, y1 + 1, z - 1.2, z + 1.2)
            zo0, zo1 = (z, z + ro + 2.0) if up else (z - ro - 2.0, z)
            rk = rk + box(xa - 2.0, xa + 2.0, *ROCK['yout'], zo0, zo1)
            zb = z + ro if up else z - ro
            yb = ROCK['yball'][key]
            rk = rk + geo.Manifold.sphere(1.6, 24).translate((xa, yb, zb)) + cyl((xa, yb, zb), (xa, (ROCK['yout'][0] + ROCK['yout'][1]) / 2, zb), 0.9, 12)
            return rk - cyl((xa, y0 - 1, z), (xa, ROCK['yout'][1] + 1, z), 1.55, 12)
        rk = roty(cached(f'rock2_{key}', rocker), rocker_rot_deg(key, phi), ROCK['xa'][key], ROCK['z'])
        out.append(Part(f'{key} rocker', 'esc', 'print', rk, COL['esc'], f'rocker_{key}', 'PETG',
                        note=f'качалка {"забоя" if key == "bksp" else "«назад на литеру»"}: плечи {abs(ROCK["xpin"][key] - ROCK["xa"][key]):.0f} и {ROCK["r_out"][key]:.0f} мм',
                        mov=f'rock{key}'))
        A = rocker_ball(key, phi)
        Bp = stud_world(key, kb if key == 'bksp' else beta)
        u_ = (Bp - A) / np.linalg.norm(Bp - A)
        lk = cyl(tuple(A + u_ * 1.9), tuple(Bp - u_ * 1.9), 0.75, 8) + geo.Manifold.sphere(2.2, 24).translate(tuple(A)) + \
            geo.Manifold.sphere(2.2, 24).translate(tuple(Bp))
        lk = lk - geo.Manifold.sphere(1.66, 32).translate(tuple(A)) - geo.Manifold.sphere(1.66, 32).translate(tuple(Bp))
        lk = lk - zcyl(Bp[0], Bp[1], Bp[2], Bp[2] + 3.0, 1.5, 16)              # B's neck goes up
        ym = (ROCK['yout'][0] + ROCK['yout'][1]) / 2
        lk = lk - cyl(tuple(A), (A[0], ym, A[2]), 1.5, 16)                        # the rocker's neck goes along Y
        out.append(Part(f'{key} link', 'esc', 'buy', lk, COL['steel'], 'ball_link', 'сталь',
                        'тяга 1,5 мм с шаровыми наконечниками' + (' и пружиной' + ('' if key == 'back' else ', упорная втулка')), mov=f'rock{key}'))
    rb = box(110.0, 144.0, 33.3, 36.3, 0.0, 54.0) - box(108.0, 124.0, 32.0, 38.0, 38.0, 48.8)   # window for the backspace link
    for k_ in ('bksp', 'back'):
        rb = rb - cyl((ROCK['xa'][k_], 33.0, ROCK['z']), (ROCK['xa'][k_], 37.0, ROCK['z']), 1.55, 12)
        out.append(Part(f'{k_} rocker axle', 'esc', 'buy', cyl((ROCK['xa'][k_], ROCK['yin'][k_][0], ROCK['z']), (ROCK['xa'][k_], 36.3, ROCK['z']), 1.5, 12),
                        COL['steel'], 'rod3x12', 'сталь'))
    out.append(Part('rocker bracket', 'esc', 'print', rb, (110, 112, 120), 'rocker_bracket', 'PETG',
                    note='стенка качалок забоя и «назад на литеру» (оси вдоль Y)'))
    return out


def roty(m, deg, cx, cz):
    return m.translate((-cx, 0, -cz)).rotate((0, deg, 0)).translate((cx, 0, cz))


def tail_pin_centre(key, f):
    """(y, z) of the tail pin's axis for key travel f (the lever turns about its pivot)."""
    ky = P.KEY_ROW_Y[0] if key == 'bksp' else P.KEY_ROW_Y[1]
    a = math.atan2(P.KEY_TRAVEL * f, P.LEVER_PIVOT_Y - ky)
    zc = (P.LEVER_Z0 + P.LEVER_Z1) / 2
    ty, tz = 24.75, TAIL_PIN['z']
    return (P.LEVER_PIVOT_Y + (ty - P.LEVER_PIVOT_Y) * math.cos(a) - (tz - zc) * math.sin(a),
            zc + (ty - P.LEVER_PIVOT_Y) * math.sin(a) + (tz - zc) * math.cos(a))


def rocker_phi(key, f):
    """Rocker angle (rad, >= 0): the input arm's end rises with the pin."""
    pc = tail_pin_centre(key, f)
    return math.atan2(pc[1] - ROCK['z'], abs(ROCK['xpin'][key] - ROCK['xa'][key]))


def rocker_rot_deg(key, phi):
    """Rotation about +Y that lifts the input arm's end (toward the pin)."""
    return -math.degrees(phi) if ROCK['xpin'][key] > ROCK['xa'][key] else math.degrees(phi)


def rocker_ball(key, phi):
    ro = ROCK['r_out'][key]; xa, z = ROCK['xa'][key], ROCK['z']
    p = np.array([0.0, ro if ROCK['up'][key] else -ro])           # (x, z) of the ball relative to the axis
    a = math.radians(rocker_rot_deg(key, phi))
    x_ = p[0] * math.cos(a) + p[1] * math.sin(a); z_ = -p[0] * math.sin(a) + p[1] * math.cos(a)
    return np.array([xa + x_, ROCK['yball'][key], z + z_])


def stud_world(key, beta):
    r, a = STUD[key]
    c = P2(r, a - beta)
    return np.array([-c[0], c[1], STUD_Z[key]])


PV = None


def pawl_lift_angle():
    """Turn of B's pawl about its pin (deg) that lifts its tip 0.3 mm off the tooth tips (sign: outward)."""
    pv = np.array(P2(25.0, 13.0)); T = np.array(P2(19.4, TH_B + B_CATCH)); c = np.array(ESC)
    v = np.array([-(T - pv)[1], (T - pv)[0]])
    sgn = 1.0 if v @ (T - c) > 0 else -1.0
    lift = R_TIP + 0.3 - (R_ROOT + 0.35)          # the tip's underside over the tooth tips
    return sgn * math.degrees(lift / np.linalg.norm(T - pv))


def guard_face():
    """Centre of the guard pin (r 0.8) and the drop direction of the pawl's tail. The pin sits a little behind the tail
    (against B's CW turn), so B's first 0.6 deg lets the tail slip off it and the pawl drop in."""
    pv = np.array(P2(25.0, 13.0)); tl = np.array(P2(27.5, 21.0))
    a = math.radians(pawl_lift_angle())
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    t_up = pv + R @ (tl - pv)
    d = tl - t_up; d = d / np.linalg.norm(d)
    r_ = t_up - np.array(ESC); tcw = np.array([r_[1], -r_[0]]) / np.linalg.norm(r_)     # CW tangent at the tail
    v = d - 0.45 * tcw; v = v / np.linalg.norm(v)
    return t_up + v * (1.2 + 0.8 + 0.03), d


def geo_split(m):
    return m


def bksp_phi_stop():
    """Rocker angle at which B has turned 1.4 teeth (found from the link geometry)."""
    return _bksp_phi()[0]


_cache = {}


def _link_len(key):
    return float(np.linalg.norm(stud_world(key, 0.0) - rocker_ball(key, 0.0)))


def rocker_for_beta(key, beta):
    """Rocker angle that turns B by beta with a rigid link."""
    L = _link_len(key)
    B = stud_world(key, beta)
    lo, hi = 0.0, 1.5
    for _ in range(60):
        mid = (lo + hi) / 2
        A = rocker_ball(key, mid)
        if np.linalg.norm(B - A) < L:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _bksp_phi():
    if 'b' not in _cache:
        _cache['b'] = (rocker_for_beta('bksp', BKSP_DEG),)
    return _cache['b']


def stop_pad():
    """Where the backspace rocker's output arm (its back face) stands at the stop."""
    phi = bksp_phi_stop(); ro = ROCK['r_out']['bksp']
    y = ROCK['y'] - (ro + 2.0) * math.sin(phi) - 2.0 * math.cos(phi)
    z = ROCK['z'] - (ro + 2.0) * math.cos(phi) + 2.0 * math.sin(phi)
    return y, z


def summary():
    """Numbers for the document."""
    tail = P.KEY_TRAVEL * (24.75 - P.LEVER_PIVOT_Y) / (P.LEVER_PIVOT_Y - P.KEY_ROW_Y[1])
    phi_full = rocker_phi('back', 1.0)
    out = {}
    for key in ('bksp', 'back'):
        need = BKSP_DEG if key == 'bksp' else B_CATCH + 16 * PITCH + M_PLAY
        out[key] = dict(rock_need=math.degrees(rocker_for_beta(key, need)), rock_full=math.degrees(phi_full), beta_need=need,
                        link=_link_len(key))
    return dict(tail=tail, **out)
