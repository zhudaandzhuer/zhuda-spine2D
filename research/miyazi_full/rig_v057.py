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
MAN = {q["name"]: q for q in json.loads((HERE / "parts" / "manifest.json").read_text())["parts"]}
GY = max(MAN[n]["y"] + MAN[n]["h"] for n in ("leg_far", "leg_near")) - 4
GROUND = (448, GY)
HIP = (448, 880)
CHEST = (450, 640)
NECK = (452, 330)
HEADP = (452, 300)
SH = {"far": (335, 380), "near": (560, 360)}
EL = {"far": (282, 540), "near": (615, 540)}
WR = {"far": (185, 706), "near": (700, 706)}
TIP = {"far": (95, 860), "near": (805, 870)}
HIPJ = {"far": (380, 880), "near": (515, 880)}
KNEE = {"far": (342, 1220), "near": (548, 1220)}
ANK = {"far": (318, 1520), "near": (572, 1520)}
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
    rib = rig.chain("ribbon", "head", [(560, 175), (570, 225), (582, 272), (594, 318)])          # turns with the head (never swings across the face)
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
        mb = W.smoothstep(np.clip((sx - 540) / 40.0, 0, 1)) * W.smoothstep(np.clip((sy - 190) / 40.0, 0, 1)) * 0.5
        mf = W.smoothstep(np.clip((380 - sx) / 40.0, 0, 1)) * W.smoothstep(np.clip((sy - 210) / 40.0, 0, 1)) * 0.5
        out = {}
        for d_, w_ in ((base, 1 - mb - mf), (hb, mb), (hf, mf)):
            for k, v in d_.items():
                out[k] = out.get(k, 0) + v * w_
        return out

    def leg_field(s):
        base = W.chain([f"thigh_{s}", f"shin_{s}", f"foot_{s}"], blend=1.0)

        def f(rig_, sx, sy):
            w = W.normalize(base(rig_, sx, sy))
            # crotch / inner top of the jeans: the fabric between the thighs stays with the pelvis and stretches smoothly
            m = W.smoothstep(np.clip((902 - sy) / 40.0, 0, 1)) * 0.85          # the strip under the hem rides with the torso
            out = {k: v * (1 - m) for k, v in w.items()}
            out["belly"] = out.get("belly", 0) + m
            return out
        return f

    def torso_field(rig_, sx, sy):
        base = W.normalize(W.chain(["hip", "belly", "chest"], blend=1.3)(rig_, sx, sy))
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
        rig.part(f"leg_{s}", f"thigh_{s}", mesh=dict(cols=5, rows=30), weights=leg_field(s))
    rig.part("pelvis", "belly")              # tips with the torso when she bends (never shows behind the back)
    for s in ("far", "near"):
        rig.part(f"hand_{s}", f"hand_{s}", slot=f"hand_{s}")
        rig.part(f"fist_{s}", f"hand_{s}", slot=f"hand_{s}", active=False)
        rig.part(f"arm_{s}", f"arm_up_{s}", mesh=dict(cols=5, rows=24), weights=W.chain([f"arm_up_{s}", f"arm_low_{s}"], blend=0.9, root=f"shoulder_{s}", root_blend=0.3))
    rig.part("torso", "belly", mesh=dict(step=36), weights=torso_field)
    rig.part("apple_held", "hand_far", active=False)
    rig.part("head", "head", mesh=dict(step=28), weights=head_field)
    rig.part("ribbon_tail", "head", mesh=dict(cols=3, rows=16), weights=W.chain(rib, blend=1.2, root="head", root_blend=0.3))

    rig.physics_chain(rib, inertia=(0.35, 0.6), strength=(180, 130), damping=(0.86, 0.9), mix=(0.7, 0.8))
    rig.physics_chain(hairb, inertia=(0.4, 0.7), strength=(220, 180), damping=(0.88, 0.9), mix=(0.4, 0.5))
    rig.physics_chain(hairf, inertia=(0.4, 0.7), strength=(220, 180), damping=(0.88, 0.9), mix=(0.35, 0.45))

    ORDER = ["apple", "leg_far", "leg_near", "pelvis", "hand_far", "arm_far", "hand_near", "arm_near", "torso", "apple_held", "head", "ribbon_tail"]

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
    # The art is an A-pose (arms clear of the body, for clean parts).  Every clip starts from a RELAXED pose instead:
    # arms hanging close to the body, elbows soft.  All arm keys below are written relative to it (rel()).
    REL = {"arm_up_far": 16.0, "arm_up_near": -11.0, "arm_low_far": -14.0, "arm_low_near": -12.0}
    FWD = -1.0      # facing screen-left: swinging an arm / bending an elbow forward = negative rotation

    def rel(a, bone, keys, ease="ease"):
        a.rotate(bone, [(k[0], REL[bone] + k[1]) + tuple(k[2:]) for k in keys], ease=ease)

    rig.event("step")
    rig.event("hit")
    rig.event("grab")

    # idle: relaxed, breathing, a slow weight shift, hands drift a little
    a = rig.animation("idle", duration=4.0, loop=True)
    for b in REL:
        rel(a, b, [(0, 0), (4.0, 0)])
    a.osc("chest", "rotate", 0.7, period=4)
    a.osc("belly", "rotate", 0.6, period=4, phase=0.25)
    a.osc("hip", "y", 3, period=2)
    a.osc("hip", "x", 3, period=4, phase=0.1)
    a.osc("head", "rotate", 1.4, period=4, phase=0.2)
    a.osc("look", "x", 0.12 * U, period=4, phase=0.35)
    for s_, k in (("far", 1), ("near", -1)):
        a.osc(f"arm_up_{s_}", "rotate", 1.6 * k, period=2, phase=0.15)
        a.osc(f"arm_low_{s_}", "rotate", 2.0 * k, period=2, phase=0.25)
    a.sway(rib, 2.5, period=2, lag=0.1, grow=1.2)
    a.sway(hairb, 1.2, period=2, lag=0.1, grow=1.1)

    # run: lean in, fists, elbows bent ~75 deg, arms swing opposite to the legs; feet planted on IK (no skating)
    D, SX, LIFT, ST = 0.56, 130.0, 105.0, 0.40
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
            return 0.0 if p < ST else (-30 * math.sin(math.pi * u / 0.55) ** 2 if u < 0.55 else 12 * math.sin(math.pi * (u - 0.55) / 0.45) ** 2)
        return fx, fy, fr

    a = rig.animation("run", duration=D, loop=True)
    for s_, ph in (("far", 0.0), ("near", 0.5)):
        fx, fy, fr = foot(ph)
        a.fn(f"ik_{s_}", "x", fx, n=36)
        a.fn(f"ik_{s_}", "y", fy, n=36)
        a.fn(f"ik_{s_}", "rotate", lambda t, fr=fr: -fr(t), n=36)
    a.osc("hip", "y", 12, period=D / 2, phase=0.0, bias=-40)
    a.rotate("belly", [(0, 12), (D, 12)])
    a.rotate("chest", [(0, 4), (D, 4)])
    a.osc("chest", "rotate", 2.0, period=D / 2, phase=0.3)
    a.rotate("head", [(0, -11), (D, -11)])                     # keeps the face level while the body leans
    a.osc("head", "rotate", 1.5, period=D / 2, phase=0.45)
    for s_, ph, amp in (("far", 0.0, 42), ("near", 0.5, 32)):
        rel(a, f"arm_up_{s_}", [(0, -2), (D, -2)])
        a.osc(f"arm_up_{s_}", "rotate", amp, period=D, phase=ph + 0.75)    # back when the same-side leg is forward (checked on frames)
        rel(a, f"arm_low_{s_}", [(0, -52), (D, -52)])
        a.osc(f"arm_low_{s_}", "rotate", 16, period=D, phase=ph + 0.75)    # elbow closes on the forward swing (fist rises), opens behind
        a.attachment(f"hand_{s_}", [(0, f"fist_{s_}")])
    a.sway(rib, 5, period=D / 2, lag=0.06, grow=1.2, phase=0.2)
    a.sway(hairb, 5, period=D / 2, lag=0.06, grow=1.15, phase=0.15)
    a.sway(hairf, 4, period=D / 2, lag=0.06, grow=1.15, phase=0.1)
    a.draw_order_list(0, ORDER)
    a.event(0.0, "step")
    a.event(round(D * 0.5, 3), "step")

    # jump: arms swing back as she crouches, swing forward-up to launch, knees tuck in the air, squash on landing
    a = rig.animation("jump", duration=1.3)
    Hj = 260
    a.translate("hip", [(0, 0, 0), (0.2, 0, -105, "out"), (0.32, 0, 30), (0.58, 0, Hj, "in"), (0.8, 0, 40, "in"), (0.86, 0, -100, "out"), (1.05, 0, -12), (1.3, 0, 0)])
    for s_, dx in (("far", 90), ("near", 60)):
        a.translate(f"ik_{s_}", [(0, 0, 0), (0.31, 0, 0, "out"), (0.46, dx, Hj + 60), (0.6, dx, Hj + 40, "in"), (0.79, 0, 30, "in"), (0.84, 0, 0), (1.3, 0, 0)])
        a.rotate(f"ik_{s_}", [(0, 0), (0.31, 0), (0.46, 35), (0.62, 28), (0.8, 0), (1.3, 0)])
    a.rotate("belly", [(0, 0), (0.2, 12), (0.32, -2), (0.58, 4), (0.86, 12), (1.05, 3), (1.3, 0)])
    a.rotate("head", [(0, 0), (0.2, -8), (0.36, -10), (0.58, -6), (0.86, -9), (1.05, -2), (1.3, 0)])
    a.translate("look", [(0, 0, 0), (0.2, 0, -0.4 * U), (0.36, 0, 0.6 * U), (0.7, 0, 0.3 * U), (0.86, 0, -0.4 * U), (1.3, 0, 0)])
    # one arm thrown up (fist), the other swung back and down: reads as a jump, not "hands up"
    rel(a, "arm_up_far", [(0, 0), (0.2, 36), (0.34, -105, "out"), (0.58, -92), (0.86, -24), (1.1, 0), (1.3, 0)])
    rel(a, "arm_low_far", [(0, 0), (0.2, -8), (0.34, -40), (0.58, -50), (0.86, -26), (1.1, 0), (1.3, 0)])
    rel(a, "arm_up_near", [(0, 0), (0.2, 30), (0.34, 26, "out"), (0.58, 18), (0.86, -26), (1.1, 0), (1.3, 0)])
    rel(a, "arm_low_near", [(0, 0), (0.2, -8), (0.34, -20), (0.58, -28), (0.86, -26), (1.1, 0), (1.3, 0)])
    for s_ in ("far", "near"):
        a.attachment(f"hand_{s_}", [(0, f"hand_{s_}"), (0.3, f"fist_{s_}"), (0.84, f"hand_{s_}")])
    a.sway(rib, 5, period=0.65, lag=0.08, grow=1.2)

    # attack: guard up, far-hand jab (body steps into it), back to guard, near-leg front kick (chamber, extend, retract)
    a = rig.animation("attack", duration=1.7)
    GU = {"far": (-34, -62), "near": (-24, -58)}           # guard: upper arm forward, elbow folded, fists at chest height
    for s_ in ("far", "near"):
        a.attachment(f"hand_{s_}", [(0, f"fist_{s_}"), (1.5, f"hand_{s_}")])
    a.translate("hip", [(0, 0, 0), (0.14, 0, -55), (0.24, -40, -65), (0.38, -40, -60), (0.55, -10, -45), (0.66, 0, -25), (0.8, 10, -10), (1.08, 0, -20), (1.28, 0, -50), (1.7, 0, 0)])
    a.rotate("belly", [(0, 0), (0.14, 3), (0.22, 11, "out"), (0.38, 9), (0.55, 2), (0.78, -10), (0.9, -10), (1.04, -4), (1.2, 2), (1.7, 0)])
    a.rotate("chest", [(0, 0), (0.22, 6), (0.38, 5), (0.8, -3), (1.7, 0)])
    a.rotate("head", [(0, 0), (0.22, -8), (0.38, -6), (0.8, 4), (1.2, 0), (1.7, 0)])
    gf, gn = GU["far"], GU["near"]
    rel(a, "arm_up_far", [(0, 0), (0.14, gf[0]), (0.22, -88, "out"), (0.36, -88), (0.5, gf[0]), (1.3, gf[0]), (1.6, 0), (1.7, 0)])
    rel(a, "arm_low_far", [(0, 0), (0.14, gf[1]), (0.22, 10, "out"), (0.36, 10), (0.5, gf[1]), (1.3, gf[1]), (1.6, 0), (1.7, 0)])
    rel(a, "arm_up_near", [(0, 0), (0.14, gn[0]), (0.22, gn[0] + 14), (0.36, gn[0] + 14), (0.5, gn[0]), (0.8, gn[0] + 10), (1.3, gn[0]), (1.6, 0), (1.7, 0)])
    rel(a, "arm_low_near", [(0, 0), (0.14, gn[1]), (0.5, gn[1]), (1.3, gn[1]), (1.6, 0), (1.7, 0)])
    a.translate("ik_near", [(0, 0, 0), (0.55, 0, 0), (0.68, -200, 220, "out"), (0.78, -560, 330, "out"), (0.9, -560, 330), (1.02, -200, 220), (1.16, -40, 0, "in"), (1.7, -40, 0)])
    a.rotate("ik_near", [(0, 0), (0.68, 40), (0.78, 75), (0.9, 75), (1.02, 40), (1.16, 0), (1.7, 0)])
    a.sway(rib, 5, period=0.8, lag=0.08, grow=1.2)
    a.draw_order_list(0, ORDER)
    a.event(0.22, "hit")
    a.event(0.8, "hit")

    # pick up: a hip hinge (torso tips forward, standing knee soft) with the near leg lifted behind -- the knees never
    # bend past ~60 deg, so the jeans keep their shape; the far hand reaches the apple, grabs it, she straightens up
    PK = json.loads((HERE / "pickup.json").read_text()) if (HERE / "pickup.json").is_file() else {}
    tilt, hipy, hipx, au, al, ax = PK.get("tilt", 62), PK.get("hipy", -150), PK.get("hipx", 60), PK.get("arm_up", -6), PK.get("arm_low", -10), PK.get("ax", 0)
    a = rig.animation("pickup", duration=2.4)
    a.translate("hip", [(0, 0, 0), (0.25, 0, -30), (0.75, hipx, hipy, "out"), (1.1, hipx, hipy), (1.55, 0, -20), (1.85, 0, 0), (2.4, 0, 0)])
    a.rotate("belly", [(0, 0), (0.25, 4), (0.75, tilt * 0.62, "out"), (1.1, tilt * 0.62), (1.55, 6), (1.9, 0), (2.4, 0)])
    a.rotate("chest", [(0, 0), (0.75, tilt * 0.38, "out"), (1.1, tilt * 0.38), (1.55, 2), (2.4, 0)])
    a.rotate("head", [(0, 0), (0.75, -tilt * 0.35), (1.1, -tilt * 0.35), (1.6, -4), (2.0, 0), (2.4, 0)])
    a.translate("look", [(0, 0, 0), (0.6, -0.3 * U, -0.5 * U), (1.1, -0.3 * U, -0.5 * U), (1.6, -0.4 * U, 0.1 * U), (2.4, 0, 0)])
    a.translate("ik_near", [(0, 0, 0), (0.3, 0, 0), (0.75, 330, 190, "out"), (1.1, 330, 190), (1.55, 60, 40), (1.75, 0, 0), (2.4, 0, 0)])
    a.rotate("ik_near", [(0, 0), (0.75, -35), (1.1, -35), (1.6, 0), (2.4, 0)])
    rel(a, "arm_up_far", [(0, 0), (0.75, au, "out"), (1.1, au), (1.55, 0), (1.95, -30), (2.4, -30)])
    rel(a, "arm_low_far", [(0, 0), (0.75, al, "out"), (1.1, al), (1.55, -30), (1.95, -78), (2.4, -78)])
    rel(a, "arm_up_near", [(0, 0), (0.75, -tilt + 14, "out"), (1.1, -tilt + 14), (1.6, 0), (2.4, 0)])     # hangs (counters the tilt), a touch back
    rel(a, "arm_low_near", [(0, 0), (0.75, -22), (1.1, -22), (1.6, 0), (2.4, 0)])
    a.attachment("hand_far", [(0, "hand_far"), (0.92, "fist_far")])
    a.attachment("apple", [(0, "apple"), (0.92, None)])
    a.attachment("apple_held", [(0, None), (0.92, "apple_held")])
    a.translate("apple", [(0, ax, 0), (2.4, ax, 0)])
    a.sway(rib, 4, period=1.2, lag=0.1, grow=1.2)
    a.event(0.92, "grab")

    # idle while holding the picked-up apple (pickup returns here; the game switches to idle when the item is used)
    a = rig.animation("idle_hold", duration=4.0, loop=True)
    for b_ in REL:
        if b_ not in ("arm_up_far", "arm_low_far"):
            rel(a, b_, [(0, 0), (4.0, 0)])
    rel(a, "arm_up_far", [(0, -30), (4.0, -30)])
    rel(a, "arm_low_far", [(0, -78), (4.0, -78)])
    a.osc("arm_up_far", "rotate", 1.2, period=2, phase=0.15)
    a.attachment("hand_far", [(0, "fist_far")])
    a.attachment("apple_held", [(0, "apple_held")])
    a.osc("chest", "rotate", 0.7, period=4)
    a.osc("hip", "y", 3, period=2)
    a.osc("head", "rotate", 1.4, period=4, phase=0.2)
    a.osc("arm_up_near", "rotate", -1.6, period=2, phase=0.15)
    a.sway(rib, 2.5, period=2, lag=0.1, grow=1.2)

    rig.contract(
        title="米丫子 Miyazi（全身）", background="#3a4152", mix={"default": 0.15},
        animations={
            "idle": {"label": "待機", "loop": True, "track": 0, "role": "base"},
            "run": {"label": "跑步", "loop": True, "track": 0, "role": "base", "speed": round(SPEED, 1), "facing": "left", "feet": ["ik_far", "ik_near"]},
            "jump": {"label": "跳躍", "role": "action", "return": "idle"},
            "attack": {"label": "攻擊", "role": "action", "return": "idle"},
            "pickup": {"label": "撿東西", "role": "action", "return": "idle_hold"},
            "idle_hold": {"label": "拿著蘋果", "loop": True, "track": 0, "role": "base"},
        },
        facing={"mode": "flip"},
    )
