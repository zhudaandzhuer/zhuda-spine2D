"""Shared geometry for art.py and rig.py -- one source of truth, in canvas pixels (x right, y down).

Side convention: _L / _R are SCREEN left / right (the viewer's), not the character's own.
"""
W, H, CX = 1000, 1200, 500
FRAME = (130, 40, 740, 960)          # intended camera frame (x, y, w, h): bust sprite, art continues below it

# pivots
ROOT = (500, 1200)
HIP = (500, 1060)
WAIST = (500, 900)
CHEST = (500, 730)
NECK = (500, 528)
HEAD = (500, 448)                    # skull base: head tilts around here
FACE_C = (500, 330)                  # look controller sits at the face centre
SHOULDER_L, SHOULDER_R = (328, 604), (672, 604)
ELBOW_L, ELBOW_R = (307, 862), (693, 862)
WRIST_L, WRIST_R = (301, 1160), (699, 1160)

EYE_L, EYE_R = (447, 320), (553, 320)
BROW_L, BROW_R = (448, 280), (552, 280)
NOSE = (500, 378)
MOUTH = (500, 412)

LOOK_UNIT = 22.0                     # px the face centre travels at full look deflection


def mx(pts):
    """Mirror a point list across the centre line, keeping winding."""
    return [(2 * CX - x, y) for x, y in reversed(pts)]


def flip(p):
    return (2 * CX - p[0], p[1])


# ---- face ------------------------------------------------------------------------------------------
FACE_RIGHT = [(500, 152), (556, 158), (598, 188), (611, 240), (610, 300), (603, 345), (587, 385), (562, 417), (536, 439.5), (516, 450.5)]
FACE = FACE_RIGHT + [(500, 453.5)] + mx(FACE_RIGHT[1:])

# screen-left eye opening; the right eye is the mirror image
EYE_UP_L = [(417, 322.5), (424, 313.5), (437, 308), (451, 307), (464, 311), (475, 324)]   # outer corner -> inner corner
EYE_LOW_L = [(475, 324), (467, 330), (453, 333), (438, 332.5), (426, 329), (417, 322.5)]    # inner -> outer
EYE_HOLE_L = EYE_UP_L + EYE_LOW_L[1:-1]
LID_TOP_Y = 276.0                    # top of the eyelid skin patch
LID_FEATHER = 9.0                    # px of soft edge at the top of that patch; this band never moves
LID_CLOSE = 26.5                     # px the lash line centre travels to close


def face_depth_params():
    """Ellipsoid used for parallax depth of everything lying on the face surface."""
    return dict(cx=500, cy=322, rx=146, ry=188)
