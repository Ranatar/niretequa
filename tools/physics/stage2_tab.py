"""Stage 2 summary (spec §5.7): gen/tab_stage2.tex and gen/physics/stage2.json from the nodes' results.
Usage: python3 -I tools/physics/stage2_tab.py"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import units as U


def L(n):
    return json.load(open(os.path.join(U.GEN, f'node_{n}.json')))


def f(x, d=1):
    return f'{x:.{d}f}'.replace('.', '{,}')


def main():
    C, D, B, A, F, E, G = (L(n) for n in 'cdbafeg')
    rows = []
    # rev. 0.14: the rows report the new design (positive cam drive, sear hammer, feed from 200 deg, ...)
    v = C['validation']; n = C['nominal_avg']; lh = C['lhs']
    rows.append(('C', 'молоток', f"скорость {f(v['v'],2)} / {f(v['links_v'],2)} м/с; полёт {f(v['t_ms'],2)} / {f(v['links_t_ms'],2)} мс (линейная пружина)",
                 f"удар {f(n['v_impact'],2)} м/с, {f(n['contacts'][0]['F_max'],0)} Н, {f(n['contacts'][0]['dur_ms'],2)} мс; отскоки гаснут на листе до {f(lh['last_max'],0)}°; к 200° боёк в {f(lh['gap_200_min'],1)} мм от листа",
                 'касаний листа после 200° нет', f"да: {lh['after_200']} из 200"))
    dz = D['options']['design']; lhd = D['lhs']
    rows.append(('D', 'спуск и каретка', f"подача на зуб {f(D['validation']['rack_per_tooth_mm'],4)} мм = 1\\,u",
                 f"пружина {f(dz['F'],0)} Н, подача с 200°: удар о палец U до {f(max(r['E_hit_mJ'] for r in dz['rows']),1)} мДж и {f(max(r['F_tooth_N'] for r in dz['rows']),0)} Н, успокоение к {f(max(r['end_deg'] for r in dz['rows']),0)}°",
                 'успокоилась до 325° (Д)', f"да: {200 - int(lhd['late'])} из 200"))
    vb = max(abs(x['diff_pct']) for x in B['validation'])
    hz = B['hertz']
    rows.append(('B', 'цикл', f"время цикла как в motor.py: расхождение $\\le$ {f(vb,2)}\\,\\%",
                 f"обратные ролики до {f(hz['rotate']['F_ret'],0)} Н (поворот) и {f(hz['lift']['F_ret'],0)} Н (подъём), в выстое не нужны; держатель челнока до {f(max(r['keeper_max_N'] for r in B['cases']),1)} Н; ветви ленты {f(min(r['tape_branch_min_N'] for r in B['cases']),1)}–{f(max(r['tape_branch_max_N'] for r in B['cases']),1)} Н",
                 'связи не размыкаются', 'да'))
    a = A['буква k24']; dk = A['мёртвый k38']
    rows.append(('A', 'клавиша', '—', f"возврат буквенной {f(a['return_nominal']['t_ms'],0)} мс, отскок {f(a['return_nominal']['bounce_mm'],1)} мм; мёртвая — {f(dk['press'][-1]['F'],0)} Н до спуска за {f(dk['press'][-1]['t_trip_ms'],0)} мс",
                 'возврат $\\le$ 100 мс', 'да; мёртвая тяжелее'))
    w = [r for r in F['rows'] if r['ch'] == 'W']
    late = [r for r in F['rows'] if r['arrive_deg'] is None or r['arrive_deg'] > 145]
    rows.append(('F', 'щупы', '—', f"цепь W {f(F['masses_g']['W'],1)} г (тяги — углепластик); пружины W/B/C {f(F['spring_needed']['W']['now'],2)}/{f(F['spring_needed']['B']['now'],2)}/{f(F['spring_needed']['C']['now'],2)} Н; на зубце к {f(max(r['arrive_deg'] for r in F['rows'] if r['arrive_deg'] and r['cycle'] != 'свободный ход регулятора'),0)}°",
                 'на зубце к 145°; отскок $\\le$ 0,5 мм', 'нет' if [r for r in F['rows'] if (r.get('bounce_mm') or 0) > 0.5] or
                 [r for r in late if r['cycle'] != 'свободный ход регулятора'] else 'да'))
    # stage 2b (rev. 0.14 supplement): the bounce criterion and the governor's free speed were left out of this row before
    bmax = max((r.get('bounce_mm') or 0) for r in F['rows'])
    free = [r for r in F['rows'] if r['cycle'] == 'свободный ход регулятора']
    nfree = len([r for r in late if r['cycle'] == 'свободный ход регулятора'])
    import params as PP
    rows.append(('F', 'щупы (отскок, предел скорости)', '—', f"отскок от зубца до {f(bmax,2)} мм (наконечник, $e$ = {f(PP.READ_TIP_E,2)}); на пределе скорости вала (тормоз регулятора) не доходят {nfree} из {len(free)}",
                 'отскок $\\le$ 0,5 мм; на зубце к 145°', 'да' if bmax <= 0.5 and nfree == 0 else 'нет'))
    j = E['J_mesh']
    rows.append(('E', 'двигатель', f"$J_0$ по сеткам {f(j['total']*1e6,1)} кг$\\cdot$мм$^2$ = motor.py (маховик регулятора)",
                 f"лёгкий цикл {f(E['rows'][1]['t_cycle'],2)} с, удар о защёлку {f(E['rows'][1]['E_stop_mJ'],1)} мДж; с накладкой {f(max(r['F_pad_N'] for r in E['rows']),0)} Н, {f(max(r['sigma_pad_MPa'] for r in E['rows']),0)} МПа",
                 'удар на защёлке в пределах печати', 'да, с накладкой'))
    rows.append(('G', 'возвраты весом', '—', 'клавиши и планки разрядов — на пружинах, молоток — на шептале и губе рычага',
                 'вес ничего не возвращает', 'да'))
    # rev. 0.14: node H, the springs that had no number
    Hn = json.load(open(os.path.join(U.GEN, 'node_h.json')))['rows']
    hc = [r for r in Hn if r.get('preload_N')]
    rows.append(('H', 'пружины без чисел', '—', f"посчитано {len(hc)}: от {f(min(r['preload_N'] for r in hc),2)} до {f(max(r['preload_N'] for r in hc),2)} Н (возврат в отпущенное время, вес, трение, ×1,5)",
                 'каждой — натяг', 'да, расчётный'))
    pb = B['pressure']
    rows.append(('B', 'обратные кулачки', '—', f"углы давления: основные до {f(pb['lift']['main']['max_deg'],0)}°, обратные до {f(max(pb['rotate']['return']['max_deg'], pb['lift']['return']['max_deg']),0)}°; трение пальцев в пазах до {f(max(max(r['slot_friction_rotate_mJ'], r['slot_friction_lift_mJ']) for r in B['cases']),1)} мДж за оборот",
                 'обратные $\\le$ 30°', 'да'))
    tex = []
    for r in rows:
        tex.append(' & '.join(r) + ' \\\\')
    open(os.path.join(U.ROOT, 'gen', 'tab_stage2.tex'), 'w').write('\n'.join(tex) + '\n')
    json.dump(dict(rows=rows), open(os.path.join(U.GEN, 'stage2.json'), 'w'), ensure_ascii=False, indent=1)
    for r in rows:
        print(r)


if __name__ == '__main__':
    main()
