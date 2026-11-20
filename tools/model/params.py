"""All dimensions of the TPM-2 layout model, mm. Coordinates: X along the line (right), Y away from the
typist (back), Z up. The paper plane is y = 0, the print point is (0, 0, ZP) with the slide at zero."""
import math, json, os

INCH = 25.4
EM = INCH / 3
U = EM / 16
PITCH_U = 19                     # u per shuttle position
NPOS = 11                        # rev. 0.6: 8 rows x 11 positions (one position per keyboard column)
RH = 1.35 * EM                   # shuttle row pitch
NROWS = 8
HOME_ROW = 3.5                   # geometric reference: the shuttle drawing has rows 4-5 (index 3.5) at the print line
# rev. 0.8: the shuttle rests BELOW the line, so the typist sees the line being typed: one row pitch under the top row.
# Every stroke lifts it (rows are counted from 0 at the top); row 0 is printed with a lift of one pitch.
REST_ROW = -1.0
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from layout import ROW_CODE      # keyboard row -> shuttle row code (rev. 0.8, by frequency)
RIBBON_DROP = 10.0               # rev. 0.8: the ribbon rests 10 mm under the print line and is raised for the blow
MARK_REF_U = 8                   # dead marks: anchor sits 8u right of the hammer axis on the type block
SLIDE_MAX_U = 9 + MARK_REF_U     # largest retraction of the print unit, u
SLIDE_MAX = SLIDE_MAX_U * U

# shuttle
R_FACE = 60.0                    # type face radius
STEP = PITCH_U * U / R_FACE      # rad per position
STEP_DEG = math.degrees(STEP)
ARC_DEG = STEP_DEG * NPOS
GAP_PAPER = 0.6                  # type face to paper (rev. 0.9.2: was 1.5 -- the hammer could not carry the sheet that far)
RIBBON_Y = -GAP_PAPER / 2        # ribbon mid-plane: 0.25 mm from the face and from the sheet
AXIS_Y = -(R_FACE + GAP_PAPER)   # shuttle axis
RELIEF, BLOCK_DEPTH = 1.2, 4.0
BLOCK_U0, BLOCK_U1 = -1.0, 17.0  # block extent along the line, u from the hammer axis
RING_R1 = R_FACE - RELIEF - BLOCK_DEPTH + 2.0   # ring band (blocks sit 2 mm into it)
RING_R0 = RING_R1 - 6.0
ZP = 234.0                       # print line height above the table (rev. 0.8: +9 mm, room for the shuttle resting under the line)
BASE1 = ZP - 0.18 * EM + HOME_ROW * RH   # baseline of shuttle row 1 (index 0) at home
BLOCK_TOP = BASE1 + 0.85 * EM
BLOCK_BOT = BLOCK_TOP - NROWS * RH
SHAFT_R = 4.0                    # 8 mm steel shaft
HUB_R = 13.0

# position selection (rev. 0.6): cycle-driven whiffletrees, tape pulley and detent wheel on the shaft
LEVER_PITCH = 19 / 4             # 4.75 mm
X0_KEYS = -LEVER_PITCH * 43 / 2  # x of lever 0
PULLEY_R = 30.0                  # rotate tape pulley on the shuttle shaft
Z_PULLEY = (111.0, 117.0)
DETENT_R = 40.0
Z_DETENT = (119.0, 124.0)
GUIDE_R = 30.0                   # anti-rotation rod radius
GUIDE_ANG = 180.0                # rev. 0.10: the rod stands behind the shaft (CCW from +Y in the shuttle frame); the
                                 # reading head works inside the ring in front of the shaft, where the rod used to be

