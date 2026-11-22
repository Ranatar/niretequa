"""Stage 1 (spec §4.5-4.9): bodies, their path to the ground, mobility (rank of the linearised constraints), statics
under gravity in every attitude (linear programme with slacks), fastener loads and the list of missing fastening.

Bodies are the components of the graph of 'rigid' joints. Three readings of the registry:
  design   -- every rigid joint holds (as the document intends, missing fasteners included);
  declared -- rigid joints that are modeled or described hold; 'missing' ones are plain contacts (the main reading);
  model    -- only fastening that exists in the model's geometry holds.
Two-sided constraints: fastening (inside bodies) and linear guides (MGN12, MGN7, LM8UU) or schematic overlaps of moving
joints; everything else -- pins in bores, levers on axles, parts lying on parts -- is one-sided contact with friction,
from the geometry (contactgeo.py). Usage: python3 -I tools/physics/stage1.py [mode]"""
import sys, os, json, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import units as U
import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog
import meshes as MS
import contactgeo as CG

FLEX_NAMES = {'rotate tape', 'escapement tape', 'ribbon', 'paper', 'bksp link', 'back link', 'mainspring'}
LINEAR = ('MGN12H', 'MGN7H', 'LM8UU')


# rev. 0.14 stage 2b: the governor brake's flat springs (0.1 x 2 mm steel, ~2.4 N/mm) carry their 0.3 g weights with
# a micrometre's sag: for statics a stiff suspension of the weights, not a force
STIFF_SPRINGS = ('governor leaf spring 1', 'governor leaf spring 2', 'governor leaf spring 3')


def is_flex(name):
    if name in STIFF_SPRINGS:
        return False
    return name in FLEX_NAMES or 'spring' in name.split() or name.endswith(' spring')


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def f(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]; a = self.p[a]
        return a

    def u(self, a, b):
        a, b = self.f(a), self.f(b)
        if a != b:
            self.p[max(a, b)] = min(a, b)


def holds(j, mode):
    if j['type'] != 'rigid':
        return False
    if mode == 'design':
        return True
    if mode == 'declared':
        return j['status'] in ('modeled', 'described')
    return j['status'] == 'modeled'


def bodies(S, J, mode):
    N = len(S.names)
    uf = UF(N)
    for g in J['ground'][1:]:
        uf.u(S.idx[J['ground'][0]], S.idx[g])
    for j in J['joints']:
        if holds(j, mode) and not is_flex(j['a']) and not is_flex(j['b']):
            uf.u(S.idx[j['a']], S.idx[j['b']])
    roots = {}
    body = np.full(N, -1)
    g0 = uf.f(S.idx[J['ground'][0]])
    order = [g0] + [i for i in range(N) if uf.f(i) == i and i != g0 and not all(is_flex(S.names[k]) for k in range(N) if uf.f(k) == i)]
    for r in order:
        roots[r] = len(roots)
    for i in range(N):
        if not is_flex(S.names[i]):
            body[i] = roots[uf.f(i)]
    return body, len(roots)          # body 0 is the ground


def linear_joint(j, S):
    pa, pb = S.p(j['a']), S.p(j['b'])
    if j['type'] not in ('prismatic', 'revolute', 'cylindrical'):
        return False
    return any((p['bom'] or '').startswith(LINEAR) for p in (pa, pb)) or (j.get('overlap') or 0) > 0.0


