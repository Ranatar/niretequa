"""Build the TPM-2 layout model: checks, bill of materials, printable STL, assembly GLB and pictures.
Usage: python3 -I build.py OUT_DIR GEN_DIR"""
import sys, os, json, math, hashlib, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import trimesh
from manifold3d import Manifold
import params as P
import parts as PT
import geo, checks, render, relief, contacts, strike
import scenarios

out, gen = sys.argv[1:3]
os.makedirs(os.path.join(out, 'stl'), exist_ok=True)
for _f in os.listdir(os.path.join(out, 'stl')):          # no stale files from an earlier revision
    os.remove(os.path.join(out, 'stl', _f))
os.makedirs(os.path.join(out, 'renders'), exist_ok=True)
t0 = time.time()
REST = PT.State()
parts = PT.build(REST)
print('parts', len(parts))
_empty = [p.name for p in parts if p.mesh.is_empty() or p.mesh.volume() < 1e-6]
assert not _empty, f'empty parts: {_empty}'

# ------------------------------------------------------------------ checks
rest_int = checks.interferences(parts)
scen = scenarios.run(verbose=False)
nstates = {'shuttle': 11 * 21, 'slide': 3 * 3 * 5, 'carriage': 18, 'keys': 2 * 2 * len(PT.key_list()), 'cycle': 36 * 4, 'marks': (9 + 10) * 3 * 2,
           'escape': len(scenarios.escape_states()),
           'read': 2 * sum(1 for m in range(P.NPOS) for r in range(P.NROWS) if __import__('reader').cell_code(m, r) is not None),
           'idle': 36 * 3}
# rev. 0.9c: contact audit of the driving pairs
cont = contacts.run()
json.dump(cont, open(os.path.join(gen, 'contacts.json'), 'w'), ensure_ascii=False, indent=1)
open(os.path.join(gen, 'tab_contacts.tex'), 'w').write(contacts.tex(cont))
print('contacts', len(cont), 'failed', sum(1 for r in cont if not r['ok']))
# rev. 0.9.2: the blow for every item: chain closed, the ink is the item's own glyph, nothing foreign near the face
strk = strike.run()
json.dump(strk, open(os.path.join(gen, 'strike.json'), 'w'), ensure_ascii=False, indent=1)
strike.tex(strk, os.path.join(gen, 'tab_strike.tex'))
print('strike', len(strk), 'failed', sum(1 for r in strk if not r['ok']))
os.makedirs(os.path.join(out, 'renders'), exist_ok=True)
strike.figure(os.path.join(out, 'renders', 'strike.png'))
print('rest interferences', len(rest_int), {k: len(v) for k, v in scen.items()}, round(time.time() - t0))

# ------------------------------------------------------------------ BOM
DENS = 1.27e-3      # g/mm3, PETG
bom = {}
for p in parts:
    if p.bom is None:
        continue
    b = bom.setdefault(p.bom, dict(id=p.bom, kind=p.kind, group=p.group, mat=p.mat, note=p.note, qty=0, vol=0.0, names=[]))
    b['qty'] += 1; b['vol'] += p.mesh.volume(); b['names'].append(p.name)

# printable unique shapes (a part may be printed in several pieces)
uniq = {}
for p in parts:
    if p.kind != 'print':
        continue
    pcs = p.printable() if p.printable else p.mesh
    pcs = pcs if isinstance(pcs, list) else [pcs]
    for pi, m in enumerate(pcs):
        V = np.asarray(m.to_mesh().vert_properties)[:, :3]
        Vn = np.round(V - V.min(0), 2)
        Vn = Vn[np.lexsort(Vn.T[::-1])]
        sig = (p.bom, hashlib.md5(Vn.tobytes()).hexdigest())
        keep = p.printable is not None and p.bom not in ('comb', 'comb_space')
        u = uniq.setdefault(sig, dict(bom=p.bom, mesh=m, names=[], vol=m.volume(), keep=keep, piece=pi, npcs=len(pcs)))
        u['names'].append(p.name)
print('unique printable shapes', len(uniq))

