"""rev. 0.11: the table of font sets (gen/fonts/<id>/report.json) for the document.
Usage: python3 -I fonttab.py GEN_DIR"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from fontsets import FONTSETS

gen = sys.argv[1]
f2 = lambda x: f'{x:.2f}'.replace('.', '{,}')
f1 = lambda x: f'{x:.1f}'.replace('.', '{,}')
rows, n_ok, worst_I = [], 0, 0.0
base = None
for fs in FONTSETS:
    fn = os.path.join(gen, 'fonts', fs['id'], 'report.json')
    if not os.path.exists(fn):
        continue
    R = json.load(open(fn))
    if fs['id'] == 'alcarin':
        base = R
    pr = R['profile'] or dict(scale=1.0, pad=[], shift=[], missing=[])
    shr = len(set(x[0] for x in (pr.get('shrunk') or []))) if 'shrunk' in pr else 0
    rg = R['ranges']
    rows.append(f"{R['name'].replace('Tengwar ', '')} & {f2(pr['scale'])} & {rg['w'][0]}--{rg['w'][1]} & {rg['b'][0]}--{rg['b'][1]} & "
                f"{rg['c'][0]}--{rg['c'][1]} & {len(pr.get('pad', []))} & {len(pr.get('shift', []))} & {shr} & "
                f"{f1(R['combs']['mass_g'])} & {f1(R['combs']['I_kgmm2'])} & {R['read']['n'] - R['read']['bad']}/{R['read']['n']} & "
                f"{R['strike']['n'] - R['strike']['bad']}/{R['strike']['n']}\\\\\n")
    n_ok += bool(R['ok'])
    worst_I = max(worst_I, R['combs']['I_kgmm2'])
open(os.path.join(gen, 'tab_fonts.tex'), 'w').write(''.join(rows))
mac = dict(fsN=str(len(rows)), fsOk=str(n_ok), fsIworst=f1(worst_I), fsIbase=f1(base['combs']['I_kgmm2']) if base else '?',
           fsIdelta=f1(worst_I - base['combs']['I_kgmm2']) if base else '?')
open(os.path.join(gen, 'fonts_num.tex'), 'w').write(''.join(f'\\newcommand\\{k}{{{v}}}\n' for k, v in mac.items()))
print(len(rows), 'sets,', n_ok, 'ok', mac)
