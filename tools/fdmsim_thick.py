"""Loss/fill of thickened slugs under the FDM opening/closing model. Usage: python3 -I fdmsim_thick.py FONT DATA GEN"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont
from thicken import slug_geometry
font, data_dir, gen = sys.argv[1:4]
D = json.load(open(os.path.join(data_dir, 'codes.json')))
import glyphvar
F = TTFont(font); GS = glyphvar.VarGlyphSet(F.getGlyphSet(), D.get('synth'))
names = [t['glyph'] for t in D['tengwar']] + [m['glyph'] for m in D['marks']] + [n['glyph'] for n in D['numerals'] + D['punct']]
INCH = 25.4
out = []
for noz, em, pos, gap in (('0,4', INCH / 3, 0.45, 0.35), ('0,25', INCH / 4, 0.30, 0.25)):
    k = 1000 / em; rp, rg = pos / 2 * k * 0.98, gap / 2 * k
    L, Fl, growth = [], [], []
    for g in names:
        th, orig = slug_geometry(GS, g, em, pos)
        L.append(1 - th.buffer(-rp, 16).buffer(rp, 16).area / th.area)
        Fl.append((th.buffer(rg, 16).buffer(-rg, 16).area - th.area) / th.area)
        growth.append(th.area / orig.area - 1)
    L.sort(); Fl.sort(); growth.sort()
    r = dict(nozzle=noz, em=em, loss_med=L[len(L)//2], loss_max=L[-1], n_loss5=sum(x > .05 for x in L),
             fill_med=Fl[len(Fl)//2], fill_max=Fl[-1], growth_med=growth[len(growth)//2], growth_max=growth[-1])
    out.append(r); print(r)
json.dump(out, open(os.path.join(gen, 'fdmsim_thick.json'), 'w'), indent=1)
open(os.path.join(gen, 'tab_fdmsim_thick.tex'), 'w').write(''.join(
    f"{r['nozzle']} & {r['em']:.2f} & {100*r['growth_med']:.0f} & {100*r['growth_max']:.0f} & {100*r['loss_med']:.1f} & "
    f"{100*r['loss_max']:.1f} & {r['n_loss5']} & {100*r['fill_max']:.1f}\\\\\n" for r in out))
