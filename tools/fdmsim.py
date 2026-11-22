"""Simulate FDM printability of the slugs: morphological opening (lost thin ink) and closing (filled gaps).
Usage: python3 -I fdmsim.py FONT DATA_DIR OUT_DIR"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont
from glyphgeom import glyph_geom

font, data_dir, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
D = json.load(open(os.path.join(data_dir, 'codes.json')))
import glyphvar
F = TTFont(font); GS = glyphvar.VarGlyphSet(F.getGlyphSet(), D.get('synth'))
INCH = 25.4
EMS = [('1/6', INCH / 6), ('1/4', INCH / 4), ('1/3', INCH / 3), ('1/2', INCH / 2)]
NOZZLES = {'0.4': dict(pos=0.45, gap=0.35), '0.25': dict(pos=0.30, gap=0.25)}   # mm, assumptions

names = [(t['name'], t['glyph']) for t in D['tengwar']] + [(m['key'], m['glyph']) for m in D['marks']] \
    + [(n['name'], n['glyph']) for n in D['numerals'] + D['punct']]
geoms = {lbl: glyph_geom(GS, g) for lbl, g in names}
res = []
for noz, lim in NOZZLES.items():
    for emname, em in EMS:
        k = 1000.0 / em                       # font units per mm
        rp, rg = lim['pos'] / 2 * k, lim['gap'] / 2 * k
        worst_loss = worst_fill = 0; wl = wf = None; losses = []; fills = []
        for lbl, g in geoms.items():
            opened = g.buffer(-rp, 16).buffer(rp, 16)
            loss = 1 - opened.area / g.area
            closed = g.buffer(rg, 16).buffer(-rg, 16)
            fill = (closed.area - g.area) / g.area
            losses.append(loss); fills.append(fill)
            if loss > worst_loss: worst_loss, wl = loss, lbl
            if fill > worst_fill: worst_fill, wf = fill, lbl
        losses.sort(); fills.sort()
        res.append(dict(nozzle=noz, em=emname, em_mm=em, loss_med=losses[len(losses)//2], loss_max=worst_loss,
                        loss_worst=wl, fill_med=fills[len(fills)//2], fill_max=worst_fill, fill_worst=wf,
                        n_loss5=sum(1 for x in losses if x > 0.05), n_fill5=sum(1 for x in fills if x > 0.05)))
        print(noz, emname, f"loss med {res[-1]['loss_med']:.3f} max {worst_loss:.2f} ({wl}) >5%: {res[-1]['n_loss5']}; "
              f"fill med {res[-1]['fill_med']:.3f} max {worst_fill:.2f} ({wf}) >5%: {res[-1]['n_fill5']}")
json.dump(res, open(os.path.join(out, 'fdmsim.json'), 'w'), ensure_ascii=False, indent=1)
