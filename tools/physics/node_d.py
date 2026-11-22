"""Stage 2, node D (spec §5.2): the escapement and the carriage. The carriage (mass of group 'carriage' + the sheet, the
wheel's inertia reflected through the pinion z = 10, r = 5.053 mm) is pulled by its spring motor (force F: there is
no number in the project -- spring 'carriage drive spring' is 'missing'); the holding dog D is drawn out at 310 deg
(params.CYCLE feed), the wheel turns w teeth until a face meets U's finger (an elastic contact: stiffness of a printed
tooth, restitution e); then D drops in under its 0.3 N spring. Reduced 1-DOF model with events (solve_ivp).
Outputs: feed time for every width, the impact on U's finger (speed, force, energy), the rebound in teeth while D
falls, the smallest F that finishes the feed by 340 deg (10 deg before U is drawn out at 350), the margin stop and the
release. Validation (spec §5.5): the slow kinematic feed is exactly w units (escape.py, params.U).
Rev. 0.14: the feed starts at params.CYCLE['feed'][0] (200 deg, after the blow); D drops in at CYCLE['dog'] (325 deg),
when the carriage has settled on U's finger (the rebounds e^k decay under F), so a rebound can no longer put D into a
wrong tooth; the design force is params.CAR_SPRING_N (a constant-force spring), U's finger carries an elastomer pad
(e 0.2, stiffness 0.3e6 N/m nominal; without it a printed tooth is 1.5e6).
Usage: python3 -I tools/physics/node_d.py"""
FEED0 = None
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import units as U
import numpy as np
from scipy.integrate import solve_ivp
import params as P
import escape as E

MASS = {x['name']: x for x in json.load(open(os.path.join(U.GEN, 'mass.json')))['parts']}
PARTS = {p['name']: p for p in json.load(open(os.path.join(U.GEN, 'parts.json')))}
MJ = json.load(open(os.path.join(U.ROOT, 'gen', 'motor.json')))
R_P = 5.053e-3                        # pinion pitch radius (z = 10, m = 1.0106)
R_T = (E.R_ROOT + E.R_TIP) / 2 * U.MM   # where U's finger meets the face
UNIT = P.U * U.MM
DEG_T = {'free': 0.18 / 360, 'light': MJ['pick']['light'] / 360, 'avg': MJ['pick']['avg'] / 360, 'worst': MJ['pick']['worst'] / 360}
FEED0 = P.CYCLE['feed'][0]; DOG_AT = P.CYCLE['dog']
DOG_M = MASS['escapement dog']['m']; DOG_F = 0.3; DOG_TRAVEL = 2.5e-3      # teeth 2.5 mm deep
TOOTH_W = 5e-3                         # finger in one tier of the wheel (5 mm)


def masses(f_print=None, roller='solid'):
    """Carriage mass (kg) by its parts; f_print rescales printed parts; roller 'solid' (model) or 'tube' (hollow steel
    tube 14 x 1 with a 2 mm rubber skin)."""
    m = 0.0
    for n, p in PARTS.items():
        if p['group'] != 'carriage':
            continue
        mi = MASS[n]['m']
        if f_print is not None and p['kind'] == 'print':
            mi = mi / max(MASS[n]['f'], 1e-9) * f_print
        if n == 'feed roller' and roller == 'tube':
            L = 0.23; mi = 7850 * math.pi * (0.005 ** 2 - 0.004 ** 2) * L + 1200 * math.pi * (0.007 ** 2 - 0.005 ** 2) * L
        m += mi
    m += MASS['paper']['m']
    Iw = np.array(MASS['escapement wheel and pinion']['I'])[2, 2]
    return m, Iw / R_P ** 2


