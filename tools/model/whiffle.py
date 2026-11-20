"""Whiffletree kinematics and tolerance check against the detent capture. Usage: python3 -I whiffle.py OUT_JSON"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import params as P

S = 6.0                 # input stroke of a latched bit, mm (cam lift)
L_LEVER = 24.0          # length of the floating summing levers, mm
RNG = np.random.default_rng(7)


def design(nbits, step_out):
    """Floating levers in a chain: y_k = (W_{k-1} y_{k-1} + w_k x_k) / W_k; output amplifier gain G."""
    w = [2 ** i for i in range(nbits)]
    W = sum(w)
    unit = S / W                       # tree output per unit of the code
    G = step_out / unit                # amplifier
    levers = []
    acc = w[0]
    for k in range(1, nbits):
        acc_new = acc + w[k]
        # division point measured from the accumulated end: fraction w_k/acc_new
        levers.append(dict(a=L_LEVER * w[k] / acc_new, b=L_LEVER * acc / acc_new))
        acc = acc_new
    return dict(w=w, W=W, unit=unit, G=G, levers=levers)


def output(d, code, bias_units, pert=None):
    """Output displacement (mm at the output member) for a code; pert: dict of random errors."""
    w = d['w']; n = len(w)
    bits = [(code >> i) & 1 for i in range(n)]
    x = [S * b for b in bits]
    if pert:
        x = [xi + pert['stroke'][i] * b + pert['latch'][i] for i, (xi, b) in enumerate(zip(x, bits))]
    y = x[0]
    for k, lv in enumerate(d['levers'], start=1):
        a, b = lv['a'], lv['b']
        if pert:
            a += pert['hole'][k][0]; b += pert['hole'][k][1]
        y = (y * b + x[k] * a) / (a + b)          # output point at distance a from the accumulated end
        if pert:
            y += pert['play'][k]
    G = d['G']
    if pert:
        G *= 1 + pert['gain']
        y += pert['play_amp_in']
    out = G * (y - bias_units * d['unit'])
    if pert:
        out += pert['play_amp_out'] + pert['bias'] * d['G'] * d['unit']
    return out


def mc(d, codes, bias_units, step_out, capture, n=20000, sig=None):
    nb = len(d['w'])
    errs = []
    for _ in range(n):
        p = dict(stroke=RNG.normal(0, sig['stroke'], nb), latch=RNG.uniform(-sig['latch'], sig['latch'], nb),
                 hole={k: RNG.normal(0, sig['hole'], 2) for k in range(1, nb)},
                 play={k: RNG.uniform(-sig['play'], sig['play']) for k in range(1, nb)},
                 gain=RNG.normal(0, sig['gain']), play_amp_in=RNG.uniform(-sig['play'], sig['play']),
                 play_amp_out=RNG.uniform(-sig['play'], sig['play']) * 2, bias=RNG.normal(0, sig['bias_units']))
        e = [output(d, c, bias_units, p) - (c - bias_units) * step_out for c in codes]
        errs.append(max(abs(v) for v in e))
    errs = np.array(errs)
    return dict(p50=float(np.percentile(errs, 50)), p95=float(np.percentile(errs, 95)), p997=float(np.percentile(errs, 99.7)),
                miss=float(np.mean(errs > capture)), capture=capture)


SIG = dict(stroke=0.05, latch=0.05, hole=0.05, play=0.05, gain=0.005, bias_units=0.02)
CAL = dict(SIG, hole=0.0, gain=0.0, bias_units=0.0)        # after setting gain and zero with the adjusting screws
cap_rot = 0.48 * P.TAPE_PER_POS
cap_lift = 0.45 * P.RH
variants = []
for s_in in (6.0, 12.0):
    S = s_in
    rot = design(4, P.TAPE_PER_POS); lift = design(3, P.RH)
    for name, sg in (('как напечатано', SIG), ('после настройки', CAL), ('допуски вдвое хуже, после настройки', {k: 2 * v for k, v in CAL.items()})):
        variants.append(dict(S=s_in, name=name, G_rot=rot['G'], G_lift=lift['G'],
                             rot=mc(rot, range(P.NPOS), (P.NPOS - 1) / 2, P.TAPE_PER_POS, cap_rot, n=8000, sig=sg),
                             lift=mc(lift, range(P.NROWS), P.REST_ROW, P.RH, cap_lift, n=8000, sig=sg)))
S = 12.0
rot = design(4, P.TAPE_PER_POS); lift = design(3, P.RH)
assert all(abs(output(rot, c, 5) - (c - 5) * P.TAPE_PER_POS) < 1e-9 for c in range(11))
res = dict(S=S, rot=rot, lift=lift, sig=SIG, variants=variants, cap_rot=cap_rot, cap_lift=cap_lift)
json.dump(res, open(sys.argv[1], 'w'), indent=1, ensure_ascii=False)
for v in variants:
    print(v['S'], v['name'], round(v['G_rot'], 2), {k: round(x, 3) for k, x in v['rot'].items()}, {k: round(x, 3) for k, x in v['lift'].items()})
