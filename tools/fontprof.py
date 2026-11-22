"""rev. 0.11: measure any CSUR tengwar font for the TPM-2 shuttle (font sets beside Alcarin).

The machine is the same for every font: em = 1/3", u = em/16, the hammer window and the type blocks are those of
Alcarin, the codes are read from the shuttle (w - 4 in 0..12, b in 0..8, c in 0..9). For another font this module
  * scales its outlines so that its body height equals Alcarin's (the short tengwar's tops, 0.412 em), then, if a
    code or the ink leaves the machine's limits, tries smaller and slightly larger scales (0.80..1.10 of that) and keeps
    the one nearest to 1 that fits;
  * takes the tehta axes and the bottom axes from the font's GPOS mark-to-base anchors (any lookup whose marks
    include the vowel tehtar above, or the dots below);
  * pads carriers narrower than 4 u to w = 4 (the escapement's smallest step), keeping their axis;
  * reports what does not fit.
The result has the layout of data/codes.json (font units normalised to 1000 per em) plus 'scale', 'issues', 'pad'
and 'missing', and a glyph set with the same normalisation (ScaledGlyphSet), so the rest of the chain (gen of the
items, thickening, type blocks, combs, the page) works unchanged.
Usage: python3 -I fontprof.py FONT [FONT ...]      (prints a fit report)"""
import os, sys, json, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen
import inventory as inv

ALCARIN_BODY = 0.412                 # em: median top of tinco..ungwe and numen..vilya in Alcarin
# limits of the machine (mm and u, from the Alcarin build: hammer window = Alcarin's ink extents + 0.1 mm)
EM_MM = 25.4 / 3
U_MM = EM_MM / 16
WIN_X = (-0.471, 8.704)              # mm from the hammer axis (parts.hammer_face)
WIN_Z = (-4.200, 6.600)              # mm from the baseline; rev. 0.11: -4.2..6.6 (Alcarin's ink: -2.85..6.13) for the long
                                     # stems of other fonts; the neighbouring rows (11.43 mm) keep 0.63 mm clear of the face
INK_MARGIN = 0.15                    # mm: the thickening of hairlines (0.45 mm least stroke) may widen the ink this much
_WX = (WIN_X[0] + INK_MARGIN, WIN_X[1] - INK_MARGIN)
_WZ = (WIN_Z[0] + INK_MARGIN, WIN_Z[1] - INK_MARGIN)
W_RANGE, B_MAX, C_MAX = (4, 16), 8, 9
MARK_REF_U = 8
TOP_CP = (0xE040, 0xE044, 0xE046, 0xE04A, 0xE04C)
BOT_CP = (0xE045, 0xE043)
# mark key -> codepoint (gen_shuttle.MARK_CP); the variant names are Alcarin's, used when the font has them
MARK_CP = {'a': 0xE040, 'e': 0xE046, 'i': 0xE044, 'o': 0xE04A, 'u': 0xE04C, 'tilde': 0xE052, 'nas': 0xE050,
           'nasW': 0xE050, 'dotb': 0xE045, 'ddotb': 0xE043, 'dbl': 0xE051, 'dblW': 0xE051, 'dblL': 0xE051, 'ddotbL': 0xE043, 'lsd': 0xE07D}


class _G:
    def __init__(self, g, k, gs):
        self.g, self.k, self.gs = g, k, gs
        self.width = g.width * k

    def draw(self, pen):
        # composites are decomposed in the font's own glyph set first: a pen that looks components up in the scaled
        # set would scale them twice (rev. 0.11, found on Tengwar Formal CSUR, whose tehtar are composites)
        from fontTools.pens.recordingPen import DecomposingRecordingPen
        rp = DecomposingRecordingPen(self.gs)
        self.g.draw(rp)
        rp.replay(TransformPen(pen, (self.k, 0, 0, self.k, 0, 0)))


class ScaledGlyphSet:
    """Glyph set whose outlines are scaled by k (font units -> 1000 per em at the chosen scale), some glyphs by an
    extra factor (numerals and punctuation taller than the hammer window)."""
    def __init__(self, gs, k, extra=None):
        self.gs, self.k, self.extra = gs, k, extra or {}

    def __getitem__(self, name):
        return _G(self.gs[name], self.k * self.extra.get(name, 1.0), self.gs)

    def __contains__(self, name):
        return name in self.gs

    def keys(self):
        return self.gs.keys()


def _markbase(font):
    if 'GPOS' not in font or font['GPOS'].table.LookupList is None:
        return
    for lk in font['GPOS'].table.LookupList.Lookup:
        for st in lk.SubTable:
            t = lk.LookupType
            if t == 9:
                t = st.ExtensionLookupType; st = st.ExtSubTable
            if t == 4:
                yield st


