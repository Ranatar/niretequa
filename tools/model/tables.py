"""LaTeX tables for the layout model and the dynamics estimate. Usage: python3 -I tables.py GEN_DIR"""
import sys, os, json, re
from collections import defaultdict
gen = sys.argv[1]
M = json.load(open(os.path.join(gen, 'model', 'model.json')))
PR = json.load(open(os.path.join(gen, 'model', 'printable.json')))
MO = json.load(open(os.path.join(gen, 'motor.json')))
DY = json.load(open(os.path.join(gen, 'links.json')))['strength']
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import params as P
N = M['numbers']
f = lambda x, d=1: f'{x:.{d}f}'.replace('.', '{,}')


def w(name, s):
    open(os.path.join(gen, name), 'w').write(s)


# purchased and cut stock, grouped
bom = {b['id']: b for b in M['bom']}
rows = []
prof = sorted([(int(k[5:]), b['qty']) for k, b in bom.items() if k.startswith('2020x')], reverse=True)
rows.append(('профиль 2020 (алюминий)', sum(q for _, q in prof), ', '.join(f'{L} мм ×{q}' for L, q in prof)))
grubs = sorted([(int(k[6:].split('x')[1]), b['qty']) for k, b in bom.items() if k.startswith('grubM3x')])
rows.append(('установочный винт М3 с плоским концом', sum(q for _, q in grubs), ', '.join(f'×{L}: {q}' for L, q in grubs)))
bars = sorted([(int(k[5:]), b['qty']) for k, b in bom.items() if k.startswith('rod5x')])
rows.append(('стальной пруток 5 мм (планки рамок)', sum(q for _, q in bars), ', '.join(f'{L} мм ×{q}' for L, q in bars)))
simple = [('MGN12_300', 'линейная направляющая MGN12, 300 мм', 'опоры ползуна (U-рамы)'),
          ('MGN12H', 'каретка MGN12H', ''), ('MGN7_75', 'линейная направляющая MGN7, 75 мм', 'каретка ленты поворота'),
          ('MGN7H', 'каретка MGN7H', ''), ('rod8x460', 'калиброванный пруток 8 мм, 460 мм', 'направляющие каретки'),
          ('LM8UU', 'линейный подшипник LM8UU', 'каретка'), ('608', 'подшипник 608', 'вал челнока'),
          ('mainspring', 'заводная пружина 32×0,8 мм, около 6,3 м', 'граммофонного типа, с концевыми петлями'),
          ('rod10x100', 'вал 10 мм, 100 мм', 'ось барабана пружины'),
          ('rod8x380', 'вал 8 мм, 380 мм', 'цикловой вал'), ('bushing6', 'бронзовая втулка 6 мм', 'поводок челнока'),
          ('tape', 'стальная лента 5×0,1 мм', 'лента поворота, около 0,15 м'),
          ('rod3x40', 'пруток 3 мм, 40 мм', 'стержни выбора'), ('rod3x80', 'пруток 3 мм, 80 мм', 'толкатели кулачков'),
          ('rod4x280', 'пруток 4 мм, 280 мм', 'ось рычагов'), ('rod4x200', 'пруток 4 мм, 200 мм', 'промежуточный вал'),
          ('uframe_plate', 'плита Д16Т 326×188×6', 'основание печатающего узла, сверловка'),
          ('roller14', 'вал 6 мм с резиновой трубкой', 'подающий валик'), ('pinch7', 'прижимной ролик 7 мм', ''),
          ('pipe32x230', 'труба 30 мм, 230 мм', 'кассета бумаги'), ('spool', 'катушка ленты 13 мм', 'красящая лента')]
for k, name, note in simple:
    if k in bom:
        rows.append((name, bom[k]['qty'], note))