fit_rows = []
SAFE = lambda t: ''.join(c if (c.isascii() and (c.isalnum() or c in '_+.-')) else '_' for c in t)
for i, (sig, u) in enumerate(sorted(uniq.items(), key=lambda kv: (kv[0][0], kv[1]['names'][0], kv[1]['piece']))):
    num_ = i + 1
    m = u['mesh']
    rot, dims, fits = checks.bed_fit(m, keep_up=u['keep'])
    mm = m.rotate((rot[0], rot[1], 0)).rotate((0, 0, rot[2]))
    b = mm.bounding_box(); mm = mm.translate((-b[0], -b[1], -b[2]))
    # rev. 0.9c: the running number debossed into the top face (or the face on the bed), and the one-body check
    mm, where = relief.number_part(mm, num_, bottom_only=u['bom'].startswith('case'))   # rev. 0.12: the case's faces stay clean
    bodies = len(mm.decompose())
    assert bodies == 1, f'{u["names"][0]}: {bodies} bodies'
    base = SAFE(u['names'][0].replace(' ', '_'))
    suf = f"_p{u['piece'] + 1}" if u['npcs'] > 1 else ''
    fn = f"{num_:03d}_{SAFE(u['bom'])}__{base}{suf}" + (f"_x{len(u['names'])}" if len(u['names']) > 1 else '') + '.stl'
    V, F = geo.to_arrays(mm)
    trimesh.Trimesh(V, F, process=False).export(os.path.join(out, 'stl', fn))
    fit_rows.append(dict(num=num_, file=fn, bom=u['bom'], qty=len(u['names']), dims=[round(float(d), 1) for d in dims], fits=bool(fits),
                         vol=round(float(u['vol']), 0), mass=round(float(u['vol']) * DENS, 1), first=u['names'][0], names=u['names'],
                         number_on=where, bodies=bodies))
json.dump(fit_rows, open(os.path.join(out, 'printable.json'), 'w'), ensure_ascii=False, indent=1)
# rev. 0.12: the device plaque in colours: one STL per colour, all in the plaque's frame (load them as parts of one object)
os.makedirs(os.path.join(out, 'stl', 'device'), exist_ok=True)
for _f in os.listdir(os.path.join(out, 'stl', 'device')):
    os.remove(os.path.join(out, 'stl', 'device', _f))
_pl = [p for p in parts if p.name == 'case device plaque'][0]
_b = np.array(_pl.mesh.bounding_box())
_dev = [_pl] + [p for p in parts if p.name.startswith('case device ') and p.kind == 'inlay']
for i, p in enumerate(_dev):
    V, F = geo.to_arrays(p.mesh.translate((-_b[0], -_b[1], -_b[2])))
    hexc = '%02x%02x%02x' % tuple(p.color)
    trimesh.Trimesh(V, F, process=False).export(os.path.join(out, 'stl', 'device', f'device_{i:02d}_{hexc}.stl'))
# rev. 0.9c: assembly sheets and the table of part numbers
import assembly
FONT_B = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'fonts', 'PT_Sans-Web-Bold.ttf')
asm = assembly.sheets(parts, fit_rows, os.path.join(out, 'renders'), FONT_B)
json.dump(asm, open(os.path.join(out, 'assembly.json'), 'w'), ensure_ascii=False, indent=1)
grp_of = {p.name: p.group for p in parts}
TT = lambda t: t.replace('_', '\\_').replace('&', '\\&').replace('#', '\\#')
with open(os.path.join(gen, 'tab_part_numbers.tex'), 'w') as f_:
    for r in fit_rows:
        where = {'top': 'сверху', 'bottom': 'снизу', None: '—'}[r['number_on']]
        g_ = assembly.TITLES.get(grp_of.get(r['first'], ''), '')
        f_.write(f"{r['num']} & \\texttt{{\\footnotesize {TT(r['first'])}}} & {r['qty']} & {g_} & {where} \\\\\n")
print('assembly sheets', len(asm), round(time.time() - t0))
print('stl written', round(time.time() - t0))

# ------------------------------------------------------------------ GLB of the assembly
scene = trimesh.Scene()
for p in parts:
    V, F = geo.to_arrays(p.mesh)
    if len(F) == 0:
        continue
    tm = trimesh.Trimesh(V / 1000.0, F, process=False)
    tm.visual = trimesh.visual.ColorVisuals(tm, face_colors=np.tile(np.r_[p.color, 255], (len(F), 1)).astype(np.uint8))
    scene.add_geometry(tm, node_name=p.name, geom_name=p.name)
