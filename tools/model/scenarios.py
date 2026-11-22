"""Motion scenarios for interference checks."""
import numpy as np
import params as P
import parts as PT
import data as D
import checks

def key_frames(k, tier):
    """Bail travels produced by a full press of key k in the given tier."""
    fr = {}
    for bail, t, gap in PT.plate_lugs(k):
        if t == tier:
            fr[bail] = max(fr.get(bail, 0.0), P.TP - gap)
    return fr


def check_moving(state, movers, others_filter=None):
    """Interference of parts whose mov matches movers against everything else."""
    ps = PT.build(state)
    mov = [p for p in ps if any(p.mov.startswith(m) for m in movers)]
    rest = [p for p in ps if p not in mov]
    res = []
    bb_m = checks.bboxes(mov); bb_r = checks.bboxes(rest)
    # movers of different motion groups against each other (e.g. the lifting shuttle and the turning detent wheel)
    for i, a in enumerate(mov):
        for j in range(i + 1, len(mov)):
            b = mov[j]
            if a.mov == b.mov or checks.allowed(a.name, b.name):
                continue
            if np.all(bb_m[j, :3] < bb_m[i, 3:] - 0.05) and np.all(bb_m[j, 3:] > bb_m[i, :3] + 0.05):
                v = (a.mesh ^ b.mesh).volume()
                if v > 0.05:
                    res.append((a.name, b.name, round(v, 2)))
    for i, a in enumerate(mov):
        lo, hi = bb_m[i, :3], bb_m[i, 3:]
        ov = np.all(bb_r[:, :3] < hi - 0.05, 1) & np.all(bb_r[:, 3:] > lo + 0.05, 1)
        for j in np.nonzero(ov)[0]:
            b = rest[j]
            if checks.allowed(a.name, b.name):
                continue
            v = (a.mesh ^ b.mesh).volume()
            if v > 0.05:
                res.append((a.name, b.name, round(v, 2)))
    return res


def cycle_state(a, pos_t, row_t, **kw):
    """Machine state at cycle angle a for a target position/row (the shuttle starts at home)."""
    k = PT.cam_lift('out', a)
    home_p = (P.NPOS - 1) / 2
    bits = tuple(b for b, v in (('r1', 1), ('r2', 2), ('r4', 4), ('r8', 8)) if int(pos_t) & v) + \
        tuple(b for b, v in (('l1', 1), ('l2', 2), ('l4', 4)) if int(row_t) & v)
    # rev. 0.10: the feelers go out while the read cam is low and stop on the tabs of the target cell; the W latch
    # holds the escapement rods from the reading to 345 deg, the sectors hold B and C
    import reader as RD
    v = RD.cell_code(pos_t, row_t)
    feel, fr = {}, {}
    if kw.get('lock_read'):            # rev. 0.11: dead marks and spaces: the read lock keeps the feelers in
        v = None
    if v is not None and 'feel' not in kw:
        feel, fr = RD.read_state(v, 1.0 - PT.cam_lift('read', a))
        if P.CYCLE['read'][0] <= a <= P.CYCLE['wlatch']:
            fr['Wr'] = P.READ_K * v[0]
        kw = dict(kw, feel=feel, frames=dict(kw.get('frames', {}), **fr))
    if 'u_in' not in kw:               # rev. 0.11: U's finger goes into the teeth for the release; rev. 0.14: from 190 deg
        kw = dict(kw, u_in=P.CYCLE['u_in'][0] <= a <= P.CYCLE['u_in'][1])
    return PT.State(pos=home_p + (pos_t - home_p) * k, row=P.REST_ROW + (row_t - P.REST_ROW) * k, cycle=a, bits=bits,
                    detent=PT.cam_lift('detent', a), hammer=0.0 if kw.get('lock_hammer') else PT.cam_lift('strike', a),
                    cock=PT.cam_lift('cock', a),
                    lock=1.0 if 5 <= a <= 345 else 0.0, **kw)