def feed(F, w, m, mw, mu=0.005, k=0.3e6, e=0.2, deg_t=DEG_T['avg'], drag=0.1, t_max=1.0, clock=None):
    """One feed of w units from rest. k: stiffness at the tooth (N/m); returns dict. Stage 2b: clock (shaft.Clock)
    turns the times into angles on the real law (the feed starts at clock.t(FEED0)); without it 1 / deg_t deg/s."""
    if clock is None:
        ang = lambda t_rel: FEED0 + t_rel / deg_t                  # angle at t_rel s after the start of the feed
        dog_done = lambda t_d: DOG_AT + t_d / deg_t
    else:
        t_f0 = clock.t(FEED0)
        ang = lambda t_rel: clock.phi(t_f0 + t_rel) if t_f0 + t_rel <= clock.T else 360.0 + (t_f0 + t_rel - clock.T) * math.degrees(clock.w(360.0))
        dog_done = lambda t_d: clock.phi(clock.t(DOG_AT) + t_d)
    M = m + mw
    d = w * UNIT
    m_t = M * (R_P / R_T) ** 2                      # reflected to the tooth radius
    k_x = k * (R_T / R_P) ** 2 * (R_P / R_T) ** 2   # the same spring seen at the rack: k (R_T/R_P)^-2 x (R_T/R_P)^2 = k
    # contact at the rack coordinate: force at the tooth Ft = k * delta_t, delta_t = delta_x * R_T / R_P
    kx = k * (R_T / R_P) ** 2
    ln = math.log(e); z = -ln / math.sqrt(math.pi ** 2 + ln ** 2); c = 2 * z * math.sqrt(kx * M)
    fr = mu * m * U.G + drag                         # bushings + dog and finger drag
    def rhs(t, y):
        x, v = y
        a = F - math.copysign(fr, v) if abs(v) > 1e-6 else max(0.0, F - fr)
        pen = x - d
        if pen > 0:
            a -= max(0.0, kx * pen + c * v)
        return [v, a / M]
    def hit(t, y): return y[0] - d
    hit.terminal = True; hit.direction = 1
    s = solve_ivp(rhs, (0, t_max), [0.0, 0.0], method='LSODA', events=hit, rtol=1e-9, atol=1e-12, max_step=1e-4)
    if not len(s.t_events[0]):
        return dict(ok=False)
    t1 = float(s.t_events[0][0]); v1 = float(s.y_events[0][0][1])
    def out_(t, y): return y[0] - d
    out_.terminal = True; out_.direction = -1
    tc = math.pi * math.sqrt(M / kx)
    s2 = solve_ivp(rhs, (t1, t1 + 40 * tc), [d + 1e-12, v1], method='Radau', events=out_, rtol=1e-9, atol=1e-14, max_step=tc / 100,
                   dense_output=True)
    t2 = float(s2.t_events[0][0]) if len(s2.t_events[0]) else float(s2.t[-1])
    tt = np.linspace(t1, t2, 300); Y = s2.sol(tt)
    pen = Y[0] - d; Fx = np.maximum(0, kx * pen + c * Y[1])
    Ft = Fx * R_P / R_T
    v2 = float(s2.y[1, -1])
    # rebound: free motion back against F until it stops (then F brings it in again)
    reb = (v2 ** 2) / (2 * (F + fr) / M) if v2 < 0 else 0.0
    t_dog = math.sqrt(2 * DOG_TRAVEL * DOG_M / max(DOG_F - 0.35 * 0.0, 1e-9))
    pen_max = float(pen.max())
    # rev. 0.14: the rebounds decay (each comes back with e of the last speed): settled after sum 2 e^k v / a
    acc = max((F - fr) / M, 1e-6)
    ee = abs(v2) / max(v1, 1e-9)
    t_settle = 2 * abs(v2) / acc / max(1 - ee, 1e-3) if v2 < 0 else 0.0
    end = ang(t2 + t_settle)
    return dict(ok=True, w=w, t_feed_ms=t1 * 1e3, v_hit=v1, E_hit_mJ=0.5 * M * v1 ** 2 * 1e3, F_tooth_N=float(Ft.max()),
                contact_ms=(t2 - t1) * 1e3, pen_tooth_um=pen_max * R_T / R_P * 1e6, rebound_mm=reb * 1e3, rebound_teeth=reb / UNIT,
                t_dog_ms=t_dog * 1e3, deg=ang(t1 + (t2 - t1)) - FEED0, settle_ms=t_settle * 1e3, end_deg=end,
                dog_done_deg=dog_done(t_dog), sigma_MPa=float(Ft.max()) / (TOOTH_W * 1e-3) / 1e6)


