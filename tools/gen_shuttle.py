"""Generate LaTeX/TikZ fragments for TPM-2 rev. 0.2: mechanical machine on a Hammond-type shuttle.
Usage: python3 -I gen_mech.py FONT DATA_DIR OUT_DIR

Model: an advancing slug prints with the LEFT edge of its cell at the print point; the carriage
then feeds w. Dead marks sit on two sledges displaced back by b (marks above) or c = b - d
(marks below); the sledges are set by the last advancing key and held by a latch (memory).
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont
import inventory as inv
import layout as lay
from layout import ROW_CODE

font_path, data_dir, out = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
F = TTFont(font_path)
GID = {n: i for i, n in enumerate(F.getGlyphOrder())}
D = json.load(open(os.path.join(data_dir, 'codes.json')))
U = D['U']
SYNTH = D.get('synth', {})
SPACE_W, SPACE_N = 6, 4

from items import build_items, ADV, MARK_CP, BELOW_MARKS, QUENYA, SINDARIN
ITEMS, MARK_AX = build_items(D, F)



def hexs(cp):
    return f"{cp:04X}"


def gl(name, x=0, y=0, extra=''):
    if name in SYNTH:                # rev. 0.14: a synthetic glyph (glyphvar.py): its base glyph, moved
        b, dx, dy = SYNTH[name]; name, x, y = b, x + dx, y + dy
    return (f"\\node[anchor=base west,inner sep=0pt,outer sep=0pt{extra}] at ({x:.1f},{y:.1f}) "
            f"{{\\TG{{{GID[name]}}}}};\n")


def inline(key, size='\\tgsmall'):
    it = ITEMS[key]
    if it['kind'] in ('T', 'N', 'P'):
        return f"{{{size}\\symbol{{\"{hexs(it['cps'][0])}}}}}"
    if it['kind'] == 'C':
        return f"{{{size}\\symbol{{\"{hexs(it['cps'][0])}}}\\symbol{{\"{hexs(it['cps'][1])}}}}}"
    return ("{\\tikz[baseline=0pt,x=\\tgu,y=\\tgu]{\\draw[gray!60,densely dotted] (0,0) -- (0,520);"
            + gl(it['glyph'], -it['ax'], 0) + "}}")


# ---------- validation of the layout ----------
used = [k for row in lay.ROWS for pair in row for k in pair if k is not None]
assert len(used) == len(set(map(str, used))), 'duplicate slugs'
assert all(len(r) == 11 for r in lay.ROWS) and len(lay.ROWS) == 4

# ---------- simulation ----------

def simulate_mech(words):
    X = 0          # print point on the paper = left edge of the next cell (u)
    SA = SB = SW = 0    # memory sectors: b, c, w of the last advancing slug
    ev, placed = [], []
    for wi, word in enumerate(words):
        if wi:
            X += SPACE_W; SA = SB = SW = 0
            ev.append(dict(key='space', X=X, SA=SA, SB=SB, SW=SW, hit=None))
        for k in word:
            it = ITEMS[k]
            if it['kind'] in ADV:
                hit = X
                placed.append(('base', k, X + it['a']))       # axis position on the paper
                X += it['w']; SA, SB, SW = it['b'], it['c'], it['w']
                ev.append(dict(key=k, X=X, SA=SA, SB=SB, SW=SW, hit=hit, feed=it['w']))
            else:
                off = SB if it['below'] else SA
                hit = X - off
                placed.append(('mark', k, hit))
                ev.append(dict(key=k, X=X, SA=SA, SB=SB, SW=SW, hit=hit, off=off, sled='B' if it['below'] else 'A'))
    return ev, placed, X


def simulate_tpm1(words):
    """Reference: the electromechanical TPM-1 model (axial slugs, deferred phase)."""
    R = dict(a=0, b=0, d=0); X = 0; placed = []
    for wi, word in enumerate(words):
        if wi:
            X += R['b'] + SPACE_W; R = dict(a=0, b=0, d=0)
        for k in word:
            it = ITEMS[k]
            if it['kind'] in ADV:
                X += R['b'] + it['a']; placed.append(('base', k, X)); R = dict(a=it['a'], b=it['b'], d=it['d'])
            else:
                placed.append(('mark', k, X + (R['d'] if it['below'] else 0)))
    return placed


def render(placed, y=0):
    s = []
    for kind, k, X in placed:
        it = ITEMS[k]
        s.append(gl(it['glyph'], X * U - it['ax'], y))
        if kind == 'base' and it['kind'] == 'C':
            s.append(gl(it['mark'], X * U - MARK_AX[it['mark']], y))
    return ''.join(s)


def ustring(words):
    out = []
    for wi, word in enumerate(words):
        if wi:
            out.append('\\ ')
        for k in word:
            if k in MARK_CP:
                out.append(f"\\symbol{{\"{hexs(MARK_CP[k])}}}")
            else:
                out.extend(f"\\symbol{{\"{hexs(c)}}}" for c in ITEMS[k]['cps'])
    return ''.join(out)


def fig_trace(words, ref_y=-1250):
    ev, placed, Xend = simulate_mech(words)
    ref = simulate_tpm1(words)
    assert [(a, str(b), c) for a, b, c in placed] == [(a, str(b), c) for a, b, c in ref], 'TPM-2 != TPM-1'
    s = [render(placed, 0)]
    s.append(f"\\node[anchor=base west,inner sep=0pt] at (0,{ref_y}) {{\\TGtext{{{ustring(words)}}}}};\n")
    for e in ev:
        if e['key'] not in ('space',) and e['hit'] is not None:
            col = 'axisred' if e.get('feed') else ('sledA' if e.get('sled') == 'A' else 'sledB')
            s.append(f"\\draw[{col},thick] ({e['hit']*U},-380) -- ({e['hit']*U},-290);\n")
    s.append(f"\\draw[base] (0,0) -- ({Xend*U},0); \\draw[base] (0,{ref_y}) -- ({Xend*U},{ref_y});\n")
    s.append(f"\\node[lbl,anchor=east] at (-60,250) {{ТПМ-2}};\n")
    s.append(f"\\node[lbl,anchor=east] at (-60,{ref_y + 250}) {{шрифт}};\n")
    return ''.join(s), ev


def trace_table(ev):
    rows = []; n = 0
    for e in ev:
        if e['key'] == 'space':
            rows.append(f"— & пробел {SPACE_W}u & — & — & {e['X']} & 0 / 0 / 0\\\\\n"); continue
        n += 1; it = ITEMS[e['key']]
        kind = {'T': 'тенгва', 'C': 'ára+техта', 'N': 'цифра', 'P': 'знак'}.get(it['kind'])
        mem = f"{e['SA']} / {e['SB']} / {e['SW']}"
        if kind:
            rows.append(f"{n} & {inline(e['key'])}\\ {kind} & {e['hit']} & — & {e['X']} & {mem}\\\\\n")
        else:
            what = 'подстр.' if it['below'] else 'надстр.'
            rows.append(f"{n} & {inline(e['key'])}\\ {what} & {e['hit']} & $-{e['off']}$ & {e['X']} & {mem}\\\\\n")
    return ''.join(rows)


# ---------- figures ----------

def slug_adv(key, x0, title):
    it = ITEMS[key]; w = it['w'] * U; ax = it['a'] * U; s = []
    s.append(f"\\draw[slug] ({x0 - 60},-400) rectangle ({x0 + w + 60},820);\n")
    s.append(f"\\fill[cellfill] ({x0},-330) rectangle ({x0 + w},740);\n")
    s.append(gl(it['glyph'], x0 + ax - it['ax'], 0))
    if it['kind'] == 'C':
        s.append(gl(it['mark'], x0 + ax - MARK_AX[it['mark']], 0))
    s.append(f"\\draw[axisT,thin,draw=ink!35] ({x0 + ax},-330) -- ({x0 + ax},760);\n")
    s.append(f"\\draw[ppoint] ({x0},-470) -- ({x0},900);\n")
    s.append(f"\\draw[dim] ({x0},-540) -- ({x0 + w},-540);\n")
    s.append(f"\\node[lbl,anchor=north] at ({x0 + w/2},-570) {{$w{{=}}{it['w']}$}};\n")
    s.append(f"\\node[lbl,anchor=north] at ({x0 + w/2},-700) {{$b{{=}}{it['b']}$, $c{{=}}{it['c']}$}};\n")
    s.append(f"\\node[lbl,anchor=south] at ({x0 + w/2},930) {{{title}}};\n")
    return ''.join(s), w


def slug_dead(key, x0, title):
    it = ITEMS[key]; width = max(it['length'], 300) + 120; cx = x0 + width / 2; s = []
    s.append(f"\\draw[slug,fill={'sledB' if it['below'] else 'sledA'}!12] ({x0 - 60},-400) rectangle ({x0 + width + 60},820);\n")
    s.append(gl(it['glyph'], cx - it['ax'], 0))
    s.append(f"\\draw[ppoint] ({cx},-470) -- ({cx},900);\n")
    s.append(f"\\node[lbl,anchor=north] at ({cx},-570) {{отвод ${'c' if it['below'] else 'b'}$}};\n")
    s.append(f"\\node[lbl,anchor=south] at ({cx},930) {{{title}}};\n")
    return ''.join(s), width


def row(items, gap=260):
    s = []; x = 0
    for k, ttl in items:
        f = slug_adv if ITEMS[k]['kind'] in ADV else slug_dead
        code, w = f(k, x, ttl); s.append(code); x += w + gap
    return ''.join(s)


def fig_geometry():
    """Three moments for 'tinco + e + y-dots': strike letter, feed w, strike marks from sledges."""
    t = ITEMS[0xE000]; e = ITEMS['mark:e']; y2 = ITEMS['mark:ddotb']
    s = []; w = t['w'] * U; ax = t['a'] * U
    # paper cell
    s.append(f"\\fill[cellfill] (0,-330) rectangle ({w},740);\n")
    s.append(gl(t['glyph'], ax - t['ax'], 0))
    s.append(gl(e['glyph'], ax - e['ax'], 0))
    bx = (t['w'] - t['c']) * U
    s.append(gl(y2['glyph'], bx - y2['ax'], 0))
    s.append(f"\\draw[base] (-200,0) -- ({w + 200},0);\n")
    # moments
    s.append(f"\\draw[ppoint] (0,-420) -- (0,880); \\node[lbl,anchor=south,text=axisred] at (0,890) {{1}};\n")
    s.append(f"\\draw[ppoint] ({w},-420) -- ({w},880); \\node[lbl,anchor=south,text=axisred] at ({w},890) {{2}};\n")
    s.append(f"\\draw[sledA,thick,dash pattern=on 4pt off 2pt] ({ax},300) -- ({ax},880); \\node[lbl,anchor=south,text=sledA] at ({ax},890) {{3}};\n")
    s.append(f"\\draw[sledB,thick,dash pattern=on 4pt off 2pt] ({bx},-420) -- ({bx},60); \\node[lbl,anchor=north,text=sledB] at ({bx},-430) {{4}};\n")
    s.append(f"\\draw[dim] (0,-680) -- ({w},-680); \\node[lbl,anchor=west] at ({w + 40},-680) {{подача: $w{{=}}{t['w']}$}};\n")
    s.append(f"\\draw[dim,draw=sledA] ({ax},800) -- ({w},800); \\node[lbl,anchor=west,text=sledA] at ({w + 40},800) {{отвод узла для надстрочного: $b{{=}}{t['b']}$}};\n")
    s.append(f"\\draw[dim,draw=sledB] ({bx},-500) -- ({w},-500); \\node[lbl,anchor=west,text=sledB] at ({w + 40},-500) {{отвод узла для подстрочного: $c{{=}}{t['c']}$}};\n")
    return ''.join(s)


# ---------- shuttle ----------
PITCH = 19   # u per shuttle position: widest cell 16u + 3u gap


def shuttle_rows():
    """8 shuttle rows x 11 positions (rev. 0.6): position = keyboard column, row = keyboard row + 4 * register."""
    rows = [[None] * 11 for _ in range(8)]
    for r, rw in enumerate(lay.ROWS):
        for c, (lo, up) in enumerate(rw):
            rows[ROW_CODE[r]][c] = lo
            rows[4 + ROW_CODE[r]][c] = up
    return rows


def fig_shuttle():
    """Development of the shuttle as the blocks carry the type: hammer axis 1u from the left of each block;
    advancing letters start at the axis, dead marks have their anchor 8u right of it."""
    s = []; P = PITCH * U; RH = 1750
    reg = ['нижний', 'верхний']
    for ri, rw in enumerate(shuttle_rows()):
        y = -ri * RH
        s.append(f"\\node[lbl,anchor=east] at (-150,{y + 200}) {{{ri + 1}}};\n")
        for pi, k in enumerate(rw):
            x0 = pi * P
            ref = x0 + U
            s.append(f"\\draw[slug,fill=white] ({x0},{y - 380}) rectangle ({x0 + P - 40},{y + 780});\n")
            if k is None:
                s.append(f"\\node[keyres] at ({x0 + P/2},{y + 200}) {{—}};\n"); continue
            it = ITEMS[k]
            if it['kind'] in ADV:
                s.append(f"\\fill[cellfill] ({ref},{y - 330}) rectangle ({ref + it['w'] * U},{y + 740});\n")
                s.append(gl(it['glyph'], ref + it['a'] * U - it['ax'], y))
                if it['kind'] == 'C':
                    s.append(gl(it['mark'], ref + it['a'] * U - MARK_AX[it['mark']], y))
            else:
                col = 'sledB' if it['below'] else 'sledA'
                s.append(f"\\fill[{col}!12] ({x0},{y - 380}) rectangle ({x0 + P - 40},{y + 780});\n")
                s.append(gl(it['glyph'], ref + 8 * U - it['ax'], y))
            s.append(f"\\draw[ppoint,thin] ({ref},{y - 380}) -- ({ref},{y + 780});\n")
    for pi in range(11):
        s.append(f"\\node[lbl,anchor=north] at ({pi * P + P / 2},{-7 * RH - 420}) {{{pi + 1}}};\n")
    return ''.join(s)


# ---------- keyboard ----------

def esc(c):
    return {'\\': '\\textbackslash{}', "'": '\\textquotesingle{}', '[': '{[}'}.get(c, c)


def key_face(k, pos):
    it = ITEMS[k]
    size = '\\tgkeyU' if pos == 'up' else '\\tgkeyL'
    if it['kind'] in ('T', 'N', 'P'):
        return f"{{{size}\\symbol{{\"{hexs(it['cps'][0])}}}}}"
    if it['kind'] == 'C':
        return f"{{{size}\\symbol{{\"{hexs(it['cps'][0])}}}\\symbol{{\"{hexs(it['cps'][1])}}}}}"
    scale = '\\tgkuU' if pos == 'up' else '\\tgkuL'
    return (f"\\tikz[baseline=0pt,x={scale},y={scale}]{{\\draw[gray!55,densely dotted] (0,-150) -- (0,650);"
            + gl(it['glyph'], -it['ax'], 0).replace('\\TG{', '\\TGk' + ('U' if pos == 'up' else 'L') + '{') + "}")


def keyboard():
    s = []; KW, KH, G = 12.4, 14.0, 1.3; offs = [0, 4, 6, 9]
    for r, rw in enumerate(lay.ROWS):
        for c, (lo, up) in enumerate(rw):
            x = offs[r] + c * (KW + G); y = -r * (KH + G)
            itl = ITEMS[lo]
            fill = 'keyadv' if itl['kind'] in ADV else ('sledB!18' if itl['below'] else 'sledA!18')
            s.append(f"\\draw[key,fill={fill}] ({x},{y}) rectangle +({KW},{-KH});\n")
            s.append(f"\\node[keyleg] at ({x + KW - 1.0},{y - 1.2}) {{\\texttt{{{esc(lay.LEGENDS[r][c])}}}}};\n")
            for k, pos in ((up, 'up'), (lo, 'lo')):
                if k is None:
                    if pos == 'up':
                        s.append(f"\\node[keyres] at ({x + KW*0.4},{y - 3.6}) {{резерв}};\n")
                    continue
                yy = y - 4.6 if pos == 'up' else y - 10.9
                xx = x + (KW*0.32 if pos == 'up' else KW*0.6)
                s.append(f"\\node[anchor=base,inner sep=0pt,{('keyup' if pos == 'up' else 'keylo')}] at ({xx},{yy}) {{{key_face(k, pos)}}};\n")
    y = -4 * (KH + G)
    def fk(x, wdt, txt):
        s.append(f"\\draw[key,fill=keyfn] ({x},{y}) rectangle +({wdt},{-KH*0.8}); \\node[fnleg,align=center] at ({x + wdt/2},{y - KH*0.4}) {{{txt}}};\n")
        return x + wdt + G
    x = fk(0, KW*1.6, 'РЕГИСТР'); x = fk(x, KW*1.3, 'ЗАБОЙ\\\\1u'); x = fk(x, KW*3.2, f'ПРОБЕЛ {SPACE_N}u')
    x = fk(x, KW*3.2, f'ПРОБЕЛ {SPACE_W}u'); x = fk(x, KW*1.3, '$\\pm$u'); fk(x, KW*1.9, 'НАЗАД\\\\НА ЛИТЕРУ')
    return ''.join(s)


# ---------- tables ----------

def tab_codes():
    rows = []
    for t in D['tengwar']:
        it = ITEMS[t['cp']]
        rows.append(f"{inline(t['cp'])} & {t['name']} & {hexs(t['cp'])} & {it['w']} & {it['a']} & {it['b']} & "
                    f"{it['d']:+d} & {it['c']}\\\\\n")
    for key in [n['cp'] for n in D['numerals']] + [p['cp'] for p in D['punct']] + ['combo:' + c['name'] for c in D['combos']]:
        it = ITEMS[key]
        rows.append(f"{inline(key)} & {it['label']} & {hexs(key) if isinstance(key, int) else '02C+…'} & {it['w']} & "
                    f"{it['a']} & {it['b']} & {it['d']:+d} & {it['c']}\\\\\n")
    return ''.join(rows)


files = {}
files['fig_geometry.tex'] = fig_geometry()
files['fig_slugs_adv.tex'] = row([(0xE000, 'tinco'), (0xE004, 'ando'), (0xE00A, 'harma'), (0xE028, 'hyarmen'),
                                  (0xE02E, 'telco'), ('combo:ára+e', 'ára+e')])
files['fig_slugs_dead.tex'] = row([('mark:a', 'a'), ('mark:e', 'e'), ('mark:nasW', 'нос. шир.'), ('mark:ddotb', 'y'),
                                   ('mark:dbl', 'удв. узк.'), ('mark:dblL', 'удв. lambe'), ('mark:ddotbL', 'y в lambe')])
files['keyboard.tex'] = keyboard()
files['fig_shuttle.tex'] = fig_shuttle()
files['tab_codes.tex'] = tab_codes()
tq, evq = fig_trace(QUENYA); files['fig_trace_q.tex'] = tq; files['tab_trace_q.tex'] = trace_table(evq)
ts, evs = fig_trace(SINDARIN); files['fig_trace_s.tex'] = ts; files['tab_trace_s.tex'] = trace_table(evs)
for n, c in files.items():
    open(os.path.join(out, n), 'w').write(c)

adv_items = [it for it in ITEMS.values() if it['kind'] in ADV]
st = dict(slots=len(used), w=(min(i['w'] for i in adv_items), max(i['w'] for i in adv_items)),
          b=(min(i['b'] for i in adv_items), max(i['b'] for i in adv_items)),
          c=(min(i['c'] for i in adv_items), max(i['c'] for i in adv_items)),
          w_levels=sorted({i['w'] for i in adv_items}), b_levels=sorted({i['b'] for i in adv_items}),
          c_levels=sorted({i['c'] for i in adv_items}),
          missing=sorted(set(map(str, list(ITEMS))) - set(map(str, used))))
json.dump(st, open(os.path.join(out, 'stats.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(st, ensure_ascii=False))


# ---------- rev. 0.3: code plates and the acceptance test text ----------
AN = json.load(open(os.path.join(out, 'analysis_fdm.json')))   # rev. 0.4: FDM profile
T_TRAVEL, K_STEP = AN['choice']['Tp'], AN['choice']['k']
W_OFFSET = 4                                                    # W measures w - 4


def gap(v):
    return T_TRAVEL - K_STEP * v


def tab_plates():
    rows = []
    for r, rw in enumerate(lay.ROWS):
        for c, pair in enumerate(rw):
            for tier, k in (('н', pair[0]), ('в', pair[1])):
                leg = esc(lay.LEGENDS[r][c])
                srow = ROW_CODE[r] + (4 if tier == 'в' else 0) + 1
                pin = c + 1
                if k is None:
                    rows.append(f"\\texttt{{{leg}}} & {tier} & — & резерв & {srow} & {pin} & \\multicolumn{{6}}{{c}}{{—}}\\\\\n")
                    continue
                it = ITEMS[k]
                if it['kind'] in ADV:
                    cells = f"0 & {gap(it['w'] - W_OFFSET):.1f} & {gap(it['b']):.1f} & {gap(it['c']):.1f} & — & —"
                    kind = 'прод.'
                else:
                    cells = f"— & — & — & — & 0 & {'0' if it['below'] else '—'}"
                    kind = 'подстр.' if it['below'] else 'надстр.'
                rows.append(f"\\texttt{{{leg}}} & {tier} & {inline(k)} & {kind} & {srow} & {pin} & {cells}\\\\\n")
    return ''.join(rows)


def test_sequence():
    """Greedy cover of all w, b and c values; each slug is followed by a dot above and a dot below."""
    cand = [k for row in lay.ROWS for pair in row for k in pair if k is not None and ITEMS[k]['kind'] in ADV]
    need = {('w', v) for v in {ITEMS[k]['w'] for k in cand}} | {('b', v) for v in {ITEMS[k]['b'] for k in cand}} \
        | {('c', v) for v in {ITEMS[k]['c'] for k in cand}}
    chosen = []
    while need:
        best = max(cand, key=lambda k: (len(need & {('w', ITEMS[k]['w']), ('b', ITEMS[k]['b']), ('c', ITEMS[k]['c'])}), ITEMS[k]['kind'] == 'T'))
        got = need & {('w', ITEMS[best]['w']), ('b', ITEMS[best]['b']), ('c', ITEMS[best]['c'])}
        assert got, 'cover stuck'
        chosen.append(best); need -= got; cand.remove(best)
    chosen.sort(key=lambda k: (ITEMS[k]['w'], ITEMS[k]['b'], ITEMS[k]['c']))
    words, word = [], []
    for k in chosen:
        word += [k, 'mark:i', 'mark:dotb']
        if len(word) >= 3 * 5:
            words.append(word); word = []
    if word:
        words.append(word)
    return chosen, words


def fig_test(words):
    ev, placed, Xend = simulate_mech(words[:1] if False else words)
    s = [render(placed, 0)]
    for kind, k, X in placed:
        if kind == 'base':
            it = ITEMS[k]
            s.append(f"\\draw[axisT,thin] ({X*U},700) -- ({X*U},860);\n")
            s.append(f"\\draw[{'axisB' if it['d'] else 'axisT'},thin] ({(X + it['d'])*U},-360) -- ({(X + it['d'])*U},-200);\n")
    s.append(f"\\draw[base] (0,0) -- ({Xend*U},0);\n")
    return ''.join(s), Xend


def tab_test(chosen):
    return ''.join(f"{inline(k)} & {ITEMS[k]['label']} & {ITEMS[k]['w']} & {ITEMS[k]['b']} & {ITEMS[k]['c']}\\\\\n"
                   for k in chosen)


chosen, twords = test_sequence()
extra = {'tab_plates.tex': tab_plates(), 'tab_test.tex': tab_test(chosen)}
lines = [[w] for w in twords]
extra['fig_test.tex'] = ''
for li, ln in enumerate(lines):
    code, xe = fig_test(ln)
    extra['fig_test.tex'] += f"\\begin{{scope}}[shift={{(0,{-li * 1700})}}]\n" + code + "\\end{scope}\n"
for n, c in extra.items():
    open(os.path.join(out, n), 'w').write(c)
print('test slugs:', len(chosen), [ITEMS[k]['label'] for k in chosen])
