"""FDM profile of the TPM-2 estimates (rev. 0.4).
Usage: python3 -I analysis_fdm.py OUT_DIR
Code plates sit on a lever arm with travel T_p (larger than the 14 mm key travel); W encodes w-4."""
import sys, os, json, math, random

out = sys.argv[1]
INCH = 25.4
EM = INCH / 3
U = EM / 16
res = dict(em=EM, u=U)

# ---- code plate budget ----
RESET_END, MARGIN = 3.5, 0.5
VMAX = dict(w=16 - 4, b=8, c=9)          # W measured as w-4
rows = []; budget = []
for Tp in (16, 18, 20, 22):
    for k in (0.8, 1.0, 1.2):
        first = Tp - k * max(VMAX.values())
        ok = first >= RESET_END + MARGIN
        budget.append(dict(Tp=Tp, k=k, gw=Tp - k * VMAX['w'], gb=Tp - k * VMAX['b'], gc=Tp - k * VMAX['c'],
                           half=k / 2, ratio=Tp, ok=ok))   # rev. 0.5: plate under the key, key travel = Tp
CH = dict(Tp=16, k=1.0)
res['budget'] = budget; res['choice'] = CH
for b in budget:
    sel = b['Tp'] == CH['Tp'] and abs(b['k'] - CH['k']) < 1e-9
    f = (lambda s: r'\textbf{' + s + '}') if sel else (lambda s: s)
    rows.append(' & '.join(f(x) for x in [f"{b['Tp']}", f"{b['ratio']:.0f}", f"{b['k']:.1f}", f"{b['gw']:.1f}",
                                         f"{b['gb']:.1f}", f"{b['gc']:.1f}", f"{b['half']:.2f}",
                                         'да' if b['ok'] else 'нет']) + '\\\\\n')
open(os.path.join(out, 'tab_budget_fdm.tex'), 'w').write(''.join(rows))

# ---- gap tolerance ----
phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
half = CH['k'] / 2
rows = []
res['gap'] = []
for s in (0.05, 0.08, 0.10, 0.12, 0.15):
    p = 2 * (1 - phi(half / s)); pp = p * 3 * 1500
    res['gap'].append(dict(sigma=s, p=p, per_page=pp))
    rows.append(f"{s:.2f} & $\\pm${3*s:.2f} & {half/s:.1f} & {p:.1e} & {pp:.1e}\\\\\n".replace('e-0', 'e-').replace('e+0', 'e+'))
open(os.path.join(out, 'tab_gap_fdm.tex'), 'w').write(''.join(rows))

# ---- Monte Carlo with FDM tolerances ----
A = [
    ('рисунок литеры (печать блока)', 'sys', 0.030, 'per_glyph'),
    ('рисунок знака (печать блока)', 'sys', 0.030, 'per_glyph'),
    ('посадка блока литеры на челноке', 'sys', 0.040, 'per_pos'),
    ('посадка блока знака на челноке', 'sys', 0.040, 'per_pos'),
    ('фиксатор колеса челнока', 'rep', 0.030, 'strike2'),
    ('подача каретки (люфт передачи)', 'rep', 0.040, 'strike'),
    ('упор сектора (фиксатор)', 'sys', 0.030, 'per_value'),
    ('нулевой и рабочий упоры ползуна', 'rep', 0.025, 'strike'),
]
random.seed(20261111)
NM, NS = 400, 400
THR = 0.024 * EM          # same relative threshold as 0.1 mm at em = 1/6 inch


def mc(drop=None):
    errs = []
    for _ in range(NM):
        sysv = {i: [random.gauss(0, s) for _ in range({'per_glyph': 90, 'per_pos': 22, 'per_value': 10}[sc])]
                for i, (l, kd, s, sc) in enumerate(A) if kd == 'sys' and i != drop}
        for _ in range(NS):
            e = 0.0
            for i, (l, kd, s, sc) in enumerate(A):
                if i == drop:
                    continue
                if kd == 'sys':
                    e += random.choice(sysv[i]) * (1 if i % 2 == 0 else -1)
                else:
                    e += sum(random.gauss(0, s) for _ in range(2 if sc == 'strike2' else 1))
            errs.append(abs(e))
    errs.sort(); q = lambda p: errs[int(p * (len(errs) - 1))]
    return dict(p50=q(.5), p95=q(.95), p997=q(.997), share=sum(1 for x in errs if x > THR) / len(errs))


base = mc()
VARIANTS = [('как напечатано', {}),
            ('калибровка гнёзд блоков', {2: 0.015, 3: 0.015}),
            ('калибровка + стальные штифты и оси', {2: 0.015, 3: 0.015, 4: 0.012, 5: 0.020})]
A0 = list(A); vres = []
for vname, ov in VARIANTS:
    A[:] = [(l, kd, ov.get(i, s_), sc) for i, (l, kd, s_, sc) in enumerate(A0)]
    vres.append((vname, mc()))
A[:] = A0
res['variants'] = vres
open(os.path.join(out, 'tab_mc_fdm_var.tex'), 'w').write(''.join(
    f"{n} & {r['p50']:.3f} & {r['p95']:.3f} & {r['p997']:.3f} & {100*r['share']:.2f}\\,\\%\\\\\n" for n, r in vres))
sens = [(a[0], base['p95'] - mc(i)['p95']) for i, a in enumerate(A)]
res['mc'] = base; res['sens'] = sens; res['thr'] = THR
open(os.path.join(out, 'tab_mc_fdm.tex'), 'w').write(
    f"{base['p50']:.3f} & {base['p95']:.3f} & {base['p997']:.3f} & {THR:.2f} & {100*base['share']:.2f}\\,\\%\\\\\n")
open(os.path.join(out, 'tab_assume_fdm.tex'), 'w').write(''.join(
    f"{l} & {'сист.' if kd == 'sys' else 'случ.'} & {s:.3f} & {max(d, 0):.3f}\\\\\n" for (l, kd, s, sc), (_, d) in zip(A, sens)))
json.dump(res, open(os.path.join(out, 'analysis_fdm.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(dict(choice=[b for b in budget if b['Tp'] == CH['Tp'] and b['k'] == CH['k']], gap=res['gap'], mc=base,
                      thr=THR, sens=sens), ensure_ascii=False, indent=1))