rods = sum(bom[k]['qty'] for k in bom if k in ('rod4x40', 'rod4x24', 'rod4x80', 'rod4x60', 'rod6x60', 'rod3x20') or k.startswith('rod6x1'))
rows.append(('пруток 3--6 мм, короткие оси', rods, 'оси секторов, молотка, спуска, передачи, поводок'))
sh = [k for k in bom if k.startswith('shaft8x')]
rows.append(('вал 8 мм', sum(bom[k]['qty'] for k in sh), 'вал челнока, ' + ', '.join(k[7:] + ' мм' for k in sh)))
covered = {k for k, _, _ in simple} | {k for k in bom if k.startswith(('2020x', 'grubM3x', 'rod5x', 'shaft8x', 'rod6x1'))} | \
    {'rod4x40', 'rod4x24', 'rod4x80', 'rod4x60', 'rod6x60', 'rod3x20'}
NOTE = {'rod4x50': 'ось 4 мм, 50 мм (толкатель рамки W)', 'strip3x2_5': 'тяга запорной гребёнки, полоса 3×2,5 мм',
        'strip4x3x30': 'ползун узла коромысла: полоса 4×3 мм'}
extra = defaultdict(int)
for k, b in bom.items():
    if k in covered or b['kind'] == 'print':
        continue
    extra[b['note'] or NOTE.get(k, k)] += b['qty']
for note, q in sorted(extra.items()):
    rows.append((note.replace('—', '--'), q, ''))
w('tab_model_buy.tex', ''.join(f'{a} & {b} & {c}\\\\\n' for a, b, c in rows))

# printed parts by group
GR = [('литерные блоки', ('type_block',)), ('челнок, шкив и колесо фиксатора', ('shuttle', 'shaft_hub')),
      ('клавиши, штоки, гребёнки, блокировка', ('keycap', 'spacebar', 'keystem', 'comb', 'lock_guide', 'trip_lever', 'ball_race')), ('рычаги', ('lever',)),
      ('кодовые пластины', ('code_plate',)), ('боковины рамок, кронштейны', ('bail_side', 'bail_bracket')),
      ('рамки, сектора памяти, связь со спуском', ('sector', 'latch', 'bail_plate_', 'tier_carriage', 'sleeve_', 'memory_pawls', 'wfol', 'w_follower')), ('выбор: толкатели, планки, коромысла, усилители', ('col_pusher', 'pusher_guide', 'sel_', 'guide_lift', 'guide_rotate', 'wlever', 'amp_', 'bellcrank')),
      ('печатающий узел: башня, коромысла, фиксатор, вилка, молоток', ('tower', 'uframe_arm', 'fork', 'hammer', 'lift_fork', 'whiffletree', 'wt_', 'detent', 'tape_clamp', 'lift_collar', 'row_', 'cock_lever', 'hammer_link')),
      ('пружинный двигатель и цикл', ('barrel', 'gear', 'pinion', 'bevel', 'governor', 'crank', 'wind', 'cam_', 'stop_', 'cycle_', 'motor_', 'lay_')),
      ('упоры и отвод печатающего узла', ('zero_stop', 'stop_', 'nsel', 'o_')), ('каретка', ('car_end', 'rack', 'paper_rest')), ('спуск', ('esc',)), ('корпус (ред. 0.12)', ('case_',)),
      ('прочее', ('pivot', 'ribbon', 'pusher_post'))]
agg = defaultdict(lambda: dict(q=0, files=0, mass=0.0, mx=0.0))
for r in PR:
    g = next((n for n, pre in GR if any(r['bom'].startswith(p) for p in pre)), 'прочее')
    a = agg[g]; a['q'] += r['qty']; a['files'] += 1; a['mass'] += r['mass'] * r['qty']; a['mx'] = max(a['mx'], max(r['dims'][:2]))
rows = []
for n, _ in GR:
    if n in agg:
        a = agg[n]
        rows.append(f"{n} & {a['q']} & {a['files']} & {f(a['mass'], 0)} & {f(a['mx'], 0)}\\\\\n")
