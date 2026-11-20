"""Links of the machine worked out from the layout parameters (rev. 0.8): selection whiffletrees with latches and
amplifiers, gauge frames on vertical guides, memory sectors on nested sleeves, the W link to the escapement stop,
hammer cocking, the row detent, the ribbon vibrator, the interlocks; strength checks.
Every link that sets a position is a slotted lever driven by a pin on a straight slider ("кулиса"): the output is then
exactly linear in the input, y = (b/a) x, whatever the angle; no small-angle error enters the code.
Usage: python3 -I links.py OUT_JSON"""
import sys, os, json, math, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import params as P

E_STEEL = 206000.0      # MPa
E_PETG = 2000.0         # MPa
RHO_PETG = 1.27e-3      # g/mm3
RHO_STEEL = 7.85e-3

# ------------------------------------------------------------------------------------------- selection
S = 12.0                # stroke of a latched bit slider (cam lift), mm
SLIDER_W = 4.0          # width of a slider (steel strip 4 x 3 in a printed comb)
MIN_GAP = 9.0           # min distance between slider axes (pins, comb teeth)


def ladder(nbits, x_out, x_min, x_max, step=1.0, bit_gap=15.0):
    """Positions (x) of the bit sliders b_i and the nodes n_k of a slider-lever ladder: lever k joins node n_{k-1}
    (n_0 = b_0) and b_k; node n_k divides it in the ratio of the weights, n_k = n_{k-1} + (b_k - n_{k-1}) 2^k/(2^(k+1)-1).
    The last node is the tree output at x_out. Brute force over b_0..b_{n-2} (b_{n-1} follows from x_out),
    maximising the smallest distance between any two sliders."""
    g = np.arange(x_min, x_max + 1e-9, step)
    best = None
    for combo in itertools.product(g, repeat=nbits - 1):
        b = list(combo)
        n = [b[0]]
        acc = 1
        for k in range(1, nbits - 1):
            w = 2 ** k
            n.append(n[-1] + (b[k] - n[-1]) * w / (acc + w)); acc += w
        w = 2 ** (nbits - 1)
        frac = w / (acc + w)
        bl = n[-1] + (x_out - n[-1]) / frac
        if not (x_min <= bl <= x_max):
            continue
        xs = b + [bl]
        sb = sorted(xs)
        if min(q - p for p, q in zip(sb, sb[1:])) < bit_gap:      # rod fingers (13 mm along X) must not overlap
            continue
        allx = sorted(xs + n[1:] + [x_out])
        gap = min(q - p for p, q in zip(allx, allx[1:]))
        if best is None or gap > best[0]:
            best = (gap, xs, n + [x_out])
    gap, xs, nodes = best
    return dict(b=[float(v) for v in xs], n=[float(v) for v in nodes], min_gap=float(gap))


def node_y(tree, bits, f=1.0):
    """y displacement of every node for the given bits (list of 0/1) at drive phase f (0..1)."""
    y = [S * f * b for b in bits]
    nodes = [y[0]]
    acc = 1
    for k in range(1, len(bits)):
        w = 2 ** k
        nodes.append((acc * nodes[-1] + w * y[k]) / (acc + w))
        acc += w
    return y, nodes


def amplifier(step_out, nbits, offset_steps, a):
    """Second-class lever, pins in slots: input at a from the fulcrum, output at b; the fulcrum rides on a slide
    moved by the drive through the offset lever: y_out = G y_in + (1 - G) y_F, y_F = delta * f."""
    unit = S / (2 ** nbits - 1)
    G = step_out / unit
    b = G * a
    delta = offset_steps * step_out / (1 - G)       # (1 - G) delta = offset * step
    return dict(unit=unit, G=G, a=a, b=b, delta=delta, offset_ratio=delta / S)


