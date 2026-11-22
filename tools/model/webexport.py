"""Export the layout model for the browser viewer: meshes at rest with motion descriptors, key data, glyph paths.
Usage: python3 -I webexport.py OUT_JSON"""
import sys, os, json, math, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from fontTools.pens.svgPathPen import SVGPathPen
import params as P
import parts as PT
import data as D
import geo
import links as LK

st = PT.State()
ps = PT.build(st)
keys = {k['n']: k for k in PT.key_list()}
Q = 0.02    # mm per int16 step


def wtree_motion(n):
    """Descriptor of a part of the selection unit; the page recomputes the tree pose (bits, drive phase) itself."""
    for name, t in PT.TREE.items():
        if not n.startswith(name + ' ') and not n.startswith('lift '):
            continue
        if n.startswith('lift ') and name != 'lift':
            continue
        sel = t['sel']; tr = sel['tree']; amp = sel['amp']; sd = t['dir']
        y_amp = t['y_amp'] if t['y_amp'] is not None else PT.SLIDER_Y0
        yT = t['y_tree']
        rest = n[len(name) + 1:]
        if rest.startswith('bit slider'):
            return dict(t='wt', tr=name, w='bit', i=t['bits'].index(rest.split()[-1]))
        if rest.startswith('latch pin'):
            b = rest.split()[-1]
            return dict(t='wt', tr=name, w='pin', i=t['bits'].index(b), b=b)
        if rest.startswith('node slider'):
            return dict(t='wt', tr=name, w='node', i=int(rest.split()[-1]))
        if rest.startswith('summing lever'):
            k = int(rest.split()[-1])
            return dict(t='wt', tr=name, w='lev', i=k, xa=tr['n'][k - 1], xb=tr['b'][k], y=yT)
        if rest == 'amplifier':
            return dict(t='wt', tr=name, w='amp', xa=amp['x_out'], xb=amp['x_F'], y=y_amp)
        if rest == 'fulcrum slide':
            return dict(t='wt', tr=name, w='fs')
        if rest == 'drive bail':
            return dict(t='wt', tr=name, w='bail')
        if rest == 'drive link':
            return dict(t='wt', tr=name, w='link')
        if rest == 'drive bellcrank':
            g = PT.drive_bc_geom(name)
            return dict(t='wt', tr=name, w='bc', p=[g['yp'], g['zp']], L=g['L'])
        if rest in ('output slider', 'output pin'):
            return dict(t='wt', tr=name, w='out')
        if rest == 'bellcrank':
            hb = PT.LIFT_BC_H
            return dict(t='wt', tr=name, w='obc', p=[P.AXIS_Y + hb, PT.SL_PIN_Z - hb], h=hb)
        if rest == 'push rod':
            return dict(t='wt', tr=name, w='push')
    return dict(t='unit', s='unit')


ESC_PARTS = {'escapement rod Y': 'rodY', 'escapement bellcrank': 'bc', 'escapement rod X': 'rodX', 'escapement stop': 'stop',
             'W wire clamp': 'rodY', 'W latch rack': 'rodY'}     # rev. 0.10: the W wire's clamp and the latch strip ride rod Y


ESC2 = {'escdog': 'dog', 'backB': 'B', 'backK': 'K', 'escM': 'M', 'rockbksp': 'rock', 'rockback': 'rock', 'pmu': 'fixed'}