tot_q = sum(a['q'] for a in agg.values()); tot_m = sum(a['mass'] for a in agg.values())
rows.append(f"\\midrule\n\\textbf{{итого}} & {tot_q} & {len(PR)} & {f(tot_m, 0)} & \\\\\n")
w('tab_model_print.tex', ''.join(rows))

# checks
names = {'shuttle': 'челнок на всех позициях и во всех рядах, включая покой под строкой (с шагом пол-позиции)', 'slide': 'отвод узла 0, 9 и 17\\,u при разных позициях, подъёме и ударе',
         'carriage': 'ход каретки по всей строке, молоток взведён и в ударе', 'keys': 'каждая клавиша нажата в обоих регистрах, при открытой и запертой гребёнке; рамки сдвинуты по коду',
         'cycle': 'оборот циклового вала через 10° для четырёх крайних знаков (с лентой, взводом, защёлками и блокировкой)',
         'marks': 'мёртвый знак при каждом значении памяти B и C: в начале, на 40\\,\\% и у ступени; второй сектор в крайних положениях',
         'escape': 'спуск: упор U для всех ширин при $\\pm u$, память M, забой и «назад на литеру» в трёх местах строки',
         'read': 'чтение кода (ред. 0.10): каждая продвигающая литера на оси удара, щупы на полпути и на зубцах, ползунки и тяга W с ними',
         'idle': 'холостой цикл (ред. 0.11): мёртвые знаки над и под строкой и пробел, оборот через 10°, запоры чтения и удара введены'}
rows = [f"покой (все детали попарно) & 1 & {N['rest_interferences']}\\\\\n"]
for k, v in names.items():
    rows.append(f"{v} & {N['nstates'][k]} & {N['scen'][k]}\\\\\n")
w('tab_model_checks.tex', ''.join(rows))

# motor
rows = [f"{k} & {f(v, 0)}\\\\\n" for k, v in MO['rot'].items()]
rows.append(f"\\midrule\n\\textbf{{итого}} & \\textbf{{{f(MO['I_rot'], 0)}}}\\\\\n")
w('tab_motor_I.tex', ''.join(rows))
tb = MO['table']
sel = [r for r in tb if r['tau'] >= MO['pick']['tau'] - 1e-9 and r['avg'] <= 0.9][::2]    # rev. 0.14 stage 2b: below the end-of-wind torque the shaft stops
if MO['pick'] not in sel:
    sel = sorted(sel + [MO['pick']], key=lambda r: r['tau'])
rows = []
for r in sel:
    bold = abs(r['tau'] - MO['pick']['tau']) < 1e-9
    # rev. 0.14 stage 2b: with the governor's brake a character takes one turn of the shaft whatever the torque: the
    # characters per wind are the barrel's turns above the needed torque (linear fall of the spring's torque)
    Mn = r['tau'] * MO['ratio'] / 0.93 ** 4
    cells = [f(r['tau'] * 1000, 1), f(r['E'] * 1000, 0), f(r['light'], 2), f(r['avg'], 2), f(r['worst'], 2),
             f(MO['spring']['turns'] * max(0.0, 1 - Mn / MO['spring']['M_max']) * MO['ratio'], 0)]
    if bold:
        cells = [f'\\textbf{{{c}}}' for c in cells]
    rows.append(' & '.join(cells) + '\\\\\n')
