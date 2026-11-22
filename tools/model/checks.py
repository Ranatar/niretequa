"""Interference checks between parts of the layout model."""
import numpy as np
from manifold3d import Manifold

# designed contacts: (substring a, substring b)
ALLOW = [
    # rev. 0.14 stage 2b: the governor's brake -- collars on the arbor (fixed pinned, sliding), the felt on the plate,
    # the leaf springs in the collars and the weights on the springs, the arbor's end in the plate
    ('governor sliding collar', 'governor arbor'), ('governor fixed collar', 'governor arbor'), ('governor brake pad', 'governor brake plate'),
    ('governor leaf spring', 'governor sliding collar'), ('governor leaf spring', 'governor fixed collar'), ('governor weight', 'governor leaf spring'),
    ('governor brake plate', 'governor arbor'), ('governor brake plate', 'base plate'),
    # rev. 0.14b: key return springs under the levers, their bar and posts; the stem's collar under the comb (rest stop)
    ('key return spring', 'lever '), ('key return spring', 'key return bar'), ('key return bar post', 'key return bar'),
    ('key return bar post', 'base plate'),
    # rev. 0.14 (physics checks): the clips on the lever pivot rod (in their grooves, against the brackets)
    ('lift collar keeper', 'shuttle'),
    # rev. 0.14: supports of stage 1
    ('cycle trip post', 'base plate'), ('cycle trip pin', 'cycle trip post'), ('cycle trip pin', 'cycle trip lever'), ('cycle trip post', 'cycle trip lever'),
    ('cycle stop latch post', 'base plate'), ('cycle stop latch pin', 'cycle stop latch'), ('cycle stop latch pin', 'cycle stop latch post'),
    ('zero stop M bridge', 'escapement bracket'), ('zero stop M bridge', 'memory zero stop'), ('pusher guide hanger', 'selector comb'), ('pusher guide hanger', 'pusher guide'),
    ('stop carrier rod clip', 'stop carrier rod'), ('stop carrier rod clip', 'stop carrier rod bracket'), ('read lock axle clip', 'read lock axle'),
    ('paper guide cheek', 'carriage end plate'), ('paper guide cheek', 'paper guide'), ('paper rest arm', 'carriage end plate'), ('paper rest arm', 'paper rest'),
    ('return rocker post', 'base plate'), ('row detent wedge spring', 'row detent wedge'), ('row detent wedge spring', 'row detent wedge lug'),
    ('row detent wedge lug', 'row detent post'), ('governor flywheel', 'governor arbor'),
    # rev. 0.14: return rockers -- the rod's pin in the slot, the roller on the return cam, the rocker on its pin and post
    ('return rocker', 'cam rod'), ('return rocker', 'return rocker pin'), ('return rocker pin', 'return rocker post'),
    ('return rocker', 'return rod'), ('return rod', 'return rocker post'), ('return rod rotate', 'cam rotate return'), ('return rod lift', 'cam lift return'),
    ('rotate tape return', 'pulley and detent'), ('rotate tape return', 'rotate tape idler'), ('rotate tape return', 'rotate tape tensioner'),
    ('rotate tape idler', 'rotate tape idler post'), ('rotate tape idler post', 'U-frame base'), ('rotate tape tensioner', 'tape slider'),     # rev. 0.14: the keeper is screwed round the hub
    ('lever pivot clip', 'lever pivot rod'), ('lever pivot clip', 'pivot bracket'),
    # rev. 0.12: the case: its panels, inlays and pillars are bonded or screwed to each other
    ('case ', 'case '),
    # rev. 0.11: carriage release (axle in its bores, the sheath stop on the escapement's back post)
    ('carriage release axle', 'carriage release key'), ('carriage release axle', 'carriage release bracket'),
    ('dog release sheath stop', 'escapement bracket'),
    # rev. 0.11: the indicator's wire in the reading head's top, the margin abutment on the escapement bracket
    ('print point indicator', 'reading head'), ('margin abutment', 'escapement bracket'),
    # rev. 0.11: the idle cycle's locks (axles in their bores, the hammer lock's bar bonded to the post plate)
    ('read lock lever', 'read lock axle'), ('read lock guide', 'read lock axle'), ('hammer lock lever', 'hammer lock axle'),
    ('hammer lock guide', 'hammer lock axle'), ('hammer lock guide', 'U-frame arm and hammer post'),
    # rev. 0.10: code combs on the ring, the reading head, receivers and the read cam
    ('code comb', 'shuttle'), ('comb pin', 'shuttle'), ('comb pin', 'code comb'), ('feeler', 'reading head'),
    ('reading retract bar', 'reading head'), ('reading retract bar', 'feeler'), ('reading head', 'reading stem'),
    ('reading stem', 'reading post'), ('reading post', 'U-frame base'), ('read cable end', 'reading post'),
    ('read cable end', 'U-frame base'), ('read slide', 'memory sleeve'), ('read slide', 'read slide stop'),
    ('read slide', 'guides'), ('read slide stop', 'guides'), ('cam read', 'cycle shaft'), ('read rocker', 'cam read'),
    ('read rocker', 'read rocker axle'), ('read rocker bracket', 'read rocker axle'), ('W wire clamp', 'escapement rod Y'),
    ('W latch rack', 'escapement rod Y'), ('W latch pawl', 'W latch rack'), ('W latch pawl', 'W wire bracket'),
    ('W wire bracket', 'W follower bracket'), ('feeler', 'code comb'),
    # rev. 0.9c: escapement rebuilt -- pins pressed into the levers, ball joints, shafts in bores, the tape on the drum
    ('tail pin', 'lever '), ('rocker axle', 'rocker'), ('rocker axle', 'rocker bracket'), ('escapement tape', 'escapement stop'),
    ('escapement tape', 'escapement rod X'), ('pm-u eccentric', 'escapement bellcrank'), ('pm-u eccentric', 'pm-u detent'),
    ('escapement shaft', 'back lever B'), ('escapement shaft', 'memory lever M'), ('memory zero stop', 'escapement bracket'),
    ('back pawl', 'back lever B'), ('memory holding pawl', 'memory lever M'), ('memory coupling wedge', 'memory lever M'),
    ('memory ratchet sector', 'escapement bracket'), ('back pawl guard', 'escapement bracket'), ('escapement stop finger', 'escapement stop'),
    ('rocker bracket', 'frame'), ('rocker bracket', 'base'),
    # rev. 0.9b: pins of the reworked drives in their slots; links fixed to the parts they ride on
    ('drive bellcrank', 'cam rod'), ('drive bellcrank', 'drive bail'), ('drive bellcrank', 'drive link'), ('drive link', 'drive bail'),
    ('detent pawl', 'row detent link'), ('row detent link', 'row detent roller'), ('row detent wedge', 'row detent roller'),
    ('ribbon link', 'ribbon vibrator'), ('ribbon link', 'cam rod ribbon'), ('detent link', 'detent pawl'), ('detent link', 'cam rod detent'),
    ('lift bellcrank', 'lift output slider'), ('lift bellcrank', 'lift push rod'), ('lift push rod', 'lift fork'),
    ('stem ', 'lever '), ('selector rod', 'selector comb'), ('lift output pin', 'lift'), ('lift fork pin', 'lift fork'), ('amplifier', 'output slider'), ('amplifier', 'tape slider'),
    # rev. 0.8b: stops of the print unit, O link, frame springs (pins in their bores, rods in their slots)
    ('zero stop', 'zero stop screw'), ('stop bellcrank', 'stop bellcrank pin'), ('stop bellcrank bracket', 'stop bellcrank pin'),
    ('stop carrier', 'stop carrier rod'), ('stop carrier rod bracket', 'stop carrier rod'), ('stop selector lever', 'stop selector pin'),
    ('stop selector bracket', 'stop selector pin'), ('stop selector lever', 'stop selector bracket'), ('W follower axis', 'O follower'),
    ('O follower', 'O rod A rear'), ('O rod A rear', 'O rod A spring'), ('O rod A spring', 'O rod A front'), ('O rod A front', 'O rocker'),
    ('O rocker', 'O rocker pin'), ('lock bail guide', 'O rocker pin'), ('O rocker', 'O rod B'), ('O rod B', 'O bellcrank'),
    ('O bellcrank', 'O bellcrank pin'), ('O bellcrank bracket', 'O bellcrank pin'), ('O bellcrank', 'O post'),
    ('stop bellcrank', 'stop feeler'), ('stop bellcrank', 'stop carrier'), ('stop finger', 'stop carrier'), ('stop selector lever', 'stop finger'),
    ('stop finger', 'memory sleeve'), ('stop selector lever', 'bail N'), ('O follower', 'bail O'),
    ('frame', 'zero stop'), ('frame', 'O bellcrank bracket'), ('stop bellcrank bracket', 'motor cheek'), ('stop carrier rod bracket', 'motor cheek'),
    ('stop selector bracket', 'motor cheek'), ('stop feeler', 'U-frame base'), ('O post', 'U-frame base'), ('slide return spring', 'zero stop'),
    ('cycle trip lever', 'cycle trip link'), ('cycle trip link', 'cycle stop latch'), ('cycle trip lever', 'bail R'), ('cycle trip lever', 'bail O'),
    ('lock bail', 'lock bail guide'), ('lock link', 'lock bail'), ('lock link', 'cycle stop latch'), ('ball race', 'lever'),
    ('row detent wedge', 'row detent post'), ('row detent link', 'row detent wedge'),
    ('row detent post', 'U-frame base'), ('row detent link', 'row detent post'), ('row detent link', 'detent link'),
    ('hammer cocking lever', 'hammer axle'), ('hammer cocking lever', 'hammer cocking rod'), ('hammer cocking rod', 'hammer trip link'),
    ('hammer spring', 'hammer axle'), ('hammer spring', 'hammer'),
    # rev. 0.14: the hammer's collar on its axle, the lip on the tab, the sear on its pin and bracket, the lug on the toe
    ('hammer collar', 'hammer axle'), ('hammer collar', 'hammer cocking lever'), ('hammer collar', 'hammer sear'),
    ('hammer sear', 'hammer sear pin'), ('hammer sear', 'hammer cocking lever'), ('hammer sear pin', 'hammer sear bracket'),
    ('hammer sear bracket', 'U-frame arm and hammer post'), ('hammer cocking lever', 'hammer'), ('escapement stop', 'escapement shaft'),
    ('escapement stop', 'escapement wheel'), ('hammer cocking rod', 'U-frame arm'),
    ('sector axis', 'memory sleeve'), ('memory sleeve', 'memory sleeve'), ('sector axis', 'sector bracket'), ('sector bracket', 'motor cheek'), ('sector axis', 'motor cheek'),
    ('memory pawl', 'sector bracket'), ('memory pawl', 'memory sleeve'), ('memory pawl', 'memory pawl'),
    ('spring barrel', 'spring barrel lid'), ('spring barrel lid', 'mainspring'), ('spring barrel lid', 'barrel arbor'), ('memory sleeve', 'plate'), ('W follower', 'W follower axis'),
    ('W follower axis', 'W follower bracket'), ('W follower bracket', 'frame side'), ('W follower', 'plate'), ('W follower', 'escapement rod Y'),
    ('escapement rod Y', 'escapement bellcrank'), ('escapement bellcrank', 'escapement rod X'), ('escapement rod X', 'escapement stop'),
    ('guides', 'plate'), ('guides', 'tier carriage'), ('bail bracket', 'frame'),
    # rev. 0.8 selection unit: pins in sliders and slots, levers on node pins, bail on raised pins, fingers under pins
    ('latch pin', 'bit slider'), ('summing lever', 'node slider'), ('summing lever', 'bit slider'), ('summing lever', 'summing lever'),
    ('amplifier', 'node slider'), ('amplifier', 'fulcrum slide'), ('amplifier', 'summing lever'), ('drive bail', 'latch pin'),
    ('drive bellcrank', 'drive bail'), ('drive bellcrank', 'drive link'), ('drive link', 'drive bail'), ('drive bellcrank', 'cam rod'),
    ('selector rod', 'latch pin'), ('lift bellcrank', 'lift output slider'), ('lift bellcrank', 'lift push rod'),
    ('lift bellcrank', 'lift bellcrank bracket'), ('lift bellcrank bracket', 'U-frame base'), ('lift push rod', 'lift fork'),
    ('amplifier', 'lift output slider'), ('guide plate', 'U-frame base'), ('amplifier', 'tape slider'),

    ('frame ', 'frame '), ('beam', 'beam post'), ('beam', 'rail MGN12'), ('frame', 'beam post'), ('frame', 'carriage post'),
    ('carriage post', 'carriage rod'), ('rail MGN12', 'MGN12H block'), ('MGN12H block', 'U-frame base'),
    ('lever pivot rod', 'lever '), ('lever pivot rod', 'pivot bracket'), ('pivot bracket', 'frame cross'),
    ('stem ', 'cap '), ('lever ', 'key comb'), ('lever ', 'space comb'), ('stem ', 'lever '), ('plate ', 'lever '), ('grub ', 'plate '), ('grub ', 'bail '),
    ('shaft', 'bearing'), ('shaft', 'drum'), ('shaft', 'shuttle'), ('guide rod', 'drum'), ('guide rod', 'shuttle bushing'),
    ('shuttle bushing', 'shuttle'), ('type block', 'shuttle'), ('bearing', 'shaft tower'), ('bearing', 'U-frame base'),
    ('shaft tower', 'U-frame base'), ('stop rail', 'U-frame base'), ('stop rail', 'stop slider'), ('stop slider', 'stop finger'),
    ('pins block', 'U-frame base'), ('stop pin', 'pins block'), ('stop pin', 'U-frame base'), ('band pulley', 'pulley post'),
    ('pulley post', 'U-frame base'), ('band', 'drum'), ('band', 'band pulley'), ('band', 'stop finger'),
    ('lift fork bracket', 'U-frame base'), ('lift fork', 'lift fork bracket'), ('lift fork', 'shuttle'), ('lift fork', 'lift collar'), ('lift collar', 'shuttle'), ('lift collar', 'shaft'),
    ('hammer axle', 'hammer'), ('hammer axle', 'U-frame arm'), ('U-frame arm', 'U-frame base'),
    ('carriage end plate', 'carriage bushing'), ('carriage bushing', 'carriage rod'), ('paper tube', 'carriage end plate'),
    ('feed roller', 'carriage end plate'), ('paper guide', 'carriage end plate'), ('carriage rack', 'carriage end plate'),
    ('paper', 'feed roller'), ('paper', 'paper guide'), ('paper', 'paper rest'), ('paper', 'pinch roller'),
    ('pinch roller', 'carriage end plate'), ('paper rest', 'carriage end plate'),
    ('escapement shaft', 'escapement'), ('escapement wheel', 'carriage rack'), ('escapement bracket', 'frame back'),
    ('escapement dog', 'escapement wheel'), ('escapement stop', 'escapement wheel'),
    ('pusher ', 'lever '), ('push rod', 'pusher '), ('push rod', 'pusher comb'), ('pusher comb post', 'pusher comb'),
    ('pusher comb post', 'frame'), ('push rod', 'stop pin'), ('stop pin', 'stop finger'),
    ('sector shaft', 'sector '), ('sector bracket', 'frame'), ('sector shaft', 'sector bracket'), ('latch', 'sector bracket'),
    ('latch', 'sector '), ('bail bracket', 'frame'), ('ribbon post', 'beam'), ('ribbon spool', 'ribbon post'),
    ('ribbon guide', 'ribbon post'), ('ribbon', 'ribbon guide'), ('lift bail', 'lever '), ('key comb', 'stem '),
    ('space comb', 'stem '),
    ('column pusher', 'lever '), ('column pusher', 'pusher guide'), ('selector bar', 'column pusher'), ('selector bar', 'lever '),
    ('selector rod', 'selector bar'), ('selector rod', 'selector comb'), ('selector comb', 'selector post'), ('selector post', 'frame'),
    ('pusher guide', 'selector post'), ('latch pad', 'U-frame base'), ('latch pad', 'selector rod'), ('cam rod', 'whiffletree'), ('cam rod', 'latch pad'),
    ('cam rod', 'cam '), ('cam ', 'cycle shaft'), ('cycle stop arm', 'cycle shaft'), ('cycle stop arm', 'cycle stop latch'),
    ('cycle bearing block', 'cycle shaft'), ('cycle bearing block', 'frame'), ('tape rail', 'U-frame base'),
    ('tape rail', 'tape slider'), ('tape slider', 'tape clamp'), ('rotate tape', 'tape clamp'), ('rotate tape', 'pulley and detent'),
    ('whiffletree', 'U-frame base'), ('whiffletree', 'latch pad'), ('whiffletree', 'tape slider'), ('whiffletree', 'tape clamp'),
    ('detent pawl', 'U-frame base'), ('detent pawl', 'pulley and detent'), ('detent pawl', 'detent link'), ('detent link', 'cam rod'),
    ('hammer trip link', 'U-frame'), ('hammer trip link', 'cam rod'), ('pulley and detent', 'shaft'), ('pulley and detent', 'guide rod'),
    ('pulley and detent', 'bearing'), ('lift fork', 'lift whiffletree'),
    ('winding gear', 'barrel arbor'), ('winding gear', 'winding pinion'), ('winding pinion', 'winding crank'),
    ('int1 shaft', 'int1 pinion'), ('int1 shaft', 'int1 gear'), ('int1 pinion', 'barrel gear'), ('int1 gear', 'int2 pinion'),
    ('int2 shaft', 'int2 pinion'), ('int2 shaft', 'bevel gear 24'), ('bevel gear 24', 'bevel pinion 12'), ('bevel pinion 12', 'lay shaft'),
    ('lay shaft', 'bevel lay'), ('bevel lay', 'bevel cycle'), ('bevel cycle', 'cycle shaft'), ('lay shaft', 'lay shaft bearing'),
    ('lay shaft bearing', 'frame'), ('motor cheek', 'shaft'), ('motor cheek', 'arbor'), ('motor cheek', 'frame'),
    ('spring barrel', 'mainspring'), ('spring barrel', 'barrel arbor'), ('mainspring', 'barrel arbor'), ('barrel arbor', 'motor plate'),
    ('barrel arbor', 'frame side'), ('barrel arbor', 'winding crank'), ('barrel gear', 'barrel arbor'), ('barrel gear', 'pinion A'),
    ('arbor A', 'pinion A'), ('arbor A', 'gear A'), ('gear A', 'pinion B'), ('arbor B', 'pinion B'), ('arbor B', 'gear B'),
    ('gear B', 'pinion C'), ('pinion C', 'cycle shaft'), ('governor gear', 'cycle shaft'), ('governor gear', 'governor pinion'),
    ('governor pinion', 'governor arbor'), ('governor fan', 'governor arbor'), ('motor plate', 'frame'), ('arbor A', 'motor plate'),
    ('arbor B', 'motor plate'), ('cycle shaft', 'motor plate'), ('governor arbor', 'motor plate'), ('cycle stop latch', 'motor plate'),
    ('pinion A', 'gear A'), ('pinion B', 'gear B'), ('cycle shaft', 'frame side'),
]


