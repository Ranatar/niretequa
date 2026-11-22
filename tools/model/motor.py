"""Spring motor and cycle dynamics for rev. 0.6, from the layout model.
Usage: python3 -I motor.py OUT_JSON"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import trimesh
import params as P
import parts as PT
import data as D
import geo

DENS = 1.27e-3          # g/mm3 PETG
FILL = 0.5              # large printed parts
ps = {p.name: p for p in PT.build(PT.State())}


def mass_inertia(m, dens, axis=(0.0, P.AXIS_Y)):
    V, F = geo.to_arrays(m)
    tm = trimesh.Trimesh(V, F, process=False)
    tm.density = dens / 1000.0
    c = tm.center_mass; I = tm.moment_inertia
    d2 = (c[0] - axis[0]) ** 2 + (c[1] - axis[1]) ** 2
    return tm.mass * 1000, I[2, 2] + tm.mass * d2      # g, kg*mm2


rot = {}; lift = {}
m, I = mass_inertia(ps['shuttle'].mesh, DENS * FILL); rot['кольцо челнока'] = I; lift['кольцо челнока'] = m
mb = Ib = 0.0
for k in range(P.NPOS):
    m, I = mass_inertia(ps[f'type block {k}'].mesh, DENS); mb += m; Ib += I
rot['11 литерных блоков'] = Ib; lift['11 литерных блоков'] = mb
m, I = mass_inertia(ps['pulley and detent wheel'].mesh, DENS * FILL); rot['шкив и колесо фиксатора'] = I
rot['поводок'] = 7.85e-3 * math.pi * 9 * 110 * 1e-3 * P.GUIDE_R ** 2
rot['втулка поводка'] = 6.0 * 1e-3 * P.GUIDE_R ** 2; lift['втулка и вилка'] = 21.0
rot['каретка ленты (приведённая)'] = 12.0 * 1e-3 * P.PULLEY_R ** 2
# rev. 0.10: the code combs and their pins ride the shuttle (solid PETG); the rod now stands behind the shaft (same radius)
mc = Ic = 0.0
for k in range(P.NPOS):
    m_, I_ = mass_inertia(ps[f'code comb {k}'].mesh, DENS); mc += m_; Ic += I_
rot['11 кодовых гребёнок'] = Ic; lift['11 кодовых гребёнок'] = mc + 22 * 0.12
I_rot = sum(rot.values()) * 1e-6                     # kg m2
m_lift = sum(lift.values()) * 1e-3                   # kg

# ---------------------------------------------------------------- cycle dynamics
C = P.CYCLE
ETA = 0.8              # cams with rollers and links, per transfer
E_HAMMER = 0.020       # J, hammer spring cocked by the cycle from 0 deg to just before the strike
TAU_FRIC = 0.0012      # N m at the cycle shaft: bearings, latches, detent, escapement trip
def _Ix(name, y0, z0, dens=DENS):
    V, F = geo.to_arrays(ps[name].mesh)
    tm = trimesh.Trimesh(V, F, process=False); tm.density = dens / 1000.0
    c = tm.center_mass
    return (tm.moment_inertia[0, 0] + tm.mass * ((c[1] - y0) ** 2 + (c[2] - z0) ** 2)) * 1e-6   # kg m2


# rev. 0.14 (physics checks, node E): J0 from the meshes -- the cycle shaft with its cams, gears and stop arm, and the
# governor through its 32/8 pair (x 16); rev. <= 0.13 took 4e-5 kg m2, eight times too much, and so a cycle too slow
_yC, _zC = PT.CYC
_yD = _yC + (PT.ZG['gov'] + PT.ZG['govpin']) / 2
J0 = sum(_Ix(n, _yC, _zC, 7.85e-3 if ps[n].mat == 'сталь' else DENS) for n in
         ('cycle shaft', 'cam lift', 'cam rotate', 'cam detent', 'cam hammer', 'cam ribbon', 'cam read', 'cycle stop arm',
          'cam rotate return', 'cam lift return',
          'governor gear', 'bevel cycle 1:1') if n in ps) + \
    16 * sum(_Ix(n, _yD, _zC, 7.85e-3 if ps[n].mat == 'сталь' else 8.5e-3 if ps[n].mat == 'латунь' else DENS) for n in
             ('governor fan', 'governor arbor', 'governor pinion', 'governor flywheel', 'governor sliding collar', 'governor fixed collar',
              'governor weight 1', 'governor weight 2', 'governor weight 3', 'governor leaf spring 1', 'governor leaf spring 2',
              'governor leaf spring 3') if n in ps)          # rev. 0.14 stage 2b: + the brake's collars, springs and weights


def cyc(t):
    t = min(max(t, 0.0), 1.0); return t - math.sin(2 * math.pi * t) / (2 * math.pi)


def dcyc(t):
    if t <= 0 or t >= 1: return 0.0
    return 1 - math.cos(2 * math.pi * t)


def shape(phi_deg):
    """Normalised shuttle travel s(phi) and ds/dphi (per rad)."""
    a0, a1 = C['out']; b0, b1 = C['back']
    if a0 <= phi_deg < a1:
        t = (phi_deg - a0) / (a1 - a0); return cyc(t), dcyc(t) / math.radians(a1 - a0)
    if a1 <= phi_deg < b0: return 1.0, 0.0
    if b0 <= phi_deg < b1:
        t = (phi_deg - b0) / (b1 - b0); return 1 - cyc(t), -dcyc(t) / math.radians(b1 - b0)
    return 0.0, 0.0


def read_work(item):
    """rev. 0.10: (returned, taken) work of the read cam on one character, J. Going out (118..140 deg) the feeler springs
    push the bar and give the shaft what they do not spend on their loads (escapement spring, slide springs, wire
    friction); coming back (150..197 deg) the cam pulls them in against the full springs. Roller and lever losses
    (1 - ETA) on both strokes. Dead marks and spaces do not read."""
    import reader as RD
    v = RD.code_v(item) if item not in (None, 'SP') else None
    if v is None:
        return 0.0, 0.0
    back = take = 0.0
    for ch, vv in zip(P.READ_CH, v):
        t = (P.READ_C0 + P.READ_K * vv) * 1e-3
        back += (P.READ_F_SPRING[ch] - P.READ_F_LOAD[ch]) * t * ETA
        take += P.READ_F_SPRING[ch] * t / ETA
    return back, take


def e_read(item):
    b, t = read_work(item)
    return t - b


READ_OUT = (P.CYCLE['read'][0] - P.READ_RAMP[0], P.CYCLE['read'][0])
READ_WIN = (P.CYCLE['read'][1], P.CYCLE['read'][1] + P.READ_RAMP[1])


W_FREE = 2 * math.pi / 0.18          # the fan was sized for an unloaded cycle of 0.18 s at 18.5 mN m (rev. 0.14)
TAU_FAN = 0.0185                     # rev. 0.14 stage 2b: the fan as built: its coefficient does not follow tau_C
C_FAN = (TAU_FAN - TAU_FRIC) / W_FREE ** 2
# rev. 0.14, stage 2b: the fan's drag goes with w^2, so the shaft's speed went with sqrt(torque) -- twice the design speed at
# full wind. A centrifugal brake on the governor's arbor grips above W_CAP (params.GOV_T_FREE per free turn).
W_CAP = 2 * math.pi / P.GOV_T_FREE
K_BRAKE = P.GOV_K_BRAKE


def gov_drag(w, c_gov=None, cap=True):
    c = C_FAN if c_gov is None else c_gov
    x = c * w * w
    if cap and w > W_CAP:
        x += K_BRAKE * (w - W_CAP)
    return x


def simulate(tau, c_gov, th, dz, dphi=0.25, er=(0.0, 0.0), cap=True):
    """Integrate one revolution from rest; returns time, min/max speed. th rad, dz m; er: read work (returned, taken), J;
    both follow the cycloidal cam (torque ~ 1 - cos). Rev. 0.14 stage 2b: the governor's brake above W_CAP (cap)."""
    Jsh = I_rot * th ** 2 + m_lift * dz ** 2          # x (ds/dphi)^2 gives reflected inertia
    E = 0.0; t = 0.0; phi = 0.0; wmax = 0.0; wmin = 1e9
    s_prev, d_prev = shape(0.0)
    J_prev = J0 + Jsh * d_prev ** 2
    hammer_t = math.radians(C['strike'] - 10.0)
    while phi < 360.0:
        phi1 = phi + dphi
        s1, d1 = shape(phi1)
        J1 = J0 + Jsh * d1 ** 2
        w_prev = math.sqrt(2 * E / J_prev) if E > 0 else 0.0
        drive = tau - gov_drag(w_prev, c_gov, cap) - TAU_FRIC
        if 0.0 <= phi < C['strike'] - 10.0:
            drive -= E_HAMMER / hammer_t
        if er[0] and READ_OUT[0] <= phi < READ_OUT[1]:
            u = (phi - READ_OUT[0]) / (READ_OUT[1] - READ_OUT[0])
            drive += er[0] / math.radians(READ_OUT[1] - READ_OUT[0]) * (1 - math.cos(2 * math.pi * u))
        if er[1] and READ_WIN[0] <= phi < READ_WIN[1]:
            u = (phi - READ_WIN[0]) / (READ_WIN[1] - READ_WIN[0])
            drive -= er[1] / math.radians(READ_WIN[1] - READ_WIN[0]) * (1 - math.cos(2 * math.pi * u))
        dE = drive * math.radians(dphi)
        # shuttle kinetic energy change at constant speed: transfers lose (1 - ETA)
        dKsh = 0.5 * Jsh * (d1 ** 2 - d_prev ** 2) * w_prev ** 2
        dE -= (1 - ETA) * abs(dKsh)
        E = max(E + dE, 1e-12)
        w1 = math.sqrt(2 * E / J1)
        wm = 0.5 * (w_prev + w1)
        t += math.radians(dphi) / max(wm, 1e-3)
        if phi > 20:
            wmax = max(wmax, w1); wmin = min(wmin, w1)
        phi, d_prev, J_prev = phi1, d1, J1
        if t > 5: break
    return t, wmin, wmax


