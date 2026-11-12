"""figure3d -- white models: pose a figure in 3D, bake it into a flat 2D Spine rig that can be re-skinned.

The pose lives in 3D (joint angles, feet solved by IK on the ground, loose things simulated).  Every frame is projected
orthographically, and each body part becomes one bone + one slot:

    sphere (joints)      -> circle                                  translate
    cone-tube (limbs)    -> tube between two projected joints        translate + rotate + scaleX (foreshortening)
    ellipsoid (the rest) -> ellipse, mapped from a reference image   translate + rotate + scale + shearY

Parts that look different from different sides (head, chest, pelvis, feet) carry EIGHT view images -- front, 3/4, side,
3/4 back, back and their left-hand counterparts -- and the baker switches between them as the part turns.  Between two
views the image is deformed so the silhouette stays exact; only the content "pops".  That is what makes a skin possible:
a skin replaces the images, the motion is untouched.

Body types are presets of proportions plus "extras": rigid add-ons (ears, snout, a club), simulated chains (ponytail,
scarf, tail, cape panels), a skirt cone that the thighs push, a shoulder bag on a strap.  Extras are simulated in 3D at
bake time (springs + gravity), so the runtime needs no physics.

Frames: body x = the figure's LEFT, y = up, z = FORWARD.  heading 0 faces the camera, +90 faces screen-right.
Degrees everywhere.  pitch > 0 leans forward, yaw > 0 turns left, roll > 0 leans to the figure's right.
"""
from __future__ import annotations

import copy
import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import curves as C

SIDES = ("L", "R")
RAD = math.radians
VIEW_CODES = ["F", "FR", "R", "BR", "B", "BL", "L", "FL"]          # index * 45 degrees = which way the part faces on screen
VIEW_ZH = ["正面", "右前 3/4", "右側", "右後 3/4", "背面", "左後 3/4", "左側", "左前 3/4"]
GRAVITY = 2400.0
EPS_T = 0.001


def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _unit(v):
    return v / max(float(np.linalg.norm(v)), 1e-9)


# ------------------------------------------------------------------------------------------- bodies
PRESETS = {
    #            legs  arms  torso  shoulders  hips   limb radii      head  foot  hand  neck  chest / waist / pelvis (x, y, z)
    "hero":    dict(leg=1.00, arm=1.00, torso=1.00, shoulder=1.08, hip=0.97, leg_r=1.00, arm_r=1.02, head=1.00, foot=1.00, hand=1.00, neck=1.0, chest=(1.08, 1.00, 1.05), waist=(1.00, 1.00, 1.00), pelvis=(0.98, 1.00, 1.00)),
    "heroine": dict(leg=1.00, arm=0.94, torso=0.93, shoulder=0.86, hip=1.05, leg_r=0.88, arm_r=0.82, head=0.97, foot=0.88, hand=0.85, neck=0.85, chest=(0.86, 0.93, 0.95), waist=(0.80, 0.95, 0.86), pelvis=(1.03, 1.00, 1.00)),
    "chibi":   dict(leg=0.42, arm=0.50, torso=0.52, shoulder=0.60, hip=0.68, leg_r=0.78, arm_r=0.80, head=1.85, foot=0.72, hand=0.78, neck=0.9, chest=(0.64, 0.56, 0.78), waist=(0.68, 0.56, 0.82), pelvis=(0.70, 0.58, 0.82)),
    "brute":   dict(leg=0.82, arm=1.12, torso=1.04, shoulder=1.50, hip=1.18, leg_r=1.40, arm_r=1.55, head=0.92, foot=1.25, hand=1.50, neck=1.5, chest=(1.50, 1.18, 1.50), waist=(1.32, 1.08, 1.42), pelvis=(1.22, 1.05, 1.30)),
    "knight":  dict(leg=0.96, arm=1.02, torso=1.00, shoulder=1.22, hip=1.05, leg_r=1.18, arm_r=1.25, head=0.98, foot=1.10, hand=1.20, neck=1.2, chest=(1.25, 1.05, 1.25), waist=(1.12, 1.00, 1.20), pelvis=(1.10, 1.00, 1.15)),
    "mage":    dict(leg=0.98, arm=1.00, torso=1.00, shoulder=0.90, hip=0.95, leg_r=0.90, arm_r=0.85, head=1.00, foot=0.95, hand=0.90, neck=0.9, chest=(0.90, 1.00, 0.95), waist=(0.90, 1.00, 0.95), pelvis=(0.95, 1.00, 1.00)),
    "vtuber":  dict(leg=1.00, arm=0.94, torso=0.93, shoulder=0.86, hip=1.04, leg_r=0.88, arm_r=0.82, head=1.18, foot=0.88, hand=0.90, neck=0.85, chest=(0.86, 0.93, 0.95), waist=(0.80, 0.95, 0.86), pelvis=(1.02, 1.00, 1.00)),
    "mascot":  dict(leg=0.34, arm=0.46, torso=0.60, shoulder=0.98, hip=0.86, leg_r=1.15, arm_r=1.05, head=1.50, foot=0.90, hand=0.95, neck=1.2, chest=(1.18, 0.74, 1.55), waist=(1.36, 0.80, 1.72), pelvis=(1.30, 0.84, 1.66)),
}
PRESET_ZH = {"hero": "標準成人（圍巾）", "heroine": "女性成人（馬尾、裙）", "chibi": "Q 版大頭（雙馬尾）", "brute": "壯漢（披風、手持棍棒）", "mascot": "吉祥物（耳朵、口鼻、尾巴、側背包）",
             "knight": "盾牌戰士（盾、劍、肩甲、盔纓）", "mage": "魔法師（尖帽、長袍、寬袖、法杖）",
             "vtuber": "正面看板／虛擬主播（臉部零件、參數驅動、即時物理頭髮）"}
# How a body carries what it holds: side -> (flex, abd, twist, elbow, weight).  Locomotion clips blend the arm toward this
# pose (weight 1 = fully held), so a shield stays in front and a staff stays upright while the body walks, runs and turns.
# (The shield's face points along the upper arm's forward axis, so the upper arm stays low: raising it forward would tip
#  the shield face-up like a tray.  The shield is lifted by raising the arm SIDEWAYS and bending the elbow.)
HOLDS = {"knight": {"L": (16.0, 14.0, -90.0, 100.0, 0.9), "R": (8.0, 14.0, 0.0, 38.0, 0.7)},
         "mage": {"R": (22.0, 12.0, 0.0, 82.0, 0.85)}}
CLIPSETS = {"knight": "knight", "mage": "mage", "vtuber": "front"}


class Body:
    """Proportions (pixels) for one body type.  Body("hero"), Body("mascot", leg=0.4) ..."""

    def __init__(self, preset: str = "hero", cam_pitch: float = 10.0, **over):
        if preset not in PRESETS:
            raise ValueError(f"unknown body preset '{preset}' (have {', '.join(PRESETS)})")
        f = dict(PRESETS[preset])
        f.update(over)
        self.preset, self.f, self.k = preset, f, 1.0
        self.cam = _rx(RAD(cam_pitch))                 # the camera looks slightly down, so depth along the ground is visible
        L, A, T, H, F, Hn = f["leg"], f["arm"], f["torso"], f["head"], f["foot"], f["hand"]
        self.thigh = self.shin = 138.0 * L
        self.ankle_h = 26.0 * F
        self.upper_arm, self.forearm = 96.0 * A, 88.0 * A
        self.hip_w, self.shoulder_w = 32.0 * f["hip"], 66.0 * f["shoulder"]
        self.hip_drop, self.spine1, self.waist_c, self.spine2 = 16.0 * T, 38.0 * T, 24.0 * T, 54.0 * T
        self.chest_c, self.shoulder_y, self.neck_y, self.neck_len = 52.0 * T, 98.0 * T, 114.0 * T, 22.0 * T
        self.head_c, self.head_z, self.hand_c = 36.0 * H, 5.0 * H, 20.0 * Hn
        self.hip_h = self.ankle_h + self.thigh + self.shin - 2.0 * L + self.hip_drop       # standing, knees a touch soft
        lr, ar, nk = f["leg_r"], f["arm_r"], f["neck"]
        self.r = dict(hip=27 * lr, knee=19.5 * lr, ankle=12.5 * lr, thigh1=19.5 * lr, shin1=12.5 * lr, shoulder=19.5 * ar, elbow=14.5 * ar, wrist=10.5 * ar,
                      upper1=14.5 * ar, fore1=10.5 * ar, neck0=14 * nk, neck1=13 * nk)
        mul = lambda v, m: tuple(a * b for a, b in zip(v, m))
        self.e = dict(pelvis=mul((60, 46, 41), f["pelvis"]), waist=mul((52, 44, 36), f["waist"]), chest=mul((66, 72, 43), f["chest"]), head=tuple(x * H for x in (36, 43, 40)),
                      hand=tuple(x * Hn for x in (8.5, 22, 13)), foot=tuple(x * F for x in (13, 11.5, 35)))
        self.foot_c, self.heel, self.ball = (-13.5 * F, 16.0 * F), 14.0 * F, 46.0 * F
        self.leg = self.thigh + self.shin
        self.s = self.leg / 276.0                      # motion scale: strides, bob and jumps follow leg length
        self.w = self.hip_w / 32.0
        self.stance_x = self.hip_w * 1.06
        self.height = self.hip_h + self.spine1 + self.spine2 + self.neck_y + self.neck_len + self.head_c + self.e["head"][1]
        self.hold = dict(HOLDS.get(preset, {}))
        self.clipset = CLIPSETS.get(preset, "standard")
        self.extras = _extras(preset, self)
        self.asymmetric = any(e.get("asym") for e in self.extras)
        self.views = {"head": 8, "chest": 8, "pelvis": 8, "foot_L": 8, "foot_R": 8}
        self.view_radii = {}
        self.plates = set()
        hx, hy, hz = self.e["head"]
        cx, cy, cz = self.e["chest"]
        px_, py_, pz_ = self.e["pelvis"]
        fx, fy, fz = self.e["foot"]
        # features painted into the view images so the white model itself shows which way each part faces
        self.markers = {"head": [((0, -hy * 0.12, hz * 0.84), (hx * 0.61, hy * 0.63, hz * 0.2), "plate")],
                        "chest": [((0, cy * 0.12, cz * 0.88), (cx * 0.36, cy * 0.46, cz * 0.16), "plate")],
                        "pelvis": [((0, py_ * 0.30, pz_ * 0.93), (px_ * 0.16, py_ * 0.17, pz_ * 0.1), "dark")],
                        "foot_L": [((0, fy * 0.1, fz * 0.56), (fx * 1.03, fy * 1.03, fz * 0.46), "plate")],
                        "foot_R": [((0, fy * 0.1, fz * 0.56), (fx * 1.03, fy * 1.03, fz * 0.46), "plate")]}
        for e in self.extras:                          # an add-on with a face and a back (a shield) gets view images too
            if e.get("views"):
                self.views[e["name"]] = e["views"]
                self.view_radii[e["name"]] = tuple(e["radii"])
                if e.get("plate"):
                    self.plates.add(e["name"])
                self.markers[e["name"]] = e.get("marker", [])
        self.tones = {e["name"]: e["tone"] for e in self.extras if e.get("tone")}
        for e in self.extras:
            if e["kind"] == "rchain" and e.get("tone"):
                for i in range(1, e["n"] + 1):
                    self.tones[f"{e['name']}_{i}"] = e["tone"]
        # A face made of parts (eyes, brows, mouth ...) that sit on the head and turn with it in 3D.
        self.face = _face(preset, self)
        self.states, self.choosers, self.alpha_slots = {}, {}, {}
        if self.face:
            self.views.pop("head", None)                 # the parts carry the facing; the head itself needs no view images
            for f in self.face:
                self.tones[f["name"]] = f.get("tone", "base")
                if f.get("states"):
                    self.states[f["name"]] = list(f["states"])
                    self.choosers[f["name"]] = f["chooser"]
                if f.get("alpha"):
                    self.alpha_slots[f["name"]] = f["alpha"]

    def pose(self, heading: float = 90.0) -> "Pose":
        """Relaxed standing pose for THIS body (feet under the hips at its own ankle height)."""
        p = Pose(heading=heading)
        for s, sg in (("L", 1.0), ("R", -1.0)):
            p.foot[s].update(x=sg * self.stance_x, y=self.ankle_h)
        return p