def anchors(font, top_marks, bot_marks, lambe_marks=()):
    """Base anchors for the classes of the top / bottom marks, and the mark anchors of every mark glyph."""
    top, bot, botL, mark = {}, {}, {}, {}
    for st in _markbase(font):
        cls_of = {}
        for mi, mr in enumerate(st.MarkArray.MarkRecord):
            g = st.MarkCoverage.glyphs[mi]
            cls_of[g] = mr.Class
            mark.setdefault(g, (mr.MarkAnchor.XCoordinate, mr.MarkAnchor.YCoordinate))
        tc = {cls_of[g] for g in top_marks if g in cls_of}
        bc = {cls_of[g] for g in bot_marks if g in cls_of}
        lc = {cls_of[g] for g in lambe_marks if g in cls_of}
        for bi, bg in enumerate(st.BaseCoverage.glyphs):
            rec = st.BaseArray.BaseRecord[bi]
            for ci, a in enumerate(rec.BaseAnchor):
                if a is None:
                    continue
                xy = (a.XCoordinate, a.YCoordinate)
                if ci in tc: top.setdefault(bg, xy)
                if ci in bc: bot.setdefault(bg, xy)
                if ci in lc: botL.setdefault(bg, xy)
    return top, bot, botL, mark


def _bounds(gs, name):
    p = BoundsPen(gs); gs[name].draw(p); return p.bounds


def raw(path):
    """Font-unit measurements, independent of the scale."""
    f = TTFont(path)
    cm = f.getBestCmap(); gs = f.getGlyphSet(); hm = f['hmtx']; upm = f['head'].unitsPerEm
    if not (0xE000 in cm and 0xE004 in cm):
        if all(ord(c) in cm for c in '1qaz2wsx#EDC%TGB'):
            return raw_ds(path, f)
        return dict(path=path, ok=False, why='ни CSUR, ни раскладка Дэна Смита: знаки не опознаны')
    tops = [cm[c] for c in TOP_CP if c in cm]
    bots = [cm[c] for c in BOT_CP if c in cm]
    lam = [g for g in ('uniE051.lambe',) if g in gs]
    top, bot, botL, mark = anchors(f, tops, bots, lam)
    if not top:
        return raw_shaped(path, f)
    name = f['name'].getDebugName(4) or os.path.basename(path)
    def glyph(cp):
        g = cm.get(cp)
        if g is None or g not in gs:
            return None
        b = _bounds(gs, g)
        return g if b is not None else None
    T = []
    for cp, nm in inv.TENGWAR:
        g = glyph(cp)
        if g is None:
            T.append(dict(cp=cp, name=nm, missing=True)); continue
        T.append(dict(cp=cp, name=nm, glyph=g, adv=hm[g][0], bbox=_bounds(gs, g), top=top.get(g), bot=bot.get(g),
                      botL=botL.get(g)))
    M = []
    for key, gname, kind, role in inv.MARKS:
        g = gname if gname in gs and _bounds(gs, gname) is not None else glyph(MARK_CP[key])
        if g is None:
            M.append(dict(key=key, kind=kind, role=role, missing=True)); continue
        bb = _bounds(gs, g)
        M.append(dict(key=key, glyph=g, kind=kind, role=role, bbox=bb, anchor=mark.get(g, ((bb[0] + bb[2]) / 2, 0)),
                      length=bb[2] - bb[0], variant=g == gname and gname != cm.get(MARK_CP[key])))
    NP = []
    for cp, nm in inv.NUMERALS + inv.PUNCT:
        g = glyph(cp)
        if g is None:
            NP.append(dict(cp=cp, name=nm, missing=True)); continue
        NP.append(dict(cp=cp, name=nm, glyph=g, adv=hm[g][0], bbox=_bounds(gs, g), top=top.get(g)))
    short = [t['bbox'][3] for t in T if not t.get('missing') and (0xE000 <= t['cp'] <= 0xE007 or 0xE010 <= t['cp'] <= 0xE017)]
    body = statistics.median(short) / upm if short else None
    return dict(path=path, ok=True, name=name, upm=upm, gs=gs, T=T, M=M, NP=NP, body=body,
                anchored=sum(1 for t in T if t.get('top')))