def feed_settle(F, w, m, mw, mu=0.005, k=0.3e6, e=0.2, drag=0.1, t_max=0.4, amp=0.1, vtol=5e-3):
    """Stage 2b: the whole feed integrated through every rebound until the carriage rests on U's finger: settled when
    |x - d| <= amp units and |v| <= vtol (m/s) from then on. The contact is the same Kelvin-Voigt layer as feed();
    friction is smoothed (tanh, 1 mm/s). Returns times (s from the start of the feed) and the rebounds."""
    M = m + mw
    d = w * UNIT
    kx = k * (R_T / R_P) ** 2
    ln = math.log(e); z = -ln / math.sqrt(math.pi ** 2 + ln ** 2); c = 2 * z * math.sqrt(kx * M)
    fr = mu * m * U.G + drag
    tc = math.pi * math.sqrt(M / kx)
    def rhs(t, y):
        x, v = y
        f = F - fr * math.tanh(v / 1e-3)
        pen = x - d
        if pen > 0:
            f -= max(0.0, kx * pen + c * v)
        return [v, f / M]
    s = solve_ivp(rhs, (0, t_max), [0.0, 0.0], method='LSODA', rtol=1e-8, atol=1e-12, max_step=tc / 30, dense_output=True)
    tt = np.linspace(0, t_max, int(t_max / (tc / 30)) + 1)
    X, V = s.sol(tt)
    ok = (np.abs(X - d) <= amp * UNIT) & (np.abs(V) <= vtol)
    bad = np.flatnonzero(~ok)
    if len(bad) and bad[-1] == len(tt) - 1:
        t_set = None
    else:
        t_set = float(tt[bad[-1] + 1]) if len(bad) else 0.0
    hit = np.flatnonzero(X >= d)
    t_hit = float(tt[hit[0]]) if len(hit) else None
    after = tt >= (t_hit or 0.0)
    back = np.maximum(0.0, d - X[after])
    return dict(t_hit=t_hit, t_settled=t_set, rebound_max_teeth=float(back.max() / UNIT) if after.any() else 0.0,
                x=X, v=V, t=tt, d=d)


def rebound_at(fs, t_rel):
    """How far (teeth) the carriage is off U's finger at time t_rel (s from the start of the feed) and the largest
    rebound after it."""
    tt, X, d = fs['t'], fs['x'], fs['d']
    i = int(np.searchsorted(tt, t_rel))
    if i >= len(tt):
        return 0.0, 0.0
    return float(max(0.0, d - X[i]) / UNIT), float(np.maximum(0.0, d - X[i:]).max() / UNIT)


def f_min(w, m, mw, deg_t, end=None, **kw):
    end = DOG_AT - 5.0 if end is None else end
    lo, hi = 0.05, 200.0
    for _ in range(50):
        mid = math.sqrt(lo * hi)
        r = feed(mid, w, m, mw, deg_t=deg_t, **kw)
        if r['ok'] and r['end_deg'] <= end:
            hi = mid
        else:
            lo = mid
    return hi