def _extras(preset: str, B: Body) -> List[dict]:
    hx, hy, hz = B.e["head"]
    cx, cy, cz = B.e["chest"]
    px_, py_, pz_ = B.e["pelvis"]
    if preset == "hero":
        return [dict(kind="chain", name="scarf", parent="chest", anchor=(0, B.neck_y - 4, -cz * 0.55), n=3, len=36, radii=[12, 11, 9, 6], rest=(0.0, -0.93, -0.37), stiff=0.035, damp=0.04)]
    if preset == "heroine":
        return [dict(kind="chain", name="ponytail", parent="head", anchor=(0, hy * 0.35, -hz * 0.9), n=3, len=42, radii=[15, 14, 11, 7], rest=(0, -0.96, -0.28), stiff=0.045, damp=0.035),
                dict(kind="chain", name="skirt", parent="pelvis", anchor=(0, py_ * 0.45, 0), n=1, len=112, radii=[px_ * 0.82, px_ * 1.38], rest=(0, -1, 0), stiff=0.22, damp=0.12, follow_legs=0.5, joints=False, encloses=("pelvis", "hip_", "thigh_"))]
    if preset == "chibi":
        return [dict(kind="chain", name=f"pigtail_{s}", parent="head", anchor=(sg * hx * 0.92, hy * 0.2, -hz * 0.15), n=2, len=46, radii=[21, 19, 11], rest=(sg * 0.38, -0.92, -0.05), stiff=0.06, damp=0.04)
                for s, sg in (("L", 1), ("R", -1))]
    if preset == "brute":
        return [dict(kind="chain", name="cape", parent="chest", anchor=(0, B.shoulder_y * 0.98, -cz * 0.9), n=2, len=118, shape="panel", panel=[(cx * 0.98, 9), (cx * 1.1, 8)],
                     radii=[0, 0, 0], rest=(0, -0.97, -0.24), stiff=0.035, damp=0.05),
                dict(kind="tube", name="club", parent="hand_R", a=(0, 6, -24), b=(0, 30, 128), ra=9, rb=21, cap=23, asym=True)]
    if preset == "vtuber":
        out = [dict(kind="ell", name="hair_cap", parent="head", offset=(0, hy * 0.10, -hz * 0.16), radii=(hx * 1.1, hy * 1.06, hz * 1.02), rot=(0, 0, 0), tone="hair"),
               # rchain = a chain simulated by the RUNTIME (Spine physics), for things that must react to live input
               dict(kind="rchain", name="hair_back", parent="head", anchor=(0, -hy * 0.15, -hz * 0.8), n=3, len=48, radii=[30, 27, 20, 10], bias=-hz * 0.6, tone="hair",
                    inertia=(0.35, 0.7), strength=(110, 70), damping=(0.85, 0.9))]
        out += [dict(kind="ell", name=f"ear_{s}", parent="head", offset=(sg * hx * 0.97, -hy * 0.06, -hz * 0.06), radii=(5, 9.5, 6), rot=(0, 0, 0)) for s, sg in (("L", 1), ("R", -1))]
        out += [dict(kind="rchain", name=f"lock_{s}", parent="head", anchor=(sg * hx * 0.9, -hy * 0.28, hz * 0.22), n=3, len=36, radii=[9.5, 9, 7.5, 4], bias=hz * 0.35, tone="hair",
                     inertia=(0.4, 0.75), strength=(130, 85), damping=(0.83, 0.88)) for s, sg in (("L", 1), ("R", -1))]
        out += [dict(kind="chain", name="skirt", parent="pelvis", anchor=(0, py_ * 0.45, 0), n=1, len=112, radii=[px_ * 0.82, px_ * 1.38], rest=(0, -1, 0), stiff=0.22, damp=0.12, follow_legs=0.5,
                     joints=False, encloses=("pelvis", "hip_", "thigh_"))]
        return out
    if preset == "knight":
        out = [dict(kind="ell", name=f"pauldron_{s}", parent="chest", offset=(sg * B.shoulder_w * 1.02, B.shoulder_y + 7, 0), radii=(29, 19, 30), rot=(0, 0, -sg * 14)) for s, sg in (("L", 1), ("R", -1))]
        out += [dict(kind="chain", name="plume", parent="head", anchor=(0, hy * 0.92, -hz * 0.15), n=2, len=30, radii=[10, 9, 5], rest=(0, 0.45, -0.89), stiff=0.25, damp=0.08, grav=0.5),
                # the shield's own z axis is its face; rot turns that onto the forearm's outer side
                dict(kind="ell", name="shield", parent="hand_L", offset=(B.r["fore1"] + 9, B.hand_c + B.forearm * 0.45, 0), radii=(54, 64, 7), rot=(90, 0, 0), views=8, plate=True, asym=True,
                     marker=[((0, 0, 5), (18, 18, 8), "plate")]),
                # a blade is flat: a thin ellipsoid, broad face to the side, so it reads as a blade side-on and as a line edge-on
                dict(kind="ell", name="sword", parent="hand_R", offset=(0, -3, 84), radii=(2.5, 9, 82), rot=(0, 0, 0), asym=True),
                dict(kind="ell", name="sword_guard", parent="hand_R", offset=(0, 0, 10), radii=(15, 4.5, 4.5), rot=(0, 0, 0))]
        return out
    if preset == "mage":
        out = [dict(kind="chain", name="robe", parent="pelvis", anchor=(0, py_ * 0.35, 0), n=1, len=B.hip_h - B.ankle_h * 0.7, radii=[px_ * 0.92, px_ * 1.55], rest=(0, -1, 0), stiff=0.25, damp=0.12,
                    follow_legs=0.55, joints=False, encloses=("pelvis", "hip_", "thigh_", "knee_", "shin_"))]
        out += [dict(kind="tube", name=f"sleeve_{s}", parent=f"hand_{s}", a=(0, B.hand_c + B.forearm * 0.96, 0), b=(0, B.hand_c * 0.5, 0), ra=B.r["elbow"] * 1.15, rb=27, encloses=(f"forearm_{s}", f"wrist_{s}")) for s in SIDES]
        out += [dict(kind="ell", name="hat_brim", parent="head", offset=(0, hy * 0.6, 0), radii=(hx * 1.55, 5, hz * 1.5), rot=(0, 8, 0)),
                dict(kind="chain", name="hat", parent="head", anchor=(0, hy * 0.62, 0), n=2, len=40, radii=[hx * 0.85, hx * 0.42, 4], rest=(0, 1, -0.16), stiff=0.55, damp=0.15, grav=0.12),
                dict(kind="tube", name="staff", parent="hand_R", a=(0, 0, -B.height * 0.58), b=(0, 0, B.height * 0.42), ra=5, rb=5, cap=15, asym=True)]
        return out
    if preset == "mascot":
        out = [dict(kind="ell", name=f"ear_{s}", parent="head", offset=(sg * hx * 0.62, hy * 0.86, -hz * 0.05), radii=(17, 25, 8), rot=(0, 0, -sg * 24)) for s, sg in (("L", 1), ("R", -1))]
        out += [dict(kind="ell", name="snout", parent="head", offset=(0, -hy * 0.16, hz * 0.94), radii=(22, 16, 14), rot=(0, 0, 0)),
                dict(kind="chain", name="tail", parent="pelvis", anchor=(0, py_ * 0.1, -pz_ * 0.96), n=2, len=17, radii=[8.5, 7.5, 5.5], rest=(0, 0.55, -0.83), stiff=0.4, damp=0.1),
                dict(kind="pendulum", name="bag", parent="chest", anchor=(B.shoulder_w * 0.92, B.shoulder_y * 0.9, 4), len=B.shoulder_y + B.spine2 * 0.6, strap_r=3.5, radii=(21, 17, 10),
                     rest=(0.42, -0.9, 0.12), stiff=0.03, damp=0.03, asym=True)]
        return out
    return []


def _eye_state(face):
    return "open" if face["open"] >= 0.62 else ("half" if face["open"] >= 0.28 else "closed")


def _iris_state(face):
    return "on" if face["open"] >= 0.28 else None


def _mouth_state(face):
    m = face["mouth"]
    if m < 0.12:
        return "smile" if face["smile"] >= 0.5 else "closed"
    return "open1" if m < 0.42 else ("open2" if m < 0.72 else "open3")