# ------------------------------------------------------------------ rev. 0.11: fonts in Dan Smith's layout
# The characters sit on ASCII and Latin-1 keys (the same map in all of Dan Smith's fonts). Such a font has no anchors:
# the typist picks one of four widths of every tehta (wide, normal, narrow, narrowest), and the tehta, a glyph of zero
# advance drawn left of its origin, falls over the letter typed before it. So each width gives a candidate axis for a
# letter: its advance plus the tehta's offset. The axis of a letter is the candidate nearest to the centre of its ink
# in the upper body zone (stems left out), i.e. the width the font's designer meant for letters of that shape; the
# bottom axis likewise from the four dots below and the ink of the lower body zone. On the fonts that do have
# anchors the geometric estimate alone misses the true axis by 0.6-1.3 u on average (up to 2.5 u); snapping to the
# designer's widths, 2-3 u apart, removes most of that, and the sheet tools/fontaxes.py draws every letter with its
# axes for a look.
DS_T = {0xE000: '1', 0xE001: 'q', 0xE002: 'a', 0xE003: 'z', 0xE004: '2', 0xE005: 'w', 0xE006: 's', 0xE007: 'x',
        0xE008: '3', 0xE009: 'e', 0xE00A: 'd', 0xE00B: 'c', 0xE00C: '4', 0xE00D: 'r', 0xE00E: 'f', 0xE00F: 'v',
        0xE010: '5', 0xE011: 't', 0xE012: 'g', 0xE013: 'b', 0xE014: '6', 0xE015: 'y', 0xE016: 'h', 0xE017: 'n',
        0xE018: '!', 0xE019: 'Q', 0xE01A: 'A', 0xE01B: 'Z', 0xE01C: '@', 0xE01D: 'W', 0xE01E: 'S', 0xE01F: 'X',
        0xE020: '7', 0xE021: 'u', 0xE022: 'j', 0xE023: 'm', 0xE024: '8', 0xE025: 'i', 0xE026: 'k', 0xE027: ',',
        0xE028: '9', 0xE029: 'o', 0xE02A: 'l', 0xE02B: '.', 0xE02C: '~', 0xE02D: '½', 0xE02E: '`'}
DS_NP = {0xE070 + i: chr(0xF0 + i) for i in range(12)}            # numerals 0..11 on ð..û
DS_NP.update({0xE060: '=', 0xE061: '-', 0xE065: 'Á', 0xE066: 'À', 0xE067: 'Œ', 0xE06A: '«', 0xE06B: '»'})
DS_V = {'a': '#EDC', 'e': '$RFV', 'i': '%TGB', 'o': '^YHN', 'u': '&UJM'}     # widths: wide, normal, narrow, narrowest
DS_BELOW = 'ÈÉÊË'                               # dot below, four widths
DS_MARK = {'a': 'E', 'e': 'R', 'i': 'T', 'o': 'Y', 'u': 'U', 'tilde': 'p', 'nas': '[', 'nasW': '{', 'dotb': 'É',
           'ddotb': 'Í', 'dbl': "'", 'dblW': '"', 'dblL': "'", 'ddotbL': 'Í'}           # the dead marks: the normal width


def _ink_centre(G, body, zone, strip_stems=False):
    """Centre of the ink of G in the band zone (fractions of the body height); with strip_stems the stems (parts that
    reach above 1.15 or under -0.15 body, narrower than 0.35 body) are cut out of the band first."""
    from shapely.geometry import box as sbox
    x0, y0, x1, y1 = G.bounds
    g = G.intersection(sbox(x0 - 1, zone[0] * body, x1 + 1, zone[1] * body))
    if g.is_empty:
        return None
    if strip_stems:
        for ys in ((1.15 * body, y1 + 1), (y0 - 1, -0.15 * body)):
            if ys[1] <= ys[0]:
                continue
            st = G.intersection(sbox(x0 - 1, ys[0], x1 + 1, ys[1]))
            for p in (list(st.geoms) if hasattr(st, 'geoms') else [st]):
                if p.is_empty:
                    continue
                a, _, b2, _ = p.bounds
                if b2 - a < 0.35 * body:
                    rest = g.difference(sbox(a - 0.04 * body, zone[0] * body - 1, b2 + 0.04 * body, zone[1] * body + 1))
                    if not rest.is_empty and rest.area > 0.25 * g.area:
                        g = rest
    b = g.bounds
    return (b[0] + b[2]) / 2


