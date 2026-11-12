"""米丫子 full body, 3/4 view facing screen-left.  `spk build` calls build(rig).

Forward = -x.  far = her right side (screen left, behind), near = her left side (screen right, in front).
Legs: two-bone IK on root-level targets (planted feet don't slide).  Arms: two bones in one mesh per sleeve, a separate
hand on a hand bone (open / fist swap).  Ribbon tail: physics chain.  Item: an apple to pick up.
Canvas 941 x 1672 px (y down).
"""
import json
import math
from pathlib import Path

import numpy as np

from spinekit import weights as W

NAME = "miyazi_full"
HERE = Path(__file__).resolve().parent
REP = json.loads((HERE / "parts-report.json").read_text())
GROUND = (468, 1600)
HIP = (468, 880)
CHEST = (464, 640)
NECK = (460, 330)
HEADP = (455, 290)
SH = {"far": (330, 445), "near": (612, 380)}
EL = {"far": (285, 625), "near": (650, 600)}
WR = {"far": tuple(REP["wrist_far"]), "near": tuple(REP["wrist_near"])}
TIP = {"far": (206, 915), "near": (704, 922)}
HIPJ = {"far": (395, 900), "near": (525, 900)}
KNEE = {"far": (352, 1230), "near": (511, 1230)}
ANK = {"far": (317, 1505), "near": (512, 1480)}
TOE = {"far": (300, 1630), "near": (600, 1560)}
APPLE = tuple(REP["apple"])
U = 16.0


