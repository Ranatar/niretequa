"""LaTeX tables from fdmsim.json and stl/stamps.json. Usage: python3 -I tables_fdm.py GEN_DIR STL_DIR"""
import sys, os, json
gen, stl = sys.argv[1:3]
S = json.load(open(os.path.join(gen, 'fdmsim.json')))
rows = []
for r in S:
    rows.append(f"{r['nozzle'].replace('.', ',')} & {r['em']}'' & {r['em_mm']:.2f} & {100*r['loss_med']:.1f} & {r['n_loss5']} & "
                f"{100*r['fill_med']:.1f} & {r['n_fill5']}\\\\\n")
open(os.path.join(gen, 'tab_fdmsim.tex'), 'w').write(''.join(rows))
T = json.load(open(os.path.join(stl, 'stamps.json')))
names = {'sample': 'строки на квенья и синдарине', 'control': 'контрольный текст', 'sheet': 'все 86 литер (8 рядов по 11)'}
rows = []
for t in T:
    kind = t['file'].rsplit('_', 1)[1].replace('.stl', '')
    rows.append(f"\\texttt{{{t['file'].replace('_', '\\_')}}} & {names[kind]} & {t['em_mm']:.2f} & {t['pmin']:.2f} & "
                f"{t['W']:.0f}$\\times${t['H']:.0f}\\\\\n")
open(os.path.join(gen, 'tab_stamps.tex'), 'w').write(''.join(rows))
