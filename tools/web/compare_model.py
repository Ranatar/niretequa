"""rev. 0.9.3: the page against the model. Puts the python model and the page (in headless Chromium) in the same states
-- the cycle at several angles for two targets, keys pressed, the unit retracted, the carriage moved -- and compares
every part present in both by its exact bounding box. Parts the page animates and the model keeps still (governor,
motor train) and the sheet and ribbon pressed at the blow (not modelled on the page) show up as small differences.

Usage: python3 tools/web/compare_model.py PAGE_HTML [THREE_MIN_JS ORBIT_CONTROLS_JS]
Needs playwright with chromium; three.js r128 is taken from the given files (the CDN is not reachable offline)."""
import asyncio, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'model'))
import parts as PT, scenarios as SC, params as P

LIMIT = 0.1


def reference():
    out = []
    def add(tag, st, vs):
        bb = {}
        for p in PT.build(st):
            bb.setdefault(p.name, []).append(list(p.mesh.bounding_box()))
        out.append(dict(tag=tag, st=vs, bb=bb))
    for a in (0, 60, 120, 168, 200, 300):
        for pt, rt in ((10, 7), (0, 0)):
            st = SC.cycle_state(float(a), pt, rt)
            add(f'cycle {a} target {pt}/{rt}', st, dict(pos=st.pos, row=st.row, detent=st.detent, rib=PT.ribbon_lift(st),
                hammer=st.hammer, cock=st.cock, lock=st.lock, phi=a, bits=list(st.bits),
                feel=dict({'W': 0, 'B': 0, 'C': 0}, **st.feel), frames=dict(st.frames), uIn=bool(st.u_in)))   # rev. 0.10: the reading
    for a in (130, 145, 175):                          # rev. 0.10: a letter read (target 4/6: ext. ando)
        st = SC.cycle_state(float(a), 4, 5)
        add(f'read {a} target 4/6', st, dict(pos=st.pos, row=st.row, detent=st.detent, rib=PT.ribbon_lift(st),
            hammer=st.hammer, cock=st.cock, lock=st.lock, phi=a, bits=list(st.bits),
            feel=dict({'W': 0, 'B': 0, 'C': 0}, **st.feel), frames=dict(st.frames)))
    for a in (145, 165, 320):                          # rev. 0.11: the idle cycle of a space: both locks in
        st = SC.cycle_state(float(a), 5, 0, lock_read=1.0, lock_hammer=1.0, frames={'W': 2.0, 'R': 16.0})
        add(f'idle space {a}', st, dict(pos=st.pos, row=st.row, detent=st.detent, rib=PT.ribbon_lift(st), hammer=st.hammer,
            cock=st.cock, lock=st.lock, phi=a, bits=list(st.bits), frames=dict(st.frames), lockRead=1, lockHammer=1, uIn=bool(st.u_in)))
    st = PT.State(pos=3.0, row=2.0, slide_u=10.0)
    add('shuttle 3/2, unit back 10u', st, dict(pos=3.0, row=2.0, slide=10.0))
    st = PT.State(car=P.CAR_X_START - 100.0)
    add('carriage -100', st, dict(car=P.CAR_X_START - 100.0))
    return out


JS = '''(s) => {
  const T = window.__tpm, st = T.st;
  Object.assign(st, {pos: 5, row: -1, detent: 0, rib: 0, hammer: 0, cock: 0, lock: 0, phi: 0, slide: 0, tier: 0,
                    feel: {W: 0, B: 0, C: 0}, mem: {b: 0, c: 0, w: 0}, lockRead: 0, lockHammer: 0, uIn: false});
  st.car = T.C0; st.f = {}; st.bits = {}; for (const b of Object.keys(st.frames)) st.frames[b] = 0;
  for (const [k, v] of Object.entries(s)) {
    if (k === 'bits') for (const b of v) st.bits[b] = 1; else st[k] = v;
  }
  T.apply(); T.scene.updateMatrixWorld(true);
  const out = {};
  T.scene.traverse(o => { if (o.isMesh && o.userData && o.userData.n && o.geometry && o.geometry.attributes.position) {
    const bb = new THREE.Box3(), v = new THREE.Vector3(), pa = o.geometry.attributes.position;
    for (let i = 0; i < pa.count; i++) { v.fromBufferAttribute(pa, i).applyMatrix4(o.matrixWorld); bb.expandByPoint(v); }
    (out[o.userData.n] = out[o.userData.n] || []).push([bb.min.x, bb.min.y, bb.min.z, bb.max.x, bb.max.y, bb.max.z]); } });
  return out; }'''


async def compare(url, ref, three, orbit):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=swiftshader', '--enable-unsafe-swiftshader'])
        pg = await b.new_page()
        async def route(r):
            u = r.request.url
            if 'three.min.js' in u: await r.fulfill(path=three)
            elif 'OrbitControls.js' in u: await r.fulfill(path=orbit)
            elif u.startswith('file://'): await r.continue_()
            else: await r.abort()
        await pg.route('**/*', route)
        await pg.goto(url)
        await pg.wait_for_function('window.__READY', timeout=300000, polling=1000)
        await pg.evaluate('window.__tpm.C0 = window.__tpm.st.car')
        worst = {}
        for c in ref:
            res = await pg.evaluate(JS, c['st'])
            for n, lst in c['bb'].items():
                w = res.get(n)
                if not w or len(w) != len(lst):
                    continue
                for a in lst:
                    d = min(max(abs(x - y) for x, y in zip(a, v)) for v in w)
                    if d > worst.get(n, (0,))[0]:
                        worst[n] = (d, c['tag'])
        await b.close()
    return worst


if __name__ == '__main__':
    page = os.path.abspath(sys.argv[1])
    three = sys.argv[2] if len(sys.argv) > 2 else '/tmp/threejs/node_modules/three/build/three.min.js'
    orbit = sys.argv[3] if len(sys.argv) > 3 else '/tmp/threejs/node_modules/three/examples/js/controls/OrbitControls.js'
    worst = asyncio.run(compare('file://' + page, reference(), three, orbit))
    bad = sorted(((v, k) for k, v in worst.items() if v[0] > LIMIT), reverse=True)
    print(f'parts compared: {len(worst)}; over {LIMIT} mm: {len(bad)}')
    for v, k in bad:
        print(f'{v[0]:8.2f} mm  {k}  ({v[1]})')