def joint_rows(j, S):
    """Rows (w_omega, w_v) in SI of a two-sided joint, as wrenches of unit reactions on body b (minus on a)."""
    ax = j.get('axis') or {}
    d = np.array(ax.get('d', [1, 0, 0]), float); d /= np.linalg.norm(d)
    p = np.array(ax.get('p', S.V[S.idx[j['b']]].mean(0)), float) * U.MM
    e1 = np.cross(d, [1, 0, 0] if abs(d[0]) < 0.9 else [0, 1, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(d, e1)
    rows = []
    tr = {'prismatic': [e1, e2], 'revolute': [d, e1, e2], 'cylindrical': [e1, e2]}[j['type']]
    rot = {'prismatic': [d, e1, e2], 'revolute': [e1, e2], 'cylindrical': [e1, e2]}[j['type']]
    for e in tr:
        rows.append((np.cross(p, e), e))
    for e in rot:
        rows.append((e, np.zeros(3)))
    return rows


def build_contacts(S, J, body, pairs, Tposes=None, key=None, skip_flex=True):
    """Contact points between parts of different bodies: list of dict(i, j, ba, bb, X (m), N, side, mu)."""
    out = []
    jt = {(j['a'], j['b']): j for j in J['joints']}
    for pr in pairs:
        a, b = pr['a'], pr['b']
        if is_flex(a) or is_flex(b):
            continue
        i, k = S.idx[a], S.idx[b]
        if body[i] == body[k]:
            continue
        j = jt.get((a, b)) or jt.get((b, a))
        if j is not None and linear_joint(j, S):
            continue
        tol = max(0.06, pr['gap'] + 0.05)
        Ti = Tposes[i] if Tposes is not None else None
        Tk = Tposes[k] if Tposes is not None else None
        X, Nn, side = CG.patch(S, i, k, tol, Ti, Tk, key)
        if len(X) == 0:
            continue
        mu = U.mu_pair(S.parts[i]['mat'], S.parts[k]['mat'], 0)
        out.append(dict(a=a, b=b, i=i, k=k, X=X * U.MM, N=Nn, side=side, mu=mu, type=(j or {}).get('type')))
    return out


def body_props(S, M, body, nb):
    m = np.zeros(nb); c = np.zeros((nb, 3))
    flexload = {}
    for i, p in enumerate(S.parts):
        mi = M[i]['m']; ci = np.array(M[i]['c'])
        if body[i] < 0:
            flexload[i] = (mi, ci)
            continue
        m[body[i]] += mi; c[body[i]] += mi * ci
    c = c / np.maximum(m, 1e-12)[:, None]
    return m, c, flexload


def flex_hosts(S, body, pairs):
    """Bodies a flexible part (spring, tape, sheet, ribbon) touches: its weight goes onto them, shared equally."""
    h = {}
    for pr in pairs:
        for x, y in ((pr['a'], pr['b']), (pr['b'], pr['a'])):
            if is_flex(x) and not is_flex(y):
                h.setdefault(S.idx[x], set()).add(int(body[S.idx[y]]))
    return h


def generators(contacts, nb, mu_scale=1.0, zero_mu=False, joints=None):
    """Columns of the equilibrium matrix: one-sided generators (n + mu t) >= 0, two-sided rows free.
    Returns (A (6nb x ncol) sparse, lb, meta)."""
    rows, cols, vals, lb, meta = [], [], [], [], []
    col = 0

    def put(bi, w, sgn):
        if bi == 0:
            return
        for q in range(6):
            if w[q] != 0.0:
                rows.append(6 * bi + q); cols.append(col); vals.append(sgn * w[q])

    for ci, c in enumerate(contacts):
        for x, n, s in zip(c['X'], c['N'], c['side']):
            pushed, pusher = (c['i'], c['k']) if s == 0 else (c['k'], c['i'])
            bp, bq = c['bp'][s], c['bq'][s]
            mu = 0.0 if zero_mu else c['mu'] * mu_scale
            e1 = np.cross(n, [1, 0, 0] if abs(n[0]) < 0.9 else [0, 1, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(n, e1)
            dirs = [n] if mu == 0 else [n + mu * e1, n - mu * e1, n + mu * e2, n - mu * e2]
            for d in dirs:
                w = np.r_[np.cross(x, d), d]
                put(bp, w, +1); put(bq, w, -1)
                lb.append(0.0); meta.append(('c', ci)); col += 1
    for ji, (ba, bb, rws) in enumerate(joints or []):
        for wo, wv in rws:
            w = np.r_[wo, wv]
            put(bb, w, +1); put(ba, w, -1)
            lb.append(-np.inf); meta.append(('j', ji)); col += 1
    A = sp.csc_matrix((vals, (rows, cols)), shape=(6 * nb, col))
    return A, np.array(lb), meta


def solve_statics(A, lb, wext, nb, Lm=0.05):
    """min sum |slack| (moment slack weighted as force at Lm) s.t. A x + s+ - s- = -wext, x >= lb."""
    nrow = 6 * nb
    keep = np.arange(6, nrow)                       # the ground's six rows are not equations
    A = A[keep, :]
    b = -wext[keep]
    n = A.shape[1]; m = len(keep)
    w = np.tile([1 / Lm] * 3 + [1.0] * 3, nb - 1)   # moment rows (N m) -> N at Lm
    I = sp.identity(m, format='csc')
    Aeq = sp.hstack([A, I, -I], format='csc')
    c = np.r_[np.zeros(n), w, w]
    bounds = [(l if np.isfinite(l) else None, None) for l in lb] + [(0, None)] * (2 * m)
    r = linprog(c, A_eq=Aeq, b_eq=b, bounds=bounds, method='highs', options=dict(presolve=True, time_limit=600))
    if r.status != 0:
        return None, None, r
    x = r.x[:n]
    s = (r.x[n:n + m] - r.x[n + m:]).reshape(nb - 1, 6)
    return x, np.vstack([np.zeros(6), s]), r


def gravity_wrench(m, c, nb, gdir, flex=None):
    w = np.zeros(6 * nb)
    g = np.asarray(gdir, float) * U.G
    for b in range(nb):
        F = m[b] * g
        w[6 * b:6 * b + 3] = np.cross(c[b], F); w[6 * b + 3:6 * b + 6] = F
    for (mi, ci, hosts) in (flex or []):
        hs = [h for h in hosts if h >= 0]
        for h in hs:
            F = mi * g / len(hs)
            w[6 * h:6 * h + 3] += np.cross(ci, F); w[6 * h + 3:6 * h + 6] += F
    return w


ATTITUDES = [('рабочее', (0, 0, -1))]
for a in (5, 15):
    s, cth = math.sin(math.radians(a)), math.cos(math.radians(a))
    ATTITUDES += [(f'наклон {a}° вперёд', (0, -s, -cth)), (f'наклон {a}° назад', (0, s, -cth)),
                  (f'наклон {a}° влево', (-s, 0, -cth)), (f'наклон {a}° вправо', (s, 0, -cth))]
s30, c30 = math.sin(math.radians(30)), math.cos(math.radians(30))
ATTITUDES += [('перенос 30° вперёд', (0, -s30, -c30)), ('перенос 30° назад', (0, s30, -c30)), ('перенос 30° влево', (-s30, 0, -c30)),
              ('перенос 30° вправо', (s30, 0, -c30)), ('на боку −x', (-1, 0, 0)), ('на боку +x', (1, 0, 0)),
              ('на передней стенке −y', (0, -1, 0)), ('на задней стенке +y', (0, 1, 0)), ('вверх дном', (0, 0, 1))]


def local_mobility(nb, contacts, joints, c):
    """Free twists of each body with every other body held (normal contact rows as equalities): its nullspace."""
    per = [[] for _ in range(nb)]
    for cc in contacts:
        for x, n, s in zip(cc['X'], cc['N'], cc['side']):
            w = np.r_[np.cross(x, n), n]
            per[cc['bp'][s]].append(w); per[cc['bq'][s]].append(w)
    for ba, bb, rws in joints:
        for wo, wv in rws:
            w = np.r_[wo, wv]
            per[ba].append(w); per[bb].append(w)
    out = []
    for b in range(nb):
        if b == 0:
            out.append([]); continue
        R = np.array(per[b]) if per[b] else np.zeros((0, 6))
        # twist about the body's centre: v(x) = v_c + w x (x - c); row . (w, v0) with v0 = v_c - w x c
        # (w, v0) = M (w, v_c): v0 = v_c - w x c = v_c + c x w
        Mx = np.eye(6); Mx[3:, :3] = skew(c[b])
        Rc = R @ Mx if len(R) else R
        if len(Rc):
            sc = np.r_[np.full(3, 0.05), np.ones(3)]          # rotation scaled to 5 cm
            Us, sv, Vt = np.linalg.svd(Rc * sc, full_matrices=True)
            tol = max(1e-9, 1e-6 * (sv[0] if len(sv) else 1))
            rank = int((sv > tol).sum())
            ns = Vt[rank:] * sc
        else:
            ns = np.eye(6)
        out.append([v / np.linalg.norm(v) for v in ns])
    return out


def skew(a):
    return np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])


def describe_twist(v, c):
    """v = (w, v_c) about the body centre c (m) -> text and numbers."""
    w, u = v[:3], v[3:]
    if np.linalg.norm(w) < 1e-6 * max(1.0, np.linalg.norm(u) / 0.05):
        d = u / np.linalg.norm(u)
        return dict(kind='сдвиг', d=d.round(3).tolist())
    wn = np.linalg.norm(w); d = w / wn
    p = c + np.cross(w, u) / wn ** 2
    h = float(w @ u / wn ** 2)
    return dict(kind='поворот', d=d.round(3).tolist(), p_mm=(p / U.MM).round(1).tolist(), pitch_mm=round(h / U.MM, 2))


def all_patches(S, J, pairs, cache):
    """Contact patches of every candidate pair (cached on disk; independent of the reading of the registry)."""
    import pickle
    if os.path.exists(cache):
        return pickle.load(open(cache, 'rb'))
    body = np.arange(len(S.names))         # every part its own body: all pairs
    J2 = dict(J, joints=[j for j in J['joints']])
    t0 = time.time()
    out = build_contacts(S, J2, body, pairs)
    pickle.dump(out, open(cache, 'wb'))
    print('patches', len(out), sum(len(c['X']) for c in out), 'points', round(time.time() - t0, 1), 's', flush=True)
    return out


def setup(mode, S=None, J=None, pairs=None, P=None, M=None):
    S = S or MS.Snap()
    J = J or json.load(open(os.path.join(U.DATA, 'joints.json')))
    pairs = pairs or json.load(open(os.path.join(U.GEN, 'pairs.json')))
    M = M or json.load(open(os.path.join(U.GEN, 'mass.json')))['parts']
    P = P or all_patches(S, J, pairs, os.path.join(U.GEN, 'patches_rest.pkl'))
    body, nb = bodies(S, J, mode)
    cont = []
    for c in P:
        if body[c['i']] == body[c['k']]:
            continue
        c = dict(c)
        c['bp'] = [int(body[c['i']]), int(body[c['k']])]     # side 0: i is pushed; side 1: k is pushed
        c['bq'] = [int(body[c['k']]), int(body[c['i']])]
        cont.append(c)
    jt = []
    for j in J['joints']:
        if is_flex(j['a']) or is_flex(j['b']):
            continue
        ba, bb = int(body[S.idx[j['a']]]), int(body[S.idx[j['b']]])
        if ba != bb and linear_joint(j, S):
            jt.append((ba, bb, joint_rows(j, S)))
    m, c, flexload = body_props(S, M, body, nb)
    hosts = flex_hosts(S, body, pairs)
    flex = [(flexload[i][0], flexload[i][1], sorted(hosts.get(i, []))) for i in flexload]
    return dict(S=S, J=J, pairs=pairs, M=M, P=P, body=body, nb=nb, cont=cont, joints=jt, m=m, c=c, flex=flex, hosts=hosts, mode=mode)


def connectivity(D):
    nb = D['nb']
    adj = [set() for _ in range(nb)]
    for c in D['cont']:
        a, b = c['bp'][0], c['bq'][0]
        adj[a].add(b); adj[b].add(a)
    for ba, bb, _ in D['joints']:
        adj[ba].add(bb); adj[bb].add(ba)
    for i, hs in D['hosts'].items():
        hs = list(hs)
        for x in hs:
            for y in hs:
                if x != y:
                    adj[x].add(y)
    seen = {0}; st = [0]
    while st:
        x = st.pop()
        for y in adj[x]:
            if y not in seen:
                seen.add(y); st.append(y)
    return [b for b in range(nb) if b not in seen]


def body_names(D, b):
    return [D['S'].names[i] for i in np.nonzero(D['body'] == b)[0]]


def statics(D, gdir, zero_mu=False, mu_scale=1.0):
    A, lb, meta = generators(D['cont'], D['nb'], mu_scale=mu_scale, zero_mu=zero_mu, joints=D['joints'])
    w = gravity_wrench(D['m'], D['c'], D['nb'], gdir, D['flex'])
    x, s, r = solve_statics(A, lb, w, D['nb'])
    if x is None:
        return dict(status=str(r.message)), None, None, None
    W = D['m'] * U.G
    unheld = []
    for b in range(1, D['nb']):
        fs = np.linalg.norm(s[b, 3:]); ms = np.linalg.norm(s[b, :3])
        if fs > 0.02 * W[b] + 2e-4 or ms > 0.02 * W[b] * 0.05 + 1e-5:
            unheld.append(dict(body=b, W_N=round(float(W[b]), 4), slack_F=(s[b, 3:]).round(5).tolist(), slack_M=(s[b, :3]).round(6).tolist(),
                               parts=body_names(D, b)[:6], nparts=int((D['body'] == b).sum())))
    return dict(status='ok', unheld=unheld), x, meta, s


SPRING_PARTS = {'compression': None, 'extension': None}


def spring_loads(D, springs, scale=1.0):
    """External wrenches of the springs that exist as parts (frame springs, slide return, O rod A): the preload along the
    spring's axis between the two bodies it touches at its two ends (compression pushes them apart, extension pulls)."""
    S = D['S']
    w = np.zeros(6 * D['nb'])
    used, skipped = [], []
    pairs = D['pairs']
    for sp_ in springs:
        nm = sp_.get('part')
        if not nm or nm not in S.idx or sp_['kind'] not in ('compression', 'extension') or not sp_.get('preload'):
            if nm:
                skipped.append(nm)
            continue
        i = S.idx[nm]
        V = S.V[i]; c0 = V.mean(0)
        _, sv, Vt = np.linalg.svd(V - c0, full_matrices=False); d = Vt[0]
        ends = {}
        for pr in pairs:
            if nm not in (pr['a'], pr['b']):
                continue
            o = pr['b'] if pr['a'] == nm else pr['a']
            if is_flex(o):
                continue
            x = np.array(pr['pa'] if pr['a'] == nm else pr['pb'])
            t = float((x - c0) @ d)
            b = int(D['body'][S.idx[o]])
            side = 1 if t > 0 else -1
            Vo = S.V[S.idx[o]]
            _, _, Vto = np.linalg.svd(Vo - Vo.mean(0), full_matrices=False)
            po = Vo @ d
            inside = (abs(float(Vto[0] @ d)) > 0.95 and np.ptp(Vo @ Vto[0]) > np.ptp(V @ d) * 0.9
                      and po.min() < float(c0 @ d) < po.max())         # the guide rod through the coil (rev. 0.14: it passes the middle)
            if abs(t) > 0.35 * np.ptp(V @ d) and not inside:
                ends.setdefault(side, []).append((b, x))
        if 1 not in ends or -1 not in ends:
            skipped.append(nm); continue
        F = sp_['preload'] * scale
        sgn = 1 if sp_['kind'] == 'compression' else -1
        for side in (1, -1):
            b, x = max(ends[side], key=lambda q: abs((q[1] - c0) @ d))
            f = sgn * side * F * d
            xm = x * U.MM
            w[6 * b:6 * b + 3] += np.cross(xm, f); w[6 * b + 3:6 * b + 6] += f
        used.append(nm)
    return w, used, skipped


def local_hold(D, gdir, wsp=None, zero_mu=False, mu_scale=1.0, bodies_=None):
    """Each body alone on its neighbours (held fixed): can its contacts and joints carry its weight (and spring loads)?
    Returns {body: dict(slack_F, slack_M, ok)}."""
    nb = D['nb']
    wg = gravity_wrench(D['m'], D['c'], nb, gdir, D['flex'])
    if wsp is not None:
        wg = wg + wsp
    by = [[] for _ in range(nb)]
    for ci, c in enumerate(D['cont']):
        for q, (x, n, s) in enumerate(zip(c['X'], c['N'], c['side'])):
            by[c['bp'][s]].append((x, n, +1, c['mu'])); by[c['bq'][s]].append((x, n, -1, c['mu']))
    jb = [[] for _ in range(nb)]
    for ba, bb, rws in D['joints']:
        for wo, wv in rws:
            jb[ba].append(np.r_[wo, wv]); jb[bb].append(np.r_[wo, wv])
    out = {}
    for b in (bodies_ or range(1, nb)):
        cols, lb = [], []
        for x, n, sg, mu in by[b]:
            mu = 0.0 if zero_mu else mu * mu_scale
            e1 = np.cross(n, [1, 0, 0] if abs(n[0]) < 0.9 else [0, 1, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(n, e1)
            for d in ([n] if mu == 0 else [n + mu * e1, n - mu * e1, n + mu * e2, n - mu * e2]):
                cols.append(sg * np.r_[np.cross(x, d), d]); lb.append(0.0)
        for w in jb[b]:
            cols.append(w); lb.append(None)
        rhs = -wg[6 * b:6 * b + 6]
        W = max(D['m'][b] * U.G, 1e-6)
        sc = np.r_[np.full(3, 1 / 0.05), np.ones(3)]
        nC = len(cols)
        A = np.array(cols).T if nC else np.zeros((6, 0))
        Aeq = np.hstack([A, np.eye(6), -np.eye(6)])
        cst = np.r_[np.zeros(nC), sc, sc]
        bnds = [(l, None) for l in lb] + [(0, None)] * 12
        r = linprog(cst, A_eq=Aeq, b_eq=rhs, bounds=bnds, method='highs')
        if r.status != 0:
            out[b] = dict(ok=False, slack_F=[np.nan] * 3, slack_M=[np.nan] * 3, why=str(r.message)); continue
        sl = r.x[nC:nC + 6] - r.x[nC + 6:]
        fs, ms = np.linalg.norm(sl[3:]), np.linalg.norm(sl[:3])
        ok = fs <= 0.02 * W + 1e-5 and ms <= 0.02 * W * 0.05 + 1e-6
        out[b] = dict(ok=bool(ok), slack_F=(sl[3:] / W).round(3).tolist(), slack_M=(sl[:3] / (W * 0.05)).round(3).tolist(), ncols=nC)
    return out


def _xf(T, R=None, t=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    if t is not None:
        M[:3, 3] = t
    return M


def rotm(axis, ang):
    a = np.asarray(axis, float); a /= np.linalg.norm(a)
    K = skew(a)
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


def probe(D, b, trans=None, rot=None, dmax=3.0, step=0.05, T0=None):
    """Move body b (all its parts) along a translation (unit vector, mm) or a rotation (axis, point mm; dmax in degrees)
    until it meets another part: returns (distance mm or deg, part hit) or (None, None) when free up to dmax.
    A new contact: a pair whose gap was > 0.02 mm falls under 0.005 mm; an existing contact: its overlap grows by 0.02 mm3."""
    S = D['S']
    ids = [i for i in np.nonzero(D['body'] == b)[0]]
    lo = S.lo[ids].min(0) - dmax - 1; hi = S.hi[ids].max(0) + dmax + 1
    if rot is not None:
        ext = np.linalg.norm(hi - lo) * math.radians(dmax)
        lo, hi = lo - ext, hi + ext
    cand = [k for k in np.nonzero(np.all(S.lo <= hi, 1) & np.all(S.hi >= lo, 1))[0]
            if D['body'][k] != b and D['body'][k] >= 0]
    pairs = []
    for i in ids:
        for k in cand:
            if np.all(S.lo[k] <= S.hi[i] + dmax + 1) and np.all(S.hi[k] >= S.lo[i] - dmax - 1) or rot is not None:
                g, _, _ = MS.distance(S, i, k, Ti=T0)
                ov = 0.0
                if g == 0.0:
                    ov = MS.overlap(S, i, k) if T0 is None else float((MS.manifold(S, i).transform(T0[:3, :]) ^ MS.manifold(S, k)).volume())
                pairs.append((i, k, g, ov))
    n = int(round(dmax / step))
    for q in range(1, n + 1):
        dd = q * step
        if trans is not None:
            T = _xf(None, None, np.asarray(trans, float) * dd)
        else:
            ax, pt = rot
            R = rotm(ax, math.radians(dd)); pt = np.asarray(pt, float)
            T = _xf(None, R, pt - R @ pt)
        if T0 is not None:
            T = T @ T0
        for i, k, g0, ov0 in pairs:
            g, _, _ = MS.distance(S, i, k, Ti=T)
            if g0 > 0.02 and g < 0.005:
                return dd, S.names[k]
            if g0 <= 0.02 and g == 0.0:
                from manifold3d import Manifold
                ov = float((MS.manifold(S, i).transform(T[:3, :]) ^ MS.manifold(S, k)).volume())
                if ov > ov0 + 0.02:
                    return dd, S.names[k]
    return None, None


def settle(D, b, res):
    """For an unheld body: which way it goes (opposite to the missing force or moment) and how far before a stop."""
    F = -np.array(res['slack_F']); Mo = -np.array(res['slack_M'])
    if np.linalg.norm(F) >= 0.3 * np.linalg.norm(Mo) and np.linalg.norm(F) > 0:
        d = F / np.linalg.norm(F)
        dist, hit = probe(D, b, trans=d)
        return dict(move='сдвиг', d=d.round(3).tolist(), dist_mm=dist, hit=hit)
    ax = Mo / np.linalg.norm(Mo)
    c = D['c'][b] / U.MM
    dist, hit = probe(D, b, rot=(ax, c), dmax=5.0, step=0.1)
    return dict(move='поворот', axis=ax.round(3).tolist(), about_mm=c.round(1).tolist(), dist_deg=dist, hit=hit)


def body_contacts_at(D, b, T, key):
    """Contact points of body b moved by T (mm pose) against every other non-flexible part nearby."""
    S = D['S']
    ids = list(np.nonzero(D['body'] == b)[0])
    lo = S.lo[ids].min(0) - 1; hi = S.hi[ids].max(0) + 1
    cand = [k for k in np.nonzero(np.all(S.lo <= hi + 2, 1) & np.all(S.hi >= lo - 2, 1))[0] if D['body'][k] not in (b, -1)]
    rows = []
    for i in ids:
        for k in cand:
            g, _, _ = MS.distance(S, i, k, Ti=T)
            if g > 0.12:
                continue
            X, N, side = CG.patch(S, i, k, max(0.06, g + 0.05), T, None, key=('b', b, key))
            mu = U.mu_pair(S.parts[i]['mat'], S.parts[k]['mat'], 0)
            for x, n, sd in zip(X * U.MM, N, side):
                rows.append((x, n if sd == 0 else -n, mu))      # force on b along +n
    return rows


def hold_rows(rows, wb, W, zero_mu=False, mu_scale=1.0, extra=None):
    cols, lb = [], []
    for x, n, mu in rows:
        mu = 0.0 if zero_mu else mu * mu_scale
        e1 = np.cross(n, [1, 0, 0] if abs(n[0]) < 0.9 else [0, 1, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(n, e1)
        for d in ([n] if mu == 0 else [n + mu * e1, n - mu * e1, n + mu * e2, n - mu * e2]):
            cols.append(np.r_[np.cross(x, d), d]); lb.append(0.0)
    for w in (extra or []):
        cols.append(w); lb.append(None)
    nC = len(cols)
    A = np.array(cols).T if nC else np.zeros((6, 0))
    sc = np.r_[np.full(3, 1 / 0.05), np.ones(3)]
    r = linprog(np.r_[np.zeros(nC), sc, sc], A_eq=np.hstack([A, np.eye(6), -np.eye(6)]), b_eq=-wb,
                bounds=[(l, None) for l in lb] + [(0, None)] * 12, method='highs')
    sl = r.x[nC:nC + 6] - r.x[nC + 6:]
    fs, ms = np.linalg.norm(sl[3:]), np.linalg.norm(sl[:3])
    ok = fs <= 0.02 * W + 1e-5 and ms <= 0.02 * W * 0.05 + 1e-6
    return ok, sl


def settle_iter(D, b, res, wb, gdir, zero_mu=False, mu_scale=1.0, nmax=5, dmax=3.0):
    """Quasi-static settling of an unheld body: move to the first stop, rebuild its contacts, test again.
    -> dict(verdict 'оседает'|'падает'|'опрокидывается'|'неустойчиво', path [(move, amount, hit)], total_mm, total_deg)."""
    T = np.eye(4); path = []; tot_mm = tot_deg = 0.0
    W = max(D['m'][b] * U.G, 1e-6)
    sl = np.r_[np.array(res['slack_M']) * W * 0.05, np.array(res['slack_F']) * W]
    jextra = []
    for ba, bb, rws in D['joints']:
        if b in (ba, bb):
            jextra += [np.r_[wo, wv] for wo, wv in rws]
    for it in range(nmax):
        F = -sl[3:]; Mo = -sl[:3]
        if np.linalg.norm(F) >= 0.3 * np.linalg.norm(Mo) / 0.05 * 0.05 and np.linalg.norm(F) > 1e-9:
            d = F / np.linalg.norm(F)
            dist, hit = probe(D, b, trans=d, dmax=dmax, T0=T)
            if dist is None:
                return dict(verdict='падает', path=path + [('сдвиг', d.round(2).tolist(), None, None)], total_mm=tot_mm, total_deg=tot_deg)
            T = _xf(None, None, d * dist) @ T; tot_mm += dist
            path.append(('сдвиг', d.round(2).tolist(), round(dist, 2), hit))
        else:
            ax = Mo / np.linalg.norm(Mo)
            c = (T[:3, :3] @ (D['c'][b] / U.MM)) + T[:3, 3]
            dist, hit = probe(D, b, rot=(ax, c), dmax=8.0, step=0.1, T0=T)
            if dist is None:
                return dict(verdict='опрокидывается', path=path + [('поворот', ax.round(2).tolist(), None, None)], total_mm=tot_mm, total_deg=tot_deg)
            R = rotm(ax, math.radians(dist)); T = _xf(None, R, c - R @ c) @ T; tot_deg += dist
            path.append(('поворот', ax.round(2).tolist(), round(dist, 2), hit))
        rows = body_contacts_at(D, b, T, key=(it, round(tot_mm, 3), round(tot_deg, 3)))
        # the weight acts at the moved centre
        cm = (T[:3, :3] @ (D['c'][b] / U.MM) + T[:3, 3]) * U.MM
        Fg = D['m'][b] * U.G * np.asarray(gdir, float)
        wsp = wb.copy()
        wsp[:3] = wsp[:3] - np.cross(D['c'][b], D['m'][b] * U.G * np.asarray(gdir, float)) + np.cross(cm, Fg)
        ok, sl = hold_rows(rows, wsp, W, zero_mu, mu_scale, jextra)
        if ok:
            return dict(verdict='оседает', path=path, total_mm=round(tot_mm, 2), total_deg=round(tot_deg, 2))
    return dict(verdict='неустойчиво', path=path, total_mm=round(tot_mm, 2), total_deg=round(tot_deg, 2))
