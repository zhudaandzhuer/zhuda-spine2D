"""米丫子 (Miyazi) -- VTuber half-body rig.  `spk build` calls build(rig).

Parts: every pixel visible at rest is the key art's own (parts.py); generated layers fill only what is hidden.
Face: a head mesh on a pseudo-3D look controller; eyes = white patch + iris (gaze) + upper lashes, blink / smile
eyes and mouth shapes are state patches that cover the whole feature.  Hair front / back are single meshes driven by
chains with Spine physics (no cut seams); the ribbon tail is its own chain.
Live parameters (contract.parameters) follow the kit's front-performer convention (docs/39).
Canvas 1024 x 1536 px, x right, y down.
"""
import json
from pathlib import Path

import numpy as np

from spinekit import weights as W

NAME = "miyazi"
HERE = Path(__file__).resolve().parent
M = {q["name"]: q for q in json.loads((HERE / "parts" / "manifest.json").read_text())["parts"]}


def c(n):
    q = M[n]
    return (q["x"] + q["w"] / 2, q["y"] + q["h"] / 2)


CX = 512
HEAD = (CX, 300)
NECK = (CX, 445)
CHEST = (CX, 700)
WAIST = (CX, 1050)
HIP = (CX, 1350)
SH = {"L": (305, 545), "R": (719, 545)}
EL = {"L": (215, 1000), "R": (809, 1000)}
WR = {"L": (165, 1440), "R": (859, 1440)}
U = 20.0            # look unit (px)
T = 14.0            # body turn unit
G = 3.0             # gaze unit (iris travel)
EYES = ("half", "closed", "smile")
MOUTHS = ("closed", "a", "aa", "o", "smile")
FACE_SLOTS = ["eye_L", "eye_R", "mouth"]