scene.export(os.path.join(out, 'tpm2_assembly.glb'))

# ------------------------------------------------------------------ pictures
def objs(ps, clip=None, hide=(), case=False):
    res = []
    for i, p in enumerate(ps):
        if any(h == p.group or p.name.startswith(h) for h in hide):
            continue
        if p.group == 'case' and not case:          # rev. 0.12: the mechanism's pictures are drawn without the case
            continue
        m = p.mesh
        if clip is not None:
            m = m ^ clip
            if m.is_empty():
                continue
        V, F = geo.to_arrays(m)
        res.append((V, F, p.color, i))
    return res


def save(img, name, crop=False):
    if crop:                                   # trim the white margins around a detail view
        import PIL.ImageOps
        img = PIL.ImageOps.expand(img.crop(PIL.ImageOps.invert(img.convert('L')).getbbox()), 24, 'white')
    img.save(os.path.join(out, 'renders', name + '.png'))


views = {}
img, _ = render.render(objs(parts), ((-560, -760, 640), (0, -140, 120)), W=2000, H=1500); save(img, 'iso_front')
img, _ = render.render(objs(parts), ((640, 680, 600), (0, -80, 130)), W=2000, H=1500); save(img, 'iso_back')
half = geo.box(-14, 0, -500, 300, -10, 500)
img, _ = render.render(objs(parts, clip=half), ((900, 0, 170), (0, -130, 170)), W=2200, H=1100, light=(0.6, -0.3, 0.8))
save(img, 'section_x0')
sel = PT.build(PT.State(pos=9.0, row=6.0, detent=1.0))
HIDE_UNIT = ('carriage', 'paper', 'keys', 'plates', 'bails', 'sectors', 'ribbon', 'frame', 'esc', 'hammer', 'U-frame arm', 'MGN12H',
             'levers', 'drive', 'select')
img, _ = render.render(objs(sel, hide=HIDE_UNIT), ((380, 300, 420), (20, -50, 150)), W=1800, H=1400); save(img, 'print_unit')
img, _ = render.render(objs(sel, hide=HIDE_UNIT + ('shuttle', 'type block', 'guide rod', 'shuttle bushing')),
                       ((250, 120, 300), (40, -40, 112)), W=1800, H=1200); save(img, 'unit_top')
drv = [p for p in parts if p.group in ('drive', 'select', 'sectors') or p.name.startswith(('frame side +1', 'beam'))]
img, _ = render.render(objs(drv), ((560, -520, 380), (150, -140, 40)), W=2000, H=1400); save(img, 'drive')
img, _ = render.render(objs(parts, hide=('uframe', 'shuttle', 'hammer', 'carriage', 'paper', 'ribbon', 'esc', 'keys', 'frame', 'drive')),
                       ((-300, -560, -260), (0, -280, 40)), W=1800, H=1200, light=(0.3, -0.5, -0.8)); save(img, 'code_under')
sh = [p for p in parts if p.group == 'shuttle' and ('type block' in p.name or p.name == 'shuttle')]
img, _ = render.render(objs(sh), ((180, 260, 330), (0, -60, 225)), W=1600, H=1500); save(img, 'shuttle')
# rev. 0.8: pictures of the links worked out
mid = PT.State(pos=8.0, row=5.0, bits=('r8', 'l1', 'l4'), cycle=90.0, detent=0.0)
HIDE_SEL = ('carriage', 'paper', 'keys', 'plates', 'bails', 'sectors', 'ribbon', 'frame', 'esc', 'hammer', 'levers', 'shuttle',
            'type block', 'shaft', 'guide rod', 'shuttle bushing', 'U-frame arm', 'select', 'drive')
img, _ = render.render(objs(PT.build(mid), hide=HIDE_SEL), ((0, -150, 420), (0, -10, 110)), W=2200, H=1300, light=(0.2, -0.4, 0.9))
save(img, 'select_unit')
fr = PT.build(PT.State(frames={'R': 16.0, 'W': 6.0, 'B': 4.0, 'C': 2.0}))
FR_KEEP = ('bails', 'sectors', 'levers')
img, _ = render.render(objs([p for p in fr if p.group in ('bails', 'sectors')], clip=geo.box(60, 200, -420, -150, -20, 120)),
                       ((520, -700, 260), (140, -300, 40)), W=2000, H=1400); save(img, 'frames')
