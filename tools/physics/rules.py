"""Stage 1, manual marking (spec §4.4) written as rules over whole part names, groups and BOM ids -- never over pieces of
names (trap 10). Each rule gives the joint the document intends, its fastener, status and a reference. A rule only
applies to pairs that do not move against each other in the model ('planar_rest' after step C).

Statuses: 'described' -- the document says how it is held (or says that the fastening exists but is not listed);
'missing' -- the document says nothing; the note gives what is usually done."""
import re

R14 = 'main.tex §«Физические проверки», «Крепёж» (ред. 0.14)'
FRAME_NOTE = ('main.tex §«Перечень покупного»: «Пружины, крепёж рамы и стыков … в перечень не входят» — крепёж задуман, '
              'но не назван и не построен')


def _bom(p):
    return p['bom'] or ''


def rule(pa, pb):
    """-> dict(type, fastener, status, doc, note) or None."""
    a, b = pa['name'], pb['name']
    ga, gb = pa['group'], pb['group']
    ba, bb = _bom(pa), _bom(pb)
    both = {a, b}
    # --- rev. 0.14: the base plate and the supports added after stage 1 (tools/model/supports.py)
    if 'base plate' in both:
        return dict(type='rigid', fastener='screw M3 + insert', status='described', doc=R14,
                    note='деталь на основании: винт М3 снизу во вставку (основание к профилю — М5 с Т-гайками)')
    if any('clip' in n and _bom(pp).startswith('eclip') for n, pp in ((a, pa), (b, pb))):
        return dict(type='rigid', fastener='E-clip', status='described', doc=R14, note='стопорное кольцо DIN 6799 в канавке')
    # --- the case (rev. 0.12)
    if ga == 'case' and gb == 'case':
        if any(n.startswith('case standoff') for n in both):
            return dict(type='rigid', fastener='screw M3 + insert', status='described', doc=R14,
                        note='панель на упоре: винт М3 во вставку панели (ред. 0.14)')
        return dict(type='rigid', fastener='screw M3 + insert', status='described', doc='§«Корпус»: «швы скрепляются накладками на винтах (в модели их нет)»',
                    note='шов панелей: накладка на винтах М3 — не построена')
    if ga == 'case' or gb == 'case':
        o = pa if gb == 'case' else pb
        c = pb if gb == 'case' else pa
        if c['name'].startswith('case standoff') and o['group'] == 'frame':
            return dict(type='rigid', fastener='screw M5 + T-nut', status='described',
                        doc='§«Корпус»: «упоры, привёрнутые в пазы профиля (… винты М5 с Т-гайками — нет)»', note='винт М5 с Т-гайкой не построен')
        if 'pillar' in c['name'] and o['name'].startswith('carriage post'):
            return dict(type='planar_rest', fastener=None, status='described', doc='§«Корпус»: «пилястры … надеты на стойки»',
                        note='надета сверху; от подъёма держит только вес')
        return dict(type='contact_only', fastener=None, status='described', doc='§«Корпус»: «корпус не трогает механизма»',
                    note='касание корпуса с механизмом')
    # --- keys: cap on stem
    if {ga, gb} == {'keys'} and any(n.startswith('cap ') for n in both) and any(n.startswith('stem ') for n in both):
        return dict(type='rigid', fastener='press', status='described', doc=R14, note='колпачок на штоке: посадка с натягом и капля клея (ред. 0.14)')
    # --- shuttle: type blocks in sockets with an adjusting screw; comb pins pressed into the ring
    if 'shuttle' in both:
        o = pb if a == 'shuttle' else pa
        if o['name'].startswith('type block'):
            return dict(type='rigid', fastener='screw M3', status='described',
                        doc='§«Литерные блоки и челнок»: «в гнёзда с регулировочным винтом»', note='винт гнезда в модели не построен')
        if o['name'].startswith('comb pin'):
            return dict(type='rigid', fastener='press', status='described', doc='§«Литерные блоки и челнок»: «в кольце штифты сидят с натягом»',
                        note='в модели штифт касается отверстия без натяга')
        if o['name'].startswith('code comb'):
            return dict(type='planar_rest', fastener=None, status='described', doc='§«Чтение»: гребёнка на двух штифтах, «прижим к поясу»',
                        note='прижим к поясу — чем? (держит гребёнку на штифтах по их оси)')
    if any(n.startswith('code comb') for n in both) and any(n.startswith('comb pin') for n in both):
        return dict(type='prismatic_pins', fastener=None, status='described', doc='§«Чтение»: «полоса … на двух стальных штифтах Ø2»',
                    note='гребёнка надета на штифты с зазором: сдвиг вдоль штифтов держит только «прижим к поясу»')
    # --- carriage: plates, bushings, tube, roller -- carriage frame
    if ga == 'carriage' and gb == 'carriage':
        return dict(type='rigid', fastener='screw M3', status='described', doc=R14,
                    note='сборка каретки: торцевые стенки на винтах М3 к трубе, валику и рейке, LM8UU в запрессовку, щёчки и кронштейны на М3 (ред. 0.14)')
    # --- U-frame: everything on the base plate
    if (a == 'U-frame base' or b == 'U-frame base'):
        o = pb if a == 'U-frame base' else pa
        if _bom(o).startswith('MGN12H'):
            return dict(type='rigid', fastener='screw M3', status='described', doc='§«U-образная рама и ползун»: «плита Д16Т на MGN12»',
                        note='каретки MGN12H на винтах М3 (по 4) — в модели нет')
        return dict(type='rigid', fastener='screw M3', status='described', doc=R14,
                    note='деталь на плите узла: винты М3 в резьбу плиты Д16Т (ред. 0.14)')
    # --- the frame and its posts, brackets, cheeks: 2020 profiles
    fixed = pa['mov'] == 'fixed' and pb['mov'] == 'fixed'
    if fixed:
        prof = {n for n in both if (n.startswith('frame ') or n.startswith('beam ') and not n.startswith('beam post'))}
        if prof:
            return dict(type='rigid', fastener='screw M5 + T-nut', status='described', doc=FRAME_NOTE,
                        note='деталь на профиле 2020: винт М5 с Т-гайкой не построен')
        return dict(type='rigid', fastener='screw M3', status='described', doc=FRAME_NOTE,
                    note='стык неподвижных деталей: вид крепежа не назван')
    # --- moving assemblies whose parts do not move against each other
    if pa['mov'] == pb['mov']:
        if any(n.startswith('selector bar') for n in both) and any(n.startswith('selector rod') for n in both):
            return dict(type='rigid', fastener='press', status='described', doc=R14, note='гнутый стержень выбора запрессован в отверстие планки (ред. 0.14)')
        if any(n.startswith('bail ') and ' guides ' in n for n in both) and any(n.startswith('tier carriage') for n in both):
            return dict(type='rigid', fastener='press', status='described', doc=R14,
                        note='пруток направляющей запрессован в кронштейн яруса (ред. 0.14)')
        return dict(type='rigid', fastener=None, status='missing', doc='—', note=f'детали одного движения ({pa["mov"]}) касаются; чем скреплены — нет')
    return None