w('tab_motor_sim.tex', ''.join(rows))
sp = MO['spring']
rows = [f"полоса & {f(sp['b'], 0)}$\\times${f(sp['t'], 1)} мм, длина {f(sp['L'] / 1000, 2)} м\\\\\n",
        f"барабан & внутренний радиус {f(sp['Rb'], 1)} мм, вал {f(2 * sp['Ra'], 0)} мм\\\\\n",
        f"рабочих оборотов барабана & {f(sp['turns'], 1)}\\\\\n",
        f"энергия (предел / в работе) & {f(sp['U_theory'], 0)} / {f(sp['U_use'], 0)} Дж\\\\\n",
        f"момент (наибольший / средний) & {f(sp['M_max'], 1)} / {f(sp['M_avg'], 2)} Н$\\cdot$м\\\\\n",
        f"передача к цикловому валу & 1 : {f(MO['ratio'], 1)} (80/12 · 48/12 · 24/12)\\\\\n",
        f"нужно на цикловом валу / на барабане & {f(MO['tau_C'] * 1000, 1)} мН$\\cdot$м / {f(MO['M_need'], 2)} Н$\\cdot$м\\\\\n",
        f"знаков на завод (обороты барабана выше нужного момента; до ступени 2б) & {f(MO.get('chars_usable', MO['chars_energy']), 0)} ({f(MO.get('chars_usable_old', 0), 0)})\\\\\n",
        f"завод: оборотов ручки, усилие на ручке & {f(MO['crank_turns'], 0)}, до {f(MO['crank_force'], 0)} Н\\\\\n"]
w('tab_motor_spring.tex', ''.join(rows))
# cycle diagram (tikz): bars over 0..360 deg
C = P.CYCLE
def bar(y, a0, a1, col, label):
    return f"\\node[lbl,anchor=east] at (-0.2,{y}) {{{label}}};\n\\fill[{col}] ({a0 / 20},{y - 1.6}) rectangle ({a1 / 20},{y + 1.6});\n"
tz = []
tz.append(bar(40, C['out'][0], C['out'][1], 'accent!35', 'поворот и подъём челнока: туда'))
tz.append(bar(33, C['back'][0], C['back'][1], 'accent!20', 'обратно в исходное'))
tz.append(bar(26, C['detent'][0] - 10, C['detent'][1] + 10, 'sledB!40', 'фиксаторы, подъём ленты'))
tz.append(bar(19, 10, 150, 'axisred!25', 'взвод молотка'))
tz.append(bar(19, C['strike'] - 1, C['strike'] + 1, 'axisred', ''))
tz.append(bar(12, C['feed'][0], C['feed'][1], 'axisblue!45', 'подача каретки, возврат ползуна, сброс'))
tz.append(bar(5, 0, 8, 'ink!30', 'защёлки разрядов'))
tz.append(bar(-2, 5, 345, 'ink!12', 'клавиатура заперта'))
# rev. 0.10: the feelers read the code from the shuttle; the latch holds the W rod till the feed
tz.append(bar(54, C['read'][0] - P.READ_RAMP[0], C['read'][1] + P.READ_RAMP[1], 'sledA!25', 'щупы читают код с челнока'))
tz.append(bar(54, C['read'][0], C['read'][1], 'sledA!60', ''))
tz.append(bar(47, C['read'][0], C['wlatch'], 'sledA!15', 'задвижка держит ширину'))
w('fig_cycle.tex', ''.join(tz))

WH = json.load(open(os.path.join(gen, 'whiffle.json')))
rows = []
for v in WH['variants']:
    rows.append(f"{f(v['S'], 0)} & {v['name']} & {f(v['G_rot'], 1)} & {f(v['rot']['p95'], 2)} & {f(v['rot']['p997'], 2)} & "
                f"{f(v['lift']['p95'], 2)} & {f(v['lift']['p997'], 2)}\\\\\n")
w('tab_whiffle.tex', ''.join(rows))
LK = json.load(open(os.path.join(gen, 'links.json')))
VI = json.load(open(os.path.join(gen, 'visibility.json')))
# selection ladders
rows = []
for nm, ru in (('rotate', 'поворот'), ('lift', 'подъём')):
    t = LK['selection'][nm]
    rows.append(f"{ru} & {', '.join(f(b, 1) for b in t['tree']['b'])} & {', '.join(f(n, 1) for n in t['tree']['n'][1:])} & "
                f"{f(t['amp']['G'], 2)} & {f(t['amp']['a'], 0)} / {f(t['amp']['b'], 1)} & {f(t['amp']['delta'], 2)}\\\\\n")