L = D.shuttle_layout()
# rev. 0.8: keystroke frequencies (tools/model/freq.py) weight the mean cycle; the shuttle starts from its rest row
_FJ = json.load(open(os.path.join(D.ROOT, 'gen', 'freq.json')))
FQ = _FJ['items']
# rev. 0.11: frequencies from running text (two books), and the spaces with them: a space runs an idle cycle (no
# selection bits r1 + r4 since 0.11: the shuttle only drops to row 1 of the middle position; no reading, no blow), 30 % of all cycles
FQ_SP = _FJ.get('spaces', 0)
SPACE_POS = PT.SPACE_POS           # rev. 0.11: the spaces' pushers set r1 + r4
def weight(item):
    if item == 'SP':
        return FQ_SP
    return FQ.get(repr(item), 0) + 0.2          # every character counts a little, even if the text never typed it
def build_chars(rest_row, row_of):
    out = []
    for r in range(P.NROWS):
        for c in range(P.NPOS):
            if L[r][c] is None:
                continue
            out.append(((c - (P.NPOS - 1) / 2) * P.STEP, (row_of(r) - rest_row) * P.RH * 1e-3, L[r][c]))
    if FQ_SP:
        out.append(((SPACE_POS - (P.NPOS - 1) / 2) * P.STEP, (row_of(0) - rest_row) * P.RH * 1e-3, 'SP'))
    return out