def allowed(a, b):
    if a.startswith('bail ') and b.startswith('bail ') and a.split()[1] == b.split()[1]:
        return True          # bar and side of the same frame
    for x, y in ALLOW:
        if (x in a and y in b) or (x in b and y in a):
            return True
    return False


def bboxes(parts):
    out = []
    for p in parts:
        b = p.mesh.bounding_box()
        out.append(np.array(b, float))
    return np.array(out)


def interferences(parts, tol=0.05, skip_allowed=True):
    bb = bboxes(parts)
    res = []
    n = len(parts)
    for i in range(n):
        lo, hi = bb[i, :3], bb[i, 3:]
        ov = np.all(bb[i + 1:, :3] < hi - tol, 1) & np.all(bb[i + 1:, 3:] > lo + tol, 1)
        for j in np.nonzero(ov)[0] + i + 1:
            a, b = parts[i], parts[j]
            if skip_allowed and allowed(a.name, b.name):
                continue
            v = (a.mesh ^ b.mesh).volume()
            if v > tol:
                res.append((a.name, b.name, v))
    return res


def bed_fit(m, bed=(220.0, 220.0, 250.0), keep_up=False):
    """Lay a part on the bed: lowest height that fits, rotations about Z in 1 deg steps.
    keep_up: the part is already oriented for printing (only rotations about Z)."""
    best = None
    ors = [(0, 0)] if keep_up else [(0, 0), (90, 0), (0, 90), (180, 0), (-90, 0), (0, -90)]
    for rx, ry in ors:
        mm = m.rotate((rx, ry, 0))
        V = np.asarray(mm.to_mesh().vert_properties)[:, :3]
        h = V[:, 2].max() - V[:, 2].min()
        for a in range(0, 90, 1):
            c, s = np.cos(np.radians(a)), np.sin(np.radians(a))
            x = V[:, 0] * c - V[:, 1] * s; y = V[:, 0] * s + V[:, 1] * c
            w, d = x.max() - x.min(), y.max() - y.min()
            fits = w <= bed[0] and d <= bed[1] and h <= bed[2]
            key = (not fits, round(h, 1), max(w, d))
            if best is None or key < best[0]:
                best = (key, (rx, ry, a), (w, d, h), fits)
    return best[1], best[2], best[3]