def _face(preset: str, B: "Body") -> Optional[List[dict]]:
    """Face parts as patches on the head ellipsoid: (yaw, pitch) on the surface, half-size (w, h).  They are projected like
    every other part, so they foreshorten as the head turns and drop behind the head on its far side."""
    if preset != "vtuber":
        return None
    hx, hy, hz = B.e["head"]
    out = []
    for s, sg in (("L", 1.0), ("R", -1.0)):
        out += [dict(name=f"eye_{s}", yaw=sg * 19, pitch=2, size=(hx * 0.24, hy * 0.165), lift=1.5, tone="eye", states=["open", "half", "closed"], chooser=_eye_state),
                dict(name=f"iris_{s}", yaw=sg * 19, pitch=2, size=(hx * 0.115, hx * 0.115), lift=2.6, tone="iris", gaze=True, states=["on"], chooser=_iris_state),
                dict(name=f"brow_{s}", yaw=sg * 19, pitch=22, size=(hx * 0.2, 2.4), lift=2.0, tone="mouth", brow=True, side=sg),
                dict(name=f"cheek_{s}", yaw=sg * 31, pitch=-13, size=(hx * 0.17, hy * 0.075), lift=1.2, tone="blush", alpha="cheek"),
                dict(name=f"sidebang_{s}", yaw=sg * 50, pitch=24, size=(hx * 0.3, hy * 0.4), lift=2.5, tone="hair")]
    out += [dict(name="nose", yaw=0, pitch=-13, size=(3.4, 4.4), lift=3.0, tone="plate", thick=3.5),
            dict(name="mouth", yaw=0, pitch=-35, size=(hx * 0.21, hy * 0.1), lift=1.5, tone="mouth", states=["closed", "smile", "open1", "open2", "open3"], chooser=_mouth_state),
            dict(name="bangs", yaw=0, pitch=41, size=(hx * 0.86, hy * 0.27), lift=3.0, tone="hair")]
    return out


class Pose:
    """All the numbers that define a body pose.  Use Body.pose() to get one that fits a body."""

    def __init__(self, **kw):
        self.heading = 90.0
        self.root = (0.0, 0.0)                         # ground offset (x, z) in world; clips are authored in place
        self.px = self.py = self.pz = 0.0              # pelvis offset in the heading frame (left, up from standing, forward)
        self.pyaw = self.ppitch = self.proll = 0.0
        self.syaw = self.spitch = self.sroll = 0.0     # chest relative to pelvis (spread over two spine joints)
        self.hyaw = self.hpitch = self.hroll = 0.0     # head relative to chest
        self.arm = {s: dict(flex=0.0, abd=8.0, twist=0.0, elbow=10.0) for s in SIDES}
        self.foot = {"L": dict(x=34.0, y=26.0, z=0.0, pitch=0.0, yaw=7.0, world=False), "R": dict(x=-34.0, y=26.0, z=0.0, pitch=0.0, yaw=-7.0, world=False)}
        # face: gaze (-1..1), eye opening (1 open .. 0 closed), brows (-1 angry .. 1 raised), mouth opening, smile, blush
        self.face = dict(gx=0.0, gy=0.0, open=1.0, brow=0.0, mouth=0.0, smile=0.0, cheek=0.0)
        for k, v in kw.items():
            setattr(self, k, v)

    def copy(self) -> "Pose":
        return copy.deepcopy(self)


def mirror(p: Pose) -> Pose:
    """The same pose seen in a mirror (left <-> right).  The body's own left/right ANATOMY is not swapped: a bag on
    the left shoulder stays on the left shoulder; only what the limbs are doing is exchanged."""
    q = p.copy()
    q.heading, q.px, q.pyaw, q.proll, q.syaw, q.sroll, q.hyaw, q.hroll = -p.heading, -p.px, -p.pyaw, -p.proll, -p.syaw, -p.sroll, -p.hyaw, -p.hroll
    q.root = (-p.root[0], p.root[1])
    for a, b in (("L", "R"), ("R", "L")):
        q.arm[a] = dict(p.arm[b], twist=-p.arm[b]["twist"])
        f = dict(p.foot[b])
        f["x"], f["yaw"] = -f["x"], -f["yaw"]
        if f.get("pole") is not None:
            f["pole"] = np.asarray(f["pole"], dtype=float) * np.array([-1.0, 1.0, 1.0])
        q.foot[a] = f
    q.face = dict(p.face, gx=-p.face["gx"])
    return q


# ------------------------------------------------------------------------------------------- solving
def pelvis_frame(p: Pose, B: Body):
    H = _ry(RAD(p.heading))
    P = np.array([p.root[0], 0.0, p.root[1]]) + H @ np.array([p.px, B.hip_h + p.py, p.pz])
    return P, H @ _ry(RAD(p.pyaw)) @ _rx(RAD(p.ppitch)) @ _rz(RAD(p.proll))


def reach_guard(p: Pose, B: Body) -> float:
    """If a foot target is beyond the leg, lower the pelvis until it is not (a floating foot is a sliding foot).
    Returns what is still out of reach afterwards (px) -- non-zero only when the target is too far sideways."""
    lim = B.leg - 0.6
    over = 0.0
    for _ in range(5):
        P, Rp = pelvis_frame(p, B)
        H = _ry(RAD(p.heading))
        g = np.array([p.root[0], 0.0, p.root[1]])
        over = 0.0
        for s, sg in (("L", 1.0), ("R", -1.0)):
            f = p.foot[s]
            ankle = np.array([f["x"], f["y"], f["z"]]) if f.get("world") else g + H @ np.array([f["x"], f["y"], f["z"]])
            hip = P + Rp @ np.array([sg * B.hip_w, -B.hip_drop, 0])
            over = max(over, float(np.linalg.norm(ankle - hip)) - lim)
        if over <= 0:
            return 0.0
        p.py -= over * 1.25 + 0.5
    for _ in range(4):                                         # still too far: it is sideways, so bring the body over the foot
        P, Rp = pelvis_frame(p, B)
        H = _ry(RAD(p.heading))
        g = np.array([p.root[0], 0.0, p.root[1]])
        worst, vec, is_world = 0.0, None, True
        for s, sg in (("L", 1.0), ("R", -1.0)):
            f = p.foot[s]
            ankle = np.array([f["x"], f["y"], f["z"]]) if f.get("world") else g + H @ np.array([f["x"], f["y"], f["z"]])
            d = ankle - (P + Rp @ np.array([sg * B.hip_w, -B.hip_drop, 0]))
            o_ = float(np.linalg.norm(d)) - lim
            if o_ > worst:
                worst, vec, is_world = o_, np.array([d[0], 0.0, d[2]]), bool(f.get("world"))
        if vec is None or float(np.linalg.norm(vec)) < 1e-6:
            return max(0.0, worst)
        step = _unit(vec) * (worst * 1.3 + 0.5)
        if is_world:
            p.root = (p.root[0] + float(step[0]), p.root[1] + float(step[2]))
        else:                                                  # the foot is placed relative to the body: move the pelvis, not the ground point
            loc = H.T @ step
            p.px, p.pz = p.px + float(loc[0]), p.pz + float(loc[2])
        over = worst
    return max(0.0, over)


class _Out:
    def __init__(self, B: Body):
        self.B, self.parts = B, {}

    def proj(self, v):
        c = self.B.cam @ v
        return float(c[0]), float(c[1]), float(c[2])

    def ball(self, name, c, r):
        x, y, d = self.proj(c)
        self.parts[name] = dict(kind="ball", x=x, y=y, rot=0.0, a=r, b=r, depth=d + 0.6 * r)

    def tube(self, name, a, b, ra, rb):
        ax, ay, ad = self.proj(a)
        bx, by, bd = self.proj(b)
        self.parts[name] = dict(kind="tube", x=ax, y=ay, rot=math.degrees(math.atan2(by - ay, bx - ax)), a=math.hypot(bx - ax, by - ay), b=1.0, depth=(ad + bd) / 2, ra=ra, rb=rb,
                                len3=float(np.linalg.norm(np.asarray(b, dtype=float) - np.asarray(a, dtype=float))))

    def ell(self, name, c, R, radii, bias=0.0):
        Rt = self.B.cam @ R
        M = Rt @ np.diag(np.square(radii)) @ Rt.T
        w, v = np.linalg.eigh(M[:2, :2])
        x, y, d = self.proj(c)
        self.parts[name] = dict(kind="ell", x=x, y=y, rot=math.degrees(math.atan2(v[1, 1], v[0, 1])), a=math.sqrt(max(w[1], 1e-6)), b=math.sqrt(max(w[0], 1e-6)), depth=d + bias,
                                R=np.array(R, dtype=float), radii=tuple(radii))