chars = build_chars(P.REST_ROW, lambda r: r)
th_max = (P.NPOS - 1) / 2 * P.STEP
z_max = max(abs(dz) for _, dz, _ in chars)


def run(tau, chs=None):
    chs = chs or chars
    cg = C_FAN                                   # rev. 0.14 stage 2b: the fan as built, whatever the torque
    times = [simulate(tau, cg, abs(th), abs(dz), er=read_work(it))[0] for th, dz, it in chs]
    w = np.array([weight(it) for _, _, it in chs])
    worst = max(times)
    light = simulate(tau, cg, 0.0, 0.0)[0]
    return float(np.sum(w * times) / w.sum()), worst, light, cg


taus = np.linspace(0.004, 0.05, 93)
table = []
for tau in taus:
    avg, worst, light, cg = run(tau)
    table.append(dict(tau=tau, E=2 * math.pi * tau, avg=avg, worst=worst, light=light))
# choose: mean cycle 0.33 s
target = P.CYCLE_T
WORST_K = 2.0          # rev. 0.8: the rarest, farthest characters may take up to twice the mean cycle
ok = [r for r in table if r['avg'] <= target and r['worst'] <= WORST_K * target]
pick_old = min(ok, key=lambda r: r['tau'])
# rev. 0.14, stage 2b of the physics checks: the torque at the end of the wind is no longer picked by the mean cycle of
# this simplified model -- on the shaft's real law (every load at once, the start from the latch) the shaft stops on
# the cocking below params.TAU_END (tools/physics/stage2b.py, the least torque that turns every character, + 5 %)
_a, _w, _l, _cg = run(P.TAU_END)
pick = dict(tau=P.TAU_END, E=2 * math.pi * P.TAU_END, avg=_a, worst=_w, light=_l)


def pick_for(chs):
    for tau in taus:
        avg, worst, light, cg = run(tau, chs)
        if avg <= target and worst <= WORST_K * target:
            return dict(tau=float(tau), E=2 * math.pi * float(tau), avg=avg, worst=worst, light=light)