def selection():
    out = {}
    # rotate: output slider (tape) at x = 40; the amplifier lies along X; fulcrum beyond the input
    rot_amp = amplifier(P.TAPE_PER_POS, 4, -(P.NPOS - 1) / 2, a=11.0)
    x_tape = 40.0
    x_F = x_tape + rot_amp['b']
    x_in = x_F - rot_amp['a']
    rot_tree = ladder(4, x_in, 46.0, 125.0, step=1.0)       # clear of the rotate cam rod finger (x 129..142)
    # angles of the amplifier: worst |y_in - y_F| over codes and drive phase
    worst = 0.0
    for c in range(P.NPOS):
        bits = [(c >> i) & 1 for i in range(4)]
        for f in np.linspace(0, 1, 11):
            _, n = node_y(rot_tree, bits, f)
            worst = max(worst, abs(n[-1] - rot_amp['delta'] * f))
    rot_amp.update(x_F=x_F, x_in=x_in, x_out=x_tape, theta_max=math.degrees(math.atan(worst / rot_amp['a'])),
                   slot_out=rot_amp['b'] * (1 / math.cos(math.atan(worst / rot_amp['a'])) - 1))
    out['rotate'] = dict(tree=rot_tree, amp=rot_amp)
    # lift: rest one row under the top row; the output slider turns a 1:1 slotted bellcrank that pushes the fork
    # at d = 30 from its pivot (fork ratio 5, input stroke 18 mm); the amplifier's fulcrum is on the inner side
    FORK_R = 150.0; FORK_D = 30.0
    lift_amp = amplifier(P.RH * FORK_D / FORK_R, 3, -P.REST_ROW, a=48.0)
    x_out_l = -FORK_R + FORK_D
    x_F_l = x_out_l + lift_amp['b']
    x_in_l = x_F_l - lift_amp['a']
    lt = ladder(3, -x_in_l, 26.0, 128.0, step=0.5)       # mirror image on the left; clear of the lift cam rod at -145
    lift_tree = dict(b=[-v for v in lt['b']], n=[-v for v in lt['n']], min_gap=lt['min_gap'])
    worst = 0.0
    for c in range(P.NROWS):
        bits = [(c >> i) & 1 for i in range(3)]
        for f in np.linspace(0, 1, 11):
            _, n = node_y(lift_tree, bits, f)
            worst = max(worst, abs(n[-1] - lift_amp['delta'] * f))
    lift_amp.update(x_F=x_F_l, x_in=x_in_l, x_out=x_out_l, theta_max=math.degrees(math.atan(worst / lift_amp['a'])),
                    fork_r=FORK_R, fork_d=FORK_D, fork_ratio=FORK_R / FORK_D, fork_stroke=(P.NROWS - 1 - P.REST_ROW) * P.RH * FORK_D / FORK_R,
                    fork_theta_max=math.degrees(math.atan((P.NROWS - 1 - P.REST_ROW) * P.RH / FORK_R)))
    out['lift'] = dict(tree=lift_tree, amp=lift_amp)
    # check: outputs equal the wanted steps exactly (linear pins in slots)
    errs = []
    for c in range(P.NPOS):
        bits = [(c >> i) & 1 for i in range(4)]
        _, n = node_y(rot_tree, bits, 1.0)
        y = rot_amp['G'] * n[-1] + (1 - rot_amp['G']) * rot_amp['delta']
        errs.append(abs(y - (c - (P.NPOS - 1) / 2) * P.TAPE_PER_POS))
    for c in range(P.NROWS):
        bits = [(c >> i) & 1 for i in range(3)]
        _, n = node_y(lift_tree, bits, 1.0)
        y = lift_amp['G'] * n[-1] + (1 - lift_amp['G']) * lift_amp['delta']
        hub = y * FORK_R / FORK_D
        errs.append(abs(hub - (c - P.REST_ROW) * P.RH))
    out['exact_error'] = max(errs)
    # latch: a pin in the bit slider, lifted 3.5 mm by its pad; the drive bail catches only a raised pin
    out['latch'] = dict(pin_d=3.0, lift=3.5, bail_edge_above_low_pin=1.5, spring_N=0.2,
                        note='pad lever over the selector rod, 18 mm long in Y: the pin stays up over the 12 mm stroke')
    # forces: slider return springs 0.4 N each, lever and pin friction 30 %; the drive bail moves all latched sliders
    F_ret = 0.4
    F_drive_rot = 4 * F_ret * 1.3 + 0.6         # all four bits latched, plus the offset slide
    F_drive_lift = 3 * F_ret * 1.3 + 0.6
    # load on the output: tape slider and the shuttle are moved by the cam through the tree: inertial force of the
    # shuttle reflected to the tape (mean, from the motor model) is carried by the bail, not by the springs
    out['forces'] = dict(F_return=F_ret, F_drive_rot=F_drive_rot, F_drive_lift=F_drive_lift)
    return out