def solve(p: Pose, B: Body):
    """Pose -> (parts, frames, over).  parts: {name: {kind, x, y, rot, a, b, depth, ...}} in screen units (x right, y up,
    origin on the ground).  frames: {name: (origin, rotation)} for attaching extras.  over: px a foot target was out of reach."""
    o = _Out(B)
    H = _ry(RAD(p.heading))
    ground = np.array([p.root[0], 0.0, p.root[1]])
    P, Rp = pelvis_frame(p, B)
    Rs = _ry(RAD(p.syaw / 2)) @ _rx(RAD(p.spitch / 2)) @ _rz(RAD(p.sroll / 2))
    S1 = P + Rp @ np.array([0, B.spine1, 0])
    Rw = Rp @ Rs
    S2 = S1 + Rw @ np.array([0, B.spine2, 0])
    Rc = Rw @ Rs
    neck0 = S2 + Rc @ np.array([0, B.neck_y, 0])
    Rh = Rc @ _ry(RAD(p.hyaw)) @ _rx(RAD(p.hpitch)) @ _rz(RAD(p.hroll))
    neck1 = neck0 + Rc @ np.array([0, B.neck_len, B.head_z * 0.6])
    head_c = neck1 + Rh @ np.array([0, B.head_c, B.head_z])
    frames = {"pelvis": (P, Rp), "waist": (S1, Rw), "chest": (S2, Rc), "head": (head_c, Rh)}
    o.ell("pelvis", P + Rp @ np.array([0, 2 * B.f["torso"], 0]), Rp, B.e["pelvis"])
    o.ell("waist", S1 + Rw @ np.array([0, B.waist_c, 1]), Rw, B.e["waist"])
    o.ell("chest", S2 + Rc @ np.array([0, B.chest_c, 3 * B.f["torso"]]), Rc, B.e["chest"])
    o.tube("neck", neck0 - Rc @ np.array([0, 6 * B.f["torso"], 0]), neck1 + Rh @ np.array([0, 8 * B.f["head"], 0]), B.r["neck0"], B.r["neck1"])
    o.ell("head", head_c, Rh, B.e["head"])
    if B.face:
        hx, hy, hz = B.e["head"]
        for f in B.face:
            yaw, pitch = f["yaw"], f["pitch"]
            if f.get("gaze"):
                yaw, pitch = yaw + p.face["gx"] * 6.5, pitch + p.face["gy"] * 4.5
            if f.get("brow"):
                pitch += p.face["brow"] * 4.0
            d = np.array([math.sin(RAD(yaw)) * math.cos(RAD(pitch)), math.sin(RAD(pitch)), math.cos(RAD(yaw)) * math.cos(RAD(pitch))])
            nrm = _unit(np.array([d[0] / hx, d[1] / hy, d[2] / hz]))
            right = _unit(np.cross(np.array([0.0, 1.0, 0.0]), nrm))
            Rloc = np.column_stack([right, np.cross(nrm, right), nrm])
            if f.get("brow") and p.face["brow"] < 0:
                Rloc = Rloc @ _rz(RAD(f["side"] * 13.0 * -p.face["brow"]))           # frown: inner ends down
            w, h = f["size"]
            o.ell(f["name"], head_c + Rh @ (np.array([hx * d[0], hy * d[1], hz * d[2]]) + nrm * f.get("lift", 1.5)), Rh @ Rloc, (w, h, f.get("thick", 1.2)), bias=f.get("lift", 1.5))
    over = 0.0
    thighs = []
    for s, sign in (("L", 1.0), ("R", -1.0)):
        a = p.arm[s]
        sh = S2 + Rc @ np.array([sign * B.shoulder_w, B.shoulder_y, 0])
        Ra = Rc @ _rz(RAD(sign * a["abd"])) @ _rx(RAD(-a["flex"])) @ _ry(RAD(a["twist"]))
        el = sh + Ra @ np.array([0, -B.upper_arm, 0])
        Rf = Ra @ _rx(RAD(-a["elbow"]))
        wr = el + Rf @ np.array([0, -B.forearm, 0])
        hc = wr + Rf @ np.array([0, -B.hand_c, 0])
        o.ball(f"shoulder_{s}", sh, B.r["shoulder"])
        o.tube(f"upperarm_{s}", sh, el, B.r["shoulder"] * 0.93, B.r["upper1"])
        o.ball(f"elbow_{s}", el, B.r["elbow"])
        o.tube(f"forearm_{s}", el, wr, B.r["elbow"], B.r["fore1"])
        o.ball(f"wrist_{s}", wr, B.r["wrist"])
        o.ell(f"hand_{s}", hc, Rf, B.e["hand"])
        frames[f"hand_{s}"] = (hc, Rf)

        f = p.foot[s]
        hip = P + Rp @ np.array([sign * B.hip_w, -B.hip_drop, 0])
        if f.get("world"):
            ankle, fyaw = np.array([f["x"], f["y"], f["z"]], dtype=float), f["yaw"]
        else:
            ankle, fyaw = ground + H @ np.array([f["x"], f["y"], f["z"]]), p.heading + f["yaw"]
        Rft = _ry(RAD(fyaw)) @ _rx(RAD(-f["pitch"]))
        d = ankle - hip
        dist = float(np.linalg.norm(d))
        reach = B.leg - 0.6
        axis = d / max(dist, 1e-6)
        dc = min(dist, reach)
        if dist > reach:
            over = max(over, dist - reach)
            ankle = hip + axis * dc                         # out of reach: the leg straightens toward the target
        along = (B.thigh ** 2 - B.shin ** 2 + dc ** 2) / (2 * dc)
        h = math.sqrt(max(B.thigh ** 2 - along ** 2, 0.0))
        if f.get("pole") is not None:
            hint = np.asarray(f["pole"], dtype=float)
        else:
            hint = Rp @ np.array([0, 0, 1.0]) + Rft @ np.array([0, 0, 1.0]) + np.array([0, 0.25, 0])
        perp = _unit(hint - axis * float(hint @ axis))
        knee = hip + axis * along + perp * h
        thighs.append(_unit(knee - hip))
        o.ball(f"hip_{s}", hip, B.r["hip"])
        o.tube(f"thigh_{s}", hip, knee, B.r["hip"] * 0.93, B.r["thigh1"])
        o.ball(f"knee_{s}", knee, B.r["knee"])
        o.tube(f"shin_{s}", knee, ankle, B.r["knee"], B.r["shin1"])
        o.ball(f"ankle_{s}", ankle, B.r["ankle"])
        o.ell(f"foot_{s}", ankle + Rft @ np.array([0, B.foot_c[0], B.foot_c[1]]), Rft, B.e["foot"])
    frames["thighs"] = (thighs[0], thighs[1])
    gx, gy, _ = o.proj(np.array([P[0], 0.0, P[2]]))
    lift = max(0.0, min(o.parts["ankle_L"]["y"], o.parts["ankle_R"]["y"]) - (B.cam @ np.array([0, B.ankle_h, 0]))[1] - 2)
    sc = max(0.45, 1.0 - lift / (320.0 * max(B.s, 0.4)))
    o.parts["shadow"] = dict(kind="shadow", x=gx, y=gy, rot=0.0, a=sc, b=sc, depth=-1e9)
    return o.parts, frames, over