rd = PT.build(PT.State(row=5.0, detent=1.0, bits=('l1', 'l4')))
img, _ = render.render(objs([p for p in rd if p.name.startswith(('lift fork', 'row detent', 'lift collar', 'lift push', 'lift bellcrank'))]),
                       ((-60, -330, 260), (-110, -70, 140)), W=1600, H=1200); save(img, 'row_detent')
hm = PT.build(PT.State(cock=1.0))
img, _ = render.render(objs([p for p in hm if p.name.startswith(('hammer', 'U-frame arm'))]),
                       ((180, 220, 300), (0, 60, 180)), W=1400, H=1300); save(img, 'hammer_cock')
lk = PT.build(PT.State(lock=1.0, pressed={14: 1.0}))
from PIL import Image
lps = [p for p in lk if p.name.startswith(('lever ', 'lock', 'ball race'))]
ims = []
for x in (PT.lever_x(14), PT.lever_x(15)):   # section through the pressed lever and its neighbour
    im, _ = render.render(objs(lps, clip=geo.box(x - 1.6, x + 1.6, -235, -160, 20, 75)), ((x - 400, -197, 48), (x, -197, 48)),
                          W=900, H=700, scale=9)
    ims.append(im)
img = Image.new('RGB', (1820, 700), 'white'); img.paste(ims[0], (0, 0)); img.paste(ims[1], (920, 0))
import PIL.ImageOps
img = img.crop(PIL.ImageOps.invert(img.convert('L')).getbbox()); img = PIL.ImageOps.expand(img, 20, 'white')
save(img, 'lock')
# rev. 0.8b: stops of the print unit (a mark below the line, memory c = 4) and the O link
st_m = PT.State(slide_u=12.0, frames={'O': 16.0, 'N': 16.0}, mem={'C': 4.0, 'B': 6.0})
pm = PT.build(st_m)
keep = ('stop', 'memory sleeve', 'memory pawls', 'sector axis', 'sector bracket', 'bail N', 'bail C', 'bail B', 'zero stop', 'slide return', 'U-frame base')
img, _ = render.render(objs([p for p in pm if p.name.startswith(keep)], clip=geo.box(125, 180, -345, -130, 30, 115)),
                       ((420, -560, 330), (150, -250, 75)), W=2000, H=1500)
save(img, 'stops', crop=True)
img, _ = render.render(objs([p for p in pm if p.name.startswith(('O ', 'W follower axis', 'bail O', 'lock bail guide -1', 'U-frame base'))],
                            clip=geo.box(-160, -100, -345, -150, 10, 112)), ((-560, -560, 300), (-125, -250, 60)), W=2000, H=1500)
save(img, 'olink', crop=True)
# rev. 0.9c: the escapement, at rest and at back-a-letter (w = 8)
import escape as ESCM
_T = 5.053 * math.radians(6.0); _c0 = P.CAR_X_START - 60 * _T
for _nm, _st, _eye in (('escapement', PT.State(car=_c0, esc_mem=8), ((-70, 40, 150), (0, 116, 70))),
                       ('escapement_back', PT.State(car=_c0 + 5.053 * math.radians(6 * 8 + ESCM.M_PLAY), pressed={47: 1.0}, esc_mem=8),
                        ((-60, 20, 10), (0, 116, 66)))):
    _ps = [p for p in PT.build(_st) if p.group == 'esc' and p.name not in ('escapement bracket', 'rocker bracket') and
           'rocker' not in p.name and 'link' not in p.name]
    img, _ = render.render(objs(_ps), _eye, W=1600, H=1300)
    save(img, _nm, crop=True)
# what the typist sees: before (rev. 0.7 rest: shuttle mid-way, ribbon at the line) and after
EYE = ((0.0, -720.0, 460.0), (0.0, 0.0, P.ZP + 20))
line = []
for k in range(5):
    V, F = geo.to_arrays(geo.box(-150, 24, -0.6, -0.4, P.ZP - 0.5 + k * 1.6 * P.EM, P.ZP + 0.5 + k * 1.6 * P.EM))
    line.append((V, F, (220, 30, 30), 9000 + k))