def motion(p):
    n, m = p.name, p.mov
    # rev. 0.9c: the rebuilt escapement and the service keys' rockers
    if m in ESC2:
        s_ = ESC2[m]
        if s_ == 'fixed':
            return dict(t='fixed')
        if s_ == 'M':
            return dict(t='esc2', s={'memory coupling wedge': 'wedge'}.get(n, 'M'))
        if s_ == 'B' and n == 'back pawl':
            return dict(t='esc2', s='pawl')
        if s_ == 'rock':
            key = m[4:]
            return dict(t='esc2', s='link' if n.endswith('link') else 'rock', k=key)
        return dict(t='esc2', s=s_)
    if 'tail pin' in n and m.startswith('key'):
        kn = int(m[3:]); k = keys[kn]
        return dict(t='lever', n=kn, L=P.LEVER_PIVOT_Y - k['y'])
    if n in ('escapement stop', 'escapement stop finger'):
        return dict(t='esc2', s='U' if n == 'escapement stop' else 'Uf')
    if n == 'escapement tape':
        return dict(t='fixed')
    if n == 'detent link':
        return dict(t='unit', s='detlink')
    if n == 'ribbon link':
        return dict(t='ribbon', s='vib')
    if m == 'wtree':
        return wtree_motion(n)
    if m in ('stopbc', 'stopcar', 'stopfin', 'nsel', 'orodA', 'orodAf', 'orock', 'orodB', 'obc'):
        return dict(t='stops', s=m)
    if m == 'orodS':
        return dict(t='stops', s=m, y0=-262.0, L=10.0)
    # rev. 0.10: the reading from the shuttle
    if m.startswith('feel') and m != 'feelbar':
        return dict(t='feel', ch=m[4:])
    if m == 'feelbar':
        return dict(t='feelbar')
    if m.startswith('slide') and m[5:] in ('B', 'C'):
        return dict(t='rslide', b=m[5:])
    if m == 'readrocker':
        return dict(t='readrocker', p=list(PT.READ_PIV))
    # rev. 0.11: the idle cycle's locks (pins slide, levers turn; the hammer lock rides the U-frame)
    if m in ('readlock', 'hammerlock'):
        g = PT.READ_LOCK if m == 'readlock' else PT.HAM_LOCK
        s_ = 'read' if m == 'readlock' else 'hammer'
        if n.endswith('pin'):
            return dict(t='lockpin', s=s_, d=-g['travel'] if s_ == 'read' else -g['travel'])
        L = g['x_in'] + g['travel'] + g['L'] + 1.2
        if s_ == 'read':
            return dict(t='locklever', s=s_, a='z', p=[L, g['y'] + 1.0 - PT.LOCK_LEVER_R], ang=PT.lock_phi(g['travel']))
        return dict(t='locklever', s=s_, a='y', p=[L, g['z'] - 1.0 - PT.LOCK_LEVER_R], ang=-PT.lock_phi(g['travel']))
    if m.startswith('kspring'):                     # rev. 0.14b: a key's return spring, compressed by its lever
        kn = int(m[7:]); k = keys[kn]
        z0 = PT.KRS_BAR_Z[1]
        return dict(t='kspring', n=kn, L=P.LEVER_PIVOT_Y - k['y'], z0=z0, L0=PT.krs_top(k, 0.0)[0] - z0,
                    dy=PT.KRS_Y - P.LEVER_PIVOT_Y, dz=P.LEVER_Z0 - (P.LEVER_Z0 + P.LEVER_Z1) / 2, zc=(P.LEVER_Z0 + P.LEVER_Z1) / 2)
    if m.startswith('spring'):
        return dict(t='fspring', b=m[6:], z0=PT.TIER_BOT_Z[1], L=PT.SLEEVE_Z[0] - PT.TIER_BOT_Z[1])
    if m.startswith('follow'):
        if n in ESC_PARTS:
            return dict(t='escl', s=ESC_PARTS[n])
        return dict(t='follow', b=m[6:])
    if n == 'escapement stop':
        return dict(t='escl', s='stop')
    if m == 'lock':
        return dict(t='lock')
    if m == 'tier':
        return dict(t='tier')
    if n == 'hammer sear':                                  # rev. 0.14: the sear's turn by whole degrees of the cycle
        return dict(t='sear', p=list(PT._polar(*PT.SEAR_PIV)))
    if m == 'cock':
        return dict(t='unit', s='cock_lever' if n == 'hammer cocking lever' else 'cock')
    if n.startswith('return rocker ') and n.split()[2] in PT.RET:   # rev. 0.14: balance beam and return push rod
        k = n.split()[2]
        return dict(t='retrocker', k=k, p=[PT.RET[k]['xp'], PT.RET[k]['zp']])
    if n.startswith('return rod '):
        return dict(t='retrod', k=n.split()[2])
    if n in ('row detent wedge', 'row detent roller'):     # rev. 0.9.3: the roller rides on the wedge
        return dict(t='unit', s='rowwedge')
    if n == 'rotate tape return':                           # rev. 0.14: the return run is drawn in place
        return dict(t='unit', s='unit')
    if n == 'rotate tape':                                  # rev. 0.9.3: the band stretches from the pulley to the clamp
        return dict(t='unit', s='tapeband')
    if n == 'detent link':
        return dict(t='unit', s='unit')
    if m.startswith('key'):
        kn = int(m[3:]); k = keys[kn]
        if n.startswith('lever'):
            return dict(t='lever', n=kn, L=P.LEVER_PIVOT_Y - k['y'])
        return dict(t='keyz', n=kn)
    if m == 'release':                              # rev. 0.11: the carriage release key
        import escape as E_
        g = PT.REL_KEY
        return dict(t='release', p=[g['y'], g['z']], ang=math.degrees(math.asin(E_.REL_LIFT / g['h'])))
    if n.startswith('margin stop'):                 # rev. 0.11: the margin stops ride the carriage, set by the page
        return dict(t='marg', s=n[-1])
    if m.startswith('selS'):                       # rev. 0.11: the pushers of the space levers
        return dict(t='pusherS', n=int(m[4:]))
    if m.startswith('sel'):
        return dict(t='pusher', c=int(m[3:]))
    if m.startswith('bit'):
        return dict(t='bit', b=m[3:])
    if m == 'ribbon':
        return dict(t='ribbon', s='vib' if n == 'ribbon vibrator' else 'strip')
    if m.startswith('bail'):
        if n.startswith('sector'):
            return dict(t='sector', b=m[4:])
        return dict(t='bail', b=m[4:])
    if p.group in ('uframe', 'shuttle', 'hammer') or m in ('uframe', 'detent', 'tape', 'lift', 'collar', 'hammer', 'shuttle', 'drum'):
        sub = {'shuttle': 'shuttle', 'drum': 'drum', 'tape': 'tape', 'lift': 'fork', 'collar': 'collar', 'detent': 'detent', 'hammer': 'hammer'}.get(m, 'unit')
        if n == 'hammer axle':
            sub = 'unit'
        return dict(t='unit', s=sub)
    if m == 'cycle':
        if n.startswith('cam rod'):
            kind = n.split()[-1]
            return dict(t='camrod', k=kind)
        return dict(t='cyc')
    if m == 'carriage':
        return dict(t='car')
    if m == 'esc':
        return dict(t='esc')
    if n == 'governor fan' or n == 'governor pinion' or n == 'governor arbor':
        return dict(t='gov')
    if n in TRAIN:
        return TRAIN[n]
    return dict(t='fixed')


