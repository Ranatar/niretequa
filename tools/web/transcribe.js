// Transcription of Latin-letter Quenya and Sindarin, and of Russian (rev. 0.12), into the signs of the TPM-2 layout (tehta modes).
// The rules follow the descriptions of the classical mode (Quenya) and the general use of the Third Age (Sindarin)
// by Måns Björkman, Amanyë Tenceli (at.boktypografen.se), as also implemented in Glǽmscribe (glaemscrafu.jrrvf.com);
// this is an independent implementation limited to the signs on the shuttle.
// transcribe(text, mode) -> { items: [{k, src, warn}], warnings: [..] }; k: layout item (codepoint number or 'mark:…',
// 'combo:ára+…', ' ' for a space, '\n' for a new line).
const TPM2_TR = (function () {
  const TW = {
    tinco: 0xe000, parma: 0xe001, calma: 0xe002, quesse: 0xe003, ando: 0xe004, umbar: 0xe005, anga: 0xe006, ungwe: 0xe007,
    sule: 0xe008, formen: 0xe009, harma: 0xe00a, hwesta: 0xe00b, anto: 0xe00c, ampa: 0xe00d, anca: 0xe00e, unque: 0xe00f,
    numen: 0xe010, malta: 0xe011, noldo: 0xe012, nwalme: 0xe013, ore: 0xe014, vala: 0xe015, anna: 0xe016, vilya: 0xe017,
    romen: 0xe020, arda: 0xe021, lambe: 0xe022, alda: 0xe023, silme: 0xe024, silmen: 0xe025, esse: 0xe026, essen: 0xe027,
    hyarmen: 0xe028, hwestas: 0xe029, yanta: 0xe02a, ure: 0xe02b, halla: 0xe02d, telco: 0xe02e, sarince: 0xe058,
  };
  const WIDE = new Set(['ando', 'umbar', 'anga', 'ungwe', 'anto', 'ampa', 'anca', 'unque', 'numen', 'malta', 'noldo', 'nwalme']);
  const PUNCT = { ',': 0xe060, ';': 0xe060, ':': 0xe060, '·': 0xe060, '.': 0xe061, '!': 0xe065, '?': 0xe066,
    '(': 0xe067, ')': 0xe067, '«': 0xe06a, '“': 0xe06a, '„': 0xe06a, '»': 0xe06b, '”': 0xe06b };
  const VOW = 'aeiouy';
  const LONG = { á: 'a', é: 'e', í: 'i', ó: 'o', ú: 'u', ý: 'y' };

  function norm(s) {
    s = s.toLowerCase().normalize('NFC');
    const map = { ä: 'a', ë: 'e', ï: 'i', ö: 'o', ü: 'u', ÿ: 'y', â: 'á', ê: 'é', î: 'í', ô: 'ó', û: 'ú', ŷ: 'ý',
      ā: 'á', ē: 'é', ī: 'í', ō: 'ó', ū: 'ú', ȳ: 'ý', ŋ: 'ñ', 'ʒ': 'z', '’': "'", 'ð': 'đ' };
    s = s.replace(/[äëïöüÿâêîôûŷāēīōūȳŋʒ’ð]/g, (c) => map[c]);
    return s.replace(/aa/g, 'á').replace(/ee/g, 'é').replace(/ii/g, 'í').replace(/oo/g, 'ó').replace(/uu/g, 'ú');
  }
  const bar = (name, kind) => (name === 'lambe' || name === 'alda' ? (kind === 'dbl' ? 'mark:dblL' : 'mark:nas')
    : WIDE.has(name) ? `mark:${kind}W` : `mark:${kind}`);
  const tehta = (v) => 'mark:' + v;

  // units of a word: {c: [letters], m: [marks], after: [letters after the tehta]} or {v, long} or {d: diphthong}
  function units(w, table, diphs) {
    const out = [];
    let i = 0;
    while (i < w.length) {
      const ch = w[i];
      if (LONG[ch]) { out.push({ v: LONG[ch], long: true, src: ch }); i++; continue; }
      if (VOW.includes(ch) && !(ch === 'y' && table.yCons)) {
        const two = w.slice(i, i + 2);
        const vv = table.yCons ? 'aeiou' : VOW;
        if (diphs[two] && !(i + 2 < w.length && vv.includes(w[i + 2]) && two[1] !== 'w')) { out.push({ d: two, src: two }); i += 2; continue; }
        out.push({ v: ch, long: false, src: ch }); i++; continue;
      }
      let u = null, pat = '';
      for (const [p, f] of table.cons) {
        if (!w.startsWith(p, i)) continue;
        const r = f({ initial: i === 0, final: i + p.length >= w.length, next: w[i + p.length] || '' });
        if (r) { u = Object.assign({ src: p }, r); pat = p; break; }
      }
      if (!u) { out.push({ bad: ch, src: ch }); i++; continue; }
      i += pat.length;
      // palatalized consonant (Quenya): consonant + y + vowel -> two dots below
      if (table.palatal && u.pal !== false && w[i] === 'y' && 'aeiouáéíóú'.includes(w[i + 1] || '-')) {
        u.m = (u.m || []).concat('mark:ddotb'); u.src += 'y'; i++;
      }
      out.push(u);
    }
    return out;
  }
  const C = (c, m, extra) => Object.assign({ c: Array.isArray(c) ? c : [c], m: m || [] }, extra || {});

  // ------------------------------------------------------------------ Quenya, classical mode
  const Q = {
    palatal: true, yCons: true,
    cons: [
      ['lld', () => C('alda', [bar('alda', 'dbl')])], ['ll', () => C('lambe', [bar('lambe', 'dbl')])], ['ld', () => C('alda')],
      ['rrd', () => C('arda', [bar('arda', 'dbl')])], ['rr', () => C('romen', [bar('romen', 'dbl')])], ['rd', () => C('arda')],
      ['nnd', () => C('ando', [bar('ando', 'dbl')])], ['nnt', () => C('anto', [bar('anto', 'dbl')])],
      ['ngw', () => C('ungwe')], ['nqu', () => C('unque')], ['nq', () => C('unque')], ['nd', () => C('ando')], ['nt', () => C('anto')],
      ['nc', () => C('anca')], ['nk', () => C('anca')], ['ng', () => C('anga')], ['ñw', () => C('nwalme')], ['ñ', () => C('noldo')],
      ['nn', () => C('numen', [bar('numen', 'dbl')])], ['nw', (x) => (x.initial ? C('nwalme') : null)],
      ['n', () => C('numen')],
      ['mb', () => C('umbar')], ['mp', () => C('ampa')], ['mm', () => C('malta', [bar('malta', 'dbl')])], ['m', () => C('malta')],
      ['tt', () => C('tinco', [bar('tinco', 'dbl')])], ['ts', () => C('tinco', [], { sar: true, pal: false })],
      ['th', () => C('sule')], ['þ', () => C('sule')], ['t', () => C('tinco')],
      ['pp', () => C('parma', [bar('parma', 'dbl')])], ['ps', () => C('parma', [], { sar: true, pal: false })], ['p', () => C('parma')],
      ['cc', () => C('calma', [bar('calma', 'dbl')])], ['kk', () => C('calma', [bar('calma', 'dbl')])],
      ['cs', () => C('calma', [], { sar: true, pal: false })], ['ks', () => C('calma', [], { sar: true, pal: false })],
      ['x', () => C('calma', [], { sar: true, pal: false })], ['c', () => C('calma')], ['k', () => C('calma')],
      ['qu', () => C('quesse', [], { pal: false })], ['q', () => C('quesse', [], { pal: false })],
      ['hw', () => C('hwesta', [], { pal: false })], ['hy', () => C('hyarmen', ['mark:ddotb'], { pal: false })],
      ['hl', () => C(['halla', 'lambe'])], ['hr', () => C(['halla', 'romen'])],
      ['h', (x) => (x.initial && 'aeiouáéíóú'.includes(x.next) ? C('hyarmen', [], { pal: false }) : C('harma', [], { pal: false }))],
      ['χ', () => C('harma')], ['ff', () => C('formen', [bar('formen', 'dbl')])], ['f', () => C('formen')],
      ['gw', () => C('ungwe')], ['g', () => C('anga')], ['d', () => C('ando')], ['b', () => C('umbar')],
      ['v', () => C('vala')], ['w', () => C('vilya')], ['y', () => C('anna', ['mark:ddotb'], { pal: false })],
      ['ss', () => C('esse', [], { s: 'essen' })], ['z', () => C('esse', [], { s: 'essen' })], ['s', () => C('silme', [], { s: 'silmen' })],
      ['r', () => C('romen', [], { r: true })], ['l', () => C('lambe')], ["'", () => C([])],
    ],
  };
  const QDIPH = { ai: ['yanta', 'a'], au: ['ure', 'a'], eu: ['ure', 'e'], iu: ['ure', 'i'], oi: ['yanta', 'o'], ui: ['yanta', 'u'] };

  function quenyaWord(w) {
    const U = units(w, Q, QDIPH), out = [];
    for (let i = 0; i < U.length; i++) {
      const u = U[i], nx = U[i + 1];
      if (u.bad) { out.push({ k: null, src: u.bad, warn: `«${u.bad}» — нет в правилах классического режима` }); continue; }
      if (u.c) {
        if (!u.c.length) continue;
        let letters = u.c.slice();
        const vowelNext = nx && (nx.v || nx.d);
        if (u.r && !vowelNext) letters[letters.length - 1] = 'ore';
        const carries = nx && nx.v && !nx.long && nx.v !== 'y';
        if (u.s && carries) letters[letters.length - 1] = u.s;
        letters.forEach((L, j) => out.push({ k: TW[L], src: j === letters.length - 1 ? u.src : '' }));
        for (const m of u.m) out.push({ k: m, src: '' });
        if (carries) { out.push({ k: tehta(nx.v), src: nx.src }); i++; }
        if (u.sar) out.push({ k: TW.sarince, src: '' });
        continue;
      }
      if (u.d) { const [L, v] = QDIPH[u.d]; out.push({ k: TW[L], src: u.d }, { k: tehta(v), src: '' }); continue; }
      if (u.long) { out.push({ k: 'combo:ára+' + u.v, src: u.src }); continue; }
      out.push({ k: TW.telco, src: u.src }, { k: tehta(u.v), src: '' });
    }
    return out;
  }

  // ------------------------------------------------------------------ Sindarin, general use of the Third Age
  const S = {
    palatal: false, yCons: false,
    cons: [
      ['nth', () => C('sule', [bar('sule', 'nas')])], ['mph', () => C('formen', [bar('formen', 'nas')])],
      ['nch', () => C('hwesta', [bar('hwesta', 'nas')])], ['ngw', () => C('ungwe', [bar('ungwe', 'nas')], { lab: true })],
      ['nc', () => C('quesse', [bar('quesse', 'nas')])], ['nk', () => C('quesse', [bar('quesse', 'nas')])],
      ['nt', () => C('tinco', [bar('tinco', 'nas')])], ['mp', () => C('parma', [bar('parma', 'nas')])],
      ['mb', () => C('umbar', [bar('umbar', 'nas')])], ['nd', () => C('ando', [bar('ando', 'nas')])],
      ['ng', (x) => (x.initial || x.final ? C('nwalme') : C('ungwe', [bar('ungwe', 'nas')]))],
      ['nn', () => C('numen', [bar('numen', 'nas')])], ['mm', () => C('malta', [bar('malta', 'nas')])],
      ['ns', () => C('silmen', [bar('silmen', 'nas')])],
      ['th', () => C('sule')], ['þ', () => C('sule')], ['ph', () => C('formen')], ['ff', () => C('formen')],
      ['f', (x) => (x.final ? C('ampa') : C('formen'))], ['ch', () => C('hwesta')], ['dh', () => C('anto')], ['đ', () => C('anto')],
      ['bh', () => C('ampa')], ['v', () => C('ampa')], ['rh', (x) => (x.initial ? C('arda') : null)],
      ['lh', (x) => (x.initial ? C('alda') : null)], ['hw', () => C('hwestas')],
      ['ll', () => C('lambe', [bar('lambe', 'dbl')])], ['ss', () => C('esse', [], { s: 'essen' })],
      ['t', () => C('tinco')], ['p', () => C('parma')], ['c', () => C('quesse')], ['k', () => C('quesse')],
      ['gw', () => C('ungwe', [], { lab: true })], ['d', () => C('ando')], ['b', () => C('umbar')], ['g', () => C('ungwe')],
      ['n', () => C('numen')], ['m', () => C('malta')], ['r', (x) => C(x.final ? 'ore' : 'romen')], ['l', () => C('lambe')],
      ['w', () => C('vala')], ['s', () => C('silme', [], { s: 'silmen' })], ['h', () => C('hyarmen')], ['j', () => C('yanta')],
      ["'", () => C([])],
    ],
  };
  const SDIPH = { ai: ['anna', 'a'], ei: ['anna', 'e'], ui: ['anna', 'u'], ae: ['yanta', 'a'], oe: ['yanta', 'o'], au: ['vala', 'a'], aw: ['vala', 'a'] };

  function sindarinWord(w) {
    const U = units(w, S, SDIPH), out = [];
    let pend = null; // a short vowel waiting for the next consonant
    const flush = () => {
      if (!pend) return;
      if (pend.v === 'y') out.push({ k: null, src: pend.src, warn: 'гласной y (две точки сверху) на челноке нет' });
      else out.push({ k: TW.telco, src: pend.src }, { k: tehta(pend.v), src: '' });
      pend = null;
    };
    for (let i = 0; i < U.length; i++) {
      const u = U[i];
      if (u.bad) { flush(); out.push({ k: null, src: u.bad, warn: `«${u.bad}» — нет в правилах общего режима` }); continue; }
      if (u.c) {
        if (!u.c.length) continue;
        const letters = u.c.slice();
        if (pend && u.s) letters[letters.length - 1] = u.s;
        letters.forEach((L, j) => out.push({ k: TW[L], src: j === letters.length - 1 ? u.src : '' }));
        for (const m of u.m) out.push({ k: m, src: '' });
        if (pend) {
          if (pend.v === 'y') out.push({ k: null, src: pend.src, warn: 'гласной y (две точки сверху) на челноке нет' });
          else out.push({ k: tehta(pend.v), src: pend.src });
          pend = null;
        }
        if (u.lab) out.push({ k: TW.vala, src: '', warn: 'завитка w на челноке нет: w записано валой' });
        continue;
      }
      flush();
      if (u.d) { const [L, v] = SDIPH[u.d]; out.push({ k: TW[L], src: u.d }, { k: tehta(v), src: '' }); continue; }
      if (u.long) {
        if (u.v === 'y') out.push({ k: null, src: u.src, warn: 'долгой y на челноке нет' });
        else out.push({ k: 'combo:ára+' + u.v, src: u.src });
        continue;
      }
      pend = u;
    }
    flush();
    return out;
  }

  // ------------------------------------------------------------------ Russian (rev. 0.12)
  // After the system of hex.pp.ua/tengwar.php (2011), corrected: the vowel's tehta stands over the preceding
  // consonant (as in the classical mode); a soft consonant before я, е, ё, ю takes two dots below, as Quenya writes ty,
  // ny (й = anna then stands only where it sounds: at the start of a word, after a vowel, after ь and ъ); е and э thus
  // differ (мер / мэр); ь is two dots below, ъ is vilya; ы is vilya with the dot; щ (a long soft ш) is harma with the
  // bar below, ц is tinco with the hook (sa-rincë); doubled consonants take the bar below (Tolkien's sign, not the
  // wavy line of Dan Smith's fonts), unless the pair is soft: then the consonant is written twice (two signs below
  // one letter do not fit). с and з turn their tail down under a tehta.
  const RC = { т: 'tinco', п: 'parma', ч: 'calma', к: 'quesse', д: 'ando', б: 'umbar', г: 'ungwe', ф: 'formen', ш: 'harma',
    х: 'hwesta', в: 'ampa', ж: 'anca', н: 'numen', м: 'malta', й: 'anna', р: 'romen', л: 'lambe', с: 'silme', з: 'esse',
    ц: 'tinco', щ: 'harma', ў: 'vala' };
  const NUQ = { silme: 'silmen', esse: 'essen' };
  const ALWAYS = new Set(['ж', 'ш', 'ц', 'ч', 'щ', 'й']);   // hard or soft by themselves: no dots before е, ё, ю, я
  const SOFTV = { я: 'a', е: 'e', ё: 'o', ю: 'u' };
  const HARDV = { а: 'a', э: 'e', о: 'o', у: 'u' };
  const isV = (c) => !!(c && (SOFTV[c] || HARDV[c] || c === 'и' || c === 'ы'));

  function russianWord(w) {
    const out = [];
    const U = [];
    let i = 0;
    while (i < w.length) {
      const ch = w[i];
      if (w.startsWith('дж', i)) { U.push({ c: 'anga', src: 'дж', l: 'дж', m: [] }); i += 2; continue; }
      if (RC[ch]) {
        const u = { c: RC[ch], src: ch, l: ch, m: [] };
        i++;
        if (w[i] === ch && ch !== 'й') {
          const after = w[i + 1];
          if (!(SOFTV[after] || after === 'ь') || ALWAYS.has(ch)) { u.dbl = true; u.src += ch; i++; }
        }
        if (ch === 'щ') u.m.push(bar('harma', 'dbl'));
        else if (u.dbl) u.m.push(bar(u.c, 'dbl'));
        if (w[i] === 'ь') {
          if (u.m.length) u.warn = `ь после «${u.src}» опущен: под литерой уже черта`;
          else u.m.push('mark:ddotb');
          u.soft = true; u.src += 'ь'; i++;
        }
        if (ch === 'ц') u.sar = true;
        U.push(u);
        if (w[i] === 'ъ') { U.push({ c: 'vilya', src: 'ъ', l: 'ъ', m: [], sign: true }); i++; }
        continue;
      }
      if (ch === 'ь' || ch === 'ъ') {
        U.push(ch === 'ъ' ? { c: 'vilya', src: 'ъ', l: 'ъ', m: [], sign: true } : { note: '«ь» без согласной перед ним', src: 'ь' });
        i++; continue;
      }
      if (isV(ch)) { U.push({ v: ch, src: ch }); i++; continue; }
      U.push({ bad: ch, src: ch }); i++;
    }
    for (let j = 0; j < U.length; j++) {
      const u = U[j], nx = U[j + 1];
      if (u.bad) { out.push({ k: null, src: u.bad, warn: `«${u.bad}» — нет в правилах русского режима` }); continue; }
      if (u.note) { out.push({ k: null, src: u.src, warn: u.note }); continue; }
      if (u.c) {
        // does the next vowel sit on this consonant?
        let teh = null, dots = false;
        if (nx && nx.v && !u.soft && !u.sign) {
          const v = nx.v;
          if (HARDV[v]) teh = HARDV[v];
          else if (v === 'и') teh = 'i';
          else if (SOFTV[v]) { teh = SOFTV[v]; dots = !ALWAYS.has(u.l) && !u.dbl; }
          if (dots && u.m.length) dots = false;
        }
        let L = u.c;
        if (teh && NUQ[L] && !dots && !u.m.length) L = NUQ[L];      // the tail down only where nothing stands below
        out.push(u.warn ? { k: TW[L], src: u.src, warn: u.warn } : { k: TW[L], src: u.src });
        for (const m of u.m) out.push({ k: m, src: '' });
        if (dots) out.push({ k: 'mark:ddotb', src: '' });
        if (teh) { out.push({ k: tehta(teh), src: nx.src }); j++; }
        if (u.sar) out.push({ k: TW.sarince, src: '' });
        continue;
      }
      // a vowel with no consonant to sit on: at the start, after a vowel, after ь or ъ, or ы
      const pv = U[j - 1];
      const afterSign = pv && (pv.soft || pv.sign);          // ья, ьё, ьи, ьо, ъе: й sounds
      if (u.v === 'ы') { out.push({ k: TW.vilya, src: u.src }, { k: tehta('i'), src: '' }); continue; }
      if (SOFTV[u.v] || afterSign) {
        out.push({ k: TW.anna, src: u.src }, { k: tehta(SOFTV[u.v] || HARDV[u.v] || 'i'), src: '' });
        continue;
      }
      out.push({ k: TW.telco, src: u.src }, { k: tehta(u.v === 'и' ? 'i' : HARDV[u.v]), src: '' });
    }
    return out;
  }

  function transcribe(text, mode) {
    const word = mode === 'sindarin' ? sindarinWord : mode === 'russian' ? russianWord : quenyaWord;
    const s = norm(text), items = [];
    let buf = '';
    const pushWord = () => {
      if (!buf) return;
      const w = mode === 'quenya' ? buf.replace(/qu/g, 'q') : buf;
      for (const it of word(w)) items.push(it);
      buf = '';
    };
    for (const ch of s) {
      if (mode === 'russian' ? /[а-яёў]/.test(ch) : /[a-zá-ýñþχđ']/.test(ch) && ch !== '÷' && ch !== '×') { buf += ch; continue; }
      pushWord();
      if (ch === '\n') items.push({ k: '\n', src: '↵' });
      else if (/\s/.test(ch)) { if (items.length && items[items.length - 1].k !== ' ') items.push({ k: ' ', src: ' ' }); }
      else if (/[0-9]/.test(ch)) items.push({ k: 0xe070 + +ch, src: ch });
      else if (PUNCT[ch] !== undefined) items.push({ k: PUNCT[ch], src: ch });
      else if (ch === '-' || ch === '–' || ch === '—') continue;
      else items.push({ k: null, src: ch, warn: `знака «${ch}» на челноке нет` });
    }
    pushWord();
    while (items.length && items[items.length - 1].k === ' ') items.pop();
    // rev. 0.14: the two dots of y under lambe or alda stand inside the bowl (their own sign)
    let base = null;
    for (const it of items) {
      if (typeof it.k === 'number') base = it.k;
      else if (it.k === 'mark:ddotb' && (base === TW.lambe || base === TW.alda)) it.k = 'mark:ddotbL';
      else if (typeof it.k !== 'string' || !it.k.startsWith('mark:')) base = null;
    }
    return { items, warnings: items.filter((x) => x.warn).map((x) => x.warn) };
  }
  return { transcribe, TW };
})();
