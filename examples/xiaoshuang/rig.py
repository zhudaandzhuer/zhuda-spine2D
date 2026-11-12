"""小霜 (Xiaoshuang) -- full-body chibi rig: walk, wave, turn.  `spk build` calls build(rig).

Authored facing screen-right.  Facing is controller state (skeleton.scaleX); the `turn` clip passes through a
left-right symmetric front pose and fires the `flip` event there, so the mirror is invisible.
"""
import math

import numpy as np

import design as D
from spinekit import weights as W

NAME = "xiaoshuang"
HAIR = "6f86c9ff"
FAR_TINT = "dfe3edff"          # far-side limbs sit slightly in shade


def build(rig):
    rig.set_origin(*D.ROOT)        # skeleton (0, 0) = the ground point between the feet: what a game moves around
    rig.frame(*D.FRAME)

    # ----------------------------------------------------------------------------------- body
    rig.bone("root", at=D.ROOT)
    rig.bone("hip", "root", at=D.HIP, rot=0)
    rig.bone("waist", "hip", at=D.HIP, tip=D.WAIST_TIP)
    rig.bone("chest", "waist", at=D.WAIST_TIP, tip=D.CHEST_TIP)
    rig.bone("neck", "chest", at=D.NECK, tip=D.HEAD)
    rig.bone("head", "neck", at=D.HEAD, rot=0)
    for s, sh, el, wr, tip in (("n", D.SHOULDER_N, D.ELBOW_N, D.WRIST_N, D.HAND_TIP_N), ("f", D.SHOULDER_F, D.ELBOW_F, D.WRIST_F, D.HAND_TIP_F)):
        rig.bone(f"shoulder_{s}", "chest", at=sh, rot=0)
        rig.bone(f"arm_up_{s}", f"shoulder_{s}", at=sh, tip=el)
        rig.bone(f"arm_low_{s}", f"arm_up_{s}", at=el, tip=wr)
        rig.bone(f"hand_{s}", f"arm_low_{s}", at=wr, tip=tip)
    for s, hp, kn, an in (("n", D.HIP_N, D.KNEE_N, D.ANKLE_N), ("f", D.HIP_F, D.KNEE_F, D.ANKLE_F)):
        rig.bone(f"thigh_{s}", "hip", at=hp, tip=kn)
        rig.bone(f"shin_{s}", f"thigh_{s}", at=kn, tip=an)
        rig.bone(f"foot_{s}", f"shin_{s}", at=an, rot=0, length=40)
        rig.bone(f"ik_{s}", "root", at=an, rot=0, length=30, color="ff5c5cff")     # foot target: stays planted while the hip bobs

    # ----------------------------------------------------------------------------------- controllers
    zhead = rig.ellipsoid(**D.HEAD_DEPTH)
    zbody = rig.ellipsoid(**D.BODY_DEPTH)
    look = rig.look("look", parent="head", at=D.FACE_C, unit=D.LOOK_UNIT, back="look_back")     # head yaw / pitch
    rig.look("turn", parent="chest", at=D.TURN_C, unit=D.TURN_UNIT)                             # torso yaw
    for s, eye in (("L", D.EYE_L), ("R", D.EYE_R)):
        rig.bone(f"eye_{s}", "head", at=eye)
        rig.bone(f"iris_{s}", f"eye_{s}", at=eye)
        rig.bone(f"lid_{s}", f"eye_{s}", at=(eye[0], eye[1] - 16))
        rig.bone(f"brow_{s}", "head", at=(eye[0], 288))
        look.follow(f"eye_{s}", rig.depth_at(zhead, *eye))
        look.follow(f"brow_{s}", rig.depth_at(zhead, eye[0], 288))
    rig.bone("nose", "head", at=D.NOSE)
    rig.bone("mouth", "head", at=D.MOUTH)
    look.follow("nose", 1.1)
    look.follow("mouth", rig.depth_at(zhead, *D.MOUTH))
    rig.bone("gaze", "head", at=(400, 328), color="ff8a5cff")
    g = rig.bones["gaze"]
    rig.transform("gaze_follow", ["iris_L", "iris_R"], "gaze", mix_x=1.0, mix_y=1.0, x=-g.lx, y=-g.ly)

    # ----------------------------------------------------------------------------------- hair + skirt chains
    def hanging(prefix, pts, depth):
        names = rig.chain(prefix, "head", pts, inherit_first="noRotationOrReflection", color=HAIR)
        look.follow(names[0], depth)
        return names

    def fringe(prefix, pts):
        names = rig.chain(prefix, "head", pts, color=HAIR)
        look.follow(names[0], 1.0)
        return names

    M = lambda pts: [D.flip(p) for p in pts]
    bang_L, bang_C, bang_R = fringe("bang_L", [(340, 212), (338, 256), (336, 300)]), fringe("bang_C", [(400, 210), (400, 255), (400, 300)]), fringe("bang_R", M([(340, 212), (338, 256), (336, 300)]))
    cheek_pts = [(307, 236), (306, 300), (306, 362), (307, 420)]
    cheek_L, cheek_R = hanging("cheek_L", cheek_pts, 0.5), hanging("cheek_R", M(cheek_pts), 0.5)
    long_pts = [(304, 268), (297, 340), (292, 420), (295, 496), (303, 556)]
    long_L, long_R = hanging("long_L", long_pts, 0.25), hanging("long_R", M(long_pts), 0.25)
    back_pts = [(334, 300), (322, 400), (318, 500), (332, 590), (350, 640)]
    back_L, back_C, back_R = hanging("back_L", back_pts, -0.3), hanging("back_C", [(400, 300), (400, 400), (400, 500), (400, 590), (400, 650)], -0.3), hanging("back_R", M(back_pts), -0.3)
    skirt_pts = [(366, 520), (344, 576), (326, 630)]
    skirt_L, skirt_C, skirt_R = rig.chain("skirt_L", "hip", skirt_pts), rig.chain("skirt_C", "hip", [(400, 520), (400, 576), (400, 632)]), rig.chain("skirt_R", "hip", M(skirt_pts))

    # ----------------------------------------------------------------------------------- constraints that depend on order
    for s in "nf":
        rig.ik(f"leg_{s}", [f"thigh_{s}", f"shin_{s}"], f"ik_{s}", bend_positive=False)                       # knees bend toward +x (the facing direction)
        rig.transform(f"foot_level_{s}", [f"foot_{s}"], f"ik_{s}", mix_rotate=1.0, local=False, relative=False)   # after IK: the shoe takes the target's roll

    # ----------------------------------------------------------------------------------- parts (slot order comes from the art)
    head_depth = W.depth("head", "look", zhead)

    def lid_field(side):
        x_out, x_in = (322.0, 373.0) if side == "L" else (478.0, 427.0)
        curve = sorted(D.EYE_UP_L if side == "L" else D.mx(D.EYE_UP_L))
        xs_c, ys_c = [q[0] for q in curve], [q[1] for q in curve]

        def mask(sx, sy):
            u = np.clip((sx - min(x_out, x_in)) / abs(x_in - x_out), 0, 1)
            across = np.sin(np.pi * u) ** 0.7
            edge = np.interp(sx, xs_c, ys_c)
            start = D.LID_TOP_Y + D.LID_FEATHER + 2.0
            return across * W.smoothstep(np.clip((sy - start) / np.maximum(edge - 8.0 - start, 1.0), 0, 1))
        return W.blend(head_depth, W.rigid(f"lid_{side}"), mask)

    rig.part("hair_back", "head", mesh=dict(step=40), weights=W.layered(W.sheet([back_L, back_C, back_R], blend=0.6, root="head", root_blend=0.9), base="head", front="look", back="look_back", z=lambda sx, sy: np.full(sx.shape, -0.3)))
    rig.part("arm_f", "arm_up_f", mesh=dict(cols=2, rows=14), weights=W.chain(["arm_up_f", "arm_low_f"], blend=1.1), color=FAR_TINT)
    rig.part("hand_f", "hand_f", color=FAR_TINT)
    rig.part("leg_f", "thigh_f", mesh=dict(cols=2, rows=11), weights=W.chain(["thigh_f", "shin_f"], blend=0.45), color=FAR_TINT)
    rig.part("shoe_f_side", "foot_f", slot="shoe_f", color=FAR_TINT)
    rig.part("shoe_f_front", "foot_f", slot="shoe_f", active=False)
    rig.part("leg_n", "thigh_n", mesh=dict(cols=2, rows=11), weights=W.chain(["thigh_n", "shin_n"], blend=0.45))
    rig.part("shoe_n_side", "foot_n", slot="shoe_n")
    rig.part("shoe_n_front", "foot_n", slot="shoe_n", active=False)
    rig.part("neck", "neck")
    rig.part("torso", "chest", mesh=dict(step=24), weights=W.layered(W.chain(["waist", "chest"], blend=0.9), base="chest", front="turn", z=zbody))
    rig.part("skirt", "hip", mesh=dict(step=22), weights=W.sheet([skirt_L, skirt_C, skirt_R], blend=0.7, root="hip", root_blend=0.5))
    rig.part("long_L", "head", mesh=dict(cols=2, rows=12), weights=W.chain(long_L, blend=0.7, root="head", root_blend=0.5))
    rig.part("long_R", "head", mesh=dict(cols=2, rows=12), weights=W.chain(long_R, blend=0.7, root="head", root_blend=0.5))
    for s in "LR":
        rig.part(f"eye_white_{s}", f"eye_{s}")
    for s in "LR":
        rig.part(f"iris_{s}", f"iris_{s}")
    rig.part("face", "head", mesh=dict(step=24), weights=head_depth)
    rig.part("blush", "head", mesh=dict(step=30), weights=head_depth, color="ffffff00")
    for s in "LR":
        rig.part(f"eyelid_{s}", f"eye_{s}", mesh=dict(step=6, cull=False), weights=lid_field(s))
    rig.part("nose", "nose")
    rig.part("mouth_neutral", "mouth", slot="mouth")
    rig.part("mouth_smile", "mouth", slot="mouth", active=False)
    rig.part("mouth_o", "mouth", slot="mouth", active=False)
    rig.part("cheek_L", "head", mesh=dict(cols=2, rows=10), weights=W.chain(cheek_L, blend=0.7, root="head", root_blend=0.45))
    rig.part("cheek_R", "head", mesh=dict(cols=2, rows=10), weights=W.chain(cheek_R, blend=0.7, root="head", root_blend=0.45))
    rig.part("hair_top", "head", mesh=dict(step=26), weights=head_depth)
    rig.part("bangs", "head", mesh=dict(cols=10, rows=5), weights=W.sheet([bang_L, bang_C, bang_R], blend=0.9))
    rig.part("brow_L", "brow_L")
    rig.part("brow_R", "brow_R")
    rig.part("arm_n", "arm_up_n", mesh=dict(cols=2, rows=14), weights=W.chain(["arm_up_n", "arm_low_n"], blend=1.1))
    rig.part("hand_n", "hand_n", slot="hand_n")
    rig.part("hand_n_open", "hand_n", slot="hand_n", active=False)

    # ----------------------------------------------------------------------------------- physics
    for ch in (bang_L, bang_C, bang_R):
        rig.physics_chain(ch, inertia=(0.35, 0.6), strength=(190, 150), damping=(0.8, 0.82), mix=(0.6, 1.0))
    for ch in (cheek_L, cheek_R, long_L, long_R):
        rig.physics_chain(ch, inertia=(0.4, 0.75), strength=(140, 90), damping=(0.83, 0.88))
    for ch in (back_L, back_C, back_R):
        rig.physics_chain(ch, inertia=(0.35, 0.7), strength=(120, 80), damping=(0.85, 0.9))
    for ch in (skirt_L, skirt_C, skirt_R):
        rig.physics_chain(ch, inertia=(0.45, 0.8), strength=(150, 110), damping=(0.82, 0.86))

    # ----------------------------------------------------------------------------------- animation constants
    U, T = D.LOOK_UNIT, D.TURN_UNIT
    F, TF = 0.55, 0.8                 # how far head / torso are turned in the 3/4 stance
    REST, c = -2.0, D.LID_CLOSE
    hang = [long_L, long_R, back_L, back_C, back_R, cheek_L, cheek_R]
    WAVE_ARM = {"arm_up_n": {"rot": -112}, "arm_low_n": {"rot": -45}}
    FRONT_SHOES = {"shoe_n": "shoe_n_front", "shoe_f": "shoe_f_front"}

    # ----------------------------------------------------------------------------------- range-of-motion poses
    stance = {"look": [F, 0], "turn": [TF, 0]}
    rig.stress("stance_3q", look=stance)
    rig.stress("look_left", look={"look": [-1, 0], "turn": [-1, 0]})
    rig.stress("look_right", look={"look": [1, 0], "turn": [1, 0]})
    rig.stress("look_up", look={"look": [0, 1]})
    rig.stress("look_down", look={"look": [0, -1]})
    rig.stress("lids_closed", pose={"lid_L": {"y": -c}, "lid_R": {"y": -c}})
    rig.stress("smile_front", slots={"mouth": "mouth_smile", **FRONT_SHOES})
    rig.stress("step_n_fwd", pose={"ik_n": {"x": 40, "y": 22, "rot": 14}, "ik_f": {"x": -34}, "hip": {"y": -7}}, look=stance)
    rig.stress("step_n_back", pose={"ik_n": {"x": -40, "y": 10, "rot": -26}, "ik_f": {"x": 30}, "hip": {"y": -7}}, look=stance)
    rig.stress("crouch", pose={"hip": {"y": -34}})
    rig.stress("hop", pose={"hip": {"y": 14}, "ik_n": {"y": 12}, "ik_f": {"y": 12}})
    rig.stress("arms_swing", pose={"arm_up_n": {"rot": -24}, "arm_low_n": {"rot": 4}, "arm_up_f": {"rot": 24}, "arm_low_f": {"rot": 18}}, look=stance)
    rig.stress("wave_up", pose=dict(WAVE_ARM, head={"rot": 4}), slots={"hand_n": "hand_n_open", "mouth": "mouth_smile", **FRONT_SHOES})
    rig.stress("wave_swing", pose={"arm_up_n": {"rot": -112}, "arm_low_n": {"rot": -62}, "hand_n": {"rot": -12}}, slots={"hand_n": "hand_n_open", **FRONT_SHOES})
    rig.stress("lean", pose={"waist": {"rot": -6}, "chest": {"rot": -4}, "head": {"rot": 6}})
    sway = lambda a_: {b: {"rot": a_ * (0.7 + 0.2 * i)} for ch in hang + [skirt_L, skirt_C, skirt_R] for i, b in enumerate(ch)}
    rig.stress("sway_left", pose=sway(-8))
    rig.stress("sway_right", pose=sway(8))
    rig.stress("facing_left", look=stance)
    rig.stress_poses[-1]["seek"]["facing"] = -1                    # the same pose mirrored by the controller

    # ----------------------------------------------------------------------------------- animations
    rig.event("flip")
    rig.event("step")
    rig.event("wave")

    def facing(a, d):
        """Hold the 3/4 stance for a whole clip."""
        a.translate("look", [(0, F * U, 0), (d, F * U, 0)])
        a.translate("turn", [(0, TF * T, 0), (d, TF * T, 0)])
        a.translate("gaze", [(0, 2.0, 0), (d, 2.0, 0)])
        for s in "LR":
            a.translate(f"lid_{s}", [(0, 0, REST), (d, 0, REST)])

    # idle -- 4 s loop in the 3/4 stance
    a = rig.animation("idle", duration=4.0, loop=True)
    facing(a, 4.0)
    a.osc("chest", "y", 1.4, period=2)
    a.osc("chest", "sy", 0.008, period=2)
    a.osc("hip", "y", 0.9, period=2, phase=0.1)                    # knees give a little: the feet stay planted through IK
    a.osc("head", "rotate", 1.3, period=4, phase=0.15)
    a.osc("look", "x", 0.05 * U, period=4, phase=0.3)
    for s, k in (("n", 1), ("f", -1)):
        a.osc(f"arm_up_{s}", "rotate", 1.6 * k, period=2, phase=0.2)
    for i, ch in enumerate(hang):
        a.sway(ch, 0.5, period=2, lag=0.08, phase=0.15 + 0.06 * (i % 3), grow=1.12)
    for ch in (skirt_L, skirt_C, skirt_R):
        a.sway(ch, 0.6, period=2, lag=0.1, phase=0.3)

    # walk -- one cycle = two steps, authored in place; the controller moves the skeleton at SPEED px/s
    DUR, SX, LIFT, STANCE = 0.8, 34.0, 24.0, 0.6
    SPEED = 2 * SX / (STANCE * DUR)

    def foot(phase):
        def split(t):
            p = (t / DUR + phase) % 1.0
            return p, (p - STANCE) / (1 - STANCE)

        def fx(t):
            p, u = split(t)
            if p < STANCE:
                return SX - 2 * SX * p / STANCE                     # planted: travels back at exactly -SPEED
            m = -2 * SX / STANCE * (1 - STANCE)                     # swing leaves and lands at the stance velocity (no slip, no jerk)
            return (2 * u**3 - 3 * u**2 + 1) * -SX + (u**3 - 2 * u**2 + u) * m + (-2 * u**3 + 3 * u**2) * SX + (u**3 - u**2) * m

        def fy(t):
            p, u = split(t)
            return 0.0 if p < STANCE else LIFT * 16 * u * u * (1 - u) ** 2

        def fr(t):
            p, u = split(t)
            if p < STANCE:
                return 0.0
            # toe down after lift-off, toe up before landing; sin^2 so the roll starts and ends with zero speed (no slap at contact)
            return -30 * math.sin(math.pi * u / 0.55) ** 2 if u < 0.55 else 15 * math.sin(math.pi * (u - 0.55) / 0.45) ** 2
        return fx, fy, fr

    PH = 0.3                                   # cycle phase at t=0: the loop seam sits mid-stance, not on a contact
    T_N, T_F = (1 - PH) * DUR, (0.5 - PH) * DUR   # contact times of the near / far foot
    a = rig.animation("walk", duration=DUR, loop=True)
    facing(a, DUR)
    for s, phase in (("n", PH), ("f", PH + 0.5)):
        fx, fy, fr = foot(phase)
        a.fn(f"ik_{s}", "x", fx, n=40)
        a.fn(f"ik_{s}", "y", fy, n=40)
        a.fn(f"ik_{s}", "rotate", fr, n=40)
    a.osc("hip", "y", 2.5, period=DUR / 2, phase=T_F / (DUR / 2) + 0.25, bias=-4.5)   # lowest at each contact, highest mid-stance
    a.osc("hip", "x", 1.5, period=DUR, phase=0.1)
    a.rotate("waist", [(0, -3.0), (DUR, -3.0)])                     # lean into the walk
    a.osc("waist", "rotate", 1.0, period=DUR / 2, phase=0.3)
    a.rotate("head", [(0, 2.5), (DUR, 2.5)])
    a.osc("head", "rotate", 0.9, period=DUR / 2, phase=0.45)
    a.osc("head", "y", 1.2, period=DUR / 2, phase=0.4)
    arm_ph = T_N / DUR + 0.25                                       # near arm is furthest back when the near foot lands in front
    # The torso is drawn near-front, so "forward/back" swing shows as left/right.  Bias each arm toward the body
    # (near arm across the front, far arm behind) or both arms flare outward once per cycle.
    a.osc("arm_up_n", "rotate", 15, period=DUR, phase=arm_ph, bias=7)
    a.osc("arm_up_f", "rotate", 15, period=DUR, phase=arm_ph + 0.5, bias=-7)
    a.osc("arm_low_n", "rotate", 8, period=DUR, phase=arm_ph, bias=10)
    a.osc("arm_low_f", "rotate", 8, period=DUR, phase=arm_ph + 0.5, bias=10)
    for i, ch in enumerate(hang):
        a.sway(ch, 1.2, period=DUR / 2, lag=0.12, phase=0.1 + 0.07 * (i % 3), grow=1.15)
    for ch in (skirt_L, skirt_C, skirt_R):
        a.sway(ch, 2.6, period=DUR / 2, lag=0.14, phase=0.2)
    a.event(round(T_F, 3), "step")
    a.event(round(T_N, 3), "step")

    # wave -- turn to the viewer, raise the near arm, wave, return to the stance
    a = rig.animation("wave", duration=2.6)
    a.translate("look", [(0, F * U, 0), (0.34, 0, 0.1 * U), (2.1, 0, 0.1 * U), (2.5, F * U, 0), (2.6, F * U, 0)])
    a.translate("turn", [(0, TF * T, 0), (0.4, 0.1 * T, 0), (2.1, 0.1 * T, 0), (2.5, TF * T, 0), (2.6, TF * T, 0)])
    a.translate("gaze", [(0, 2.0, 0), (0.3, 0, 0), (2.1, 0, 0), (2.5, 2.0, 0), (2.6, 2.0, 0)])
    a.rotate("arm_up_n", [(0, 0), (0.16, 6), (0.55, -112, "ease"), (2.0, -112), (2.45, 0), (2.6, 0)])
    a.rotate("arm_low_n", [(0, 0), (0.55, -45), (2.0, -45), (2.45, 0), (2.6, 0)])
    a.osc("arm_low_n", "rotate", 15, period=0.36, envelope=[(0, 0), (0.55, 0), (0.75, 1), (1.85, 1), (2.05, 0), (2.6, 0)])
    a.osc("hand_n", "rotate", 12, period=0.36, phase=0.2, envelope=[(0, 0), (0.55, 0), (0.75, 1), (1.85, 1), (2.05, 0), (2.6, 0)])
    a.rotate("head", [(0, 0), (0.5, 4.5), (2.0, 4.5), (2.5, 0), (2.6, 0)])
    a.rotate("chest", [(0, 0), (0.5, 1.5), (2.0, 1.5), (2.5, 0), (2.6, 0)])
    a.translate("hip", [(0, 0, 0), (0.3, 0, -3), (0.55, 0, 2), (0.8, 0, 0), (2.6, 0, 0)])
    a.osc("chest", "y", 1.2, period=0.36, envelope=[(0, 0), (0.6, 0), (0.8, 1), (1.85, 1), (2.05, 0), (2.6, 0)])
    for s in "LR":
        a.translate(f"lid_{s}", [(0, 0, REST), (0.5, 0, -9), (2.0, 0, -9), (2.45, 0, REST), (2.6, 0, REST)])
        a.translate(f"brow_{s}", [(0, 0, 0), (0.5, 0, 3), (2.0, 0, 3), (2.45, 0, 0), (2.6, 0, 0)])
    a.attachment("hand_n", [(0, "hand_n"), (0.3, "hand_n_open"), (2.25, "hand_n")])
    a.attachment("mouth", [(0, "mouth_neutral"), (0.42, "mouth_smile"), (2.2, "mouth_neutral")])
    a.attachment("shoe_n", [(0, "shoe_n_side"), (0.28, "shoe_n_front"), (2.3, "shoe_n_side")])
    a.attachment("shoe_f", [(0, "shoe_f_side"), (0.28, "shoe_f_front"), (2.3, "shoe_f_side")])
    a.alpha("blush", [(0, 0), (0.6, 0.75), (2.0, 0.75), (2.5, 0), (2.6, 0)])
    a.event(0.75, "wave")

    # turn -- head leads to the front, a small hop, FLIP at the symmetric instant, then on to the new 3/4 stance
    a = rig.animation("turn", duration=0.7)
    MID = 0.34
    a.translate("look", [(0, F * U, 0), (0.07, (F + 0.08) * U, 0), (MID, 0, 0), (0.60, (F + 0.06) * U, 0), (0.7, F * U, 0)])
    a.translate("turn", [(0, TF * T, 0), (0.10, TF * T, 0), (MID, 0, 0), (0.58, TF * T, 0), (0.7, TF * T, 0)])
    a.translate("gaze", [(0, 2.0, 0), (0.10, -3.0, 0), (MID, 0, 0), (0.50, 3.0, 0), (0.7, 2.0, 0)])
    a.translate("hip", [(0, 0, 0), (0.11, 0, -6), (0.30, 0, 7), (0.40, 0, 7), (0.57, 0, -5), (0.7, 0, 0)])
    for s, k in (("n", -1), ("f", 1)):
        a.translate(f"ik_{s}", [(0, 0, 0), (0.13, 0, 0), (MID, 0, 11), (0.55, 0, 0), (0.7, 0, 0)])
        a.rotate(f"arm_up_{s}", [(0, 0), (MID, 14 * k), (0.7, 0)])
    for s in "LR":
        a.translate(f"lid_{s}", [(0, 0, REST), (0.7, 0, REST)])
    a.attachment("shoe_n", [(0, "shoe_n_side"), (0.24, "shoe_n_front"), (0.46, "shoe_n_side")])
    a.attachment("shoe_f", [(0, "shoe_f_side"), (0.24, "shoe_f_front"), (0.46, "shoe_f_side")])
    a.event(MID, "flip")

    # blink -- overlay
    a = rig.animation("blink", duration=0.32)
    for s in "LR":
        a.translate(f"lid_{s}", [(0, 0, REST, "in"), (0.075, 0, -c, "linear"), (0.125, 0, -c, "out"), (0.32, 0, REST)])

    rig.contract(title="小霜 Xiaoshuang", background="#8fa0b4", mix={"default": 0.15}, follow=False,
                 animations={
                     "idle": {"label": "待機", "loop": True, "track": 0, "role": "base"},
                     "walk": {"label": "走路", "loop": True, "track": 0, "role": "base", "speed": round(SPEED, 2), "feet": ["ik_n", "ik_f"]},
                     "wave": {"label": "揮手", "role": "action", "return": "idle"},
                     "turn": {"label": "轉身", "role": "action", "return": "idle"},
                     "blink": {"label": "眨眼", "role": "overlay", "track": 3, "auto": {"min": 2.0, "max": 5.0}},
                 },
                 events={"flip": {"action": "toggle_facing"}},
                 patrol={"walk": "walk", "turn": "turn", "min": -330, "max": 330, "portrait": {"min": -120, "max": 120}},
                 frame_portrait=rig.world_rect(150, 130, 500, 750),                       # tighter camera the preview uses on tall screens
                 controllers={"turn": {"manual": True}, "gaze": {"bone": "gaze", "unit": 4.0, "kind": "translate"}})