# ------------------------------------------------------------------------------------- gauge frames
LANES = {'R': 112.0, 'O': 117.0, 'W': 136.0, 'B': 141.0, 'C': 146.0, 'N': 151.0}   # side plates, |x| (clear of x = 124, 130, -127)


def frames():
    """Each frame: two steel bars, two side plates (one per side), four vertical guide rods with sleeves.
    Travel is a pure translation; the frame weight is carried by two springs."""
    out = {}
    for i, name in enumerate(P.BAIL_ORDER):
        if name in ('B', 'C'):          # rev. 0.10: read from the shuttle; short slides under the followers instead
            continue
        xa = LANES[name]
        L = 2 * xa + 4
        m_bars = 2 * RHO_STEEL * math.pi * 2.5 ** 2 * L
        m_sides = 2 * RHO_PETG * 0.6 * (66 + 16) * 27 * 4          # two plates, about 0.6 filled
        m = m_bars + m_sides
        travel = {'R': P.TP, 'W': P.K_STEP * (6 - P.W_OFFSET), 'O': P.TP, 'N': P.TP}[name]   # rev. 0.10: W only for the spaces
        F_pre = m * 9.81e-3 + 0.3                                    # holds the weight plus 0.3 N against the stop
        k = 0.15 / travel                                             # N/mm: +0.15 N over the full travel
        out[name] = dict(lane=xa, bar_len=L, mass_g=m, travel=travel, F_pre=F_pre, F_end=F_pre + 0.15, k=k)
    out['guide'] = dict(rod_d=3.0, sleeve_d=6.0, sleeve_len=10.0, clearance=0.05,
                        tilt_mrad=1000 * 0.05 / 66.0)                  # sleeve clearance over the guide spacing
    return out


# ---------------------------------------------------------------------------- memory sectors and the W link
SLEEVE_AXIS = (-322.0, 47.0)          # (y, z) of the nested sleeves, axis along X, above the frame tops
FOLLOW_R = 16.0                        # follower arm: a roller on the flat top of its frame's beam
ROLLER_R = 2.0
BEAM_TOP = P.BAIL_Z + 20.0             # 42: top of the frame beams at rest
H0 = SLEEVE_AXIS[1] - (BEAM_TOP + ROLLER_R)   # 3 mm: the roller centre sits 3 mm under the axis at rest
THETA0 = math.degrees(math.asin(H0 / FOLLOW_R))


def follower_angle(s):
    """Arm angle below the horizontal (deg) when the frame is down s mm: the roller rides the flat beam top, so a shift of
    the frames in Y (shift key) changes nothing."""
    return math.degrees(math.asin((H0 + s) / FOLLOW_R))


def sectors():
    """Memory sectors on nested sleeves; a follower arm with a roller on the frame top turns each sleeve.
    The ratchet teeth sit at the angles the follower reaches for k units: theta_k = asin((h0 + k) / r) - theta_0."""
    out = {}
    R_TEETH = 42.0
    for name, n in (('B', 8), ('C', 9)):            # rev. 0.11: sector W removed
        th = [follower_angle(P.K_STEP * k) - THETA0 for k in range(n + 1)]
        pitch = [R_TEETH * math.radians(b - a) for a, b in zip(th, th[1:])]
        out[name] = dict(n=n, theta=th, pitch_min=min(pitch), pitch_max=max(pitch), r_teeth=R_TEETH)
    out['sleeves'] = dict(axis=SLEEVE_AXIS, follow_r=FOLLOW_R, h0=H0, theta0=THETA0,
                          tubes='латунные трубки 5/6/7 мм (телескопический набор) на оси 4 мм')
    # ratchet: the pawl falls behind tooth k when the frame stops at k units; the teeth are cut to give 0.5 unit capture
    out['ratchet'] = dict(capture=0.5 * P.K_STEP, pawl_spring_N=0.15,
                          trip='палец на втулке R поднимает собачки на первых 2 мм хода R и проходит мимо')
    return out