def main():
    res = {}
    m, mw = masses()
    res['mass'] = dict(carriage_kg=m, wheel_reflected_kg=mw, total=m + mw,
                       parts={n: MASS[n]['m'] for n, p in PARTS.items() if p['group'] == 'carriage'},
                       hollow_roller_kg=masses(roller='tube')[0], f035_kg=masses(0.35)[0], f1_kg=masses(1.0)[0])
    # validation: the slow kinematic feed = w units, teeth of 6 deg (escape.py) and the rack's pitch
    res['validation'] = dict(unit_mm=P.U, rack_per_tooth_mm=2 * math.pi * R_P / E.TEETH * 1e3, deg_per_unit=E.PITCH,
                             err_um=(2 * math.pi * R_P / E.TEETH - UNIT) * 1e6)
    # smallest spring force by width and speed of the cycle
    tab = []
    for w in (4, 8, 12, 16, 17):
        row = dict(w=w)
        for sp in ('worst', 'avg', 'light', 'free'):
            row[f'Fmin_{sp}'] = round(f_min(w, m, mw, DEG_T[sp]), 2)
        tab.append(row)
    res['f_min'] = tab
    Freq = max(r['Fmin_light'] for r in tab)
    res['F_required_light'] = Freq
    res['F_required_avg'] = max(r['Fmin_avg'] for r in tab)
    # behaviour at the required force (light cycle) for every width, nominal contact
    rows = []
    for w in range(4, 18):
        r = feed(Freq, w, m, mw, deg_t=DEG_T['light'])
        rows.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    res['at_required'] = rows
    # sensitivity at the required force, w = 17
    sl = {}
    for key, vals in dict(mu=(0.002, 0.005, 0.01), k=(0.15e6, 0.3e6, 0.6e6, 1.5e6, 5e6), e=(0.1, 0.2, 0.5, 0.7), drag=(0.05, 0.1, 0.3)).items():
        sl[key] = []
        for v in vals:
            r = feed(Freq, 17, m, mw, deg_t=DEG_T['light'], **{key: v})
            sl[key].append(dict(value=v, end_deg=round(r['end_deg'], 1), F_tooth=round(r['F_tooth_N'], 1), rebound_teeth=round(r['rebound_teeth'], 3)))
    sl['mass'] = []
    for lab, (mm, mmw) in (('f 0.35', masses(0.35)), ('f 1', masses(1.0)), ('полый валик', masses(roller='tube'))):
        r = feed(Freq, 17, mm, mmw, deg_t=DEG_T['light'])
        sl['mass'].append(dict(value=lab, m=round(mm, 3), end_deg=round(r['end_deg'], 1), F_tooth=round(r['F_tooth_N'], 1)))
    res['slices'] = sl
    # Latin hypercube at the required force
    rng = np.random.default_rng(2); lh = []
    for _ in range(200):
        u = rng.random(6)
        mu = 0.002 + 0.008 * u[0]; k = 10 ** (math.log10(0.15e6) + u[1] * math.log10(4)); e = 0.1 + 0.25 * u[2]; dr = 0.05 + 0.25 * u[3]   # pad: e <= 0.35
        mm, mmw = masses(0.35 + 0.65 * u[4]); w = 4 + int(u[5] * 14)
        dd = DEG_T['light'] + (DEG_T['worst'] - DEG_T['light']) * rng.random()
        r = feed(P.CAR_SPRING_N, w, mm, mmw, mu=mu, k=k, e=e, drag=dr, deg_t=dd)
        lh.append(dict(w=w, mu=mu, k=k, e=e, drag=dr, m=mm, end_deg=r['end_deg'], rebound_teeth=r['rebound_teeth'], F_tooth=r['F_tooth_N']))
    res['lhs'] = dict(n=200, F=P.CAR_SPRING_N, late=sum(x['end_deg'] > DOG_AT for x in lh),
                      F_tooth_max=max(x['F_tooth'] for x in lh), end_max=max(x['end_deg'] for x in lh),
                      rebound_teeth_max=max(x['rebound_teeth'] for x in lh),
                      note='отскок гаснет до 325°, когда опускается собачка Д: зуб не пропускается')
    # with a lighter carriage (hollow roller) and with a feed window that starts at 200 deg (after the blow)
    mh, mwh = masses(roller='tube')
    res['options'] = dict(
        hollow_roller=dict(m=mh, F_light=max(f_min(w, mh, mwh, DEG_T['light']) for w in (4, 17)),
                           E_hit_mJ=feed(max(f_min(w, mh, mwh, DEG_T['light']) for w in (4, 17)), 17, mh, mwh, deg_t=DEG_T['light'])['E_hit_mJ']),
        design=dict(F=P.CAR_SPRING_N, rows=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in
                                             feed(P.CAR_SPRING_N, w, m, mw, deg_t=DEG_T[sp]).items()} | dict(speed=sp)
                                            for w in (4, 12, 17) for sp in ('light', 'avg', 'worst')]))
    # the margin stop at the end of the line: the carriage meets the abutment after its last feed (same energy as a feed
    # of w units into a stop instead of U's finger) -- the energy and the force on the stop
    r = feed(Freq, 17, m, mw, deg_t=DEG_T['light'], k=3e6)
    res['margin_stop'] = dict(E_mJ=r['E_hit_mJ'], F_N=r['F_tooth_N'] * R_T / R_P)
    # release: the carriage pushed by hand and let go between teeth: D (0.3 N) drops in while the carriage moves under F;
    # it catches when the wheel turns less than one tooth while D falls 2.5 mm
    t_dog = math.sqrt(2 * DOG_TRAVEL * DOG_M / DOG_F)
    s_dog = 0.5 * Freq / (m + mw) * t_dog ** 2
    res['release'] = dict(t_dog_ms=t_dog * 1e3, carriage_moves_mm=s_dog * 1e3, teeth=s_dog / UNIT,
                          whole_tooth=s_dog / UNIT < 1.0)
    # the carriage spring's work per line (hand return) and per character
    res['energy'] = dict(per_unit_mJ=Freq * UNIT * 1e3, per_line_J=Freq * P.LINE_LEN * U.MM, hand_force_N=Freq)
    json.dump(res, open(os.path.join(U.GEN, 'node_d.json'), 'w'), ensure_ascii=False, indent=1, default=float)
    plot(res, m, mw)
    print('mass', res['mass']['total'], 'validation', res['validation'])
    print('Fmin', tab)
    print('at required (light):', [(r['w'], round(r['t_feed_ms'], 1), round(r['end_deg'], 1), round(r['F_tooth_N'], 0), round(r['E_hit_mJ'], 1), round(r['rebound_teeth'], 2)) for r in rows])
    print('lhs', res['lhs']); print('options', res['options']); print('release', res['release']); print('energy', res['energy'])