# the motor train turns with the cycle shaft (k = turns per cycle-shaft turn, sign = sense);
# the winding side (arbor, winding gear, crank) turns only when the spring is wound
_ax = PT.train_axes()
_ZG = PT.ZG
_k2 = _ZG['bevpin'] / _ZG['bevel']                  # int2 shaft
_k1 = _k2 * _ZG['pin'] / _ZG['int1']                 # int1 shaft
_kb = _k1 * _ZG['pin'] / _ZG['barrel']               # barrel
_zlay = _ax['int2'][1]
_yw, _zw = _ax['barrel'][0], _ax['barrel'][1] + 1.5 * (54 + 18) / 2
TRAIN = {
    'bevel cycle 1:1': dict(t='rot', a='x', p=list(PT.CYC), k=-1.0),
    'bevel lay 1:1': dict(t='rot', a='y', p=[PT.X_LAY, _zlay], k=1.0),
    'lay shaft': dict(t='rot', a='y', p=[PT.X_LAY, _zlay], k=1.0),
    'bevel pinion 12': dict(t='rot', a='y', p=[PT.X_LAY, _zlay], k=1.0),
    'bevel gear 24': dict(t='rot', a='x', p=list(_ax['int2']), k=_k2),
    'int2 shaft': dict(t='rot', a='x', p=list(_ax['int2']), k=_k2),
    'int2 pinion': dict(t='rot', a='x', p=list(_ax['int2']), k=_k2),
    'int1 gear': dict(t='rot', a='x', p=list(_ax['int1']), k=-_k1),
    'int1 shaft': dict(t='rot', a='x', p=list(_ax['int1']), k=-_k1),
    'int1 pinion': dict(t='rot', a='x', p=list(_ax['int1']), k=-_k1),
    'barrel gear': dict(t='rot', a='x', p=list(_ax['barrel']), k=_kb),
    'spring barrel': dict(t='rot', a='x', p=list(_ax['barrel']), k=_kb),
    'barrel arbor': dict(t='wind', a='x', p=list(_ax['barrel']), k=1.0),
    'winding gear': dict(t='wind', a='x', p=list(_ax['barrel']), k=1.0),
    'winding pinion': dict(t='wind', a='x', p=[_yw, _zw], k=-3.0),
    'winding crank': dict(t='wind', a='x', p=[_yw, _zw], k=-3.0),
}