def escape_states():
    """rev. 0.9c: the escapement: U set for every width with and without +-u, the finger in; backspace and back-a-letter
    at the ends and the middle of the line; the memory arm at every width."""
    import math, escape as E
    T = 5.053 * math.radians(6.0)
    out = []
    for n in (0, 60, 300):                        # carriage at the start, the middle, near the end (units)
        car0 = P.CAR_X_START - n * T
        for w in range(4, 17, 2):
            for pm in (-1, 0, 1):
                out.append((PT.State(car=car0, frames={'W': float(w - 4)}, u_in=True, pm_u=pm), f'U w={w} pm={pm} car {n}u'))
        for mem in (0, 4, 10, 17):
            out.append((PT.State(car=car0, esc_mem=mem), f'M mem={mem} car {n}u'))
            if n > 20:
                for f in (0.3, 1.0):
                    b = (E.B_CATCH + 6 * mem + E.M_PLAY) * f
                    out.append((PT.State(car=car0 + 5.053 * math.radians(max(0.0, b - E.B_CATCH)), pressed={47: f}, esc_mem=mem),
                                f'back mem={mem} at {f} car {n}u'))
        if n > 0:
            for f in (0.1, 0.5, 1.0):
                b = E.BKSP_DEG * f
                out.append((PT.State(car=car0 + 5.053 * math.radians(max(0.0, b - E.B_CATCH)), pressed={46: f}), f'bksp at {f} car {n}u'))
        # rev. 0.11: carriage release: the dog out, the carriage moved by hand between whole teeth of the wheel
        for f, dn in ((0.5, 0.0), (1.0, 0.0), (1.0, -0.37), (1.0, -0.5)):     # (the left margin stop is at the start)
            out.append((PT.State(car=car0 + dn * T, car_release=f), f'release {f} car {n}{dn:+.2f}u'))
    return out