def escape_link():
    """W frame (live) -> the movable stop of the escapement, w teeth for w units. Sine lever: a roller on the frame top
    (input arm r) and a roller on a flat of the rod (output arm r2 at right angles): the rod moves (r2/r) s exactly.
    Escapement wheel 60 teeth, one per u; the stop arm turns about the wheel axis, 6 deg per u."""
    deg_per_u = 360.0 / 60
    r_a = P.K_STEP / math.radians(deg_per_u)      # attachment radius on the stop arm for 1 mm of rod per u
    ESC = (0.0, 116.05)
    y0 = SLEEVE_AXIS[0]
    rod_y = ESC[1] - r_a
    L1 = rod_y - y0                                # rod along Y on the left side at x = -172
    L2 = 172.0                                     # rod along X to the stop arm
    A = math.pi * 1.0 ** 2
    stretch = 0.5 * (L1 + L2) / (E_STEEL * A)
    s_max = P.K_STEP * (16 - P.W_OFFSET)
    th_max = follower_angle(s_max)
    return dict(r_a=r_a, deg_per_u=deg_per_u, base_teeth=P.W_OFFSET, rod_x=-172.0, rod_z=SLEEVE_AXIS[1] + FOLLOW_R,
                L1=L1, L2=L2, rod_d=2.0, spring_N=0.2, stretch_mm=stretch, bellcranks=1, r_in=FOLLOW_R, r_out=FOLLOW_R,
                theta_max=th_max, note='тяги только на растяжение (пружина у спуска); синусный рычаг 1:1 и угловой рычаг 1:1')


# ------------------------------------------------------------------------------------------- hammer
def hammer_geom():
    swing = math.radians(18.0)
    return dict(r_cock=6.0 / swing, swing_deg=18.0, cam_stroke=6.0)


def hammer():
    """Hammer cocked by its cam over 10..150 deg, released at 160 deg (sharp drop of the cam)."""
    import parts as PT, geo, trimesh
    V, F = geo.to_arrays(PT.hammer_mesh())
    tm = trimesh.Trimesh(V, F, process=False)
    tm.density = RHO_PETG * 0.8 / 1000.0
    yp, zp = P.HAMMER_PIVOT
    c = tm.center_mass
    I_c = tm.moment_inertia[0, 0]
    m = tm.mass                                     # kg
    d2 = (c[1] - yp) ** 2 + (c[2] - zp) ** 2
    I = (I_c + m * d2) * 1e-6 + 2e-7                # kg m2 (+ rubber pad and spring end)
    E = 0.020
    swing = math.radians(18.0)
    r_head = math.hypot(0 - yp, P.ZP - zp) * 1e-3  # m, pivot to the head
    w = math.sqrt(2 * E / I)
    v = w * r_head
    t_flight = swing / (w / 2) if w else 0          # from rest under a roughly constant torque
    # spring: torsion spring on the axle, preload so that the hammer rests on its back stop
    T_mean = E / swing                              # N m over the swing
    k_t = 2 * T_mean / swing * 0.5                  # half the torque is preload
    r_cock = 6.0 / math.degrees(swing) * 180 / math.pi   # cam stroke 6 mm through a cocking arm
    F_cam = T_mean / (r_cock * 1e-3) * 1.4          # peak about 1.4 x mean
    return dict(mass_g=m * 1000, I_kgmm2=I * 1e6, r_head_mm=r_head * 1000, E=E, swing_deg=18.0, v_impact=v,
                t_flight_ms=t_flight * 1000, T_mean_Nmm=T_mean * 1000, k_t_Nmm_per_deg=k_t * 1000 * math.pi / 180,
                r_cock_mm=r_cock, F_cam_N=F_cam, cam_rise=(10, 150), release=160)


# ------------------------------------------------------------------------------------------- row detent
def row_detent():
    """Notches of a comb on the lift fork, at radius rd from the fork pivot; row k printed at tan(theta) = lift / 150."""
    rd = 60.0
    th = [math.degrees(math.atan((k - P.REST_ROW) * P.RH / 150.0)) for k in range(P.NROWS)]
    pitch = [rd * math.radians(b - a) for a, b in zip(th, th[1:])]
    # capture at the hub: half the smallest notch pitch referred to the hub
    cap_hub = min(150.0 / math.cos(math.radians(t)) ** 2 * math.radians(b - t) / 2 for t, b in zip(th, th[1:]))
    return dict(rd=rd, theta=th, pitch_min=min(pitch), pitch_max=max(pitch), capture_hub=cap_hub, wedge_deg=60.0,
                stroke=5.0, drive='от тяги фиксатора поворота: поперечная тяга перед челноком и угловой рычаг 1:1,7')