# geometry: quantised vertices (uint16 x 3, step Q from the part's own corner) and triangle indices, packed into one
# binary file; identical shapes (key caps, grub screws, bars...) are stored once and shared
out_parts, geoms, blob, seen = [], [], bytearray(), {}
for p in ps:
    V, F = geo.to_arrays(p.mesh)
    if len(F) == 0:
        continue
    o = V.min(0)
    q = np.round((V - o) / Q).astype(np.int32)
    assert q.max() < 65535
    pos = q.astype(np.uint16).tobytes()
    idx = F.astype(np.uint16 if len(V) < 65536 else np.uint32)
    key = pos + idx.tobytes()
    if key not in seen:
        while len(blob) % 4:
            blob.append(0)
        seen[key] = len(geoms)
        geoms.append([len(blob), len(V), int(F.size), bool(idx.dtype == np.uint32)])
        blob += pos
        while len(blob) % 4:
            blob.append(0)
        blob += idx.tobytes()
    out_parts.append(dict(n=p.name, g=p.group, c=[int(v) for v in p.color], k=p.kind, mt=p.mat, m=motion(p),
                          o=[round(float(v), 3) for v in o], geo=seen[key]))
open(os.path.splitext(sys.argv[1])[0] + '.bin', 'wb').write(bytes(blob))

# glyph outlines (font units, y up)
gs = D.GLYPHSET
names = set()
for it in D.ITEMS.values():
    names.add(it['glyph'])
    if it.get('mark'):
        names.add(it['mark'])
from fontTools.pens.boundsPen import BoundsPen
paths, bbox, cps = {}, {}, {}
for nm in sorted(names):
    pen = SVGPathPen(gs)
    gs[nm].draw(pen)
    paths[nm] = pen.getCommands()
    bp = BoundsPen(gs)
    gs[nm].draw(bp)
    bbox[nm] = [round(v) for v in (bp.bounds or (0, 0, 0, 0))]


def item_json(k):
    if k is None:
        return None
    it = D.ITEMS[k]
    d = dict(kind=it['kind'], label=it.get('label', ''), glyph=it['glyph'], ax=it['ax'], w=it.get('w', 0))
    if it['kind'] in D.ADV:
        d.update(a=it['a'], b=it['b'], c=it['c'])
        if it['kind'] == 'C':
            d.update(mark=it['mark'], max=D.MARK_AX[it['mark']])
    else:
        d.update(below=bool(it.get('below')))
    return d


kj = []
for k in PT.key_list():
    e = dict(n=k['n'], id=k['id'], kind=k['kind'], r=k['r'], c=k['c'], label=k['label'])
    if k['kind'] == 'char':
        lo, up = D.ROWS[k['r']][k['c']]
        e.update(lo=item_json(lo), up=item_json(up))
    kj.append(e)