def raw_ds(path, f):
    from glyphgeom import glyph_geom
    cm = f.getBestCmap(); gs = f.getGlyphSet(); hm = f['hmtx']; upm = f['head'].unitsPerEm
    gn = lambda ch: cm.get(ord(ch)) if ch and ord(ch) in cm and _bounds(gs, cm[ord(ch)]) is not None else None
    cx = lambda g: (lambda b: (b[0] + b[2]) / 2)(_bounds(gs, g))
    off_top = [cx(gn(c)) for c in DS_V['i']]                       # axis offsets of the four widths (the dot i)
    off_bot = [cx(gn(c)) if gn(c) else None for c in DS_BELOW]
    T = []
    for cp, nm in inv.TENGWAR:
        g = gn(DS_T.get(cp))
        if g is None:
            T.append(dict(cp=cp, name=nm, missing=True)); continue
        T.append(dict(cp=cp, name=nm, glyph=g, adv=hm[g][0], bbox=_bounds(gs, g)))
    short = [t['bbox'][3] for t in T if not t.get('missing') and (0xE000 <= t['cp'] <= 0xE007 or 0xE010 <= t['cp'] <= 0xE017)]
    body = statistics.median(short)
    for t in T:
        if t.get('missing'):
            continue
        G = glyph_geom(gs, t['glyph'])
        h = _ink_centre(G, body, (0.45, 1.05)) or t['adv'] / 2
        k = min(range(4), key=lambda i: abs(t['adv'] + off_top[i] - h))
        t['top'] = (t['adv'] + off_top[k], 0.0); t['wk'] = k; t['est'] = h
        hb = _ink_centre(G, body, (-0.02, 0.3))
        cand = [(i, t['adv'] + o) for i, o in enumerate(off_bot) if o is not None]
        if hb is not None and cand:
            kb, xb = min(cand, key=lambda c: abs(c[1] - hb))
            t['bot'] = (xb, 0.0); t['wkb'] = kb
        else:
            t['bot'] = t['top']
    # the dead marks: one glyph each (the normal width); its axis is the normal width's offset of the dot i
    M = []
    for key, gname, kind, role in inv.MARKS:
        g = gn(DS_MARK.get(key))
        if g is None:
            M.append(dict(key=key, kind=kind, role=role, missing=True)); continue
        bb = _bounds(gs, g)
        ax = off_top[1] if key in DS_V else (off_bot[1] if key in ('dotb', 'ddotb') and off_bot[1] is not None else (bb[0] + bb[2]) / 2)
        M.append(dict(key=key, glyph=g, kind=kind, role=role, bbox=bb, anchor=(ax, 0.0), length=bb[2] - bb[0], variant=False))
    # ara + vowel: the vowel in the width that fits ara
    ara = next((t for t in T if t['cp'] == 0xE02C and not t.get('missing')), None)
    combo = {}
    if ara:
        for v, keys in DS_V.items():
            g = gn(keys[ara['wk']])
            if g:
                combo[v] = dict(glyph=g, bbox=_bounds(gs, g), anchor=(off_top[ara['wk']], 0.0))
    NP = []
    for cp, nm in inv.NUMERALS + inv.PUNCT:
        g = gn(DS_NP.get(cp))
        if g is None:
            NP.append(dict(cp=cp, name=nm, missing=True)); continue
        NP.append(dict(cp=cp, name=nm, glyph=g, adv=hm[g][0], bbox=_bounds(gs, g), top=None))
    name = f['name'].getDebugName(4) or os.path.basename(path)
    return dict(path=path, ok=True, name=name, upm=upm, gs=gs, T=T, M=M, NP=NP, body=body / upm, anchored=0, ds=True,
                combo=combo, off_top=off_top, off_bot=off_bot)