def ribbon():
    return dict(drop=P.RIBBON_DROP, ratio=P.RIBBON_DROP / 3.0, mass_g=6.0, F_N=0.6, E_mJ=0.6 * P.RIBBON_DROP * 1e-3 * 1000 / 1000)


def interlocks():
    """Ball race under the levers: one lever at a time. Lock comb (rev. 0.8): a 2 mm steel comb under the levers with
    a slot for each; while the cycle runs it shifts 1.55 mm along X, so a tooth stands under the tab of every lever that
    is up and the pressed lever, held by a 1 mm neck in its slot, cannot rise. R or O (every code key moves one of them
    the full 16 mm) trips the cycle at 15.5 mm; a pawl on each of the two frames enforces the full stroke."""
    pitch = P.LEVER_PITCH
    t = P.LEVER_T
    slot = t + 0.4
    tooth = pitch - slot
    shift = 1.55
    neck = 1.0
    # displacement of the levers at the comb (y = -200): smallest for the space bars, largest for the back row
    key_y = [P.KEY_ROW_Y[r] for r in range(4)] + [P.SPACE_Y]
    disp = [P.KEY_TRAVEL * (P.LEVER_PIVOT_Y + 200.0) / (P.LEVER_PIVOT_Y - y) for y in key_y]
    return dict(n_levers=47, fin=2.0, ball_d=4.75, race_slack=2.3, comb_y=-200.0, comb_z=(40.5, 42.5), comb_t=2.0,
                slot=slot, tooth=tooth, shift=shift, neck=neck, tab_gap=0.5, disp_min=min(disp), disp_max=max(disp),
                partial_blocked=0.5 / min(disp), lock_in=5, lock_out=345, trip_at=15.5,
                full_stroke='храповая собачка на рамках R и O: начатый ход нельзя вернуть, пока рамка не дойдёт до 16 мм')


def strength():
    # gauge frame bar: steel rod 5 mm, simply supported on the side plates, span 276 mm, 0.3 N from a lug mid-span
    d = 5.0; I = math.pi * d ** 4 / 64; L = 276.0; F = 0.3
    d_bar = F * L ** 3 / (48 * E_STEEL * I)
    # key lever: PETG cantilever 60 mm, 3 x 12 mm (height 12), 1 N at the end
    b, h, Lc, Fl = 3.0, 12.0, 60.0, 1.0
    d_lev = Fl * Lc ** 3 / (3 * E_PETG * b * h ** 3 / 12)
    sigma = 120.0 / 20.0
    return dict(d_bar=d_bar, d_lev=d_lev, sigma_type=sigma)


# ------------------------------------------------------------------------------- rev. 0.8b: the stops of the slide
FINGER_R0 = 33.0          # rest radius of the feeler finger's face from the sleeve axis (at the axis height)
O_ARM = 12.0              # O follower output arm (down from the axis): pushes rod A toward +Y
O_CLAMP = 12.0            # the O arm meets its stop after 12 mm; the frame goes on alone
ROCKER = (33.0, 34.0)     # rocker behind the combs: lower arm (rod A), upper arm (rod B)
BC_R = 15.0               # sine bellcrank feeler -> carrier, both arms
O_BC_R = 12.0             # bellcrank rod B -> slide post, both arms
N_IN, N_OUT, N_SHIFT = 14.5, 62.5, 5.0   # N lever: roller arm, upright arm, finger shift (C plane 5 mm from B)


def o_push(s):
    """Push of rod A (mm, +Y) when the O frame is down s mm."""
    d = follower_angle(min(s, O_CLAMP)) - THETA0
    return O_ARM * math.sin(math.radians(d))


def n_shift(s):
    """Shift of the feeler finger (mm, toward the C plane) when the N frame is down s mm; the arm stops at 5 mm."""
    return min(N_SHIFT, N_OUT * math.sin(math.asin(min(1.0, s / N_IN))))