C = dict(U=P.U, EM=P.EM, AXIS_Y=P.AXIS_Y, STEP_DEG=P.STEP_DEG, NPOS=P.NPOS, NROWS=P.NROWS, RH=P.RH, HOME_ROW=P.HOME_ROW, REST_ROW=P.REST_ROW, ROW_CODE=[P.ROW_CODE[r] for r in range(4)], RIB_DROP=P.RIBBON_DROP, VIB_X=PT.VIB_X,
         TAPE=P.TAPE_PER_POS, TAPEBAND=[P.AXIS_Y, PT.SLIDER_Y0 - 8.0], PIVOT=[P.LEVER_PIVOT_Y, (P.LEVER_Z0 + P.LEVER_Z1) / 2], KEY_TRAVEL=P.KEY_TRAVEL,
         TAIL=P.LEVER_TAIL_Y, SECT=list(PT.SECT_SHAFT), FORK=[-150.0, PT.FORK_Z + 2], HAMMER=list(P.HAMMER_PIVOT),
         CYC=list(PT.CYC), CAM_LIFT=PT.CAM_LIFT, CYCLE=P.CYCLE, ESC=list(PT.ESC), CAR0=P.CAR_X_START, ZP=P.ZP,
         TIER=P.TIER_SHIFT, TP=P.TP, K=P.K_STEP, WOFF=P.W_OFFSET, LIFT_MIN=PT.LIFT_MIN, PAPER=[-108.0, 108.0],
         ROLLER=list(P.ROLLER), LINE=P.LINE_LEN, CAREND=P.CAR_X_END, RACKP=PT.RACK_PITCH, BITS=list(PT.BIT_Y.keys()), MARKREF=P.MARK_REF_U,
         GOV=(PT.ZG['gov'] / PT.ZG['govpin']), YD=PT.CYC[0] + (PT.ZG['gov'] + PT.ZG['govpin']) / 2,
         # rev. 0.9.2: what each block carries in each row: the page prints what is under the hammer, not the key's item
         LAYOUT=[[item_json(k) for k in row] for row in D.shuttle_layout()])
def _esc2():
    """rev. 0.9c: numbers the page needs to move the escapement (machine frame; the design frame is mirrored)."""
    import escape as E, numpy as np
    pv = E.P2(25.0, 13.0)
    rock = {}
    for key, n in (('bksp', 46), ('back', 47)):
        fs = [i / 20 for i in range(21)]
        rock[key] = dict(xa=E.ROCK['xa'][key], z=E.ROCK['z'], deg=[E.rocker_rot_deg(key, E.rocker_phi(key, f)) for f in fs],
                         A=[[round(v, 3) for v in E.rocker_ball(key, E.rocker_phi(key, f))] for f in fs],
                         stud=list(E.STUD[key]), sz=E.STUD_Z[key])
    lifts = [E.dog_lift(E.PITCH * i / 24) for i in range(24)]
    return dict(c=list(E.ESC), pitch=E.PITCH, bksp=E.BKSP_DEG, catch=E.B_CATCH, drop=E.B_DROP, play=E.M_PLAY,
                lift=-E.pawl_lift_angle(), pv=[-pv[0], pv[1]], rock=rock, dog=lifts, uw=[-math.cos(math.radians(-6.0)) * 0 + math.cos(math.radians(-6.0)), math.sin(math.radians(-6.0))],
                wedge=4.6)