def plot(res, m, mw):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    w = [r['w'] for r in res['f_min']]
    for sp, col in (('worst', '#7a7a7a'), ('avg', '#2a6f97'), ('light', '#c44536'), ('free', '#e0a030')):
        ax[0].plot(w, [r[f'Fmin_{sp}'] for r in res['f_min']], 'o-', color=col, label=sp)
    ax[0].set_xlabel('ширина литеры w, u'); ax[0].set_ylabel('наименьшая сила пружины каретки, Н'); ax[0].legend(fontsize=8)
    ax[0].set_title('Подача и успокоение до опускания Д (325°)')
    rows = res['at_required']
    ax[1].plot([r['w'] for r in rows], [r['F_tooth_N'] for r in rows], 's-', color='#c44536', label='сила на зуб, Н')
    ax2 = ax[1].twinx(); ax2.plot([r['w'] for r in rows], [r['E_hit_mJ'] for r in rows], 'o--', color='#2a6f97', label='энергия, мДж')
    ax[1].set_xlabel('w, u'); ax[1].set_ylabel('сила на палец U, Н'); ax2.set_ylabel('энергия удара, мДж')
    ax[1].set_title(f"Удар о палец U при F = {res['F_required_light']:.1f} Н")
    fig.tight_layout(); fig.savefig(os.path.join(U.GEN, 'node_d_feed.png'), dpi=130); plt.close(fig)


if __name__ == '__main__':
    main()
