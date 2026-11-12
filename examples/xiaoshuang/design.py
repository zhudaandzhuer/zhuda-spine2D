"""小霜 (Xiaoshuang) -- shared geometry for art.py and rig.py, in canvas pixels (x right, y down).

Naming: head parts use _L/_R = SCREEN left/right.  Limbs use _n/_f = NEAR/FAR from the camera: the character is
authored facing screen-right in a 3/4 stance, so the near limbs are the screen-left ones and are drawn in front.
Facing left is the same skeleton mirrored by the controller (skeleton.scaleX = -1); near stays near.
"""
W, H, CX = 800, 1000, 400
GROUND = 840
FRAME = (-170, 120, 1140, 770)        # wide camera: room to walk both ways

ROOT = (400, GROUND)
HIP = (400, 602)
WAIST_TIP = (400, 522)
CHEST_TIP = (400, 438)
NECK = (400, 434)
HEAD = (400, 412)
FACE_C = (400, 318)
TURN_C = (400, 478)
LOOK_UNIT, TURN_UNIT = 20.0, 11.0

SHOULDER_N, ELBOW_N, WRIST_N, HAND_TIP_N = (346, 446), (341, 502), (336, 554), (335, 582)
HIP_N, KNEE_N, ANKLE_N = (377, 604), (377, 706), (377, 806)
EYE_L, EYE_R = (348, 328), (452, 328)
MOUTH, NOSE = (400, 384), (402, 364)


def flip(p):
    return (2 * CX - p[0], p[1])


def mx(pts):
    return [(2 * CX - x, y) for x, y in reversed(pts)]


SHOULDER_F, ELBOW_F, WRIST_F, HAND_TIP_F = flip(SHOULDER_N), flip(ELBOW_N), flip(WRIST_N), flip(HAND_TIP_N)
HIP_F, KNEE_F, ANKLE_F = flip(HIP_N), flip(KNEE_N), flip(ANKLE_N)

FACE_RIGHT = [(400, 182), (452, 188), (492, 214), (508, 260), (506, 314), (495, 358), (469, 392), (435, 409)]
FACE = FACE_RIGHT + [(400, 413)] + mx(FACE_RIGHT[1:])
EYE_UP_L = [(322, 331), (328, 313), (344, 304), (360, 307), (373, 326)]       # outer -> inner
EYE_LOW_L = [(373, 326), (366, 343), (349, 350), (332, 345), (322, 331)]      # inner -> outer
EYE_HOLE_L = EYE_UP_L + EYE_LOW_L[1:-1]
LID_TOP_Y, LID_FEATHER, LID_CLOSE = 278.0, 8.0, 43.0
HEAD_DEPTH = dict(cx=400, cy=308, rx=138, ry=158)
BODY_DEPTH = dict(cx=400, cy=478, rx=74, ry=92)