for name, st in (('view_before', PT.State(row=P.HOME_ROW, ribbon=1.0, car=P.CAR_X_START - 150)), ('view_after', PT.State(car=P.CAR_X_START - 150))):
    img, _ = render.render(objs(PT.build(st)) + line, EYE, W=2800, H=2000, persp=18)
    w, h = img.size
    save(img.crop((int(w * 0.28), int(h * 0.08), int(w * 0.74), int(h * 0.47))), name)
# rev. 0.12: the case
img, _ = render.render(objs(parts, case=True), ((-560, -760, 640), (0, -140, 120)), W=2000, H=1500); save(img, 'case_iso_front')
img, _ = render.render(objs(parts, case=True), ((640, 680, 600), (0, -80, 130)), W=2000, H=1500); save(img, 'case_iso_back')
img, _ = render.render(objs(parts, case=True), ((0.0, -720.0, 460.0), (0, -150, 140)), W=2000, H=1400, persp=30); save(img, 'case_typist')
_cp = [p for p in parts if p.group == 'case' and (p.name.startswith(('case fascia', 'case keyboard deck', 'case tower', 'case top tower', 'case device', 'case star grille'))
                                                    or p.name.startswith('cap ') or p.name.startswith('stem '))]
img, _ = render.render(objs([p for p in parts if p.group == 'case' and p.name.startswith('case fascia')], case=True),
                       ((0, -420, 160), (0, -236, 107)), W=2400, H=700, light=(-0.2, -0.8, 0.5)); save(img, 'case_fascia', crop=True)
img, _ = render.render(objs([p for p in parts if p.name.startswith('case device')], case=True), ((-201, -300.5, 600), (-201, -300.5, 140), (0, 1, 0)),
                       W=1400, H=1400, light=(-0.3, 0.3, 0.9)); save(img, 'case_device', crop=True)
print('renders', round(time.time() - t0))

# ------------------------------------------------------------------ numbers for the document
num = dict(parts=len(parts), unique_print=len(uniq), rest_interferences=len(rest_int), contacts=len(cont),
           contacts_failed=sum(1 for r in cont if not r['ok']), strike=len(strk), strike_failed=sum(1 for r in strk if not r['ok']),
           numbered=sum(1 for r in fit_rows if r['number_on']),
           numbered_top=sum(1 for r in fit_rows if r['number_on'] == 'top'),
           scen={k: len(v) for k, v in scen.items()}, nstates=nstates,
           footprint=[2 * P.FRAME_X, P.FRAME_Y1 - P.FRAME_Y0],
           height=round(max(p.mesh.bounding_box()[5] for p in parts), 1),
           extent=[[round(float(min(p.mesh.bounding_box()[i] for p in parts)), 1) for i in range(3)],
                   [round(float(max(p.mesh.bounding_box()[i + 3] for p in parts)), 1) for i in range(3)]],
           case_parts=sum(1 for p in parts if p.group == 'case' and p.kind == 'print'),
           case_inlays=sum(1 for p in parts if p.group == 'case' and p.kind == 'inlay'),
           case_mass_g=round(sum(p.mesh.volume() for p in parts if p.group == 'case') * DENS, 0),
           case_extent=[[round(float(min(p.mesh.bounding_box()[i] for p in parts if p.group == 'case')), 1) for i in range(3)],
                        [round(float(max(p.mesh.bounding_box()[i + 3] for p in parts if p.group == 'case')), 1) for i in range(3)]],
           device_colours=len(_dev) - 1, inscription=__import__('case').info(),
           print_mass_g=round(sum(b['vol'] for b in bom.values() if b['kind'] == 'print') * DENS, 0),
           not_fit=[r['file'] for r in fit_rows if not r['fits']])
json.dump(dict(numbers=num, bom=list(bom.values()), rest=rest_int, scen=scen), open(os.path.join(out, 'model.json'), 'w'),
          ensure_ascii=False, indent=1)
print(json.dumps(num, ensure_ascii=False, indent=1))