# what the visible line costs: the same machine with the rev. 0.7 rest (rows 4-5 at the line, keyboard rows in order)
code_old = {r + 4 * t: r + 4 * t for r in range(4) for t in (0, 1)}
inv_new = {}
for r_kb, code in P.ROW_CODE.items():
    for t in (0, 1):
        inv_new[code + 4 * t] = r_kb + 4 * t        # shuttle row now -> the row it had in rev. 0.7
compare = {
    'rev07': pick_for(build_chars(P.HOME_ROW, lambda r: inv_new[r])),
    'order_only': pick_for(build_chars(P.HOME_ROW, lambda r: r)),
    'rev08': pick_for(chars),
}
tau_C = pick['tau']; E_char = 2 * math.pi * tau_C

# ---------------------------------------------------------------- motor
ratio = PT.train_ratio()
ETA_TRAIN = 0.93 ** 4
M_need = tau_C * ratio / ETA_TRAIN
tau_barrel = tau_C * ratio / ETA_TRAIN
Rb = PT.BARREL['r'] - 2.5; Ra = 9.0; tsp = 0.8; bsp = PT.BARREL['x1'] - PT.BARREL['x0'] - 6.0
Lsp = math.pi * (Rb ** 2 - Ra ** 2) / 2 / tsp
rw = math.sqrt(Lsp * tsp / math.pi + Ra ** 2); ru = math.sqrt(Rb ** 2 - Lsp * tsp / math.pi)
N_turns = (rw - Ra) / tsp - (Rb - ru) / tsp
SIG = 1500.0; E_ST = 206000.0
U_theory = (SIG ** 2 / (6 * E_ST)) * Lsp * bsp * tsp * 1e-3
U_use = 0.5 * U_theory
M_max = SIG * bsp * tsp ** 2 / 6 / 1000.0
M_avg = U_use / (2 * math.pi * N_turns)
chars_energy = U_use * ETA_TRAIN / E_char
chars_turns = N_turns * ratio
# rev. 0.14 stage 2b: with the brake every character takes one turn of the shaft whatever the spring's torque, so the
# characters per wind are the barrel's turns above M_need times the ratio; the spring's torque taken linear over its
# turns from M_max (fully wound) to nothing (an assumption: the curve of a spiral spring in its barrel is to be measured)
turns_usable = N_turns * max(0.0, 1.0 - M_need / M_max)
chars_usable = turns_usable * ratio
M_need_old = TAU_FAN * ratio / ETA_TRAIN           # rev. 0.14 before stage 2b: 18.5 mN m at the shaft
chars_usable_old = N_turns * (1.0 - M_need_old / M_max) * ratio
WIND = 3.0                                  # crank gear reduction
crank_turns = N_turns * WIND
crank_force = M_max / WIND / 0.085          # N at the 85 mm handle

_w = np.array([weight(it) for _, _, it in chars])
E_read_avg = float(np.sum(_w * np.array([e_read(it) for _, _, it in chars])) / _w.sum())
E_read_max = max(e_read(it) for _, _, it in chars)
res = dict(rot={k: round(v, 1) for k, v in rot.items()}, lift={k: round(v, 1) for k, v in lift.items()},
           E_read_avg=E_read_avg, E_read_max=E_read_max,
           I_rot=I_rot * 1e6, m_lift=m_lift * 1000,
           table=[{k: float(v) for k, v in r.items()} for r in table], pick={k: float(v) for k, v in pick.items()},
           tau_C=tau_C, E_char=E_char, ratio=ratio, tau_barrel=tau_barrel, eta=ETA, E_hammer=E_HAMMER,
           spring=dict(Rb=Rb, Ra=Ra, L=Lsp, b=bsp, t=tsp, turns=N_turns, U_theory=U_theory, U_use=U_use, M_max=M_max, M_avg=M_avg),
           chars_energy=chars_energy, M_need=M_need, chars_turns=chars_turns, crank_turns=crank_turns, crank_force=crank_force,
           I_old=2174.0, cps_avg=1 / pick['avg'], cps_worst=1 / pick['worst'], cps_light=1 / pick['light'],
           compare=compare, worst_k=WORST_K, J0=J0, pick_old={k: float(v) for k, v in pick_old.items()},
           turns_usable=turns_usable, chars_usable=chars_usable, chars_usable_old=chars_usable_old, M_need_old=M_need_old,
           C_FAN=C_FAN, W_CAP=W_CAP, K_BRAKE=K_BRAKE, gov_T_free=P.GOV_T_FREE)
json.dump(res, open(sys.argv[1], 'w'), indent=1, ensure_ascii=False)
for k, v in res.items():
    if k != 'table':
        print(k, v)
for r in table[::6]:
    print({k: round(v, 3) for k, v in r.items()})