def build(rig):
    rig.set_origin(CX, 1536)
    rig.frame(40, 0, 944, 1536)
    rig.set(padding=4, bleed=6, pma=False, max_influences=4)

    # ------------------------------------------------------------------ body
    rig.bone("root", at=(CX, 1536))
    rig.bone("hip", "root", at=HIP, tip=WAIST)
    rig.bone("waist", "hip", at=WAIST, tip=CHEST)
    rig.bone("chest", "waist", at=CHEST, tip=(CX, 520))
    for s in "LR":
        rig.bone(f"shoulder_{s}", "chest", at=SH[s], rot=0, length=0)
        rig.bone(f"arm_up_{s}", f"shoulder_{s}", at=SH[s], tip=EL[s])
        rig.bone(f"arm_low_{s}", f"arm_up_{s}", at=EL[s], tip=WR[s])
    rig.bone("neck", "chest", at=(CX, 520), tip=NECK)
    rig.bone("head", "neck", at=NECK, rot=0, length=0)
    turn = rig.look("turn", parent="chest", at=(CX, 760), unit=T)            # body yaw (BodyAngleX)

    # ------------------------------------------------------------------ face
    zface = rig.ellipsoid(cx=CX, cy=300, rx=170, ry=210)
    look = rig.look("look", parent="head", at=(CX, 300), unit=U, back="look_back")
    for s in "LR":
        ex, ey = c(f"iris_{s}")
        rig.bone(f"eye_{s}", "head", at=(ex, ey))
        rig.bone(f"iris_{s}", f"eye_{s}", at=(ex, ey))
        bx, by = c(f"brow_{s}")
        rig.bone(f"brow_{s}", "head", at=(bx, by))
        look.follow(f"eye_{s}", rig.depth_at(zface, ex, ey))
        look.follow(f"brow_{s}", rig.depth_at(zface, bx, by))
    mx, my = c("mouth_closed")
    rig.bone("mouth", "head", at=(mx, my))
    look.follow("mouth", rig.depth_at(zface, mx, my))
    rig.bone("blush", "head", at=c("blush"))
    look.follow("blush", 0.9)
    rig.bone("gaze", "head", at=(CX, 280), color="ff8a5cff")
    g = rig.bones["gaze"]
    rig.transform("gaze_follow", ["iris_L", "iris_R"], "gaze", mix_x=1.0, mix_y=1.0, x=-g.lx, y=-g.ly)

    # ------------------------------------------------------------------ hair bones
    def chain(prefix, pts, depth, hanging=True):
        names = rig.chain(prefix, "head", pts, inherit_first="noRotationOrReflection" if hanging else None, color="e8c99aff")
        look.follow(names[0], depth)
        return names

    side_L = chain("side_L", [(300, 190), (296, 270), (290, 360), (284, 455)], 0.55, hanging=False)
    bang_L = chain("bang_L", [(425, 105), (424, 180), (422, 250), (420, 320)], 1.0, hanging=False)
    bang_C = chain("bang_C", [(512, 95), (512, 175), (512, 250), (512, 320)], 1.05, hanging=False)
    bang_R = chain("bang_R", [(600, 105), (601, 180), (603, 250), (605, 320)], 1.0, hanging=False)
    side_R = chain("side_R", [(724, 190), (728, 270), (733, 360), (738, 455)], 0.55, hanging=False)
    back_L = chain("back_L", [(330, 190), (318, 290), (306, 380), (296, 460)], -0.3)
    back_C = chain("back_C", [(512, 190), (512, 290), (512, 380), (512, 465)], -0.3)
    back_R = chain("back_R", [(690, 190), (702, 290), (714, 380), (722, 460)], -0.3)
    ribbon = chain("ribbon", [(700, 175), (706, 265), (712, 365), (716, 468)], 0.6)
    front_chains = [side_L, bang_L, bang_C, bang_R, side_R]
    back_chains = [back_L, back_C, back_R]

    # ------------------------------------------------------------------ weights
    head_depth = W.depth("head", "look", zface)

    def face_field(rig_, sx, sy):
        """head above the jaw rides the look controller; the neck below the jaw rides the neck / chest"""
        hd = W.normalize(head_depth(rig_, sx, sy))
        nk = W.normalize(W.chain(["chest", "neck"], blend=0.6)(rig_, sx, sy))
        m = W.smoothstep(np.clip((sy - 405.0) / 55.0, 0, 1))
        out = {}
        for k, v in hd.items():
            out[k] = out.get(k, 0) + v * (1 - m)
        for k, v in nk.items():
            out[k] = out.get(k, 0) + v * m
        return out

    def torso_field(rig_, sx, sy):
        base = W.normalize(W.layered(W.chain(["hip", "waist", "chest"], blend=0.7), base="chest", front="turn", z=rig_.ellipsoid(cx=CX, cy=820, rx=330, ry=420))(rig_, sx, sy))
        out = {k: v.copy() for k, v in base.items()}
        for s in "LR":
            d = np.hypot(sx - SH[s][0], (sy - SH[s][1]) * 1.3)
            m = W.smoothstep(1 - d / 140.0) * 0.8
            for k in out:
                out[k] = out[k] * (1 - m)
            out[f"shoulder_{s}"] = out.get(f"shoulder_{s}", 0) + m
        return out

    back_field = W.layered(W.sheet(back_chains, blend=0.6, root="head", root_blend=0.9), base="head", front="look", back="look_back",
                           z=lambda sx, sy: np.full(sx.shape, -0.3))
    front_field = W.layered(W.sheet(front_chains, blend=0.7, root="head", root_blend=0.8), base="head", front="look",
                            z=lambda sx, sy: np.full(sx.shape, 0.9))

    # ------------------------------------------------------------------ parts (manifest order)
    rig.part("hair_back", "head", mesh=dict(step=34), weights=back_field)
    rig.part("face", "head", mesh=dict(step=24), weights=face_field)
    rig.part("body", "chest", mesh=dict(step=48), weights=torso_field)
    for s in "LR":
        rig.part(f"arm_{s}", f"arm_up_{s}", mesh=dict(cols=4, rows=16), weights=W.chain([f"arm_up_{s}", f"arm_low_{s}"], blend=0.6, root=f"shoulder_{s}", root_blend=0.3))
    for s in "LR":
        rig.part(f"eye_white_{s}", f"eye_{s}")
    for s in "LR":
        rig.part(f"iris_{s}", f"iris_{s}")
    for s in "LR":
        rig.part(f"lash_{s}", f"eye_{s}")
    for k in EYES:
        for s in "LR":
            rig.part(f"eye_{k}_{s}", f"eye_{s}", slot=f"eye_{s}", active=False)
    for s in "LR":
        rig.part(f"brow_{s}", f"brow_{s}")
    for k in MOUTHS:
        rig.part(f"mouth_{k}", "mouth", slot="mouth", active=(k == "closed"))
    rig.part("blush", "blush", color="ffffff00")
    rig.part("hair_front", "head", mesh=dict(step=26), weights=front_field)
    rig.part("ribbon_tail", "head", mesh=dict(cols=3, rows=12), weights=W.chain(ribbon, blend=0.7, root="head", root_blend=0.4))

    # ------------------------------------------------------------------ physics
    for ch in (bang_L, bang_C, bang_R):
        rig.physics_chain(ch, inertia=(0.35, 0.6), strength=(190, 150), damping=(0.8, 0.84), mix=(0.5, 1.0))
    for ch in (side_L, side_R):
        rig.physics_chain(ch, inertia=(0.4, 0.75), strength=(140, 95), damping=(0.83, 0.88))
    for ch in back_chains:
        rig.physics_chain(ch, inertia=(0.35, 0.7), strength=(120, 80), damping=(0.85, 0.9))
    rig.physics_chain(ribbon, inertia=(0.45, 0.85), strength=(110, 60), damping=(0.82, 0.88))

    # ------------------------------------------------------------------ stress (range of motion)
    rig.stress("look_left", look={"look": [-1, 0]})
    rig.stress("look_right", look={"look": [1, 0]})
    rig.stress("look_up", look={"look": [0, 1]})
    rig.stress("look_down", look={"look": [0, -1]})
    rig.stress("look_ul", look={"look": [-0.8, 0.8]})
    rig.stress("look_dr", look={"look": [0.8, -0.8]})
    rig.stress("tilt_L", pose={"head": {"rot": 10}})
    rig.stress("tilt_R", pose={"head": {"rot": -10}})
    rig.stress("body_turn_L", look={"turn": [-1, 0], "look": [-0.6, 0]}, pose={"waist": {"rot": -3}})
    rig.stress("body_turn_R", look={"turn": [1, 0], "look": [0.6, 0]}, pose={"waist": {"rot": 3}})
    rig.stress("gaze_L", pose={"gaze": {"x": -G}})
    rig.stress("gaze_R_up", pose={"gaze": {"x": G, "y": G * 0.7}})
    rig.stress("brows_up", pose={"brow_L": {"y": 7}, "brow_R": {"y": 7}})
    rig.stress("brows_down", pose={"brow_L": {"y": -5, "rot": -8}, "brow_R": {"y": -5, "rot": 8}})
    for k in EYES:
        rig.stress(f"eyes_{k}", slots={"eye_L": f"eye_{k}_L", "eye_R": f"eye_{k}_R"})
    for k in MOUTHS[1:]:
        rig.stress(f"mouth_{k}", slots={"mouth": f"mouth_{k}"})
    rig.stress("breath_in", pose={"chest": {"y": 6, "sy": 1.015}, "shoulder_L": {"y": 4}, "shoulder_R": {"y": 4}})
    rig.stress("arms_out", pose={"arm_up_L": {"rot": -7}, "arm_up_R": {"rot": 7}, "arm_low_L": {"rot": -6}, "arm_low_R": {"rot": 6}})
    sway = lambda a: {b: {"rot": a * (0.6 + 0.25 * i)} for ch in front_chains + back_chains + [ribbon] for i, b in enumerate(ch)}
    rig.stress("hair_sway_L", pose=sway(-8))
    rig.stress("hair_sway_R", pose=sway(8))

    # ------------------------------------------------------------------ base clips: key every property the parameters add to
    PARAM_BONES_T = ["look", "turn", "gaze", "brow_L", "brow_R"]
    PARAM_BONES_R = ["head", "waist", "chest"]

    def base_keys(a, d):
        a.keep_static = True
        for b in PARAM_BONES_T:
            a.translate(b, [(0, 0, 0), (d, 0, 0)])
        for b in PARAM_BONES_R:
            a.rotate(b, [(0, 0), (d, 0)])
        a.alpha("blush", [(0, 0), (d, 0)])

    hang = front_chains + back_chains + [ribbon]
    a = rig.animation("idle", duration=6.0, loop=True)
    base_keys(a, 6.0)
    a.osc("chest", "y", 2.4, period=3)
    a.osc("chest", "sy", 0.006, period=3)
    for s in "LR":
        a.osc(f"shoulder_{s}", "y", 1.4, period=3, phase=0.08)
        a.osc(f"arm_up_{s}", "rotate", 0.5 * (1 if s == "L" else -1), period=3, phase=0.12)
    a.osc("waist", "rotate", 0.6, period=6)
    a.osc("head", "rotate", 1.2, period=6, phase=0.17)
    a.osc("look", "x", 0.12 * U, period=6, phase=0.2)
    a.osc("look", "y", 0.06 * U, period=3, phase=0.3)
    for i, ch in enumerate(hang):
        a.sway(ch, 0.5, period=3, lag=0.08, phase=0.15 + 0.05 * (i % 3), grow=1.1)

    # actions (track 0, return to idle) -- all key the parameter bones too
    a = rig.animation("nod", duration=1.3)
    base_keys(a, 1.3)
    a.translate("look", [(0, 0, 0), (0.12, 0, 0.15 * U), (0.38, 0, -0.9 * U), (0.62, 0, 0.1 * U), (0.84, 0, -0.45 * U), (1.1, 0, 0), (1.3, 0, 0)])
    a.translate("head", [(0, 0, 0), (0.38, 0, -4), (0.62, 0, 0.5), (0.84, 0, -2), (1.1, 0, 0), (1.3, 0, 0)])
    a.translate("gaze", [(0, 0, 0), (0.38, 0, 1.6), (0.84, 0, 0.8), (1.1, 0, 0), (1.3, 0, 0)])

    a = rig.animation("shake", duration=1.5)
    base_keys(a, 1.5)
    xs = [(0, 0), (0.2, -0.8), (0.48, 0.8), (0.74, -0.5), (1.0, 0.25), (1.25, 0), (1.5, 0)]
    a.translate("look", [(t, v * U, -0.05 * U * abs(v)) for t, v in xs], ease="smooth")
    a.translate("gaze", [(t, -v * G, 0) for t, v in xs], ease="smooth")
    a.rotate("head", [(t, -v * 2.0) for t, v in xs], ease="smooth")

    a = rig.animation("tilt", duration=2.4)
    base_keys(a, 2.4)
    a.rotate("head", [(0, 0), (0.5, 8), (1.7, 8), (2.3, 0), (2.4, 0)])
    a.translate("look", [(0, 0, 0), (0.5, -0.25 * U, 0.1 * U), (1.7, -0.25 * U, 0.1 * U), (2.3, 0, 0), (2.4, 0, 0)])
    a.translate("brow_L", [(0, 0, 0), (0.5, 0, 4), (1.7, 0, 4), (2.3, 0, 0), (2.4, 0, 0)])
    a.translate("brow_R", [(0, 0, 0), (0.5, 0, 4), (1.7, 0, 4), (2.3, 0, 0), (2.4, 0, 0)])
    a.rotate("chest", [(0, 0), (0.5, -1.5), (1.7, -1.5), (2.3, 0), (2.4, 0)])

    a = rig.animation("happy", duration=1.8)                 # a little bounce with closed smiling eyes
    base_keys(a, 1.8)
    for s in "LR":
        a.attachment(f"eye_{s}", [(0, None), (0.12, f"eye_smile_{s}"), (1.6, None)])
    a.attachment("mouth", [(0, "mouth_closed"), (0.12, "mouth_smile"), (1.6, "mouth_closed")])
    a.alpha("blush", [(0, 0), (0.3, 0.9), (1.4, 0.9), (1.8, 0)])
    a.translate("chest", [(0, 0, 0), (0.15, 0, 7), (0.35, 0, -2), (0.55, 0, 6), (0.75, 0, -1), (1.0, 0, 0), (1.8, 0, 0)])
    a.rotate("head", [(0, 0), (0.3, 5), (0.7, -3), (1.1, 2), (1.6, 0), (1.8, 0)])
    a.translate("look", [(0, 0, 0), (0.3, 0, 0.3 * U), (1.4, 0, 0.2 * U), (1.8, 0, 0)])

    a = rig.animation("surprised", duration=1.4)
    base_keys(a, 1.4)
    a.translate("brow_L", [(0, 0, 0), (0.08, 0, 7), (1.0, 0, 5), (1.35, 0, 0), (1.4, 0, 0)])
    a.translate("brow_R", [(0, 0, 0), (0.08, 0, 7), (1.0, 0, 5), (1.35, 0, 0), (1.4, 0, 0)])
    a.attachment("mouth", [(0, "mouth_closed"), (0.06, "mouth_o"), (1.0, "mouth_closed")])
    a.translate("chest", [(0, 0, 0), (0.1, 0, 6), (0.5, 0, 2), (1.3, 0, 0), (1.4, 0, 0)])
    a.translate("look", [(0, 0, 0), (0.1, 0, 0.25 * U), (0.9, 0, 0.12 * U), (1.35, 0, 0), (1.4, 0, 0)])
    for s in "LR":
        a.translate(f"shoulder_{s}", [(0, 0, 0), (0.1, 0, 7), (0.5, 0, 3), (1.3, 0, 0), (1.4, 0, 0)])

    # blink / talk are live parameters (Blink, MouthOpen): the preview drives them (auto blink, talking mouth)

    # ------------------------------------------------------------------ live parameters: 1 s clips, time = value
    def param(name, keys):
        a = rig.animation(f"p_{name}", duration=1.0)
        for kind, bone, vals in keys:
            if kind == "t":
                a.translate(bone, [(t, x, y) for t, x, y in vals], ease="linear")
            elif kind == "r":
                a.rotate(bone, [(t, v) for t, v in vals], ease="linear")
            elif kind == "alpha":
                a.alpha(bone, [(t, v) for t, v in vals])
            elif kind == "att":
                a.attachment(bone, vals)
        return a

    param("AngleX", [("t", "look", [(0, -U, 0), (0.5, 0, 0), (1, U, 0)]), ("r", "head", [(0, 1.5), (0.5, 0), (1, -1.5)])])
    param("AngleY", [("t", "look", [(0, 0, -0.85 * U), (0.5, 0, 0), (1, 0, 0.85 * U)])])
    param("AngleZ", [("r", "head", [(0, 8), (0.5, 0), (1, -8)])])
    param("BodyAngleX", [("t", "turn", [(0, -T, 0), (0.5, 0, 0), (1, T, 0)]), ("r", "chest", [(0, 1.0), (0.5, 0), (1, -1.0)])])
    param("BodyAngleZ", [("r", "waist", [(0, 4), (0.5, 0), (1, -4)])])
    param("EyeBallX", [("t", "gaze", [(0, -G, 0), (0.5, 0, 0), (1, G, 0)])])
    param("EyeBallY", [("t", "gaze", [(0, 0, -G * 0.7), (0.5, 0, 0), (1, 0, G * 0.7)])])
    param("BrowY", [("t", "brow_L", [(0, 0, -5), (0.5, 0, 0), (1, 0, 7)]), ("t", "brow_R", [(0, 0, -5), (0.5, 0, 0), (1, 0, 7)])])
    param("Cheek", [("alpha", "blush", [(0, 0), (1, 1)])])
    param("Smile", [("att", "mouth", [(0.35, "mouth_smile")]), ("att", "eye_L", [(0.7, "eye_smile_L")]), ("att", "eye_R", [(0.7, "eye_smile_R")])])
    param("MouthOpen", [("att", "mouth", [(0.15, "mouth_a"), (0.55, "mouth_aa")])])
    param("Blink", [("att", "eye_L", [(0.3, "eye_half_L"), (0.75, "eye_closed_L")]), ("att", "eye_R", [(0.3, "eye_half_R"), (0.75, "eye_closed_R")])])

    params = [("AngleX", "頭左右", -30, 30, 0), ("AngleY", "頭上下", -20, 20, 0), ("AngleZ", "頭傾斜", -20, 20, 0),
              ("BodyAngleX", "身體左右", -15, 15, 0), ("BodyAngleZ", "身體傾斜", -10, 10, 0), ("EyeBallX", "視線左右", -1, 1, 0),
              ("EyeBallY", "視線上下", -1, 1, 0), ("BrowY", "眉毛", -1, 1, 0), ("Cheek", "臉紅", 0, 1, 0), ("Smile", "微笑", 0, 1, 0),
              ("MouthOpen", "張嘴", 0, 1, 0), ("Blink", "閉眼", 0, 1, 0)]
    rig.contract(
        title="米丫子 Miyazi（VTuber 半身）", background="#3a4152", mix={"default": 0.25},
        animations={
            "idle": {"label": "待機", "loop": True, "track": 0, "role": "base"},
            "nod": {"label": "點頭", "role": "action", "return": "idle"},
            "shake": {"label": "搖頭", "role": "action", "return": "idle"},
            "tilt": {"label": "歪頭", "role": "action", "return": "idle"},
            "happy": {"label": "開心", "role": "action", "return": "idle"},
            "surprised": {"label": "驚訝", "role": "action", "return": "idle"},
        },
        parameters=[{"id": i, "label": lb, "min": mn, "max": mx_, "default": df, "clip": f"p_{i}", "track": 10 + k} for k, (i, lb, mn, mx_, df) in enumerate(params)],
        home="idle",
    )
