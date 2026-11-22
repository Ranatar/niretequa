"""Stage 1 (spec §3.4): the full list of the machine's springs, numbers taken from the code where they are, from the
document's text otherwise; a spring without a number is k = None, status 'missing' (never invented).
Writes data/springs.json (manual edits of 'points' and 'note' survive: the key is the name).
Usage: python3 -I tools/physics/springs.py"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import units as U
import params as P

LJ = json.load(open(os.path.join(U.ROOT, 'gen', 'links.json')))
MJ = json.load(open(os.path.join(U.ROOT, 'gen', 'motor.json')))


def sp(name, a, b, kind, k=None, preload=None, travel=None, unit='N/mm', source='', status='described', part=None, note=''):
    return dict(name=name, a=a, b=b, kind=kind, k=k, k_unit=unit, preload=preload, travel=travel, points=None, part=part,
                source=source, status=status, note=note)


def build():
    out = []
    fr = LJ['frames']
    for f in ('R', 'W', 'O', 'N'):
        d = fr[f]
        for s in (-1, +1):
            # links.frames: F_pre, k are for the frame (two springs in parallel): one spring carries half
            out.append(sp(f'bail {f} spring {s:+d}', f'bail {f} plate {s:+d}', f'bail {f} guides {s:+d}', 'compression',
                          k=d['k'] / 2, preload=d['F_pre'] / 2, travel=d['travel'], source='links.json frames.' + f + ' (F_pre, k of the frame / 2)',
                          status='modeled', part=f'bail {f} spring {s:+d}', note='5,2×0,5 мм на задней направляющей'))
    st = LJ['stops']
    out.append(sp('slide return spring', 'U-frame base', 'zero stop', 'extension', k=None, preload=st['F_return'], travel=P.SLIDE_MAX,
                  source='links.json stops.F_return (1 N); main.tex «около 1 Н»', status='modeled', part='slide return spring',
                  note='жёсткость не задана'))
    out.append(sp('O rod A spring', 'O rod A rear', 'O rod A front', 'compression', k=0.12, preload=st['F_spring'][0], travel=None,
                  source='links.py stops (F_pre 1,5 Н, k_sp 0,12 Н/мм; до 2,26 Н)', status='modeled', part='O rod A spring'))
    h = LJ['hammer']
    # rev. 0.14: the spring sits between the cocking lever and the hammer (preload T0 holds the hammer's tab on the
    # lip; wound 21.4 deg against the sear; 3.4 deg left at the blow)
    out.append(sp('hammer spring', 'hammer collar', 'hammer cocking lever', 'torsion', k=h['k_t_Nmm_per_deg'], unit='N*mm/deg',
                  preload=h['T0_Nmm'], travel=h['lever_deg'],
                  source='links.json hammer (T0 15 Н·мм, k; энергия полёта 20 мДж) — ред. 0.14', status='modeled', part='hammer spring',
                  note='между рычагом взвода и молотком; на шептале — T_release, на листе — T_sheet'))
    out.append(sp('hammer rod return spring', 'hammer cocking rod', 'U-frame arm and hammer post', 'compression', preload=h['rod_return_N'],
                  source='ред. 0.14: толкатель взвода идёт за спадом кулачка (175..330°)', status='decided'))
    out.append(sp('hammer sear spring', 'hammer sear', 'hammer sear bracket', 'torsion/flat', preload=0.3,
                  source='ред. 0.14: шептало падает перед зубом втулки', status='decided'))
    out.append(sp('rotate tape tensioner spring', 'rotate tape tensioner', 'tape slider MGN7H', 'compression', preload=P.TAPE_PRELOAD_N,
                  source='ред. 0.14: замкнутая лента поворота; ступень 2б: params.TAPE_PRELOAD_N (ветви не провисают на настоящем законе вала)', status='decided', part='rotate tape tensioner'))
    # rev. 0.14 stage 2b: the governor's brake (gramophone type) -- its leaf springs set the speed with the plate's screw
    for i in (1, 2, 3):
        out.append(sp(f'governor leaf spring {i}', 'governor sliding collar', 'governor fixed collar', 'flat (leaf)', preload=0.0,
                      source='ред. 0.14, ступень 2б: тормоз регулятора; уставка — params.GOV_T_FREE, винтом шайбы', status='decided',
                      part=f'governor leaf spring {i}'))
    out.append(sp('selector bar return springs', 'selector bar r1 (all selector bars)', 'pusher guide', 'extension', preload=0.2,
                  source='ред. 0.14 (узел G: планки r2, r8 опускались весом и на 15° не возвращались)', status='decided'))
    out.append(sp('row detent wedge spring', 'row detent wedge', 'row detent wedge lug', 'extension', preload=0.5,
                  source='ред. 0.14 (ступень 1: клин и ролик фиксатора ряда падали)', status='modeled', part='row detent wedge spring'))
    s = MJ['spring']
    out.append(sp('mainspring', 'spring barrel', 'barrel arbor', 'spiral (заводная)', k=None, preload=s['M_max'], unit='N*m',
                  source='motor.json spring (M_max 5,12 Н·м, M_avg 1,19 Н·м, 32×0,8 мм, ~6,3 м)', status='modeled', part='mainspring',
                  note='момент по заводу — motor.py; в цикле — на валу tau_C = 17 мН·м'))
    lt = LJ['selection']['latch']
    for b in ('r1', 'r2', 'r4', 'r8'):
        out.append(sp(f'latch pin spring {b}', f'rotate latch pin {b}', 'rotate bit slider ' + b, 'compression', preload=lt['spring_N'],
                      source='links.json selection.latch.spring_N', status='described', note='палец защёлки 3 мм «с пружиной вниз»; пружины в модели нет'))
    for b in ('l1', 'l2', 'l4'):
        out.append(sp(f'latch pin spring {b}', f'lift latch pin {b}', 'lift bit slider ' + b, 'compression', preload=lt['spring_N'],
                      source='links.json selection.latch.spring_N', status='described', note='как у r1..r8'))
    fo = LJ['selection']['forces']
    for t in ('rotate', 'lift'):
        out.append(sp(f'{t} slider return springs', f'{t} bit slider r1 (all bit sliders)', 'U-frame base', 'extension', preload=fo['F_return'],
                      source='links.json selection.forces.F_return (0,4 Н на ползун)', status='described',
                      note='возврат ползунов разрядов; в модели нет; жёсткость не задана'))
    for ch in P.READ_CH:
        out.append(sp(f'feeler spring {ch}', f'feeler {ch}', 'reading head', 'compression (long)', k=0.0, preload=P.READ_F_SPRING[ch],
                      source='params.READ_F_SPRING («long, nearly constant over the stroke»)', status='described',
                      note=f'нагрузка щупа {P.READ_F_LOAD[ch]} Н (params.READ_F_LOAD)'))
    out.append(sp('escapement stop return spring', 'escapement stop', 'escapement bracket', 'extension', preload=LJ['escape']['spring_N'],
                  source='links.json escape.spring_N (0,2 Н с ред. 0.10)', status='described', note='возврат упора U в ноль'))
    for m in ('B', 'C'):
        out.append(sp(f'memory pawl spring {m}', f'memory pawl {m}', 'sector bracket', 'flat/torsion', preload=LJ['sectors']['ratchet']['pawl_spring_N'],
                      source='links.json sectors.ratchet.pawl_spring_N; note детали', status='described'))
        out.append(sp(f'sector return spring {m}', f'memory sleeve {m}', 'sector axis', 'torsion', source='main.tex рис. «Сектор памяти»: «пружина возвращает сектор в ноль»',
                      status='missing', note='числа нет нигде'))
    out.append(sp('escapement dog spring', 'escapement dog', 'escapement bracket', 'compression', preload=0.3,
                  source='note детали escapement dog (0,3 Н)', status='described'))
    out.append(sp('back pawl spring', 'back pawl', 'back lever B', 'torsion/flat', preload=0.2, source='note детали back pawl (0,2 Н)', status='described'))
    out.append(sp('bksp link spring', 'bksp link', 'backspace arm K', 'compression (в тяге)', source='note bksp link; main.tex §«Забой»', status='missing',
                  note='«остаток забирает пружина в тяге»; числа нет; подбор по стенду Э2'))
    out.append(sp('back link spring', 'back link', 'back lever B', 'compression (в тяге)', source='note back link; main.tex', status='missing',
                  note='подбор по стенду Э2'))
    out.append(sp('memory lever M return spring', 'memory lever M', 'escapement bracket', 'torsion', source='main.tex §«Спуск»: «пружина M возвращает его на упор нуля»',
                  status='missing', note='подбор по стенду Э2'))
    out.append(sp('memory holding pawl spring', 'memory holding pawl', 'memory lever M', 'flat', source='main.tex: собачка M в храповом секторе', status='missing'))
    out.append(sp('stop carrier spring', 'stop carrier', 'stop carrier rod bracket', 'extension', source='note stop carrier: «пружина к ролику»', status='missing'))
    out.append(sp('carriage drive spring', 'carriage rack', 'frame back', 'спиральная (двигатель каретки)', preload=P.CAR_SPRING_N,
                  source='ред. 0.14: params.CAR_SPRING_N (узел D: подача с 200°; ступень 2б: 7 Н — успокоение на пальце U до собачки Д на настоящем законе вала)', status='decided',
                  note='постоянная сила (ленточная пружина), 4 Н по всей строке'))
    out.append(sp('W latch pawl spring', 'W latch pawl', 'W wire bracket', 'flat/torsion', source='contacts: собачка на храповой планке W', status='missing'))
    out.append(sp('pm-u detent spring', 'pm-u detent', 'escapement bellcrank', 'flat', source='деталь pm-u detent (фиксатор эксцентрика ±u)', status='missing'))
    out.append(sp('carriage release key spring', 'carriage release key', 'carriage release bracket', 'torsion', source='main.tex: «Когда клавиша отпущена, пружина собачки вводит её»',
                  status='described', note='возврат — пружиной собачки Д (0,3 Н) через трос'))
    out.append(sp('read lock spring', 'read lock pin', 'read lock guide', '?', source='§«Холостой цикл»', status='missing', note='возврат штыря запора чтения'))
    out.append(sp('hammer lock spring', 'hammer lock pin', 'hammer lock guide', '?', source='§«Холостой цикл»', status='missing', note='возврат штыря запора удара'))
    # rev. 0.14b: one spring per key of letters and spaces, under the lever on the bar at y = params.KRS_Y (the stem has
    # no room for one); the stem's collar with a rubber pad bears on the comb's underside -- the rest stop
    import parts as PT
    for k in PT.key_list():
        if PT.has_return_spring(k):
            out.append(sp(f"key return spring {k['id']}", f"lever {k['id']}", 'key return bar', 'compression', k=P.KRS_K,
                          preload=P.KRS_PRE, travel=round(PT.krs_top(k, 0.0)[0] - PT.krs_top(k, 1.0)[0], 2),
                          source='ред. 0.14b: params.KRS_PRE — params.KEY_RETURN_N на клавише самого длинного рычага (узел A)',
                          status='modeled', part=f"key return spring {k['id']}",
                          note='3,5×0,3 мм под рычагом на планке; упор покоя — буртик штока с резиновой прокладкой 0,5 мм под гребёнкой'))
    out.append(sp('ribbon vibrator return', 'ribbon vibrator', 'ribbon post -1', '?', preload=LJ['ribbon']['F_N'], source='links.json ribbon.F_N (0,6 Н — сила подъёма)',
                  status='missing', note='возврат вибратора — кулачок или вес? см. §4.8'))
    out.append(sp('cycle stop latch spring', 'cycle stop latch', 'cycle stop latch post', 'torsion', preload=0.3, source='ред. 0.14: защёлка на своей стойке', status='decided'))
    out.append(sp('detent pawl return', 'detent pawl', 'U-frame base', '?', source='фиксатор позиции: клин уводит тяга; обратно?', status='missing'))
    return out


def main():
    path = os.path.join(U.DATA, 'springs.json')
    old = {}
    if os.path.exists(path):
        old = {s['name']: s for s in json.load(open(path))['springs']}
    out = build()
    for s in out:
        o = old.get(s['name'])
        if o:
            for k in ('points', 'note'):
                if o.get(k) and o.get('manual'):
                    s[k] = o[k]
            if o.get('status') == 'calculated' and s['k'] is None and (s['preload'] is None or s['status'] == 'missing'):     # rev. 0.14: node H
                for k in ('preload', 'status', 'source', 'note'):
                    s[k] = o[k]
    json.dump(dict(version=1, model_revision='0.14', springs=out), open(path, 'w'), ensure_ascii=False, indent=1)
    from collections import Counter
    print(len(out), Counter(s['status'] for s in out))


if __name__ == '__main__':
    main()
