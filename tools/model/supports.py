"""rev. 0.14 (physics checks, stage 1): supports and retainers the model lacked.

* base plate: 4 mm plywood under the frame, screwed into the profiles' bottom slots (M5 + T-nuts). Everything that
  stood on z = 0 without anything under it (the cycle bearing blocks, the selector posts, the lock bail guides, the
  ball race, the rocker bracket) now stands on it and is screwed through it from below (M3 into inserts). Windows let
  the side plates of the frames R, O and N go 0.5 mm under z = 0 at full travel.
* comb bridge: the key comb and the space comb lay on the levers; a square bar (Д16Т 6x6) across the front on two
  posts standing on the base plate carries them by four tabs.
* lever pivot rod: it ended 2 mm short of its brackets; it now passes through them and two E-clips (DIN 6799, 3.2)
  hold it outside the brackets.
* cycle trip lever: a post on the base plate with a pin along Y through the lever's block (the frames R, O press the
  lever's bar at x 112 / 117, the link at x 124 rises: the lever turns about the pin at x 120.5).
* cycle stop latch: a post with an arm and a pivot pin.
* zero stop M: its pin stood in front of the top plate (y 101, the plate begins at y 110); a bridge over the
  margin strip and stops (z 103.6) carries it, the pin goes up into it.
* pusher guide: two hangers from the selector comb.
* E-clips on the stop carrier rod (its outer end stops on the sector bracket) and the read lock axle."""
import math
import params as P
from geo import box, cyl

PLATE_Z = (-4.0, 0.0)
BAIL_WINDOWS = [(109.0, 120.5), (147.5, 154.5)]       # |x| of the side plates of frames R, O (109..120) and N (148..154)
BRIDGE = dict(x=(-207.0, 206.0), y=(-373.0, -367.0), z=(56.0, 62.0))
POSTS = ((-206.0, -200.0), (199.0, 205.0))
KEY_TABS = ((-138.0, -134.5), (134.5, 138.0))
SPACE_TABS = ((-102.0, -97.0), (97.0, 102.0))
TAB_Z = (60.3, 62.0)