def stops():
    """Staircases on sectors B and C read by the feeler finger: the retraction of a mark is (8 + k) u, so the step for
    memory k sits at radius R0 - (8 + k) u, at the angle -theta_k (it comes to the finger when the sector holds k)."""
    sec = sectors()
    out = {}
    for name in ('B', 'C'):
        th = sec[name]['theta']
        out[name] = dict(R=[FINGER_R0 - (P.MARK_REF_U + k) * P.U for k in range(len(th))], theta=th)
    free = FINGER_R0 - max(out['B']['R'][0], out['C']['R'][0])     # finger travel before any step: 8 u
    s_n = N_IN * math.sin(math.asin(N_SHIFT / N_OUT))                # N travel that completes the shift
    push_at_n = o_push(s_n) * ROCKER[1] / ROCKER[0]
    # forces (estimates): slide return spring, the compliant section of rod A, extra load on an O lug
    F_ret, F_pre, k_sp = 1.0, 1.5, 0.12
    comp = o_push(O_CLAMP) * ROCKER[1] / ROCKER[0] - P.MARK_REF_U * P.U
    F_max = F_pre + k_sp * comp
    ds = 0.01
    lever = (o_push(1.0 + ds) - o_push(1.0)) / ds            # rod A per mm of O travel near the start
    return dict(stairs=out, R0=FINGER_R0, free=free, n_travel=s_n, slide_at_n=push_at_n,
                timing_ok=bool(push_at_n < free - 0.5), F_return=F_ret, F_spring=[F_pre, round(F_max, 2)],
                key_load_N=round(F_max * lever, 2), o_push_max=o_push(O_CLAMP), bc_theta_max=math.degrees(math.asin(P.SLIDE_MAX / BC_R)),
                zero_screw='М3 с контргайкой: один раз выставляет нулевое положение узла')


# ------------------------------------------------------------------ rev. 0.8b: backspace and back-a-letter
ESC_TEETH = 60
B_CRANK = 13.0            # crank of the back arm (pin at +48 deg at rest)
B_CRANK0 = 48.0


def back():
    """rev. 0.9c (escape.py): back arm B under the wheel, backspace arm K that pushes it; rockers on axes along Y behind
    the levers' tails (pins in slots), links with ball ends. Travel along each link: available at full key stroke
    (rigid link, B held) and needed for the turn (backspace 1.2 teeth after 5.4 deg of free travel; back-a-letter
    6 w + play for w = 16); the excess goes into the spring in the link."""
    import numpy as np, escape as E
    out = {}
    for key in ('bksp', 'back'):
        A0 = E.rocker_ball(key, 0.0); A1 = E.rocker_ball(key, E.rocker_phi(key, 1.0))
        S0 = E.stud_world(key, 0.0)
        need_deg = E.BKSP_DEG if key == 'bksp' else E.B_CATCH + 16 * E.PITCH + E.M_PLAY
        avail = float(np.linalg.norm(S0 - A1) - np.linalg.norm(S0 - A0))
        need = float(np.linalg.norm(S0 - A0) - np.linalg.norm(E.stud_world(key, need_deg) - A0))
        out[key] = dict(avail=avail, need=need, deg=need_deg, crank=E.STUD[key][0], rock_in=abs(E.ROCK['xpin'][key] - E.ROCK['xa'][key]),
                        rock_out=E.ROCK['r_out'][key], rock_deg=math.degrees(E.rocker_phi(key, 1.0)))
    return dict(deg_per_u=360 / ESC_TEETH, max_deg=16 * 360 / ESC_TEETH, crank=out['back']['crank'], crank0=E.STUD['back'][1],
                pull_back=out['back']['avail'], pull_back_need=out['back']['need'], pull_bksp=out['bksp']['avail'],
                pull_bksp_need=out['bksp']['need'], rock=dict(input=out['back']['rock_in'], bksp=out['bksp']['rock_out'],
                back=out['back']['rock_out']), detail=out, b_catch=E.B_CATCH, b_drop=E.B_DROP, m_play=E.M_PLAY,
                bksp_deg=E.BKSP_DEG, m_ratchet_teeth=18,
                note='M едет с колесом на клине сцепления при спуске; держится храповой собачкой в неподвижном секторе; '
                     'для «назад на литеру» клин снова сцепляет M с колесом, собачка отпущена, и колесо уходит назад, '
                     'пока M не упрётся в свой ноль')


def all_links():
    return dict(selection=selection(), frames=frames(), sectors=sectors(), escape=escape_link(), hammer=hammer(),
                row_detent=row_detent(), ribbon=ribbon(), interlocks=interlocks(), strength=strength(), stops=stops(), back=back())


if __name__ == '__main__':
    res = all_links()
    json.dump(res, open(sys.argv[1], 'w'), indent=1, ensure_ascii=False)
    for k, v in res.items():
        print(k, json.dumps(v, ensure_ascii=False)[:600])