w('tab_links_sel.tex', ''.join(rows))
# frames
names_fr = dict(R='R, поворот (4 разряда)', O='O, подъём (3 разряда)', W='W, ширина знака', B='B, левая граница', C='C, правая граница', N='N, без продвижения')
rows = []
for k, v in LK['frames'].items():
    if k not in names_fr:
        continue
    rows.append(f"{names_fr.get(k, k)} & {f(v['lane'], 0)} & {f(v['bar_len'], 0)} & {f(v['mass_g'], 0)} & {f(v['travel'], 0)} & "
                f"{f(v['F_pre'], 2)}--{f(v['F_end'], 2)}\\\\\n")
w('tab_links_frames.tex', ''.join(rows))
# visibility
rows = []
for en in VI['eyes']:
    a = VI['before'][en]['lines']; b = VI['rest'][en]['lines']
    cell = lambda d, k: f"{f(100 * d[k]['hidden'], 0)}\\,\\% / {f(-(d[k]['first_visible'] or 0), 0)}"
    rows.append(f"{en} & {cell(a, '0')} & {cell(a, '1')} & {cell(a, '3')} & {cell(b, '0')} & {cell(b, '1')} & {cell(b, '3')}\\\\\n")
w('tab_visibility.tex', ''.join(rows))
SP = LK['stops']
rows = []
for k in range(len(SP['stairs']['C']['R'])):
    b = SP['stairs']['B']; c = SP['stairs']['C']
    cb = f"{f(b['theta'][k], 1)} & {f(b['R'][k], 2)}" if k < len(b['R']) else '-- & --'
    rows.append(f"{k} & {f(P.MARK_REF_U + k, 0)} & {f((P.MARK_REF_U + k) * P.U, 2)} & {cb} & {f(c['theta'][k], 1)} & {f(c['R'][k], 2)}\\\\\n")