# rev. 0.10: the code is read from the shuttle. Each shuttle position carries a code comb on the ring's inner face:
# for every row three tabs (W, B, C) whose faces stand at r = READ_R0 + READ_C0 + READ_K v from the shuttle axis.
# Three feelers on the U-frame go out along the strike ray until they meet the tabs of the cell being printed.
READ_K = 1.0                     # mm of feeler travel per unit (as the old gauge frames)
READ_R0 = 35.5                   # feeler tips at rest, radius from the shuttle axis
READ_C0 = 1.0                    # free travel before the tab of value 0 (the lost motion of the wire)
READ_TRAVEL = READ_C0 + READ_K * 12 + 0.5   # full feeler stroke: v = 12 (W of the widest glyph) and 0.5 mm overtravel
COMB_T = 1.6                     # comb spine (radial), against the ring's inner face
COMB_W = 6.0                     # spine width along the ring, mm
TAB_W = 3.0                      # tab width along the ring (the feeler is 1.6 mm wide)
TAB_H = 2.6                      # tab height (z)
READ_DZ = {'W': 3.6, 'B': 0.0, 'C': -3.6}   # tab rows of a cell, mm above the centre of the row
READ_CH = ('W', 'B', 'C')
READ_F_SPRING = {'W': 0.6, 'B': 0.45, 'C': 0.45}  # N, feeler springs (long, nearly constant over the stroke)
READ_F_LOAD = {'W': 0.35, 'B': 0.3, 'C': 0.3}     # N, what each feeler drags out: the escapement return spring (0.2 N
                                                 # in rev. 0.10); on B and C the follower and its pawl (as the old
                                                 # frames: 0.3 N); the wire's friction in its housing
READ_RAMP = (22.0, 47.0)                          # cam ramps: release before 'read'[0], return after 'read'[1]
TAPE_PER_POS = PULLEY_R * STEP   # tape travel per shuttle position, mm

# cycle and spring motor
CYCLE_T = 0.40                   # s per character on average (2.5 characters per second)
CYCLE = dict(out=(10, 120), detent=(120, 185), ribbon=(155, 175), strike=160, back=(200, 310), feed=(310, 350),
             read=(140, 150), wlatch=345)   # degrees of the cycle shaft
# rev. 0.10: 'read' -- the feelers are out: the cam lets them go over 118..140 and takes them back over 150..197, before the
# shuttle moves back at 200 (a long return keeps the cam's torque low);
# 'wlatch' -- the latch that holds frame W from the reading to the feed lets it go

# keyboard and levers
KEY_ROW_Y = [-250.0 - 19 * r for r in range(4)]
SPACE_Y = -330.0
KEY_TRAVEL = 16.0                # = plate travel (lever ratio 1 at the key)
LEVER_PIVOT_Y = -70.0
LEVER_TAIL_Y = 24.0             # tails lift the pin pushers behind the pivot
LEVER_Z0, LEVER_Z1 = 48.0, 60.0
COMB_Z = (62.0, 65.0)
LEVER_T = 3.0
KEYTOP_Z = [96.0 - 2 * r for r in range(4)]
KEYCAP = 17.0

# code plates and bails
TP = KEY_TRAVEL
K_STEP = 1.0
W_OFFSET = 4
BAIL_PITCH = 9.0
TIER_SHIFT = 4.5
ZONE_A = (-308.0, -246.0)        # deck A (keyboard rows 0, 2) bail zone
ZONE_B = (-374.0, -312.0)        # deck B (rows 1, 3)
BAIL_Z = 22.0                    # top of the bail bars
BOSS_Z = (40.0, 48.0)
BAIL_ORDER = ['R', 'W', 'B', 'C', 'O', 'N']
PLATE_T, BOSS_W = 3.0, 6.0
STRAP_T = 2.0

# frame (2020 profiles)
EXT = 20.0
FRAME_X = 250.0
FRAME_Y0, FRAME_Y1 = -395.0, 130.0

# slide / U-frame
RAIL_Y = [-150.0, -20.0]
RAIL_Z = 90.0                    # top of the fixed beams
UF_Z = 103.0                     # underside of the U-frame base (on MGN12 carriages)
UF_T = 6.0
ARM_Z0, ARM_Z1 = 72.0, 82.0
POST_Y = (70.0, 80.0)
HAMMER_PIVOT = (75.0, ZP - 22.0)  # (y, z)

# carriage
PAPER_W = 216.0
LINE_LEN = 170.0
CAR_RAIL_LO = (58.0, 92.0)       # (y, z) of the lower rod
CAR_RAIL_HI = (98.0, ZP + 28.0)
TUBE = (38.0, ZP - 52.0, 15.0)   # (y, z, r)
CAR_X_START, CAR_X_END = 88.0, -82.0
CAR_HALF = 118.0
ROLLER = (7.0, ZP + 95.0, 7.0)   # rear feed roller (y, z, r); pinch rollers in front

def info():
    return {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float, list, tuple))}

if __name__ == '__main__':
    for k, v in info().items():
        print(k, v)