# --------------------------------------------------------------------------------- extras (add-ons)
def _extra_state(e: dict, frames) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(anchor, rest direction, lateral axis) of a chain/pendulum in the world, for one frame."""
    o_, R = frames[e["parent"]]
    d = R @ _unit(np.array(e["rest"], dtype=float))
    fl = e.get("follow_legs", 0.0)
    if fl:
        tl, tr = frames["thighs"]
        d = _unit(d * (1 - fl) + _unit(tl + tr) * fl)          # a skirt leans the way the thighs go
    return o_ + R @ np.array(e["anchor"], dtype=float), d, R[:, 0]


def _chain_step(e, pts, prev, a, d, dt):
    n, ln = e["n"], e["len"]
    new = pts + (pts - prev) * (1.0 - e["damp"]) + np.array([0.0, -GRAVITY * e.get("grav", 1.0), 0.0]) * dt * dt
    new[0] = a
    for _ in range(3):
        for i in range(1, n + 1):
            new[i] += (new[i - 1] + d * ln - new[i]) * e["stiff"]
            new[i] = new[i - 1] + _unit(new[i] - new[i - 1]) * ln
    return new, pts


def _emit_extra(o: _Out, e: dict, frames, pts=None):
    kind = e["kind"]
    if kind == "ell":
        o_, R = frames[e["parent"]]
        yw, pt, rl = e.get("rot", (0, 0, 0))
        o.ell(e["name"], o_ + R @ np.array(e["offset"], dtype=float), R @ _ry(RAD(yw)) @ _rx(RAD(pt)) @ _rz(RAD(rl)), e["radii"], bias=e.get("cover", 0.0))
    elif kind == "tube":
        o_, R = frames[e["parent"]]
        a, b = o_ + R @ np.array(e["a"], dtype=float), o_ + R @ np.array(e["b"], dtype=float)
        o.tube(e["name"], a, b, e["ra"], e["rb"])
        o.parts[e["name"]]["depth"] += e.get("cover", 0.0)        # a sleeve sorts in front of the forearm inside it
        if e.get("cap"):
            o.ball(e["name"] + "_cap", b, e["cap"])
    elif kind == "rchain":
        o_, R = frames[e["parent"]]
        x, y, d = o.proj(o_ + R @ np.array(e["anchor"], dtype=float))
        dep = d + e.get("bias", 0.0)
        o.parts[e["name"]] = dict(kind="anchor", x=x, y=y, rot=0.0, a=1.0, b=1.0, depth=dep)             # a bone only: where the chain hangs from
        for i in range(1, e["n"] + 1):                                                                    # its links are ordinary Spine bones with physics
            o.parts[f"{e['name']}_{i}"] = dict(kind="rseg", x=x, y=y - e["len"] * (i - 1), rot=-90.0, a=e["len"], b=1.0, depth=dep + 0.01 * i, ra=e["radii"][i - 1], rb=e["radii"][i],
                                               len3=float(e["len"]), chain=e["name"], index=i)
    else:
        _, _, lat = _extra_state(e, frames)
        if kind == "pendulum":
            a, b = pts[0], pts[1]
            dirv = _unit(b - a)
            o.tube(e["name"] + "_strap", a, b, e["strap_r"], e["strap_r"])
            x = _unit(lat - dirv * float(lat @ dirv))
            o.ell(e["name"], b + dirv * e["radii"][1] * 0.55, np.column_stack([x, -dirv, np.cross(x, -dirv)]), e["radii"])
        elif e.get("shape") == "panel":
            for i in range(1, e["n"] + 1):
                y = _unit(pts[i - 1] - pts[i])
                x = _unit(lat - y * float(lat @ y))
                hw, th = e["panel"][i - 1]
                o.ell(f"{e['name']}_{i}", (pts[i - 1] + pts[i]) / 2, np.column_stack([x, y, np.cross(x, y)]), (hw, e["len"] * 0.6, th))
        else:
            for i in range(1, e["n"] + 1):
                o.tube(f"{e['name']}_{i}", pts[i - 1], pts[i], e["radii"][i - 1], e["radii"][i])
                o.parts[f"{e['name']}_{i}"]["depth"] += e.get("cover", 0.0)       # a skirt or robe sorts in front of the legs inside it
                if e.get("joints", True):
                    o.ball(f"{e['name']}_j{i}", pts[i], e["radii"][i])


def sim_extras(B: Body, frames_seq: Sequence[dict], dt: float, loop: bool) -> List[Dict[str, dict]]:
    """Simulate every extra over a sequence of frames (springs toward the rest direction + gravity + length constraints)
    and return the projected parts per frame.  Loops are run three times and the last pass is kept."""
    outs = [_Out(B) for _ in frames_seq]
    sub = 4
    for e in B.extras:
        if e["kind"] in ("ell", "tube", "rchain"):
            for o, fr in zip(outs, frames_seq):
                _emit_extra(o, e, fr)
            continue
        if e["kind"] == "pendulum":
            e = dict(e, n=1)
        a0, d0, _ = _extra_state(e, frames_seq[0])
        pts = np.array([a0 + d0 * e["len"] * i for i in range(e["n"] + 1)])
        prev = pts.copy()
        for _ in range(60):                                   # settle under gravity in the first pose
            pts, prev = _chain_step(e, pts, prev, a0, d0, dt / sub)
        n = len(frames_seq)
        passes = 3 if loop and n > 2 else 1
        for ps in range(passes):
            last = ps == passes - 1
            for j in range(n):
                if j > 0:
                    a_prev, d_prev, _ = _extra_state(e, frames_seq[j - 1])
                    a_cur, d_cur, _ = _extra_state(e, frames_seq[j])
                    for k in range(1, sub + 1):
                        u = k / sub
                        pts, prev = _chain_step(e, pts, prev, a_prev + (a_cur - a_prev) * u, _unit(d_prev + (d_cur - d_prev) * u), dt / sub)
                if last:
                    _emit_extra(outs[j], e, frames_seq[j], pts.copy())
    res = [o.parts for o in outs]
    if loop and len(res) > 1:
        res[-1] = res[0]
    return res


def rest_pose(B: Body) -> Pose:
    p = B.pose(heading=0.0)
    for s in SIDES:
        if s in B.hold:
            f_, a_, t_, e_, _ = B.hold[s]
            p.arm[s].update(flex=f_, abd=a_, twist=t_, elbow=e_)        # held things are drawn the way they are carried
        else:
            p.arm[s].update(abd=15.0, elbow=5.0)
        p.foot[s]["yaw"] = 0.0
    return p


def rest_view(q: dict, plate: bool = False) -> int:
    """Which of the eight views a view part shows in the rest pose."""
    return pick_view(part_yaw(q["R"]), None, view_sectors(plate))


def rest_solution(B: Body) -> Dict[str, dict]:
    parts, frames, _ = solve(rest_pose(B), B)
    parts.update(sim_extras(B, [frames], 1 / 30, False)[0])
    return parts


# ------------------------------------------------------------------------------------ ellipse maths
def _sroot(a, b, rot_deg, inv=False):
    c, s = math.cos(RAD(rot_deg)), math.sin(RAD(rot_deg))
    R = np.array([[c, -s], [s, c]])
    return R @ np.diag([1 / a, 1 / b] if inv else [a, b]) @ R.T


def view_ref(B: Body, part: str, view: int) -> dict:
    """The reference ellipse a view image is drawn for: the part upright, turned to view * 45 degrees."""
    R = _ry(RAD(45.0 * view))
    o = _Out(B)
    o.ell("x", np.zeros(3), R, B.view_radii.get(part) or B.e["foot" if part.startswith("foot") else part])
    q = o.parts["x"]
    return dict(a=q["a"], b=q["b"], rot=q["rot"], R=R, S_inv=_sroot(q["a"], q["b"], q["rot"], inv=True), S=_sroot(q["a"], q["b"], q["rot"]))


def _ell_map(q: dict, ref: dict, cam) -> np.ndarray:
    """2x2 map taking the reference image onto the part as it is now: the silhouette lands exactly on the projected
    ellipse (S_t U S_ref^-1), and U is chosen so the image content turns the way the part really turned."""
    St = _sroot(q["a"], q["b"], q["rot"])
    A = (cam @ q["R"] @ ref["R"].T @ cam.T)[:2, :2]
    M = np.linalg.inv(St) @ A @ ref["S"]
    ang = math.atan2(M[1, 0] - M[0, 1], M[0, 0] + M[1, 1])
    # A sliver (a shield or a blade seen edge-on) has no content worth turning, and the content-based angle becomes
    # ill-conditioned there: tiny tilts swing it by tens of degrees.  For slivers, line up the long axes instead.
    thin = min(q["b"] / q["a"], ref["b"] / ref["a"])
    if thin < 0.35:
        w = min(1.0, max(0.0, (thin - 0.15) / 0.2))
        w = w * w * (3 - 2 * w)
        axis = RAD(q["rot"] - ref["rot"])
        axis = ang + ((axis - ang + math.pi / 2) % math.pi) - math.pi / 2          # the long axis is only defined up to half a turn
        ang = axis + (ang - axis) * w
    U = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
    return St @ U @ ref["S_inv"]


def _near_angle(a: float, ref: float, period: float = 360.0) -> float:
    return a - period * round((a - ref) / period)


def _decompose(L: np.ndarray, prev_rot: float, min_scale: float):
    rot = _near_angle(math.degrees(math.atan2(L[1, 0], L[0, 0])), prev_rot)
    shy = _near_angle(math.degrees(math.atan2(L[1, 1], L[0, 1])) - rot - 90.0, 0.0)
    shy = max(-85.0, min(85.0, shy))          # a thin part seen edge-on shears toward 90 degrees; past it the image would turn inside out
    return rot, max(min_scale, math.hypot(L[0, 0], L[1, 0])) - 1.0, max(min_scale, math.hypot(L[0, 1], L[1, 1])) - 1.0, shy


def view_sectors(plate: bool = False) -> List[Tuple[float, float]]:
    """Yaw range (lo, hi) of each of the eight views.  Normally 45 degrees each.  A plate (a shield) seen edge-on is a
    sliver, and a sliver image stretched to cover a plate that has turned 25 degrees looks torn; so a plate uses its
    edge-on views only within 10 degrees of edge-on and lets the 3/4 views -- which only ever get squashed -- cover the rest."""
    sec = [(45.0 * v - 22.5, 45.0 * v + 22.5) for v in range(8)]
    if plate:
        sec[2], sec[1], sec[3] = (80.0, 100.0), (22.5, 80.0), (100.0, 157.5)
        sec[6], sec[5], sec[7] = (260.0, 280.0), (202.5, 260.0), (280.0, 337.5)
    return sec


def pick_view(yaw: float, cur: Optional[int], sectors, margin: float = 5.0) -> int:
    """Keep the current view while the yaw is inside its sector (plus a margin); otherwise the sector that contains it."""
    def inside(v, m):
        lo, hi = sectors[v]
        mid, half = (lo + hi) / 2, (hi - lo) / 2 + m
        return abs(_near_angle(yaw - mid, 0.0)) <= half
    if cur is not None and inside(cur, margin if (sectors[cur][1] - sectors[cur][0]) > 30 else 3.0):
        return cur
    for v in range(len(sectors)):
        if inside(v, 1e-9):
            return v
    return int(round(yaw / 45.0)) % 8


def part_yaw(R: np.ndarray) -> float:
    """Which way a part faces on screen (0 = at the camera, 90 = screen-right).

    Read from whichever of the part's two horizontal-ish axes is the more level: the facing axis when the part is upright
    or rolled about its facing (a shield lying sideways on the forearm), the lateral axis when it is pitched (a torso
    bent forward points its facing axis at the floor, where "which way" means nothing)."""
    fwd_h, side_h = math.hypot(R[0, 2], R[2, 2]), math.hypot(R[0, 0], R[2, 0])
    if fwd_h >= side_h:
        return math.degrees(math.atan2(R[0, 2], R[2, 2]))
    return math.degrees(math.atan2(-R[2, 0], R[0, 0]))


# ----------------------------------------------------------------------------------------- art + rig
def _ell_path(cx, cy, a, b, ang):
    c, s = math.cos(RAD(ang)), math.sin(RAD(ang))
    x1, y1, x2, y2 = cx + a * c, cy + a * s, cx - a * c, cy - a * s
    return f"M{x1:.2f},{y1:.2f}A{a:.2f},{b:.2f} {ang:.2f} 1 0 {x2:.2f},{y2:.2f}A{a:.2f},{b:.2f} {ang:.2f} 1 0 {x1:.2f},{y1:.2f}Z"


PALETTE = dict(light="#ffffff", base="#f1f3f7", shade="#bcc4d0", line="#7d8695", plate="#cfd6e0", dark="#8a93a2", shadow="#1a2230")


TONES = {"hair": ("#d3d9e3", "#b3bccb", "#8f99ab"), "eye": ("#ffffff", "#ffffff", "#e3e7ee"), "iris": ("#6c7c98", "#55647f", "#3d4960"), "mouth": ("#7e6670", "#7e6670", "#63505a"),
         "blush": ("#f4a9b4", "#f4a9b4", "#f4a9b4")}


def _ell_svg(art, cx, cy, a, b, rot, pal, tone="base"):
    ang = -rot
    c0, c1, c2 = {"base": (pal["light"], pal["base"], pal["shade"]), "plate": (pal["plate"], pal["plate"], "#aeb7c4"), "dark": (pal["dark"], pal["dark"], "#6f7786"), **TONES}[tone]
    g = art.radial(cx, cy, a, [(0, c0), (0.6, c1), (1, c2)], transform=f"rotate({ang:.3f} {cx:.2f} {cy:.2f}) translate(0 {cy * (1 - b / a):.3f}) scale(1 {b / a:.5f})")
    body = f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{a:.2f}" ry="{b:.2f}" transform="rotate({ang:.3f} {cx:.2f} {cy:.2f})" fill="{g}"/>'
    rim = f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{max(a - 0.6, 0.2):.2f}" ry="{max(b - 0.6, 0.2):.2f}" transform="rotate({ang:.3f} {cx:.2f} {cy:.2f})" fill="none" stroke="{pal["line"]}" stroke-width="1.2" opacity="{0.75 if tone == "base" else 0.45}"/>'
    return body + rim


def view_svg(art, B: Body, part: str, view: int, cx: float, cy: float, pal: dict) -> str:
    """One view image of a part: its silhouette at that angle plus whatever features are on the camera side."""
    from .svgart import group
    ref = view_ref(B, part, view)
    out = _ell_svg(art, cx, cy, ref["a"], ref["b"], ref["rot"], pal)
    marks = ""
    for c_loc, radii, tone in B.markers.get(part, []):
        o = _Out(B)
        o.ell("m", ref["R"] @ np.array(c_loc, dtype=float), ref["R"], radii)
        m = o.parts["m"]
        if m["depth"] > -1.0:                                  # on the camera side, or exactly side-on (shows as a sliver at the front edge)
            marks += _ell_svg(art, cx + m["x"], cy - m["y"], m["a"], m["b"], m["rot"], pal, tone)
    if marks:
        out += group(marks, clip_path=art.clip(_ell_path(cx, cy, ref["a"], ref["b"], -ref["rot"])))
    return out


def state_svg(art, B: Body, slot: str, suffix: str, cx: float, cy: float, q: dict, pal: dict) -> str:
    """One state image of a face part (eye open / half / closed, mouth shapes), drawn in the part's rest ellipse."""
    from .svgart import group
    a, b = q["a"], q["b"]
    lash = f'<path d="M{cx - a:.2f},{cy:.2f}Q{cx:.2f},{cy - b * 2.1:.2f} {cx + a:.2f},{cy:.2f}" fill="none" stroke="#4b5568" stroke-width="2.2" stroke-linecap="round"/>'
    if slot.startswith("eye_"):
        if suffix == "open":
            body = _ell_svg(art, cx, cy, a, b, 0, pal, "eye") + lash
        elif suffix == "half":
            body = _ell_svg(art, cx, cy + b * 0.3, a, b * 0.5, 0, pal, "eye") + f'<path d="M{cx - a:.2f},{cy + b * 0.3:.2f}Q{cx:.2f},{cy - b * 0.9:.2f} {cx + a:.2f},{cy + b * 0.3:.2f}" fill="none" stroke="#4b5568" stroke-width="2.2" stroke-linecap="round"/>'
        else:
            body = f'<path d="M{cx - a:.2f},{cy:.2f}Q{cx:.2f},{cy + b * 1.1:.2f} {cx + a:.2f},{cy:.2f}" fill="none" stroke="#4b5568" stroke-width="2.4" stroke-linecap="round"/>'
    elif slot == "mouth":
        if suffix == "closed":
            body = f'<path d="M{cx - a * 0.7:.2f},{cy:.2f}L{cx + a * 0.7:.2f},{cy:.2f}" fill="none" stroke="#7e6670" stroke-width="2.2" stroke-linecap="round"/>'
        elif suffix == "smile":
            body = f'<path d="M{cx - a:.2f},{cy - b * 0.45:.2f}Q{cx:.2f},{cy + b * 1.3:.2f} {cx + a:.2f},{cy - b * 0.45:.2f}" fill="none" stroke="#7e6670" stroke-width="2.4" stroke-linecap="round"/>'
        else:
            k_ = {"open1": (0.62, 0.38), "open2": (0.7, 0.68), "open3": (0.78, 1.0)}[suffix]
            body = _ell_svg(art, cx, cy, a * k_[0], b * k_[1], 0, pal, "mouth")
    else:
        body = _ell_svg(art, cx, cy, a, b, 0, pal, B.tones.get(slot, "base"))
        if slot.startswith("iris_"):
            body += f'<circle cx="{cx - a * 0.3:.2f}" cy="{cy - b * 0.32:.2f}" r="{a * 0.26:.2f}" fill="#ffffff" opacity="0.9"/>'
    return group(body, transform=f"rotate({-q['rot']:.3f} {cx:.2f} {cy:.2f})") if abs(q["rot"]) > 0.01 and abs(abs(q["rot"]) - 180) > 0.01 else body