w('tab_stops.tex', ''.join(rows))
num = dict(parts=N['parts'], printfiles=len(PR), printpieces=tot_q, printmass=f(tot_m / 1000, 1), height=f(N['height'], 0),
           Irot=f(MO['I_rot'], 0), Iold=f(MO['I_old'], 0), mlift=f(MO['m_lift'], 0), Echar=f(MO['E_char'] * 1000, 0),
           tauC=f(MO['tau_C'] * 1000, 1), charswind=f(round(MO.get('chars_usable', MO['chars_energy']), -1), 0), charswindold=f(round(MO.get('chars_usable_old', 0), -1), 0), crankturns=f(MO['crank_turns'], 0),
           crankforce=f(MO['crank_force'], 0), cpsavg=f(MO['cps_avg'], 1), cpsworst=f(MO['cps_worst'], 1), cpslight=f(MO['cps_light'], 1),
           tavg=f(MO['pick']['avg'], 2), tworst=f(MO['pick']['worst'], 2), tlight=f(MO['pick']['light'], 2),
           springL=f(MO['spring']['L'] / 1000, 1), Uuse=f(MO['spring']['U_use'], 0), ratio=f(MO['ratio'], 1),
           Ehammer=f(MO['E_hammer'] * 1000, 0), eta=f(MO['eta'] * 100, 0),
           caprot=f(WH['cap_rot'], 1), caplift=f(WH['cap_lift'], 1), grot=f(WH['rot']['G'], 2), glift=f(WH['lift']['G'], 2),
           dbar=f(DY['d_bar'], 3), dlev=f(DY['d_lev'], 2), sigtype=f(DY['sigma_type'], 0),
           tauold=f(MO['compare']['rev07']['tau'] * 1000, 1), tavgold=f(MO['compare']['rev07']['avg'], 2),
           avgcost=f(100 * (MO['compare']['rev08']['E'] / MO['compare']['rev07']['E'] - 1), 0),
           tauorder=f(MO['compare']['order_only']['tau'] * 1000, 1), tworstold=f(MO['compare']['rev07']['worst'], 2),
           Eold=f(MO['compare']['rev07']['E'] * 1000, 0),
           vbefore=f(-VI['before']['обычная посадка']['lines']['0']['first_visible'], 0),
           vbeforeold=f(-VI['before']['обычная посадка']['lines']['1']['first_visible'], 0),
           hmass=f(LK['hammer']['mass_g'], 1), hv=f(LK['hammer']['v_impact'], 1), hrcock=f(LK['hammer']['r_cock_mm'], 1),
           hFcam=f(LK['hammer'].get('F_cam_N', LK['hammer'].get('F_cam', 0)), 1),
           rdpmin=f(LK['row_detent']['pitch_min'], 1), rdpmax=f(LK['row_detent']['pitch_max'], 1),
           rdhub=f(LK['row_detent']['capture_hub'], 1),
           lockshift=f(LK['interlocks']['shift'], 2), lockneck=f(LK['interlocks']['neck'], 0), locktooth=f(LK['interlocks']['tooth'], 2),
           escL=f(LK['escape']['L1'], 0), escLL=f(LK['escape']['L2'], 0), escra=f(LK['escape']['r_a'], 2),
           ribdrop=f(LK['ribbon']['drop'], 0),
           stopfree=f(SP['free'], 1), stopnt=f(SP['n_travel'], 1), stopslideN=f(SP['slide_at_n'], 1), stopkey=f(SP['key_load_N'], 1),
           stopFmax=f(SP['F_spring'][1], 1), stopbc=f(SP['bc_theta_max'], 0), opush=f(SP['o_push_max'], 1),
           backpull=f(LK['back']['pull_back'], 1), backneed=f(LK['back']['pull_back_need'], 1), bksppull=f(LK['back']['pull_bksp'], 1),
           bkspneed=f(LK['back']['pull_bksp_need'], 1),
           bcatch=f(LK['back']['b_catch'], 1), bdrop=f(LK['back']['b_drop'], 1), mplay=f(LK['back']['m_play'], 1), bkspdeg=f(LK['back']['bksp_deg'], 1),
           rockbk=f(LK['back']['detail']['back']['rock_deg'], 0), rockbs=f(LK['back']['detail']['bksp']['rock_deg'], 0),
           ncont=str(N['contacts']), ncontbad=str(N['contacts_failed']), nstrike=str(N['strike']), nstrikebad=str(N['strike_failed']), nprint=str(N['unique_print']), nnum=str(N['numbered']),
           nnumtop=str(N['numbered_top']), nnumbot=str(N['numbered'] - N['numbered_top']), nnonum=str(N['unique_print'] - N['numbered']),
           nescst=str(N['nstates']['escape']),
           # rev. 0.12: the case
           casepieces=str(N['case_parts']), caseinlays=str(N['case_inlays']), casemass=f(N['case_mass_g'] / 1000, 1),
           devcol=str(N['device_colours']), insw=f(N['inscription']['width'], 0), insk=f(N['inscription']['scale'], 2),
           extw=f(N['extent'][1][0] - N['extent'][0][0], 0), extd=f(N['extent'][1][1] - N['extent'][0][1], 0),
           casew=f(N['case_extent'][1][0] - N['case_extent'][0][0], 0), cased=f(N['case_extent'][1][1] - N['case_extent'][0][1], 0),
           caseh=f(N['case_extent'][1][2], 0),
           mechmass=f((tot_m - agg['корпус (ред. 0.12)']['mass']) / 1000, 1) if 'корпус (ред. 0.12)' in agg else f(tot_m / 1000, 1),
           casepmass=f(agg['корпус (ред. 0.12)']['mass'] / 1000, 1) if 'корпус (ред. 0.12)' in agg else '0')
w('model_num.tex', ''.join(f'\\newcommand\\m{k}{{{v}}}\n' for k, v in num.items()))
print(num)