# rev. 0.8 links: whiffletrees, followers, escapement link, hammer cocking, row wedge, lock comb
_E = LK.escape_link()
_ys, _zs = PT.SECT_SHAFT
_yroll = _ys - LK.FOLLOW_R * math.sin(math.radians(LK.THETA0))
C.update(
    TREES={nm: dict(bits=t['bits'], b=t['sel']['tree']['b'], n=t['sel']['tree']['n'], G=t['sel']['amp']['G'],
                    delta=t['sel']['amp']['delta'], dir=t['dir']) for nm, t in PT.TREE.items()},
    S=PT.S_STROKE, SLIDER_Y0=PT.SLIDER_Y0,
    FOLLOW=dict(R=LK.FOLLOW_R, H0=LK.H0, TH0=LK.THETA0, AX=list(PT.SECT_SHAFT)),
    ESCL=dict(px=PT.ESC_ROD_X + 19.1, py=116.05 - _E['r_a'] - 19.1, ra=19.1, wheel=list(PT.ESC)),
    ESC2=_esc2(),
    RAMP=PT.RAMP, DET_RISE=PT.DET_RISE,
    READ=dict(C0=P.READ_C0, K=P.READ_K, TRAVEL=P.READ_TRAVEL, RAMP=list(P.READ_RAMP), CAM=PT.READ_CAM_LIFT,
              CH=list(P.READ_CH), ROCK=[round(PT.read_rocker_angle(PT.State(cycle=float(a))), 3) for a in range(361)]),
    COCK=dict(rc=LK.hammer_geom()['r_cock'], lift=PT.CAM_LIFT['hammer']),
    # rev. 0.14: hammer, cocking lever and sear by whole degrees (the lever's lip governs the hammer's return)
    HAM=dict(COCK=[round(PT.cam_lift('cock', float(a)), 5) for a in range(361)],
             STRIKE=[round(PT.cam_lift('strike', float(a)), 5) for a in range(361)],
             SEAR=[round(math.degrees(PT.sear_beta(PT.cam_lift('cock', float(a)), PT.cam_lift('strike', float(a)))), 3) for a in range(361)]),
    RET={k: dict(ANG=[round(-(1 if PT.CAM_X[k] > PT.RET[k]['xp'] else -1) * math.degrees(PT.ret_psi(k, float(a)) - PT.ret_psi(k, 0.0)), 4)
                      for a in range(361)],
                 DZ=[round(PT.ret_pin_z(k, float(a)) - PT.ret_pin_z(k, 0.0), 4) for a in range(361)]) for k in PT.RET},
    ROWDET=dict(dir=PT.ROWDET_DIR, stroke=5.0), LOCK_SHIFT=PT.LOCK_SHIFT, SEL_RISE=PT.SEL_RISE,
    STOPS=dict(SBC=list(PT.SBC), BC_R=LK.BC_R, NSEL=list(PT.NSEL), N_IN=LK.N_IN, N_OUT=LK.N_OUT, N_SHIFT=LK.N_SHIFT, OBC=list(PT.OBC),
               O_BC_R=LK.O_BC_R, OROCK=list(PT.OROCK), ROCKER=list(LK.ROCKER), O_ARM=LK.O_ARM, O_CLAMP=LK.O_CLAMP))
# demo phrases as key strokes (key n, tier)
where = {}
for r, rw in enumerate(D.ROWS):
    for c, pair in enumerate(rw):
        for tier, it in enumerate(pair):
            if it is not None and it not in where:
                n, _ = D.key_slot(r, c)
                where[it] = (n, tier)
C['WHERE'] = {str(k): list(v) for k, v in where.items()}      # rev. 0.9c: sign -> (key, register) for the transcriber
G = D.G
demo = {}
for name, words in (('Elen síla lúmenn\u2019 omentielvo', G['QUENYA']), ('pedo mellon a minno', G['SINDARIN'])):
    seq = []
    for wi, wd in enumerate(words):
        if wi:
            seq.append([44, 0])
        for it in wd:
            if it in where:
                seq.append(list(where[it]))
    demo[name] = seq
MJ = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'gen', 'motor.json')))
C.update(MOTOR=dict(chars=round(min(MJ['chars_energy'], MJ['chars_turns'])), crank=MJ['crank_turns'], ratio=MJ['ratio'],
                    E_char=MJ['E_char'], U_use=MJ['spring']['U_use'], turns=MJ['spring']['turns'], t_avg=MJ['pick']['avg']))
res = dict(Q=Q, C=C, demo=demo, geoms=geoms, parts=out_parts, keys=kj, paths=paths, bbox=bbox, legends=D.LEGENDS)
json.dump(res, open(sys.argv[1], 'w'), ensure_ascii=False, separators=(',', ':'))
print(len(out_parts), 'parts,', len(geoms), 'shapes,', len(blob) / 1e6, 'MB of geometry')