# ------------------------------------------------------------------ rev. 0.11: CSUR fonts without mark anchors
# Such a font still puts its tehtar somewhere: by contextual substitution of a shifted tehta (Eldamar: GSUB; Tengwar
# Formal CSUR: AAT morx), by one fixed place for every letter (the monospaced FreeMono Tengwar, miue), or nowhere
# (Tengwar Eldamar: the tehta is centred on the pen, at the letter's right edge). HarfBuzz shapes letter + dot i
# (and letter + dot below) and the dot's ink centre is the axis the font gives. Where that axis is not over the
# letter's ink (more than 1 u outside it) or is 3 u or more off the centre of the letter's upper body, the axis is
# estimated from the outline instead (the same estimate as for Dan Smith's fonts, without widths to snap to:
# 0.6-1.3 u off on average on fonts with anchors) and counted in 'est'.
def raw_shaped(path, f):
    try:
        import uharfbuzz as hb
    except ImportError:
        return dict(path=path, ok=False, why='нет якорей техт, а для раскладки по шрифту нужен uharfbuzz')
    from glyphgeom import glyph_geom
    cm = f.getBestCmap(); gs = f.getGlyphSet(); hm = f['hmtx']; upm = f['head'].unitsPerEm; order = f.getGlyphOrder()
    hbf = hb.Font(hb.Face(hb.Blob.from_file_path(path)))
    U = upm / 16.0

    def shape(text):
        buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties(); hb.shape(hbf, buf, {})
        x, out = 0, []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            out.append((order[info.codepoint], x + pos.x_offset)); x += pos.x_advance
        return out

    def mark_axis(cp, mk):
        r = shape(chr(cp) + chr(mk))
        if len(r) < 2 or _bounds(gs, r[-1][0]) is None:
            return None, None
        b = _bounds(gs, r[-1][0])
        return r[-1][1] + (b[0] + b[2]) / 2, r[-1][0]

    def glyph(cp):
        g = cm.get(cp)
        return g if g is not None and g in gs and _bounds(gs, g) is not None else None
    T = []
    for cp, nm in inv.TENGWAR:
        g = glyph(cp)
        if g is None:
            T.append(dict(cp=cp, name=nm, missing=True)); continue
        T.append(dict(cp=cp, name=nm, glyph=g, adv=hm[g][0], bbox=_bounds(gs, g)))
    short = [t['bbox'][3] for t in T if not t.get('missing') and (0xE000 <= t['cp'] <= 0xE007 or 0xE010 <= t['cp'] <= 0xE017)]
    body = statistics.median(short)
    n_est = 0
    for t in T:
        if t.get('missing'):
            continue
        G = glyph_geom(gs, t['glyph'])
        h = _ink_centre(G, body, (0.45, 1.05), True) or t['adv'] / 2
        hb_ = _ink_centre(G, body, (-0.02, 0.3), True) or h
        x0, x1 = t['bbox'][0], t['bbox'][2]
        for key, mk, est in (('top', 0xE044, h), ('bot', 0xE045, hb_)):
            ax, _ = mark_axis(t['cp'], mk) if mk in cm else (None, None)
            if ax is None or ax < x0 - U or ax > x1 + U or abs(ax - est) >= 3 * U:
                ax = est
                if key == 'top':
                    n_est += 1; t['est'] = True
            t[key] = (ax, 0.0)
    M = []
    for key, gname, kind, role in inv.MARKS:
        g = gname if gname in gs and _bounds(gs, gname) is not None else glyph(MARK_CP[key])
        if g is None:
            M.append(dict(key=key, kind=kind, role=role, missing=True)); continue
        bb = _bounds(gs, g)
        M.append(dict(key=key, glyph=g, kind=kind, role=role, bbox=bb, anchor=((bb[0] + bb[2]) / 2, 0.0),
                      length=bb[2] - bb[0], variant=False))
    combo = {}
    ara = next((t for t in T if t['cp'] == 0xE02C and not t.get('missing')), None)
    if ara:
        for v, mk in (('a', 0xE040), ('e', 0xE046), ('i', 0xE044), ('o', 0xE04A), ('u', 0xE04C)):
            if mk not in cm:
                continue
            ax, g = mark_axis(0xE02C, mk)
            if g is None:
                continue
            b = _bounds(gs, g)
            combo[v] = dict(glyph=g, bbox=b, anchor=((b[0] + b[2]) / 2, 0.0))   # its own centre on ara's axis
    NP = []
    for cp, nm in inv.NUMERALS + inv.PUNCT:
        g = glyph(cp)
        if g is None:
            NP.append(dict(cp=cp, name=nm, missing=True)); continue
        NP.append(dict(cp=cp, name=nm, glyph=g, adv=hm[g][0], bbox=_bounds(gs, g), top=None))
    name = f['name'].getDebugName(4) or os.path.basename(path)
    return dict(path=path, ok=True, name=name, upm=upm, gs=gs, T=T, M=M, NP=NP, body=body / upm, anchored=0, shaped=True,
                combo=combo, est=n_est)