def run(verbose=True):
    report = {}
    out = []
    for row in [P.REST_ROW, -0.5, 0, 1, 2, 3, 3.5, 4, 5, 6, 7]:
        for pos in list(np.arange(0, 10.01, 0.5)):
            st = PT.State(pos=float(pos), row=row)
            for r in check_moving(st, ['shuttle', 'drum', 'tape', 'lift', 'collar', 'ribbon', 'wtree']):
                out.append((f'pos {pos:.1f} row {row}',) + r)
    report['shuttle'] = out
    out = []
    for su in (0, 9, 17):
        for pos in (0, 5, 10):
            for row, hm in ((P.REST_ROW, 0.0), (0, 0.0), (7, 0.0), (0, 1.0), (7, 1.0)):
                st = PT.State(pos=pos, slide_u=su, row=row, hammer=hm)
                for r in check_moving(st, ['uframe', 'shuttle', 'drum', 'tape', 'lift', 'collar', 'hammer', 'detent', 'ribbon', 'wtree']):
                    out.append((f'slide {su}u pos {pos} row {row} hammer {hm}',) + r)
    report['slide'] = out
    out = []
    for car in np.linspace(P.CAR_X_START, P.CAR_X_END, 9):
        for hm in (0.0, 1.0):
            st = PT.State(car=float(car), hammer=hm, slide_u=17 if hm == 0 else 0)
            for r in check_moving(st, ['carriage', 'esc', 'hammer']):
                out.append((f'car {car:.0f} hammer {hm}',) + r)
    report['carriage'] = out
    out = []
    for k in PT.key_list():
        for tier in (0, 1):
            fr = key_frames(k, tier)
            for lk in (0.0, 1.0):
                su = P.MARK_REF_U if 'O' in fr else 0.0          # a dead mark retracts the unit to the step of memory 0
                st = PT.State(pressed={k['n']: 1.0}, frames=fr, tier=tier, lock=lk, slide_u=su)
                for r in check_moving(st, [f"key{k['n']}", f"kspring{k['n']}", 'bail', 'sel', 'bit', 'tier', 'follow', 'lock', 'spring', 'nsel', 'orod', 'orock',
                                           'obc', 'stop', 'uframe']):
                    out.append((f"key {k['id']} tier {tier} lock {lk}",) + r)
    report['keys'] = out
    # rev. 0.8b: dead marks against the memory steps: every remembered value, partway and at the step, with the other
    # sector at several values (the finger must pass it)
    out = []
    MOV = ['uframe', 'stop', 'nsel', 'followO', 'orod', 'orock', 'obc', 'spring', 'bail', 'follow', 'shuttle', 'drum', 'tape', 'lift',
           'collar', 'hammer', 'detent', 'ribbon', 'wtree']
    for nm, N in (('B', 0.0), ('C', 16.0)):
        other = 'C' if nm == 'B' else 'B'
        for k in range(10 if nm == 'C' else 9):
            for f in (0.0, 0.4, 1.0):
                for ko in (0.0, 9.0 if other == 'C' else 8.0):
                    st = PT.State(slide_u=(P.MARK_REF_U + k) * f, frames={'O': 16.0 * max(f, 0.1), 'N': N * max(f, 0.1)},
                                  mem={nm: float(k), other: ko})
                    for r in check_moving(st, MOV):
                        out.append((f'mark {nm}={k} at {f:.1f} other {ko:.0f}',) + r)
    report['marks'] = out
    out = []
    for a in range(0, 360, 10):
        for pos_t, row_t in ((0, 0), (10, 7), (0, 7), (10, 0)):
            st = cycle_state(float(a), pos_t, row_t)
            for r in check_moving(st, ['cycle', 'shuttle', 'drum', 'tape', 'lift', 'collar', 'detent', 'hammer', 'ribbon', 'wtree', 'bit', 'cock', 'lock',
                                       'feel', 'slide', 'readrocker', 'followB', 'followC', 'followW']):
                out.append((f'cycle {a} target {pos_t}/{row_t}',) + r)
    report['cycle'] = out
    # rev. 0.11: idle cycles: a dead mark (the unit retracted, the read lock in) and a space (since 0.11 its own pushers: the
    # shuttle stays at position 5 and drops to row 1 (bits r1 + r4, rev. 0.11); both locks in, the hammer held, the lip on its tail)
    out = []
    MOVI = ['cycle', 'shuttle', 'drum', 'tape', 'lift', 'collar', 'detent', 'hammer', 'ribbon', 'wtree', 'bit', 'cock', 'lock',
            'feel', 'slide', 'readrocker', 'readlock', 'hammerlock', 'uframe', 'followB', 'followC', 'followW']
    for a in range(0, 360, 10):
        for lab, pos_t, row_t, kw in (('mark a', 6, 0, dict(lock_read=1.0, slide_u=float(P.MARK_REF_U + 4), frames={'O': 16.0})),
                                      ('mark y', 10, 0, dict(lock_read=1.0, slide_u=float(P.MARK_REF_U + 9), frames={'O': 16.0, 'N': 16.0})),
                                      ('space', 5, 0, dict(lock_read=1.0, lock_hammer=1.0, frames={'W': 2.0, 'R': 16.0}))):
            st = cycle_state(float(a), pos_t, row_t, **kw)
            for r in check_moving(st, MOVI):
                out.append((f'idle {lab} cycle {a}',) + r)
    report['idle'] = out
    # rev. 0.10: every advancing item read at its cell: the feelers halfway and on their tabs, the receivers with them
    import reader as RD
    out = []
    for m in range(P.NPOS):
        for r_ in range(P.NROWS):
            v = RD.cell_code(m, r_)
            if v is None:
                continue
            for f in (0.5, 1.0):
                feel, fr = RD.read_state(v, f)
                st = PT.State(pos=float(m), row=float(r_), detent=1.0, feel=feel, frames=fr, mem={'B': float(v[1]) * f, 'C': float(v[2]) * f})
                for r in check_moving(st, ['feel', 'slide', 'followB', 'followC', 'followW']):
                    out.append((f'read {m}/{r_ + 1} at {f}',) + r)
    report['read'] = out
    out = []
    for st, tag in escape_states():
        for r in check_moving(st, ['esc', 'follow', 'backB', 'rock', 'key46', 'key47', 'pmu', 'escdog', 'escM', 'carriage', 'paper', 'release']):
            out.append((tag,) + r)
    report['escape'] = out
    if verbose:
        for k, v in report.items():
            print(k, len(v))
            for r in v[:12]:
                print('   ', r)
    return report


if __name__ == '__main__':
    run()