def enclosures(B: Body, names) -> Dict[str, set]:
    """{covering part: parts that must stay under it} from the add-ons' `encloses`."""
    under: Dict[str, set] = {}
    for e in B.extras:
        if e.get("encloses"):
            covers = [f"{e['name']}_{i}" for i in range(1, e.get("n", 1) + 1)] if e["kind"] == "chain" else [e["name"]]
            inside = {p_ for p_ in names if any(p_ == pre or (pre.endswith("_") and p_.startswith(pre)) for pre in e["encloses"])}
            for c_ in covers:
                under[c_] = inside
    return under


def ordered(B: Body, r: Dict[str, dict]) -> List[str]:
    """Part names back to front for a solution: by camera depth, then with enclosed parts tucked under their cover."""
    order = sorted(r, key=lambda n: r[n]["depth"])
    for c_, inside in enclosures(B, order).items():
        for x_ in [p_ for p_ in list(order) if p_ in inside]:      # in draw order, not in set order: the build must be reproducible
            ic, ix = order.index(c_), order.index(x_)
            if ix > ic:
                order.pop(ix)
                order.insert(ic, x_)
    return order


def part_order(B: Body) -> List[str]:
    return ordered(B, rest_solution(B))


def att_names(B: Body, part: str) -> List[str]:
    if part in B.views:
        return [f"{part}_v{v}" for v in range(B.views[part])]
    return [f"{part}_{s_}" for s_ in B.states[part]] if part in B.states else [part]


def draw(art, B: Body, origin: Tuple[float, float], palette: Optional[dict] = None) -> List[str]:
    """Add every part image to an svgart.Art, back to front.  Each image is padded so a skin has room to be bigger than
    the white silhouette (hair past the skull, a sleeve wider than the arm)."""
    from .svgart import circle, ellipse, path, poly
    pal = dict(PALETTE)
    pal.update(palette or {})
    ox, oy = origin
    r = rest_solution(B)
    names = ordered(B, r)
    for n in names:
        q = r[n]
        cx, cy = ox + q["x"], oy - q["y"]
        if q["kind"] == "anchor":
            continue
        if q["kind"] == "shadow":
            rx_, ry_ = 120 * max(B.w, 0.7), 26 * max(B.w, 0.7)
            art.part(n, ellipse(cx, cy, rx_, ry_, fill=art.radial(cx, cy, rx_, [(0, pal["shadow"], 0.38), (0.6, pal["shadow"], 0.2), (1, pal["shadow"], 0)], transform=f"translate(0 {cy * (1 - ry_ / rx_):.2f}) scale(1 {ry_ / rx_:.4f})")))
        elif q["kind"] == "ball":
            rad = q["a"]
            art.part(n, circle(cx, cy, rad, fill=art.radial(cx, cy, rad, [(0, pal["light"]), (0.55, pal["base"]), (1, pal["shade"])])), circle(cx, cy, rad - 0.6, stroke=pal["line"], stroke_width=1.2, opacity=0.75), pad=max(4, round(rad * 0.3)))
        elif q["kind"] == "ell":
            if n in B.views:
                for v in range(B.views[n]):
                    ref = view_ref(B, n, v)
                    art.part(f"{n}_v{v}", view_svg(art, B, n, v, cx, cy, pal), hidden=v != rest_view(q, n in B.plates), pad=max(6, round(max(ref["a"], ref["b"]) * (0.5 if n == "head" else 0.3))))
            elif n in B.states:
                for i_, suf in enumerate(B.states[n]):
                    art.part(f"{n}_{suf}", state_svg(art, B, n, suf, cx, cy, q, pal), hidden=i_ != 0, pad=max(3, round(q["a"] * 0.35)))
            else:      # a part whose opacity is animated from zero (blush) is not in the setup picture
                art.part(n, _ell_svg(art, cx, cy, q["a"], q["b"], q["rot"], pal, B.tones.get(n, "base")), hidden=n in B.alpha_slots, pad=max(3 if B.face else 5, round(q["a"] * 0.3)))      # small face parts get a small margin; everything else keeps 5
        else:
            ra, rb = q["ra"], q["rb"]
            L, th = q["len3"], RAD(q["rot"])                  # drawn at its true length even if the rest pose foreshortens it
            ux, uy = math.cos(th), -math.sin(th)
            nx, ny = -uy, ux
            bx, by = cx + ux * L, cy + uy * L
            pts = [(cx + nx * ra, cy + ny * ra), (bx + nx * rb, by + ny * rb), (bx - nx * rb, by - ny * rb), (cx - nx * ra, cy - ny * ra)]
            rr = max(ra, rb)
            lt_, bs_, sh_ = TONES[B.tones[n]] if B.tones.get(n) in TONES else (pal["light"], pal["base"], pal["shade"])
            g = art.linear(cx + nx * rr, cy + ny * rr, cx - nx * rr, cy - ny * rr, [(0, sh_), (0.3, bs_), (0.5, lt_), (0.7, bs_), (1, sh_)])
            art.part(n, path(poly(pts), fill=g), path(poly(pts[:2], closed=False), stroke=pal["line"], sw=1.2, opacity=0.75), path(poly(pts[2:], closed=False), stroke=pal["line"], sw=1.2, opacity=0.75), pad=max(4, round(rr * 0.3)))
    return names


def build_rig(rig, B: Body, origin: Tuple[float, float]) -> Dict[str, dict]:
    """One bone + one slot per part, all children of `root`; view parts get eight attachments in their slot.
    Also records the skin specification (what every image is) for `spk skin` / `spk reskin`."""
    ox, oy = origin
    rig.set_origin(ox, oy)
    rig.bone("root", at=(ox, oy))
    rest = rest_solution(B)
    ref, spec = {}, []
    chain_bones = {}
    for e in B.extras:
        if e["kind"] == "rchain":                       # anchor bone (baked) + a real bone chain under it (runtime physics)
            q = rest[e["name"]]
            ax, ay = ox + q["x"], oy - q["y"]
            rig.bone(e["name"], "root", at=(ax, ay), rot=0, length=0)
            chain_bones[e["name"]] = rig.chain(e["name"] + "_b", e["name"], [(ax, ay + e["len"] * i) for i in range(e["n"] + 1)])
    for n in ordered(B, rest):
        q = rest[n]
        at = (ox + q["x"], oy - q["y"])
        if q["kind"] == "anchor":
            continue
        if q["kind"] == "rseg":
            rig.part(n, chain_bones[q["chain"]][q["index"] - 1])
            spec.append(dict(attachment=n, slot=n, kind="tube", zh="即時物理鏈條的一節（頭髮、飾帶）：直的、由上往下畫"))
            continue
        if q["kind"] == "tube":
            th = RAD(q["rot"])
            rig.bone(n, "root", at=at, tip=(at[0] + math.cos(th) * q["len3"], at[1] - math.sin(th) * q["len3"]))
            rig.part(n, n)
            spec.append(dict(attachment=n, slot=n, kind="tube", zh="管狀肢段：沿骨頭方向畫，兩端會被關節球蓋住", note="one image for all angles; keep it roughly cylindrical"))
        elif q["kind"] == "ell" and n in B.views:
            rig.bone(n, "root", at=at, rot=0, length=q["a"])
            for v in range(B.views[n]):
                rig.part(f"{n}_v{v}", n, slot=n, active=v == rest_view(q, n in B.plates))
                spec.append(dict(attachment=f"{n}_v{v}", slot=n, kind="view", view=VIEW_CODES[v], yaw=45 * v, zh=f"{n}：{VIEW_ZH[v]}", mirror_of=(f"{n}_v{8 - v}" if 5 <= v <= 7 and not n.startswith("foot") else None)))
            ref[n] = [view_ref(B, n, v) for v in range(B.views[n])]
        elif q["kind"] == "ell":
            rig.bone(n, "root", at=at, rot=0, length=q["a"])
            if n in B.states:
                for i_, suf in enumerate(B.states[n]):
                    rig.part(f"{n}_{suf}", n, slot=n, active=i_ == 0)
                    spec.append(dict(attachment=f"{n}_{suf}", slot=n, kind="state", state=suf, zh=f"{n} 的狀態圖「{suf}」：同一個位置、同一個軸心"))
            else:
                rig.part(n, n, **({"color": "ffffff00"} if n in B.alpha_slots else {}))
                spec.append(dict(attachment=n, slot=n, kind="ell", zh="橢球零件：一張圖，會隨零件旋轉與壓扁"))
            ref[n] = [dict(a=q["a"], b=q["b"], rot=q["rot"], R=q["R"], S=_sroot(q["a"], q["b"], q["rot"]), S_inv=_sroot(q["a"], q["b"], q["rot"], inv=True))]
        else:
            rig.bone(n, "root", at=at, rot=0, length=0)
            rig.part(n, n)
            spec.append(dict(attachment=n, slot=n, kind=q["kind"], zh="關節球：各角度都是圓" if q["kind"] == "ball" else "地面陰影"))
    for e in B.extras:
        if e["kind"] == "rchain":
            rig.physics_chain(chain_bones[e["name"]], inertia=e["inertia"], strength=e["strength"], damping=e["damping"])
    rig._figure = dict(B=B, rest=rest, ref=ref)
    rig.skin_spec = dict(body=B.preset, body_zh=PRESET_ZH.get(B.preset, B.preset), height_px=round(B.height), asymmetric=B.asymmetric, views=VIEW_CODES,
                         view_meaning={c: z for c, z in zip(VIEW_CODES, VIEW_ZH)}, attachments=spec)
    rig._bake_reports = {}
    return rest