def parts(st, Part, COL):
    out = []
    pl = box(-P.FRAME_X, P.FRAME_X, P.FRAME_Y0, P.FRAME_Y1, *PLATE_Z)
    for x0, x1 in BAIL_WINDOWS:
        for s in (-1, 1):
            a, b = sorted((s * x0, s * x1))
            pl = pl - box(a, b, -391.0, -230.0, PLATE_Z[0] - 1, PLATE_Z[1] + 1)
    out.append(Part('base plate', 'frame', 'cut', pl, (196, 170, 130), 'plywood4_500x525', 'фанера',
                    note='основание: фанера 4 мм под рамой, на винтах М5 с Т-гайками в нижние пазы профиля; детали, стоящие на '
                         'основании, привёрнуты снизу винтами М3 во вставки (ред. 0.14)'))
    out.append(Part('comb bridge', 'keys', 'cut', box(BRIDGE['x'][0], BRIDGE['x'][1], *BRIDGE['y'], *BRIDGE['z']), COL['steel'],
                    'bar6x6x413', 'Д16Т', note='брус гребёнок: квадрат 6×6 мм, на двух стойках; гребёнки клавиш и пробела на лапках, на винтах М3 (ред. 0.14)'))
    for k, (x0, x1) in enumerate(POSTS):
        out.append(Part(f'comb post {-1 if k == 0 else 1:+d}', 'keys', 'print', box(x0, x1, *BRIDGE['y'], 0.0, BRIDGE['z'][0]),
                        (110, 112, 120), 'comb_post', 'PETG', note='стойка бруса гребёнок на основании (ред. 0.14)'))
    for k, (x0, x1) in enumerate(KEY_TABS):
        out.append(Part(f'key comb tab {-1 if k == 0 else 1:+d}', 'keys', 'print', box(x0, x1, BRIDGE['y'][1], -308.0, *TAB_Z),
                        (110, 112, 120), 'comb_tab_key', 'PETG', note='лапка гребёнки клавиш от бруса (ред. 0.14)'))
    for k, (x0, x1) in enumerate(SPACE_TABS):
        out.append(Part(f'space comb tab {-1 if k == 0 else 1:+d}', 'keys', 'print', box(x0, x1, BRIDGE['y'][1], -335.0, *TAB_Z),
                        (110, 112, 120), 'comb_tab_space', 'PETG', note='лапка гребёнки пробела от бруса (ред. 0.14)'))
    zc = (P.LEVER_Z0 + P.LEVER_Z1) / 2
    for s in (-1, 1):
        x0, x1 = sorted((s * 154.0, s * 154.6))
        clip = cyl((x0, P.LEVER_PIVOT_Y, zc), (x1, P.LEVER_PIVOT_Y, zc), 3.6, 24) - cyl((x0 - 1, P.LEVER_PIVOT_Y, zc), (x1 + 1, P.LEVER_PIVOT_Y, zc), 2.0, 16)
        out.append(Part(f'lever pivot clip {s:+d}', 'levers', 'buy', clip, COL['steel'], 'eclip3_2', 'сталь',
                        note='стопорное кольцо DIN 6799 3,2 на оси рычагов (ред. 0.14)'))
    # cycle trip lever
    out.append(Part('cycle trip post', 'levers', 'print', box(123.0, 127.0, -251.5, -245.2, 0.0, 21.0) +
                    box(119.3, 127.0, -246.0, -244.8, 14.5, 21.0), (110, 112, 120), 'trip_post', 'PETG',
                    note='стойка качалки спуска цикла с осью (ред. 0.14)'))
    out.append(Part('cycle trip pin', 'levers', 'buy', cyl((120.5, -251.8, 18.0), (120.5, -244.9, 18.0), 1.0, 12), COL['steel'],
                    'pin2x8', 'сталь', 'ось качалки спуска (ред. 0.14)'))
    # cycle stop latch: post, arm, pin (the latch turns on it)
    out.append(Part('cycle stop latch post', 'drive', 'print', box(185.0, 190.0, -20.0, -15.0, 0.0, 44.4) +
                    box(181.6, 190.0, -15.0, -12.0, 36.0, 42.0), (110, 112, 120), 'latch_post', 'PETG',
                    note='стойка защёлки цикла на основании (ред. 0.14)'))
    out.append(Part('cycle stop latch pin', 'drive', 'buy', cyl((174.5, -13.5, 39.0), (186.0, -13.5, 39.0), 1.0, 12), COL['steel'],
                    'pin2x12', 'сталь', 'ось защёлки цикла (ред. 0.14)'))
    # the memory sector and the zero stop M were "hung from the top plate", which ended at y 104: the plate goes on
    out.append(Part('zero stop M bridge', 'esc', 'print', box(-10.0, 0.0, 98.0, 114.0, 103.6, 105.6) + box(-10.0, 0.0, 111.0, 114.0, 102.0, 103.6) -
                    cyl((-5.4, 101.0, 103.0), (-5.4, 101.0, 106.0), 1.5, 24), (110, 112, 120), 'zero_m_bridge', 'PETG',
                    note='мостик упора нуля M над линейкой полей: на верхней плите кронштейна спуска (ред. 0.14)'))
    # pusher guide hangers (from the selector comb)
    for s in (-1, 1):
        x0, x1 = sorted((s * 106.0, s * 110.9))
        out.append(Part(f'pusher guide hanger {s:+d}', 'select', 'print', box(x0, x1, 24.3, 28.0, 69.0, 84.0) + box(x0, x1, 25.0, 28.0, 84.0, 87.0),
                        (110, 112, 120), 'pusher_hanger', 'PETG', note='подвес направляющей толкателей к гребёнке выбора (ред. 0.14)'))
    # E-clips: stop carrier rod (its free end), read lock axle (top)
    for k, (y0, y1) in enumerate(((-302.9, -302.3),)):      # inside; outside, the sector bracket stops the rod's end (0.2 mm)
        out.append(Part(f'stop carrier rod clip {k}', 'sectors', 'buy', cyl((169.5, y0, 99.0), (169.5, y1, 99.0), 3.0, 20) -
                        cyl((169.5, y0 - 1, 99.0), (169.5, y1 + 1, 99.0), 1.2, 12), COL['steel'], 'eclip2_3', 'сталь',
                        'стопорное кольцо на прутке каретки щупа (ред. 0.14)'))
    out.append(Part('read lock axle clip', 'drive', 'buy', zcyl_(83.2, -14.1, 12.2, 12.7, 2.5) - zcyl_(83.2, -14.1, 11.0, 14.0, 0.8),
                    COL['steel'], 'eclip1_5', 'сталь', 'стопорное кольцо на оси запора чтения (ред. 0.14)'))
    return out


def zcyl_(x, y, z0, z1, r):
    return cyl((x, y, z0), (x, y, z1), r, 20)