def codes_at(R, s, shrink_letters=False):
    """Codes and the fit report at scale s (1 = Alcarin's body height). rev. 0.12: with shrink_letters a letter that
    leaves the window vertically is drawn smaller about its origin (used only when no scale fits otherwise)."""
    k = R['body'] and (ALCARIN_BODY / R['body']) * s * 1000.0 / R['upm']
    U = 1000.0 / 16
    rd = lambda x: int(round(x))
    sc = lambda v: None if v is None else tuple(c * k for c in v)
    D = dict(U=U, UPM=1000, tengwar=[], marks=[], combos=[], numerals=[], punct=[], scale=s, k=k, pad=[], shift=[], missing=[],
             issues=[], warn=[], shrink={}, shrunk=[], cclamp=[])
    mm = EM_MM / 1000.0
    def ink(name, x0_mm, bb):
        """Check the ink of a glyph placed with its origin x0_mm from the hammer axis."""
        if bb is None:
            return
        xa, xb = x0_mm + bb[0] * mm, x0_mm + bb[2] * mm
        za, zb = bb[1] * mm, bb[3] * mm
        if xa < _WX[0] - 1e-6 or xb > _WX[1] + 1e-6:
            D['issues'].append((name, 'окно X', round(xa, 2), round(xb, 2)))
        if za < _WZ[0] - 1e-6 or zb > _WZ[1] + 1e-6:
            D['issues'].append((name, 'окно Z', round(za, 2), round(zb, 2)))
    def code(name, adv, top, bot=None, kind='T', bb=None):
        tx = top[0] if top else adv / 2
        a = rd(tx / U); b = rd((adv - tx) / U); w = a + b
        if w < W_RANGE[0]:
            D['pad'].append((name, w)); b += W_RANGE[0] - w; w = W_RANGE[0]
        if bb is not None:          # ink left of the hammer window: move the glyph right in its cell by whole units
            xa = (a * U - tx + bb[0]) * mm
            if xa < _WX[0]:
                n = int(-(-(_WX[0] - xa) // U_MM))
                a += n; w += n; D['shift'].append((name, n))
        d = rd((bot[0] - tx) / U) if (bot and top) else 0
        c = b - d
        if kind in ('T', 'C') and c > C_MAX:   # the bottom axis further left than sector C reaches: the marks below go
            D['cclamp'].append((name, c)); c = C_MAX; d = b - c      # (c - 9) u right of the font's place
        if w > W_RANGE[1]: D['issues'].append((name, 'w', w))
        if kind in ('T', 'C'):
            if b > B_MAX or b < 0: D['issues'].append((name, 'b', b))
            if c > C_MAX or c < 0: D['issues'].append((name, 'c', c))
        return a, b, w, d, tx
    for t in R['T']:
        if t.get('missing'):
            D['missing'].append(t['name']); D['tengwar'].append(dict(cp=t['cp'], name=t['name'], missing=True)); continue
        adv = t['adv'] * k; top, bot = sc(t['top']), sc(t['bot']); bb = sc(t['bbox'])
        if shrink_letters and bb is not None:
            f = 1.0
            if bb[3] * mm > _WZ[1]: f = min(f, _WZ[1] / (bb[3] * mm) * 0.995)
            if bb[1] * mm < _WZ[0]: f = min(f, _WZ[0] / (bb[1] * mm) * 0.995)
            if f < 1.0:
                D['shrink'][t['glyph']] = f; D['shrunk'].append((t['name'], round(f, 3)))
                adv *= f; bb = tuple(v * f for v in bb)
                top = tuple(v * f for v in top) if top else None
                bot = tuple(v * f for v in bot) if bot else None
        a, b, w, d, tx = code(t['name'], adv, top, bot, bb=bb)
        if not top:
            D['warn'].append((t['name'], 'нет якоря: ось посередине ширины'))
        ink(t['name'], a * U * mm - tx * mm, bb)
        D['tengwar'].append(dict(cp=t['cp'], name=t['name'], glyph=t['glyph'], adv=adv, bbox=bb, top=top or (tx, 400),
                                 bot=bot or (tx, 0), botL=sc(t.get('botL')), w=w, a=a, b=b,
                                 err_top=(a * U - tx) / U, d_bot=float(d)))
    for m in R['M']:
        if m.get('missing'):
            D['missing'].append(m['role']); D['marks'].append(dict(key=m['key'], kind=m['kind'], role=m['role'], missing=True))
            continue
        bb = sc(m['bbox']); an = sc(m['anchor'])
        f = 1.0                         # a tehta that leaves the window vertically is drawn smaller (about the line)
        if bb[3] * mm > _WZ[1]: f = min(f, _WZ[1] / (bb[3] * mm) * 0.995)
        if bb[1] * mm < _WZ[0]: f = min(f, _WZ[0] / (bb[1] * mm) * 0.995)
        if f < 1.0:
            if m['glyph'] not in D['shrink']:
                D['shrunk'].append((m['role'], round(f, 3)))
            f = min(f, D['shrink'].get(m['glyph'], 1.0)); D['shrink'][m['glyph']] = f
            bb = tuple(v * f for v in bb); an = tuple(v * f for v in an)
        ink(m['role'], MARK_REF_U * U * mm - an[0] * mm, bb)
        D['marks'].append(dict(key=m['key'], glyph=m['glyph'], kind=m['kind'], role=m['role'], bbox=bb, anchor=an,
                               length=bb[2] - bb[0], variant=m['variant']))
    car = next((t for t in D['tengwar'] if t['cp'] == 0xE02C and not t.get('missing')), None)
    VK = {0xE040: 'a', 0xE046: 'e', 0xE044: 'i', 0xE04A: 'o', 0xE04C: 'u'}
    for nm, cps in inv.COMBOS:
        mk = next((m for m in D['marks'] if not m.get('missing') and MARK_CP[m['key']] == cps[1] and not m['variant']), None)
        if R.get('combo') and VK[cps[1]] in R['combo']:            # Dan Smith's fonts: the width that fits ara
            c = R['combo'][VK[cps[1]]]
            mk = dict(glyph=c['glyph'], bbox=sc(c['bbox']), anchor=sc(c['anchor']))
            f = D['shrink'].get(c['glyph'], 1.0)      # a tehta over ara higher than the window: drawn smaller, as the dead ones
            if mk['bbox'][3] * mm > _WZ[1]: f = min(f, _WZ[1] / (mk['bbox'][3] * mm) * 0.995)
            if f < 1.0:
                if c['glyph'] not in D['shrink']:
                    D['shrunk'].append((nm, round(f, 3)))
                D['shrink'][c['glyph']] = f
                mk = dict(glyph=c['glyph'], bbox=tuple(v * f for v in mk['bbox']), anchor=tuple(v * f for v in mk['anchor']))
        if car is None or mk is None:
            D['missing'].append(nm); D['combos'].append(dict(name=nm, cps=cps, missing=True)); continue
        tx = car['top'][0]; a = rd(tx / U); w = a + rd((car['adv'] - tx) / U)
        b = w - a
        if w < W_RANGE[0]:
            b += W_RANGE[0] - w; w = W_RANGE[0]
        for g0, bb in ((tx, car['bbox']), (mk['anchor'][0], mk['bbox'])):
            xa = (a * U - g0 + bb[0]) * mm
            if xa < _WX[0]:
                n = int(-(-(_WX[0] - xa) // U_MM)); a += n; w += n; D['shift'].append((nm, n))
        if w > W_RANGE[1]: D['issues'].append((nm, 'w', w))
        if w - a > B_MAX: D['issues'].append((nm, 'b', w - a))
        ink(nm, a * U * mm - tx * mm, car['bbox'])
        ink(nm, a * U * mm - mk['anchor'][0] * mm, mk['bbox'])
        D['combos'].append(dict(name=nm, cps=cps, adv=car['adv'], w=w, a=a, b=b, mark=mk['glyph'], mark_ax=mk['anchor'][0]))
    for t in R['NP']:
        grp = 'numerals' if 0xE070 <= t['cp'] < 0xE080 else 'punct'
        if t.get('missing'):
            D['missing'].append(t['name']); D[grp].append(dict(cp=t['cp'], name=t['name'], missing=True)); continue
        adv = t['adv'] * k; top = sc(t['top']); bb = sc(t['bbox'])
        f = 1.0                         # a numeral or a punctuation sign taller than the window is drawn smaller
        if bb[3] * mm > _WZ[1]: f = min(f, _WZ[1] / (bb[3] * mm) * 0.995)
        if bb[1] * mm < _WZ[0]: f = min(f, _WZ[0] / (bb[1] * mm) * 0.995)
        if adv > (W_RANGE[1] - 0.5) * U: f = min(f, (W_RANGE[1] - 0.5) * U / adv)      # wider than the widest step
        if f < 1.0:
            D['shrink'][t['glyph']] = f; D['shrunk'].append((t['name'], round(f, 3)))
            adv *= f; bb = tuple(v * f for v in bb); top = tuple(v * f for v in top) if top else None
        a, b, w, d, tx = code(t['name'], adv, top, None, kind='N', bb=bb)
        ink(t['name'], a * U * mm - tx * mm, bb)
        D[grp].append(dict(cp=t['cp'], name=t['name'], glyph=t['glyph'], adv=adv, w=w, a=a, b=w - a,
                           has_anchor=top is not None, ax=tx))
    return D


def fit(path, s_try=None):
    """Best scale: the one nearest to 1 (Alcarin's body height) at which every code and every ink fits."""
    R = raw(path)
    if not R['ok']:
        return R, None
    import glyphvar as GV
    R['gs'] = GV.VarGlyphSet(R['gs'])
    if 'font' not in R:
        R['font'] = TTFont(path)
    no_dotted_circle(R)
    in_lambe(R)
    grid = s_try or sorted({round(1.0 - 0.005 * i, 3) for i in range(0, 41)} | {round(1.0 + 0.005 * i, 3) for i in range(1, 21)},
                           key=lambda s: (abs(s - 1.0), -s))
    best = None
    for s in grid:
        D = codes_at(R, s)
        if not D['issues']:
            best = D; break
        if best is None or len(D['issues']) < len(best['issues']):
            best = D
    if best['issues']:              # rev. 0.12: no scale fits: the few letters that leave the window are drawn smaller
        for s in grid:
            D = codes_at(R, s, shrink_letters=True)
            if not D['issues']:
                best = D; break
    return R, best


def no_dotted_circle(R):
    """rev. 0.14: Tengwar Telcontar draws its marks with a dotted circle (composite: the mark + uni25CC); the
    circle would be cut into the type. The mark alone is a synthetic glyph '<mark>.nodc' (its component, where the
    composite puts it); its anchor is taken again from its own ink where it was the middle of the composite's."""
    import glyphvar as GV
    gs = R['gs']
    f = R.get('font')
    if f is None or 'glyf' not in f:
        return
    glyf = f['glyf']
    for m in R['M']:
        if m.get('missing') or m['glyph'] not in glyf:
            continue
        g = glyf[m['glyph']]
        if not g.isComposite():
            continue
        comps = [c for c in g.components if c.glyphName not in ('uni25CC', 'dottedcircle', 'dotted_circle')]
        if len(comps) == len(g.components) or len(comps) != 1:
            continue
        c = comps[0]; name = m['glyph'] + '.nodc'
        gs.add(name, c.glyphName, c.x, c.y)
        bb = GV.bounds(gs, name); ob = m['bbox']
        an = m['anchor']
        if abs(an[0] - 0.5 * (ob[0] + ob[2])) < 1e-6:
            an = (0.5 * (bb[0] + bb[2]), an[1])
        m.update(glyph=name, bbox=bb, anchor=an, length=bb[2] - bb[0])


def in_lambe(R):
    """rev. 0.14: the marks under lambe (dblL where the font has no lambe variant, ddotbL always) are moved into
    its bowl (glyphvar.py): synthetic glyphs '<mark>.inlambe', centred on the bowl's middle (or on the font's own
    doubling bar for lambe); R['inlambe'] keeps how much of each lies on lambe's ink."""
    import glyphvar as GV
    gs = R['gs']
    R['inlambe'] = {}
    lam = next((t for t in R['T'] if t['cp'] == 0xE022 and not t.get('missing')), None)
    if lam is None:
        return
    x = (lam.get('botL') or lam.get('bot') or (None,))[0]
    if x is None:
        bb = lam['bbox']; x = 0.5 * (bb[0] + bb[2])
    ref = next((m for m in R['M'] if m['key'] == 'dblL' and m.get('variant') and not m.get('missing')), None)
    centre = None
    if ref:
        b = ref['bbox']; xl = (lam.get('botL') or lam.get('bot'))[0]
        centre = (xl - ref['anchor'][0] + 0.5 * (b[0] + b[2]), 0.5 * (b[1] + b[3]))
    for m in R['M']:
        if m.get('missing') or m['key'] not in ('dblL', 'ddotbL') or m.get('variant'):
            continue
        d = GV.place_in(gs, m['glyph'], m['anchor'][0], lam['glyph'], x, centre)
        if d is None:
            continue
        dx, dy = d
        name = m['glyph'] + GV.SUFFIX
        gs.add(name, m['glyph'], dx, dy)
        b = m['bbox']
        m.update(glyph=name, bbox=(b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy), anchor=(m['anchor'][0], m['anchor'][1] + dy), variant=True)
        R['inlambe'][m['key']] = round(GV.overlap(gs, name, 0, 0, m['anchor'][0], lam['glyph'], x), 3)


def glyphset(R, D):
    return ScaledGlyphSet(R['gs'], D['k'], D['shrink'])


if __name__ == '__main__':
    for p in sys.argv[1:]:
        R, D = fit(p)
        if D is None:
            print(os.path.basename(p), '—', R['why']); continue
        print(f"{os.path.basename(p):32s} {R['name'][:28]:28s} s={D['scale']:.3f} k={D['k']:.3f} issues={len(D['issues'])} "
              f"pad={len(D['pad'])} shift={len(D['shift'])} shrunk={D['shrunk']} warn={len(D['warn'])} missing={D['missing']}")
        print('      at s=1:', codes_at(R, 1.0)['issues'][:6])
        for i in D['issues'][:8]:
            print('     ', i)