# -------------------------------------------------------------------------------------------- baking
TOL = {"x": 0.35, "y": 0.35, "rotate": 0.35, "sx": 0.004, "sy": 0.004, "shy": 0.4}


def _hermite(t0, v0, m0, t1, v1, m1, t):
    h = t1 - t0
    s = (t - t0) / h
    return (2 * s**3 - 3 * s**2 + 1) * v0 + (s**3 - 2 * s**2 + s) * h * m0 + (-2 * s**3 + 3 * s**2) * v1 + (s**3 - s**2) * h * m1


def _channel(a, bone: str, prop: str, t: List[float], v: List[float], stepped: List[bool], loop: bool, reduce: bool):
    """Dense samples -> a compact Hermite curve.  `stepped[i]` marks a jump after knot i (a view switch); each stretch
    between jumps gets its own tangents and is thinned to the fewest knots that stay within tolerance."""
    t = [round(x, 4) for x in t]              # exported times have 4 decimals; work on exactly those so a stepped knot and the knot after it never trade places
    n = len(t)
    runs, start = [], 0
    for i in range(n):
        if stepped[i] or i == n - 1:
            runs.append((start, i))
            start = i + 1
    T, V, M, S = [], [], [], []
    single = len(runs) == 1
    for (i0, i1) in runs:
        m = []
        for i in range(i0, i1 + 1):
            if i0 < i < i1:
                m.append((v[i + 1] - v[i - 1]) / (t[i + 1] - t[i - 1]))
            elif i1 == i0:
                m.append(0.0)
            elif loop and single:
                off = v[i1] - v[i0]
                m.append(((v[i0 + 1] + off) - v[i1 - 1]) / ((t[i0 + 1] - t[i0]) + (t[i1] - t[i1 - 1])) if i == i1 else (v[i0 + 1] - (v[i1 - 1] - off)) / ((t[i0 + 1] - t[i0]) + (t[i1] - t[i1 - 1])))
            else:
                m.append((v[i0 + 1] - v[i0]) / (t[i0 + 1] - t[i0]) if i == i0 else (v[i1] - v[i1 - 1]) / (t[i1] - t[i1 - 1]))
        keep = [i0]
        if reduce and i1 - i0 > 1:
            tol = TOL[prop]
            i = i0
            while i < i1:
                j = min(i1, i + 24)
                while j > i + 1:
                    if all(abs(_hermite(t[i], v[i], m[i - i0], t[j], v[j], m[j - i0], t[k]) - v[k]) <= tol for k in range(i + 1, j)):
                        break
                    j -= 1
                keep.append(j)
                i = j
        else:
            keep = list(range(i0, i1 + 1))
        for k in keep:
            T.append(t[k]); V.append(v[k]); M.append(m[k - i0]); S.append(False)
        S[-1] = stepped[i1] if i1 < n - 1 else False
    a._add(bone, prop, C.PP(T, V, M, M, S))


def bake(rig, name: str, pose_fn: Callable[[float], Pose], duration: float, B: Body, loop: bool = False, fps: int = 30,
         events: Optional[List[Tuple[float, str]]] = None, tint: float = 0.2, min_scale: float = 0.05, guard: bool = True, reduce: bool = True,
         param: bool = False, key_all: bool = False):
    """Sample pose_fn over [0, duration]; solve, simulate the extras and project every sample; write Spine timelines:
    translate / rotate / scale / shear per part, view switches, draw order (camera depth with hysteresis), depth tint.
    Returns a report (unreachable feet, view switches, flicker) and stores it in rig._bake_reports[name]."""
    fig = rig._figure
    rest, ref = fig["rest"], fig["ref"]
    a = rig.animation(name, duration=duration, loop=loop)
    # key_all: write every channel even when it does not move.  Additive parameter clips ADD to whatever the bone holds;
    # if the clip underneath does not set a property every frame, the additions pile up frame after frame.
    a.keep_static = bool(key_all)
    n = max(2, int(round(duration * fps)))
    ts = [duration * i / n for i in range(n + 1)]
    sols, frames, poses, over = [], [], [], 0.0
    for t in ts:
        p = pose_fn(t)
        left = reach_guard(p, B) if guard else 0.0
        parts, fr, ov = solve(p, B)
        over = max(over, left, ov)
        sols.append(parts)
        frames.append(fr)
        poses.append(p)
    if loop:
        sols[-1], frames[-1], poses[-1] = sols[0], frames[0], poses[0]            # a loop closes exactly
    for parts, extra in zip(sols, sim_extras(B, frames, duration / n, loop)):
        parts.update(extra)
    report = {"samples": n + 1, "reach_over_px": round(over, 1), "view_switches": {}, "flicker": []}
    names = list(rest)
    no_step = [False] * (n + 1)
    for part in names:
        r0 = rest[part]
        kind = r0["kind"]
        if kind == "rseg":                                    # a link of a runtime chain: its bones belong to the physics, not to the clip
            continue
        _channel(a, part, "x", ts, [s[part]["x"] - r0["x"] for s in sols], no_step, loop, reduce)
        _channel(a, part, "y", ts, [s[part]["y"] - r0["y"] for s in sols], no_step, loop, reduce)
        if kind in ("ball", "anchor"):
            continue
        if kind == "shadow":
            sc = [s[part]["a"] - 1.0 for s in sols]
            _channel(a, part, "sx", ts, sc, no_step, loop, reduce)
            _channel(a, part, "sy", ts, sc, no_step, loop, reduce)
            continue
        if kind == "tube":
            rots, sxs, prev = [], [], r0["rot"]
            for s in sols:
                q = s[part]
                prev = _near_angle(q["rot"], prev) if q["a"] > 0.5 else prev
                rots.append(prev - r0["rot"])
                # (laid-over parameter clips are deltas from the rest pose, and the rest pose may already foreshorten this tube)
                sxs.append(max(min_scale, q["a"] / r0["len3"]) - (r0["a"] / r0["len3"] if param else 1.0))
            if loop:
                rots[-1] = rots[0] + round((rots[-1] - rots[0]) / 360.0) * 360.0
            _channel(a, part, "rotate", ts, rots, no_step, loop, reduce)
            _channel(a, part, "sx", ts, sxs, no_step, loop, reduce)
            continue
        # ---- ellipsoid: pick the view, then map that view's image onto the projected ellipse
        refs = ref[part]
        nv = len(refs)
        views = []
        if nv > 1:
            cur, sectors = None, view_sectors(part in B.plates)
            for s in (sols + sols if loop else sols):          # one warm-up lap so a loop starts in its steady view
                cur = pick_view(part_yaw(s[part]["R"]), cur, sectors)
                views.append(cur)
            views = views[-(n + 1):]
            dwell = max(2, int(round(0.1 * n / duration)))     # a view held for under ~0.1 s is skipped: two pops are worse than a brief squash
            j0 = 0
            while j0 <= n:
                j1 = j0
                while j1 + 1 <= n and views[j1 + 1] == views[j0]:
                    j1 += 1
                if 0 < j0 and j1 < n and j1 - j0 + 1 < dwell:
                    for q_ in range(j0, j1 + 1):
                        views[q_] = views[j0 - 1]
                j0 = j1 + 1
            if loop:
                views[-1] = views[0]
        else:
            views = [0] * (n + 1)
        kt, kv, ks, prev_rot, switches = [], [], [], 0.0, []
        for j, s in enumerate(sols):
            q = s[part]
            if j > 0 and views[j] != views[j - 1]:
                old = _decompose(_ell_map(q, refs[views[j - 1]], B.cam), prev_rot, min_scale)
                kt.append(ts[j] - EPS_T); kv.append(old); ks.append(True)
                prev_rot = old[0]
                switches.append((ts[j], views[j]))
            val = _decompose(_ell_map(q, refs[views[j]], B.cam), prev_rot, min_scale)
            prev_rot = val[0]
            kt.append(ts[j]); kv.append(val); ks.append(False)
        if loop and not switches:
            kv[-1] = (kv[0][0] + round((kv[-1][0] - kv[0][0]) / 360.0) * 360.0,) + kv[0][1:]
        for idx, prop in enumerate(("rotate", "sx", "sy", "shy")):
            _channel(a, part, prop, kt, [x[idx] for x in kv], ks, loop, reduce)
        if part in B.choosers:                                # state images (eye, mouth): key a change, never the default
            prev_s, keys_ = B.states[part][0], []
            for j, pz_ in enumerate(poses):
                suf = B.choosers[part](pz_.face)
                if suf != prev_s:
                    keys_.append((round(ts[j], 4), f"{part}_{suf}" if suf else None))
                    prev_s = suf
            if keys_:
                a.attachment(part, keys_)
        if part in B.alpha_slots:
            prev_q, keys_ = 0, []
            for j, pz_ in enumerate(poses):
                q_ = int(round(max(0.0, min(1.0, pz_.face[B.alpha_slots[part]])) * 15))
                if q_ != prev_q or (keys_ and j == n):
                    keys_.append((round(ts[j], 4), "ffffff%02x" % (q_ * 17)))
                    prev_q = q_
            if key_all and (not keys_ or keys_[0][0] > 0):
                keys_.insert(0, (0.0, "ffffff00"))
            if keys_:
                a.color(part, keys_)
        if nv > 1:
            vk = ([] if param else [(0.0, f"{part}_v{views[0]}")]) + [(round(t_, 4), f"{part}_v{v_}") for t_, v_ in switches]
            if vk:
                a.attachment(part, vk)
            report["view_switches"][part] = len(switches)
            seq_v = [views[0]] + [v_ for _, v_ in switches]
            for k_ in range(1, len(switches)):                 # flicker = going to a view and straight back (a fast spin is not)
                if seq_v[k_ + 1] == seq_v[k_ - 1] and switches[k_][0] - switches[k_ - 1][0] < 0.25:
                    report["flicker"].append({"part": part, "t": round(switches[k_ - 1][0], 3), "gap_s": round(switches[k_][0] - switches[k_ - 1][0], 3)})

    # draw order: sort by camera depth, but only swap neighbours once they are clearly apart (no flicker at ties).
    # What an add-on encloses (legs in a robe, a forearm in a sleeve) may never rise above it, whatever its depth says.
    order = [n_ for n_ in ordered(B, rest) if rest[n_]["kind"] != "anchor"]
    under = enclosures(B, order)

    def settle(s, order_):
        changed = True
        while changed:
            changed = False
            for i in range(len(order_) - 1):
                lo, hi = order_[i], order_[i + 1]
                if s[lo]["depth"] > s[hi]["depth"] + 2.0 and lo not in under.get(hi, ()):
                    order_[i], order_[i + 1] = hi, lo
                    changed = True
        return order_
    for s in (sols if loop else sols[:1]):
        order = settle(s, order)
    last = None
    for t, s in zip(ts, sols):
        if param:                                             # a parameter clip is laid over other clips: it leaves the order alone
            break
        order = settle(s, order)
        if order != last:
            a.draw_order_list(t, list(order))
            last = list(order)
    if tint > 0 and not param:                                # parts behind the pelvis get darker
        for part in names:
            if rest[part]["kind"] in ("shadow", "anchor", "rseg") or part in B.alpha_slots:
                continue
            keys, prev_hex = [], None
            for i, (t, s) in enumerate(zip(ts, sols)):
                rel = s[part]["depth"] - s["pelvis"]["depth"]
                v = 255 - 8 * int(round(255 * tint * min(1.0, max(0.0, -rel / (110.0 * max(B.w, 0.6)))) / 8.0))      # coarse steps: far fewer keys
                hx = f"{v:02x}{v:02x}{min(255, v + 3):02x}ff"
                if hx != prev_hex or i == len(ts) - 1:
                    keys.append((t, hx))
                    prev_hex = hx
            if len(keys) > 1 or keys[0][1] != "ffffffff":
                a.color(part, keys)
    for t, ev in events or []:
        a.event(t, ev)
    rig._bake_reports[name] = report
    return report


