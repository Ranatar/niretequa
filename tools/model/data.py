"""Machine data: characters, keyboard and the shuttle arrangement used by the 3D model (rev. 0.5).
rev. 0.11: the font of the shuttle is chosen by the environment variable TPM_FONT (an id of tools/fontsets.py,
default alcarin). Alcarin's codes come from data/codes.json (tools/measure.py), another font is measured by
tools/fontprof.py on import. Nothing is written here (before 0.11 this module ran gen_shuttle.py, which rewrote
gen/stats.json and made `make` rebuild the model every time)."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE); ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import layout as lay
import fontsets
from items import build_items, ADV, QUENYA, SINDARIN
sys.path.insert(0, HERE)
import params as P
from fontTools.ttLib import TTFont

FONT_ID = os.environ.get('TPM_FONT', 'alcarin')
FONTSET = fontsets.BY_ID[FONT_ID]
FONT = os.path.join(ROOT, FONTSET['file'])
if FONT_ID == 'alcarin':
    CODES = json.load(open(os.path.join(ROOT, 'data', 'codes.json')))
    _F = TTFont(FONT)
    GLYPHSET = _F.getGlyphSet()
    PROFILE = None
    CACHE = os.path.join(ROOT, 'gen', 'model_cache')
else:
    import fontprof
    _R, CODES = fontprof.fit(FONT)
    if CODES is None:
        raise SystemExit(f'{FONT_ID}: {_R["why"]}')
    _F = None
    GLYPHSET = fontprof.glyphset(_R, CODES)
    PROFILE = dict(scale=CODES['scale'], k=CODES['k'], issues=CODES['issues'], pad=CODES['pad'], shift=CODES['shift'],
                   missing=CODES['missing'], shrunk=CODES['shrunk'], warn=CODES['warn'], name=_R['name'])
    CACHE = os.path.join(ROOT, 'gen', 'model_cache', 'font-' + FONT_ID)
os.makedirs(CACHE, exist_ok=True)
ITEMS, MARK_AX = build_items(CODES, _F)
U_FONT = CODES['U']
G = dict(QUENYA=QUENYA, SINDARIN=SINDARIN)
ROWS, LEGENDS = lay.ROWS, lay.LEGENDS


def key_slot(r, c):
    """Keyboard row r (0 = back) and column c -> lever index n (pitch 4.75 mm) and shuttle position m.
    rev. 0.6: one shuttle position per keyboard column."""
    n = 4 * c + r            # x = 19c + 4.75r
    return n, c


def shuttle_row(r, tier):
    """Shuttle row 1..8 (1 = top) for keyboard row r and tier (0 lower register, 1 upper); rev. 0.8: rows by frequency."""
    return P.ROW_CODE[r] + 4 * tier + 1


def shuttle_layout():
    """rows[srow-1][m] = item key or None."""
    rows = [[None] * 11 for _ in range(8)]
    for r, rw in enumerate(ROWS):
        for c, pair in enumerate(rw):
            _, m = key_slot(r, c)
            for tier in (0, 1):
                rows[shuttle_row(r, tier) - 1][m] = pair[tier]
    return rows
