"""Stage 2, node C (spec §5.2): the hammer. Rev. 0.14: the spring sits between the cocking lever and the hammer;
the sear lets go at 160 deg, the hammer flies alone, stays on the sheet until the returning lever's lip lifts it
(175..200 deg) and follows the lip home. The text below is rev. 0.13's.
 One rotational degree of freedom about the hammer axle (axis X through
params.HAMMER_PIVOT), integrated with events (solve_ivp, Radau):
  throw  -- the torsion spring (links.json hammer: k_t, mean torque over 18 deg, half of it preload) drives the hammer
            from its rest angle (-18 deg) until its arm meets the spring's stop FREE mm before the sheet;
  flight -- free, gravity and axle friction only;
  blow   -- the face on the sheet + ribbon + type: a Kelvin-Voigt layer, stiffness from the contact time t_c and the
            damping from the restitution e;
  after  -- rebound and free motion; the rest stop at -18 deg is a second layer with restitution e_back.
The cycle angle runs at a constant speed (node B gives the real speed): the release is at 160 deg, the deadline for the
hammer to be back at 200 deg ('back' of params.CYCLE).
Validation (spec §5.5): with links.py's own assumptions (constant torque, no gravity, no friction, I from links.json)
the impact speed and flight time must agree within 3 %. MuJoCo cross-checks the blow (speed in -> speed out, duration).
Usage: python3 -I tools/physics/node_c.py"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import units as U
import numpy as np
from scipy.integrate import solve_ivp
import params as P

LJ = json.load(open(os.path.join(U.ROOT, 'gen', 'links.json')))['hammer']
MJ = json.load(open(os.path.join(U.ROOT, 'gen', 'motor.json')))
MASS = {x['name']: x for x in json.load(open(os.path.join(U.GEN, 'mass.json')))['parts']}
YP, ZP_ = P.HAMMER_PIVOT
SWING = math.radians(LJ['swing_deg'])
R_HEAD = LJ['r_head_mm'] * U.MM
R_AXLE = 2.0e-3                     # 4 mm axle
T0_ = LJ['T0_Nmm'] * 1e-3            # rev. 0.14: spring preload (hammer's tab on the lever's lip)
K_T = LJ['k_t_Nmm_per_deg'] * 1e-3 * 180 / math.pi       # N m / rad
LEVER = math.radians(LJ['lever_deg'])
DEG_T = {'avg': MJ['pick']['avg'] / 360.0, 'light': MJ['pick']['light'] / 360.0, 'worst': MJ['pick']['worst'] / 360.0}


def hammer_props(f=1.0):
    h = MASS['hammer']
    m = h['m'] * f
    c = np.array(h['c'])                     # at rest (retracted 18 deg)
    d2 = (c[1] - YP * U.MM) ** 2 + (c[2] - ZP_ * U.MM) ** 2
    I = (np.array(h['I'])[0, 0] * f + m * d2) + 2e-7          # + rubber pad and spring end (as links.py)
    rc = c[1:] - np.array([YP, ZP_]) * U.MM                    # (y, z) of the centre from the pivot, at rest
    return m, I, rc


def gravity_torque(theta, m, rc, g=(0, 0, -U.G)):
    """Torque about +X of the weight; theta from rest (positive toward the sheet: rotx +)."""
    c, s = math.cos(theta), math.sin(theta)
    y = rc[0] * c - rc[1] * s; z = rc[0] * s + rc[1] * c
    return y * m * g[2] - z * m * g[1]


def lever_rad(a):
    """rev. 0.14: the cocking lever's angle (rad, from the hammer's home) at cycle angle a (its lip: hammer <= lever)."""
    import parts as PT
    return math.radians(PT.ham_lever_deg(PT.cam_lift('cock', a)))


_LT = None


def lever_tab():
    global _LT
    if _LT is None:
        aa = np.arange(150.0, 361.0, 0.05)
        _LT = (aa, np.array([lever_rad(a) for a in aa]))
    return _LT


def lever_at(a):
    aa, L = lever_tab()
    return float(np.interp(a, aa, L))


def simulate(I, m=0.0, rc=(0.0, 0.0), grav=True, mu=0.0, t_c=0.3e-3, e=0.3, e_lip=0.3, deg_t=None, a_end=340.0,
             rtol=1e-8, T0=T0_, K=K_T, release=None, clock=None):
    """rev. 0.14: the hammer between the sheet (theta = SWING) and the cocking lever's lip (theta <= L(t)); the spring
    between them gives T0 + K (L - theta) toward the sheet. Released by the sear at `release` deg from theta = 0.
    Stage 2b: clock (shaft.Clock) gives the shaft's real law; without it the shaft turns at 1 / deg_t deg/s."""
    meff = I / R_HEAD ** 2
    def layer(e_):
        k = meff * (math.pi / t_c) ** 2
        ln = math.log(max(e_, 1e-6)); z = -ln / math.sqrt(math.pi ** 2 + ln ** 2)
        return k, 2 * z * math.sqrt(k * meff)
    k_s, c_s = layer(e)
    k_l, c_l = layer(e_lip)
    release = P.CYCLE['strike'] if release is None else release
    deg_t = deg_t or DEG_T['avg']
    if clock is None:
        t_end = (a_end - release) * deg_t
        aa = lambda t: release + t / deg_t
        dps = lambda a: 1.0 / deg_t                         # deg per s of the shaft
    else:
        t_rel = clock.t(release)
        t_end = clock.t(a_end) - t_rel
        aa = lambda t: clock.phi(t_rel + t)
        dps = lambda a: math.degrees(clock.w(a))
    def rhs(t, y):
        th, w = y
        a = aa(t)
        L = lever_at(a)
        dL = (lever_at(a + 0.05) - lever_at(a - 0.05)) / 0.1 * dps(a)
        T = T0 + K * (L - th)
        if grav:
            T += gravity_torque(th, m, rc)
        pen = R_HEAD * (th - SWING)
        if pen > 0:
            T -= R_HEAD * max(0.0, k_s * pen + c_s * R_HEAD * w)
        pl = R_HEAD * (th - L)                                   # the hammer's tab into the lever's lip
        if pl > 0:
            T -= R_HEAD * max(0.0, k_l * pl + c_l * R_HEAD * (w - dL))
        if mu:
            N = m * math.hypot(w * w * math.hypot(*rc), U.G)
            T -= mu * N * R_AXLE * math.tanh(w / 0.05)
        return [w, T / I]
    sol = solve_ivp(rhs, (0, t_end), [0.0, 0.0], method='LSODA', rtol=rtol, atol=1e-12, max_step=t_c / 20, dense_output=False)
    t = sol.t; th = sol.y[0]; w = sol.y[1]
    a = aa(t)
    L = np.array([lever_at(x) for x in a])
    on = th > SWING
    lip = th > L
    out = dict(contacts=[], lip=[])
    # sheet contacts: runs of `on`
    def runs(mask):
        idx = np.flatnonzero(np.diff(mask.astype(int)) != 0) + 1
        st_ = [0] + list(idx) if mask[0] else list(idx[0::1])
        res = []
        k = 0
        edges = list(idx)
        if mask[0]:
            edges = [0] + edges
        for i0, i1 in zip(edges[0::2], edges[1::2] + ([len(mask) - 1] if len(edges) % 2 else [])):
            res.append((i0, i1))
        return res
    for i0, i1 in runs(on):
        pen = R_HEAD * (th[i0:i1 + 1] - SWING)
        F = np.maximum(0, k_s * pen + c_s * R_HEAD * w[i0:i1 + 1])
        out['contacts'].append(dict(t_ms=round(t[i0] * 1e3, 3), v_in=round(float(w[max(i0 - 1, 0)] * R_HEAD), 3), v_out=round(float(w[i1] * R_HEAD), 3),
                                    dur_ms=round((t[i1] - t[i0]) * 1e3, 4), F_max=round(float(F.max()), 2), cycle_deg=round(float(a[i0]), 2),
                                    end_deg=round(float(a[i1]), 2), pen_um=round(float(pen.max() * 1e6), 1)))
    for i0, i1 in runs(lip):
        pl = R_HEAD * (th[i0:i1 + 1] - L[i0:i1 + 1])
        out['lip'].append(dict(cycle_deg=round(float(a[i0]), 2), end_deg=round(float(a[i1]), 2), pen_um=round(float(pl.max() * 1e6), 2)))
    if not out['contacts']:
        out.update(ok=False); return out
    c0 = out['contacts'][0]
    out['v_impact'] = c0['v_in']
    out['t_flight_ms'] = c0['t_ms']
    out['E_impact_mJ'] = float(0.5 * I * (c0['v_in'] / R_HEAD) ** 2 * 1e3)
    out['last_sheet_deg'] = max(c['end_deg'] for c in out['contacts'])
    out['sheet_after_200'] = sum(1 for c in out['contacts'] if c['end_deg'] >= 200.0)
    i200 = int(np.searchsorted(a, 200.0))
    out['gap_200_mm'] = float(R_HEAD * (SWING - th[min(i200, len(th) - 1)]) * 1e3)
    late = a > 205.0
    out['track_err_mm'] = float(R_HEAD * np.max(np.abs(th[late] - np.minimum(L[late], SWING))) * 1e3) if late.any() else 0.0
    hm = np.flatnonzero((a > 250.0) & (th < math.radians(0.3)))
    out['home_deg'] = float(a[hm[0]]) if len(hm) else None
    out['trace'] = [a[::max(1, len(a) // 600)].tolist(), (th[::max(1, len(a) // 600)] * R_HEAD * 1e3).tolist(),
                    (np.minimum(L, SWING)[::max(1, len(a) // 600)] * R_HEAD * 1e3).tolist()]
    out['ok'] = True
    return out


def cam_torque(eta=0.8, deg_t=None, clocks=None):
    """rev. 0.14: torque of the cocking on the cycle shaft (the lever winds the spring against the sear, 10..163 deg),
    and the cocking rod's following of the cam's fall (175..330 deg): the downward acceleration it needs against the
    rod's return spring, gravity and the spring's push while the hammer lies on the sheet."""
    import parts as PT
    r = LJ['r_cock_mm'] * U.MM
    stroke = 6e-3
    out = []
    for a in np.arange(10, 175.5, 0.5):
        z = stroke * PT.cam_lift('cock', a)
        dz = stroke * (PT.cam_lift('cock', a + 0.05) - PT.cam_lift('cock', a - 0.05)) / math.radians(0.1)
        th = math.atan2(z, r)
        T = T0_ + K_T * th if a < P.CYCLE['strike'] else T0_ + K_T * (th - SWING)
        F = T / r / math.cos(th) ** 2
        out.append((float(a), float(F * dz / eta)))
    arr = np.array(out)
    m_rod = (MASS.get('hammer cocking rod', {}).get('m', 0.004) + MASS.get('hammer trip link', {}).get('m', 0.003) +
             MASS.get('cam rod hammer', {}).get('m', 0.004))
    lev = MASS['hammer cocking lever']; ham = MASS['hammer']
    I_lev = np.array(lev['I'])[0, 0] + lev['m'] * ((lev['c'][1] - YP * U.MM) ** 2 + (lev['c'][2] - ZP_ * U.MM) ** 2)
    m_, I_h, rc_ = hammer_props(1.0)
    fol = []
    # stage 2b: clocks {tag: shaft.Clock} -- the rod's acceleration is s'' w^2 + s' w' on the real law
    for tag in (clocks or ('light', 'avg', 'worst')):
        ck = clocks[tag] if clocks else None
        w = 1.0 / DEG_T[tag] * math.pi / 180.0 if ck is None else None   # rad/s of the cycle shaft
        worst = (1e9, None)
        for a in np.arange(175.0, 330.0, 0.25):
            d2 = stroke * (PT.cam_lift('cock', a + 0.1) - 2 * PT.cam_lift('cock', a) + PT.cam_lift('cock', a - 0.1)) / math.radians(0.1) ** 2
            if ck is None:
                acc = d2 * w * w                               # m/s2 (negative: the rod must go down)
            else:
                d1 = stroke * (PT.cam_lift('cock', a + 0.1) - PT.cam_lift('cock', a - 0.1)) / math.radians(0.2)
                acc = d2 * ck.w(a) ** 2 + d1 * ck.wdot(a)
            th = math.atan2(stroke * PT.cam_lift('cock', a), r)
            on_sheet = th > SWING
            I_ref = I_lev + (0.0 if on_sheet else I_h)
            m_eff = m_rod + I_ref / r ** 2
            F_push = LJ['rod_return_N'] + m_rod * U.G + ((T0_ + K_T * (th - SWING)) / r if on_sheet else 0.0)
            margin = F_push + m_eff * acc                      # > 0: the rod stays on the cam
            if margin < worst[0]:
                worst = (margin, a)
        fol.append(dict(speed=tag, min_margin_N=round(worst[0], 3), at_deg=worst[1]))
    a_top = P.CYCLE['strike'] + 11.5
    E = float(np.trapezoid(arr[arr[:, 0] < a_top, 1], np.radians(arr[arr[:, 0] < a_top, 0])))
    return dict(peak_mNm=float(arr[:, 1].max() * 1e3), at_deg=float(arr[np.argmax(arr[:, 1]), 0]), mean_mNm=float(E / math.radians(161) * 1e3),
                E_mJ=E * 1e3, curve=arr[::10].round(5).tolist(), follow=fol,
                sear_force_N=LJ['F_sear_N'], sear_trip_mNm=float(0.2 * LJ['F_sear_N'] * 6.5e-3 * 1e3))


def mujoco_blow(I, v_in, t_c, e):
    """The blow alone in MuJoCo: the hammer's effective mass at the head radius on a slide joint, a sphere on a plane
    (solref direct: stiffness and damping per unit effective mass, so the contact time and the restitution are the
    ODE's). Returns (v_out, duration)."""
    import mujoco
    meff = I / R_HEAD ** 2
    k = (math.pi / t_c) ** 2
    ln = math.log(e); z = -ln / math.sqrt(math.pi ** 2 + ln ** 2); b = 2 * z * math.sqrt(k)
    xml = f"""<mujoco><option timestep="1e-7" gravity="0 0 0" integrator="RK4" iterations="100" tolerance="1e-12"/>
    <worldbody><geom name="sheet" type="box" pos="0.01 0 0" size="0.01 0.01 0.01" solref="-{k:.6g} -{b:.6g}" solimp="0.9999 0.9999 0.0001 0.5 2" margin="0"/>
    <body name="h" pos="-0.001 0 0"><joint name="j" type="slide" axis="1 0 0" damping="0"/>
    <geom type="sphere" size="0.0005" solref="-{k:.6g} -{b:.6g}" solimp="0.9999 0.9999 0.0001 0.5 2" contype="1" conaffinity="1"/>
    <inertial pos="0 0 0" mass="{meff:.6g}" diaginertia="1e-9 1e-9 1e-9"/></body></worldbody></mujoco>"""
    mdl = mujoco.MjModel.from_xml_string(xml); d = mujoco.MjData(mdl)
    d.qvel[0] = v_in
    t_on = t_off = None; vout = None
    for i in range(int(4e-3 / mdl.opt.timestep)):
        mujoco.mj_step(mdl, d)
        inside = d.ncon > 0 and d.contact[0].dist < 0
        if inside and t_on is None:
            t_on = d.time
        if t_on is not None and not inside and d.qvel[0] < 0:
            t_off = d.time; vout = float(d.qvel[0]); break
    return (vout, (t_off - t_on) if t_on and t_off else None)


def lhs(n, k, rng):
    u = (rng.permuted(np.tile(np.arange(n), (k, 1)), axis=1).T + rng.random((n, k))) / n
    return u


def main():
    os.makedirs(U.GEN, exist_ok=True)
    res = {}
    # --- validation with links.py's assumptions: energy 20 mJ over the swing (no gravity, no friction, lever still)
    Il = LJ['I_kgmm2'] * 1e-6
    v1 = simulate(Il, grav=False, e=0.3, a_end=175.0)
    res['validation'] = dict(links_v=LJ['v_impact'], links_t_ms=LJ['t_flight_ms'], v=v1['v_impact'], t_ms=v1['t_flight_ms'],
                             dv_pct=100 * (v1['v_impact'] / LJ['v_impact'] - 1), dt_pct=100 * (v1['t_flight_ms'] / LJ['t_flight_ms'] - 1),
                             note='links.py: время полёта при постоянном моменте; здесь пружина линейная (T0 + K·(L − θ)) — полёт короче')
    a = simulate(Il, grav=False, e=0.3, rtol=1e-8, a_end=175.0); b = simulate(Il, grav=False, e=0.3, rtol=1e-10, a_end=175.0)
    res['convergence'] = dict(v=[a['v_impact'], b['v_impact']], F=[a['contacts'][0]['F_max'], b['contacts'][0]['F_max']])
    c = simulate(Il, grav=False, e=0.999, a_end=175.0)
    E_sp = T0_ * SWING + K_T * (LEVER * SWING - SWING ** 2 / 2)
    res['energy'] = dict(E_spring_mJ=E_sp * 1e3, E_impact_mJ=c['E_impact_mJ'], drift_pct=100 * (c['E_impact_mJ'] / (E_sp * 1e3) - 1),
                         v_out_over_in=c['contacts'][0]['v_out'] / c['contacts'][0]['v_in'])
    # --- nominal full physics
    m, I, rc = hammer_props(1.0)
    nom = dict(I=I, m=m, rc=rc, mu=0.25, t_c=0.3e-3, e=0.3, e_lip=0.3)
    res['props'] = dict(mass_g=m * 1e3, I_kgmm2=I * 1e6, links_mass_g=LJ['mass_g'], links_I=LJ['I_kgmm2'],
                        gravity_torque_rest_mNm=gravity_torque(0.0, m, rc) * 1e3, gravity_torque_sheet_mNm=gravity_torque(SWING, m, rc) * 1e3,
                        T0_mNm=T0_ * 1e3, T_sheet_mNm=(T0_ + K_T * (LEVER - SWING)) * 1e3, T_release_mNm=(T0_ + K_T * LEVER) * 1e3, k_t_Nm_rad=K_T)
    for tag, dt in DEG_T.items():
        res[f'nominal_{tag}'] = simulate(**nom, deg_t=dt)
    r = res['nominal_avg']
    vo, dur = mujoco_blow(I, r['contacts'][0]['v_in'], nom['t_c'], nom['e'])
    res['mujoco_blow'] = dict(v_in=r['contacts'][0]['v_in'], v_out_ode=r['contacts'][0]['v_out'], v_out_mj=vo, dur_ode_ms=r['contacts'][0]['dur_ms'],
                              dur_mj_ms=dur * 1e3 if dur else None)
    # --- slices and a Latin hypercube
    def row(r, v):
        return dict(value=v, v_impact=round(r['v_impact'], 3), F_max=r['contacts'][0]['F_max'], dur_ms=r['contacts'][0]['dur_ms'],
                    n_contacts=len(r['contacts']), last_sheet_deg=r['last_sheet_deg'], after_200=r['sheet_after_200'],
                    gap_200_mm=round(r['gap_200_mm'], 2), track_err_mm=round(r['track_err_mm'], 3), home_deg=r['home_deg'])
    grid = dict(f=(0.8, 1.0), mu=(0.15, 0.25, 0.35), t_c=(0.1e-3, 0.3e-3, 0.5e-3), e=(0.1, 0.2, 0.4, 0.7), e_lip=(0.1, 0.3, 0.6),
                speed=('light', 'avg', 'worst'))
    sl = {}
    for k_, vals in grid.items():
        rows = []
        for v in vals:
            kw = dict(nom); deg = DEG_T['avg']
            if k_ == 'f':
                kw['m'], kw['I'], kw['rc'] = hammer_props(v)
            elif k_ == 'speed':
                deg = DEG_T[v]
            else:
                kw[k_] = v
            rows.append(row(simulate(**kw, deg_t=deg), v))
        sl[k_] = rows
    res['slices'] = sl
    rng = np.random.default_rng(1)
    X = lhs(200, 7, rng)
    lh = []
    for x in X:
        f = 0.8 + 0.2 * x[0]; mu = 0.15 + 0.2 * x[1]; tc = (0.1 + 0.4 * x[2]) * 1e-3; e = 0.1 + 0.6 * x[3]; el = 0.1 + 0.5 * x[4]
        deg = DEG_T['light'] + (DEG_T['worst'] - DEG_T['light']) * x[5]
        T0 = T0_ * (0.7 + 0.6 * x[6])                       # spring preload +-30 %
        mm, II, rcc = hammer_props(f)
        r = simulate(II, mm, rcc, mu=mu, t_c=tc, e=e, e_lip=el, deg_t=deg, T0=T0)
        lh.append(dict(f=f, mu=mu, t_c_ms=tc * 1e3, e=e, e_lip=el, deg_ms=deg * 1e3, T0_mNm=T0 * 1e3, v=r['v_impact'], F_max=r['contacts'][0]['F_max'],
                       n=len(r['contacts']), last=r['last_sheet_deg'], after_200=r['sheet_after_200'], gap_200=r['gap_200_mm'],
                       track=r['track_err_mm'], home=r['home_deg']))
    res['lhs'] = dict(n=len(lh), after_200=sum(x['after_200'] > 0 for x in lh), v_range=[min(x['v'] for x in lh), max(x['v'] for x in lh)],
                      F_range=[min(x['F_max'] for x in lh), max(x['F_max'] for x in lh)], last_max=max(x['last'] for x in lh),
                      gap_200_min=min(x['gap_200'] for x in lh), track_max=max(x['track'] for x in lh),
                      home_max=max((x['home'] or 0) for x in lh), rows=lh)
    res['cam_cocking'] = cam_torque()
    json.dump(res, open(os.path.join(U.GEN, 'node_c.json'), 'w'), ensure_ascii=False, indent=1, default=float)
    plot(res, nom)
    v = res['validation']
    print(f"validation: v {v['v']:.3f} vs {v['links_v']:.3f} ({v['dv_pct']:+.2f} %), t {v['t_ms']:.3f} vs {v['links_t_ms']:.3f} ms ({v['dt_pct']:+.2f} %)")
    print('energy', res['energy'])
    n = res['nominal_avg']
    print('nominal: v', round(n['v_impact'], 3), 'flight', round(n['t_flight_ms'], 2), 'contacts', len(n['contacts']), n['contacts'][:3],
          'last', n['last_sheet_deg'], 'gap200', round(n['gap_200_mm'], 2), 'track', round(n['track_err_mm'], 3), 'home', n['home_deg'], 'lip', n['lip'][:4])
    print('mujoco', res['mujoco_blow'])
    print('LHS', {k: v for k, v in res['lhs'].items() if k != 'rows'})
    print('cam', {k: v for k, v in res['cam_cocking'].items() if k != 'curve'})


def plot(res, nom):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(8, 5.5), sharex=False)
    for e, col in ((0.1, '#2a6f97'), (0.3, '#c44536'), (0.7, '#7a7a7a')):
        r = simulate(nom['I'], nom['m'], nom['rc'], mu=nom['mu'], t_c=nom['t_c'], e=e, e_lip=nom['e_lip'], deg_t=DEG_T['avg'])
        a, th, L = r['trace']
        ax[0].plot(a, th, color=col, lw=1.0, label=f'молоток, e = {e}')
        ax[1].plot([c['cycle_deg'] for c in r['contacts']], [c['F_max'] for c in r['contacts']], 'o', color=col, ms=3)
    ax[0].plot(a, L, 'k--', lw=0.8, label='губа рычага (до листа)')
    for a_ in (160, 200):
        for x in ax:
            x.axvline(a_, color='k', lw=0.6, ls=':')
    ax[0].set_ylabel('ход бойка от дома, мм'); ax[0].set_xlabel('угол циклового вала, °'); ax[0].legend(fontsize=7)
    ax[1].set_ylabel('сила касания, Н'); ax[1].set_xlabel('угол циклового вала, °'); ax[1].set_xlim(159, 202)
    ax[0].set_title('Узел C (ред. 0.14): молоток между листом и губой рычага, средний цикл')
    fig.tight_layout(); fig.savefig(os.path.join(U.GEN, 'node_c_contacts.png'), dpi=130); plt.close(fig)


if __name__ == '__main__':
    main()