def build(rig):
    rig.set_origin(*GROUND)
    rig.frame(-250, -320, 1450, 2030)

    rig.bone("root", at=GROUND)
    rig.bone("hip", "root", at=HIP, rot=0)
    rig.bone("belly", "hip", at=HIP, tip=CHEST)
    rig.bone("chest", "belly", at=CHEST, tip=NECK)
    rig.bone("neck", "chest", at=NECK, tip=HEADP)
    rig.bone("head", "neck", at=HEADP, rot=0)
    for s in ("far", "near"):
        rig.bone(f"shoulder_{s}", "chest", at=SH[s], rot=0, length=0)
        rig.bone(f"arm_up_{s}", f"shoulder_{s}", at=SH[s], tip=EL[s])
        rig.bone(f"arm_low_{s}", f"arm_up_{s}", at=EL[s], tip=WR[s])
        rig.bone(f"hand_{s}", f"arm_low_{s}", at=WR[s], tip=TIP[s])
        rig.bone(f"thigh_{s}", "hip", at=HIPJ[s], tip=KNEE[s])
        rig.bone(f"shin_{s}", f"thigh_{s}", at=KNEE[s], tip=ANK[s])
        rig.bone(f"foot_{s}", f"shin_{s}", at=ANK[s], rot=0, length=40)
        rig.bone(f"ik_{s}", "root", at=ANK[s], rot=0, length=30, color="ff5c5cff")
    rig.bone("apple", "root", at=APPLE, rot=0)
    rib = rig.chain("ribbon", "head", [(560, 175), (570, 225), (582, 272), (594, 318)], inherit_first="noRotationOrReflection")
    hairb = rig.chain("hairb", "head", [(560, 190), (585, 245), (600, 300)], inherit_first="noRotationOrReflection")
    hairf = rig.chain("hairf", "head", [(360, 200), (350, 255), (345, 310)], inherit_first="noRotationOrReflection")

    look = rig.look("look", parent="head", at=(440, 180), unit=U)
    zhead = rig.ellipsoid(cx=430, cy=170, rx=160, ry=170)

    for s in ("far", "near"):
        rig.ik(f"leg_{s}", [f"thigh_{s}", f"shin_{s}"], f"ik_{s}", bend_positive=True)
        rig.transform(f"foot_level_{s}", [f"foot_{s}"], f"ik_{s}", mix_rotate=1.0, local=False, relative=False)

    # ---------------------------------------------------------------- parts
    def head_field(rig_, sx, sy):
        base = W.normalize(W.depth("head", "look", zhead)(rig_, sx, sy))
        hb = W.normalize(W.chain(hairb, blend=0.7, root="head", root_blend=0.6)(rig_, sx, sy))
        hf = W.normalize(W.chain(hairf, blend=0.7, root="head", root_blend=0.6)(rig_, sx, sy))
        mb = W.smoothstep(np.clip((sx - 540) / 40.0, 0, 1)) * W.smoothstep(np.clip((sy - 190) / 40.0, 0, 1)) * 0.8
        mf = W.smoothstep(np.clip((380 - sx) / 40.0, 0, 1)) * W.smoothstep(np.clip((sy - 210) / 40.0, 0, 1)) * 0.8
        out = {}
        for d_, w_ in ((base, 1 - mb - mf), (hb, mb), (hf, mf)):
            for k, v in d_.items():
                out[k] = out.get(k, 0) + v * w_
        return out

    def leg_field(s):
        return W.chain([f"thigh_{s}", f"shin_{s}", f"foot_{s}"], blend=0.5, root="hip", root_blend=0.35)

    def torso_field(rig_, sx, sy):
        base = W.normalize(W.chain(["hip", "belly", "chest"], blend=0.8)(rig_, sx, sy))
        out = {k: v.copy() for k, v in base.items()}
        for s in ("far", "near"):
            d = np.hypot(sx - SH[s][0], (sy - SH[s][1]) * 1.2)
            m = W.smoothstep(1 - d / 110.0) * 0.7
            for k in out:
                out[k] = out[k] * (1 - m)
            out[f"shoulder_{s}"] = out.get(f"shoulder_{s}", 0) + m
        return out

    rig.part("apple", "apple", active=False)
    for s in ("far", "near"):
        rig.part(f"leg_{s}", f"thigh_{s}", mesh=dict(cols=4, rows=22), weights=leg_field(s))
    rig.part("torso", "belly", mesh=dict(step=36), weights=torso_field)
    for s in ("far", "near"):
        rig.part(f"hand_{s}", f"hand_{s}", slot=f"hand_{s}")
        rig.part(f"fist_{s}", f"hand_{s}", slot=f"hand_{s}", active=False)
        rig.part(f"arm_{s}", f"arm_up_{s}", mesh=dict(cols=4, rows=16), weights=W.chain([f"arm_up_{s}", f"arm_low_{s}"], blend=0.7, root=f"shoulder_{s}", root_blend=0.3))
    rig.part("apple_held", "hand_far", active=False)
    rig.part("head", "head", mesh=dict(step=28), weights=head_field)
    rig.part("ribbon_tail", "head", mesh=dict(cols=3, rows=10), weights=W.chain(rib, blend=0.7, root="head", root_blend=0.3))

    rig.physics_chain(rib, inertia=(0.45, 0.85), strength=(110, 60), damping=(0.82, 0.88))
    rig.physics_chain(hairb, inertia=(0.4, 0.7), strength=(140, 100), damping=(0.84, 0.88), mix=(0.7, 0.9))
    rig.physics_chain(hairf, inertia=(0.4, 0.7), strength=(150, 110), damping=(0.84, 0.88), mix=(0.6, 0.8))

    ORDER = ["apple", "leg_far", "leg_near", "torso", "hand_far", "arm_far", "hand_near", "arm_near", "apple_held", "head", "ribbon_tail"]

    def order(*front_of_torso, behind=()):
        o = [x for x in ORDER if x not in behind]
        i = o.index("torso")
        for b_ in behind:
            o.insert(i, b_)
        return o

    # ---------------------------------------------------------------- stress
    rig.stress("crouch", pose={"hip": {"y": -200}})
    rig.stress("knee_up_near", pose={"ik_near": {"x": -160, "y": 330}})
    rig.stress("kick_near", pose={"ik_near": {"x": -440, "y": 300}, "belly": {"rot": -14}})
    rig.stress("punch_far", pose={"arm_up_far": {"rot": -78}, "arm_low_far": {"rot": -8}}, slots={"hand_far": "fist_far"})
    rig.stress("arm_back_far", pose={"arm_up_far": {"rot": 24}, "arm_low_far": {"rot": -30}})
    rig.stress("arm_fwd_near", pose={"arm_up_near": {"rot": -45}, "arm_low_near": {"rot": -40}})
    rig.stress("arm_back_near", pose={"arm_up_near": {"rot": 24}, "arm_low_near": {"rot": -30}})
    rig.stress("lean_fwd", pose={"belly": {"rot": 12}, "chest": {"rot": 8}})
    rig.stress("tuck", pose={"hip": {"y": 120}, "ik_far": {"x": 40, "y": 360}, "ik_near": {"x": 40, "y": 360}})

    # ---------------------------------------------------------------- animations
    rig.event("step")
    rig.event("hit")
    rig.event("grab")

    a = rig.animation("idle", duration=3.0, loop=True)
    a.osc("chest", "rotate", 0.8, period=3)
    a.osc("hip", "y", 4, period=1.5)
    a.osc("head", "rotate", 1.2, period=3, phase=0.15)
    for s, k in (("far", 1), ("near", -1)):
        a.osc(f"arm_up_{s}", "rotate", 2.0 * k, period=3, phase=0.1)
        a.osc(f"arm_low_{s}", "rotate", 2.5 * k, period=3, phase=0.2)
    a.sway(rib, 2.0, period=1.5, lag=0.1, grow=1.2)
    a.translate("look", [(0, 0, 0), (3.0, 0, 0)])

    # run: feet on IK; stance foot travels back (+x) at the body speed, swing foot arcs forward (-x)
    D, SX, LIFT, ST = 0.6, 150.0, 120.0, 0.42
    SPEED = 2 * SX / (ST * D)

    def foot(phase):
        def split(t):
            p = (t / D + phase) % 1.0
            return p, (p - ST) / (1 - ST)

        def fx(t):
            p, u = split(t)
            if p < ST:
                return -SX + 2 * SX * p / ST
            m = 2 * SX / ST * (1 - ST)
            return (2 * u ** 3 - 3 * u ** 2 + 1) * SX + (u ** 3 - 2 * u ** 2 + u) * m + (-2 * u ** 3 + 3 * u ** 2) * -SX + (u ** 3 - u ** 2) * m

        def fy(t):
            p, u = split(t)
            return 0.0 if p < ST else LIFT * 16 * u * u * (1 - u) ** 2

        def fr(t):
            p, u = split(t)
            return 0.0 if p < ST else (-25 * math.sin(math.pi * u / 0.6) ** 2 if u < 0.6 else 10 * math.sin(math.pi * (u - 0.6) / 0.4) ** 2)
        return fx, fy, fr

    a = rig.animation("run", duration=D, loop=True)
    for s, ph in (("far", 0.0), ("near", 0.5)):
        fx, fy, fr = foot(ph)
        a.fn(f"ik_{s}", "x", fx, n=36)
        a.fn(f"ik_{s}", "y", fy, n=36)
        a.fn(f"ik_{s}", "rotate", lambda t, fr=fr: -fr(t), n=36)
    a.osc("hip", "y", 14, period=D / 2, phase=0.0, bias=-36)
    a.rotate("belly", [(0, 9), (D, 9)])
    a.rotate("chest", [(0, 4), (D, 4)])
    a.osc("chest", "rotate", 2.5, period=D / 2, phase=0.3)
    a.osc("head", "rotate", 2, period=D / 2, phase=0.45)
    a.rotate("head", [(0, -9), (D, -9)])
    for s, ph in (("far", 0.0), ("near", 0.5)):
        a.osc(f"arm_up_{s}", "rotate", 24 if s == "far" else 9, period=D, phase=ph + 0.25)
        a.rotate(f"arm_low_{s}", [(0, -38), (D, -38)])
        a.osc(f"arm_low_{s}", "rotate", 14, period=D, phase=ph + 0.35)
        a.attachment(f"hand_{s}", [(0, f"fist_{s}")])
    a.sway(rib, 9, period=D / 2, lag=0.06, grow=1.2, phase=0.2)
    a.sway(hairb, 5, period=D / 2, lag=0.06, grow=1.15, phase=0.15)
    a.sway(hairf, 4, period=D / 2, lag=0.06, grow=1.15, phase=0.1)
    a.draw_order_list(0, order(behind=("hand_far", "arm_far")))
    a.event(round(D * (1 - 0.0) % D, 3), "step")
    a.event(round(D * 0.5, 3), "step")

    # jump: crouch -> launch (stretch) -> tuck -> land (squash) -> settle
    a = rig.animation("jump", duration=1.4)
    Hj = 300
    a.translate("hip", [(0, 0, 0), (0.22, 0, -160, "out"), (0.34, 0, 30), (0.62, 0, Hj, "in"), (0.86, 0, 60, "in"), (0.94, 0, -150, "out"), (1.15, 0, -20), (1.4, 0, 0)])
    for s, dx in (("far", 40), ("near", 30)):
        a.translate(f"ik_{s}", [(0, 0, 0), (0.33, 0, 0, "out"), (0.5, dx, Hj - 140), (0.62, dx, Hj - 150, "in"), (0.86, 0, 40, "in"), (0.92, 0, 0), (1.4, 0, 0)])
    a.rotate("belly", [(0, 0), (0.22, 10), (0.36, -4), (0.62, 6), (0.94, 12), (1.2, 2), (1.4, 0)])
    a.rotate("head", [(0, 0), (0.22, -6), (0.4, 6), (0.94, -8), (1.2, 0), (1.4, 0)])
    for s, k in (("far", 1), ("near", -1)):
        lim = 1.0 if s == "far" else 0.2
        a.rotate(f"arm_up_{s}", [(0, 0), (0.22, (25 * k + 10) * lim), (0.36, -60 * lim), (0.62, -45 * lim), (0.94, 20 * lim), (1.2, 0), (1.4, 0)])
        a.rotate(f"arm_low_{s}", [(0, 0), (0.36, -20), (0.62, -30), (0.94, -10), (1.4, 0)])
    a.sway(rib, 10, period=0.7, lag=0.08, grow=1.2)

    # attack: far-hand jab (straight forward), then near-leg front kick; body turns into each strike
    a = rig.animation("attack", duration=1.6)
    for s in ("far", "near"):
        a.attachment(f"hand_{s}", [(0, f"fist_{s}"), (1.45, f"hand_{s}")])
    a.translate("hip", [(0, 0, 0), (0.1, 0, -60), (0.2, -20, -70), (0.32, -40, -60), (0.55, -20, -40), (0.7, 0, -30), (0.82, 20, -10), (1.0, 0, 0), (1.3, 0, -20), (1.6, 0, 0)])
    # jab
    a.rotate("arm_up_far", [(0, 0), (0.1, 12), (0.18, -78, "out"), (0.32, -78), (0.45, -10), (0.6, 20), (1.3, 10), (1.6, 0)])
    a.rotate("arm_low_far", [(0, 0), (0.1, -60), (0.18, -6, "out"), (0.32, -6), (0.45, -60), (1.3, -30), (1.6, 0)])
    a.rotate("arm_up_near", [(0, 0), (0.1, -6), (0.18, 8), (0.32, 8), (0.6, -8), (0.95, -8), (1.3, 0), (1.6, 0)])
    a.rotate("arm_low_near", [(0, 0), (0.1, -50), (0.32, -40), (0.6, -60), (1.3, -20), (1.6, 0)])
    a.rotate("belly", [(0, 0), (0.1, -4), (0.18, 8, "out"), (0.32, 8), (0.62, -12), (0.82, -16), (1.0, -10), (1.3, -2), (1.6, 0)])
    a.rotate("chest", [(0, 0), (0.18, 6), (0.32, 6), (0.82, -6), (1.3, 0), (1.6, 0)])
    # front kick with the near leg
    a.translate("ik_near", [(0, 0, 0), (0.55, 0, 0), (0.68, -60, 260, "out"), (0.8, -420, 340, "out"), (0.95, -420, 340), (1.12, -120, 200), (1.3, 0, 0), (1.6, 0, 0)])
    a.rotate("ik_near", [(0, 0), (0.68, 30), (0.8, 50), (0.95, 50), (1.2, 0), (1.6, 0)])
    a.rotate("head", [(0, 0), (0.18, -4), (0.82, 6), (1.3, 0), (1.6, 0)])
    a.sway(rib, 10, period=0.8, lag=0.08, grow=1.2)
    a.draw_order_list(0, ORDER)
    a.event(0.18, "hit")
    a.event(0.8, "hit")

    # pick up: squat deep, lean in, the far hand reaches the apple at the toes; grab (apple moves to the hand), stand up
    PK = json.loads((HERE / "pickup.json").read_text()) if (HERE / "pickup.json").is_file() else {"hip": -340, "belly": 30, "chest": 16, "arm_up": -10, "arm_low": 6, "dx": -40}
    a = rig.animation("pickup", duration=2.6)
    a.translate("hip", [(0, 0, 0), (0.35, 0, -60), (0.8, PK["dx"], PK["hip"], "out"), (1.15, PK["dx"], PK["hip"]), (1.65, 0, -40), (1.95, 0, 0), (2.6, 0, 0)])
    a.rotate("belly", [(0, 0), (0.8, PK["belly"]), (1.15, PK["belly"]), (1.65, 4), (2.0, 0), (2.6, 0)])
    a.rotate("chest", [(0, 0), (0.8, PK["chest"]), (1.15, PK["chest"]), (1.65, 0), (2.6, 0)])
    a.rotate("head", [(0, 0), (0.6, 8), (1.15, 8), (1.7, -4), (2.2, 0), (2.6, 0)])
    a.translate("look", [(0, 0, 0), (0.6, -0.4 * U, -0.6 * U), (1.15, -0.4 * U, -0.6 * U), (1.7, -0.6 * U, 0.1 * U), (2.6, 0, 0)])
    a.rotate("arm_up_far", [(0, 0), (0.8, PK["arm_up"]), (1.15, PK["arm_up"]), (1.65, 10), (2.0, -38), (2.6, -38)])
    a.rotate("arm_low_far", [(0, 0), (0.8, PK["arm_low"]), (1.15, PK["arm_low"]), (1.65, -40), (2.0, -96), (2.6, -96)])
    a.rotate("arm_up_near", [(0, 0), (0.8, 8), (1.15, 8), (1.8, 0), (2.6, 0)])
    a.attachment("hand_far", [(0, "hand_far"), (1.0, "fist_far")])
    a.attachment("apple", [(0, "apple"), (1.0, None)])
    a.attachment("apple_held", [(0, None), (1.0, "apple_held")])
    a.translate("apple", [(0, PK.get("ax", 0), 0), (2.6, PK.get("ax", 0), 0)])
    a.sway(rib, 6, period=1.3, lag=0.1, grow=1.2)
    a.event(1.0, "grab")

    rig.contract(
        title="米丫子 Miyazi（全身）", background="#3a4152", mix={"default": 0.15},
        animations={
            "idle": {"label": "待機", "loop": True, "track": 0, "role": "base"},
            "run": {"label": "跑步", "loop": True, "track": 0, "role": "base", "speed": round(SPEED, 1), "facing": "left", "feet": ["ik_far", "ik_near"]},
            "jump": {"label": "跳躍", "role": "action", "return": "idle"},
            "attack": {"label": "攻擊", "role": "action", "return": "idle"},
            "pickup": {"label": "撿東西", "role": "action", "return": "idle"},
        },
        facing={"mode": "flip"},
    )
