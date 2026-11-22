"""Keystroke frequencies of the TPM layout (rev. 0.11: from running text).
Up to rev. 0.10 a small transcriber was run over a sample of names; now the counts come from the tengwar text of two
books (data/freq_books.json: Chaered's Quenya translation of "The Wonderful Wizard of Oz", 159 000 keystrokes, and
"Тенгварь в картинках и стихах"). Only the counts are kept in the repository.
The result orders the shuttle rows (layout.ROW_CODE) and weights the mean cycle (motor.py); spaces are counted apart.
Usage: python3 -I freq.py OUT_JSON
       python3 -I freq.py --books OUT_DATA_JSON TEXT [TEXT ...]   (texts: pdftotext -enc UTF-8 of the books)"""
import sys, os, json, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import layout as lay

ITEM = {}            # item key -> (keyboard row r, column c, tier)
for r, rw in enumerate(lay.ROWS):
    for c, pair in enumerate(rw):
        for tier, it in enumerate(pair):
            if it is not None and it not in ITEM:
                ITEM[it] = (r, c, tier)

VOW = {0xE040: 'a', 0xE044: 'i', 0xE046: 'e', 0xE04A: 'o', 0xE04C: 'u'}
MARK = {0xE040: 'a', 0xE044: 'i', 0xE046: 'e', 0xE04A: 'o', 0xE04C: 'u', 0xE052: 'tilde', 0xE045: 'dotb', 0xE043: 'ddotb',
        0xE07D: 'lsd'}
ALIAS = {0xE059: 0xE058, 0xE068: 0xE067, 0xE069: 0xE067, 0xE062: 0xE061}     # variants typed with the same key


def strokes(text, width):
    """CSUR text -> keystrokes: one per tengwa, tehta or bar; ára + vowel is one key; the doubling bar under a wide letter
    is the wide one, under lambe/alda the special one; a run of spaces or line breaks is one space ('SP')."""
    out = []
    s = [ord(c) for c in text if 0xE000 <= ord(c) <= 0xE0FF or c in ' \n']
    base = None
    i = 0
    while i < len(s):
        c = ALIAS.get(s[i], s[i])
        if c in (32, 10):
            if out and out[-1] != 'SP':
                out.append('SP')
            base = None; i += 1; continue
        if c == 0xE02C and i + 1 < len(s) and s[i + 1] in VOW:
            out.append('combo:ára+' + VOW[s[i + 1]]); base = 0xE02C; i += 2; continue
        if c == 0xE043 and base in (0xE022, 0xE023):          # rev. 0.14: the two dots inside lambe / alda
            out.append('mark:ddotbL'); i += 1; continue
        if c in MARK:
            out.append('mark:' + MARK[c]); i += 1; continue
        if c in (0xE050, 0xE051):
            if c == 0xE051 and base in (0xE022, 0xE023):
                out.append('mark:dblL')
            else:
                out.append('mark:' + ('nas' if c == 0xE050 else 'dbl') + ('W' if width.get(base, 10) >= 14 else ''))
            i += 1; continue
        out.append(c if c in ITEM else ('missing', c)); base = c; i += 1
    return out


if __name__ == '__main__':
    ROOT = os.path.dirname(os.path.dirname(HERE))
    if sys.argv[1] == '--books':
        codes = json.load(open(os.path.join(ROOT, 'data', 'codes.json')))
        width = {t['cp']: t['w'] for t in codes['tengwar']}
        tot = collections.Counter(); src = []
        for fn in sys.argv[3:]:
            c = collections.Counter(strokes(open(fn, encoding='utf-8').read(), width))
            src.append(dict(file=os.path.basename(fn), strokes=sum(v for k, v in c.items() if k != 'SP'), spaces=c['SP']))
            tot.update(c)
        json.dump(dict(sources=src, spaces=tot['SP'],
                       items={repr(k): v for k, v in sorted(tot.items(), key=lambda a: -a[1]) if k != 'SP'}),
                  open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
        sys.exit()
    B = json.load(open(os.path.join(ROOT, 'data', 'freq_books.json')))
    counts = {k: v for k, v in B['items'].items() if eval(k) in ITEM}
    n = sum(counts.values())
    rows = {}
    for k, v in counts.items():
        r, c, tier = ITEM[eval(k)]
        rows[f'{r},{tier}'] = rows.get(f'{r},{tier}', 0) + v
    res = dict(n=n, spaces=B['spaces'], sources=B['sources'], items=counts,
               rows={k: v / n for k, v in sorted(rows.items(), key=lambda a: -a[1])})
    json.dump(res, open(sys.argv[1], 'w'), indent=1, ensure_ascii=False)
    print(n, 'keystrokes,', B['spaces'], 'spaces;', {k: round(v, 3) for k, v in res['rows'].items()})