# ------------------------------------------------------------------------------------- choreography
def leg_fk(P, Rp, sign: float, ang, B: Body):
    """Free leg from joint angles (flex, abd, rot, knee, ankle) -> (ankle, knee direction, foot yaw, foot pitch)."""
    flex, abd, rot, knee, ankle = ang
    hip = P + Rp @ np.array([sign * B.hip_w, -B.hip_drop, 0])
    Rt = Rp @ _rz(RAD(sign * abd)) @ _rx(RAD(-flex)) @ _ry(RAD(sign * rot))
    kn = hip + Rt @ np.array([0, -B.thigh, 0])
    Rsh = Rt @ _rx(RAD(knee))
    an = kn + Rsh @ np.array([0, -B.shin, 0])
    fwd = Rsh @ _rx(RAD(-ankle)) @ np.array([0, 0, 1.0])
    return an, kn - hip, math.degrees(math.atan2(fwd[0], fwd[2])), math.degrees(math.asin(max(-1.0, min(1.0, float(fwd[1])))))


EASES = {"smooth": lambda u: u * u * (3 - 2 * u), "linear": lambda u: u, "in": lambda u: u * u, "out": lambda u: 1 - (1 - u) ** 2,
         "snap": lambda u: u ** 3, "settle": lambda u: 1 - (1 - u) ** 3}


class Choreo:
    """Pose-to-pose choreography for one figure (see docs/35-figure3d.md).

        footL=("step", fwd, lat[, yaw, lift])   put the foot down relative to the body's ground point and heading
        footL=("pivot", yaw)                    same spot, turn the foot
        footL=("fk", flex, abd, rot, knee[, ankle])   free leg posed by joint angles
        (omitted)                               keep doing what it was doing; a planted foot stays exactly where it is
    advance=(fwd, lat) moves the ground point along the heading; root=(x, z) sets it.  ease = how the motion ARRIVES.
    """

    SCALARS = ("heading", "px", "py", "pz", "pyaw", "ppitch", "proll", "syaw", "spitch", "sroll", "hyaw", "hpitch", "hroll")

    def __init__(self, B: Body, heading: float = 90.0, root=(0.0, 0.0)):
        self.B = B
        self.cur = {k: 0.0 for k in self.SCALARS}
        self.cur.update(heading=float(heading), root=(float(root[0]), float(root[1])), armL=(0.0, 8.0, 0.0, 10.0), armR=(0.0, 8.0, 0.0, 10.0))
        self.keys: List[dict] = []
        self._foot = {"L": self._ground(0.0, B.stance_x, 7.0, 34.0 * B.s), "R": self._ground(0.0, -B.stance_x, -7.0, 34.0 * B.s)}

    def _ground(self, fwd, lat, yaw, lift):
        h = RAD(self.cur["heading"])
        rx, rz = self.cur["root"]
        return ("g", rx + lat * math.cos(h) + fwd * math.sin(h), rz - lat * math.sin(h) + fwd * math.cos(h), self.cur["heading"] + yaw, lift)

    def key(self, t: float, ease: str = "smooth", ease_py: Optional[str] = None, **kw):
        if self.keys and t <= self.keys[-1]["t"]:
            raise ValueError(f"key times must increase (got {t} after {self.keys[-1]['t']})")
        if "advance" in kw:
            fwd, lat = kw.pop("advance")
            h = RAD(kw.get("heading", self.cur["heading"]))
            rx, rz = self.cur["root"]
            self.cur["root"] = (rx + lat * math.cos(h) + fwd * math.sin(h), rz - lat * math.sin(h) + fwd * math.cos(h))
        feet = {s: kw.pop("foot" + s, None) for s in SIDES}
        for k, v in kw.items():
            if k not in self.cur:
                raise ValueError(f"unknown key parameter '{k}'")
            self.cur[k] = tuple(float(x) for x in v) if isinstance(v, (tuple, list)) else float(v)
        for s, sign in (("L", 1.0), ("R", -1.0)):
            spec = feet[s]
            if spec is None:
                continue
            if spec[0] == "step":
                self._foot[s] = self._ground(spec[1], spec[2], spec[3] if len(spec) > 3 else 7.0 * sign, spec[4] if len(spec) > 4 else 34.0 * self.B.s)
            elif spec[0] == "pivot":
                prev = self._foot[s]
                if prev[0] != "g":
                    raise ValueError(f"t={t}: foot{s} cannot pivot while it is in the air")
                self._foot[s] = ("g", prev[1], prev[2], self.cur["heading"] + spec[1], 0.0)
            elif spec[0] == "fk":
                a = tuple(float(x) for x in spec[1:])
                self._foot[s] = ("f",) + a + (0.0,) * (5 - len(a))
            else:
                raise ValueError(f"foot spec '{spec[0]}' (use step / pivot / fk)")
        snap = dict(self.cur)
        snap.update(t=float(t), ease=ease, ease_py=ease_py or ease, foot=dict(self._foot))
        self.keys.append(snap)
        return self

    def spot(self, side: str) -> Tuple[float, float]:
        """World spot of a planted foot: make it the ground point (root=) before pivoting or kicking off that leg."""
        f = self._foot[side]
        return (f[1], f[2])

    @property
    def duration(self) -> float:
        return self.keys[-1]["t"]

    def pose(self, t: float) -> Pose:
        ks = self.keys
        i = 0
        while i < len(ks) - 2 and t >= ks[i + 1]["t"]:
            i += 1
        a, b = ks[i], ks[i + 1]
        u = min(1.0, max(0.0, (t - a["t"]) / (b["t"] - a["t"])))
        w, wy = EASES[b["ease"]](u), EASES[b["ease_py"]](u)
        lerp = lambda x, y, k: x + (y - x) * k
        p = Pose()
        for k in self.SCALARS:
            setattr(p, k, lerp(a[k], b[k], wy if k == "py" else w))
        p.root = (lerp(a["root"][0], b["root"][0], w), lerp(a["root"][1], b["root"][1], w))
        for s in SIDES:
            p.arm[s] = dict(zip(("flex", "abd", "twist", "elbow"), (lerp(x, y, w) for x, y in zip(a["arm" + s], b["arm" + s]))))
        P, Rp = pelvis_frame(p, self.B)
        ah = self.B.ankle_h
        for s, sign in (("L", 1.0), ("R", -1.0)):
            fa, fb = a["foot"][s], b["foot"][s]
            if fa[0] == "g" and fb[0] == "g":
                moved = math.hypot(fb[1] - fa[1], fb[2] - fa[2]) > 1.0
                arc = math.sin(math.pi * u) if moved else 0.0
                pos = np.array([lerp(fa[1], fb[1], w), ah + fb[4] * arc, lerp(fa[2], fb[2], w)])
                yaw, pitch, pole = lerp(fa[3], fb[3], w), -12.0 * arc, None
            elif fa[0] == "f" and fb[0] == "f":
                pos, pole, yaw, pitch = leg_fk(P, Rp, sign, tuple(lerp(x, y, w) for x, y in zip(fa[1:], fb[1:])), self.B)
            else:
                g, f_, k = (fa, fb, w) if fa[0] == "g" else (fb, fa, 1.0 - w)       # k = how far toward the posed (free) leg
                fpos, fpole, fyaw, fpitch = leg_fk(P, Rp, sign, f_[1:], self.B)
                gpos = np.array([g[1], ah, g[2]])
                pos = gpos + (fpos - gpos) * k
                yaw = g[3] + _near_angle(fyaw - g[3], 0.0) * k
                pitch = fpitch * k
                dflt = Rp @ np.array([0, 0, 1.0]) + _ry(RAD(g[3])) @ np.array([0, 0, 1.0]) + np.array([0, 0.25, 0])
                pole = _unit(dflt) * (1 - k) + _unit(fpole) * k
            p.foot[s] = dict(x=float(pos[0]), y=float(max(pos[1], ah)), z=float(pos[2]), yaw=yaw, pitch=pitch, world=True, pole=pole)
        return p

    def reach_report(self, step: float = 1 / 60) -> List[dict]:
        """Times where a foot target is farther than the leg can reach (before the bake's reach guard steps in)."""
        out, t = [], 0.0
        lim = self.B.leg - 0.6
        while t <= self.duration + 1e-9:
            p = self.pose(t)
            P, Rp = pelvis_frame(p, self.B)
            for s, sign in (("L", 1.0), ("R", -1.0)):
                hip = P + Rp @ np.array([sign * self.B.hip_w, -self.B.hip_drop, 0])
                d = float(np.linalg.norm(np.array([p.foot[s]["x"], p.foot[s]["y"], p.foot[s]["z"]]) - hip))
                if d > lim + 0.5:
                    out.append({"t": round(t, 3), "foot": s, "over_px": round(d - lim, 1)})
            t += step
        return out
