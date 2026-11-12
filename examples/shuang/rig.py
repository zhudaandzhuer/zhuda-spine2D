"""霜 (Shuang) -- rig.  `spk build` imports this file and calls build(rig).

Coordinates are canvas pixels shared with art.py through design.py.  _L/_R = screen left/right.
"""
import numpy as np

import design as D
from spinekit import weights as W

NAME = "shuang"

HAIR_COLOR = "6f86c9ff"


def build(rig):
    rig.frame(*D.FRAME)
    rig.set(padding=4, bleed=6, pma=False, max_influences=4)

    # ------------------------------------------------------------------------------------- body
    rig.bone("root", at=D.ROOT)
    rig.bone("hip", "root", at=D.HIP, tip=D.WAIST)
    rig.bone("waist", "hip", at=D.WAIST, tip=D.CHEST)
    rig.bone("chest", "waist", at=D.CHEST, tip=(500, 560))
    for s, sh, el, wr in (("L", D.SHOULDER_L, D.ELBOW_L, D.WRIST_L), ("R", D.SHOULDER_R, D.ELBOW_R, D.WRIST_R)):
        rig.bone(f"shoulder_{s}", "chest", at=sh, rot=0, length=0)
        rig.bone(f"arm_up_{s}", f"shoulder_{s}", at=sh, tip=el)
        rig.bone(f"arm_low_{s}", f"arm_up_{s}", at=el, tip=wr)
    rig.bone("neck", "chest", at=D.NECK, tip=D.HEAD)
    rig.bone("head", "neck", at=D.HEAD, rot=0, length=0)          # axis-aligned: look offsets read as screen x/y

    # ------------------------------------------------------------------------------------- head: look + face
    zface = rig.ellipsoid(**D.face_depth_params())
    look = rig.look("look", parent="head", at=D.FACE_C, unit=D.LOOK_UNIT, back="look_back")
    for s, eye, brow in (("L", D.EYE_L, D.BROW_L), ("R", D.EYE_R, D.BROW_R)):
        rig.bone(f"eye_{s}", "head", at=eye)
        rig.bone(f"iris_{s}", f"eye_{s}", at=eye)
        rig.bone(f"lid_{s}", f"eye_{s}", at=(eye[0], eye[1] - 12))
        rig.bone(f"lid_low_{s}", f"eye_{s}", at=(eye[0], eye[1] + 12))
        rig.bone(f"brow_{s}", "head", at=brow)
        look.follow(f"eye_{s}", rig.depth_at(zface, *eye))
        look.follow(f"brow_{s}", rig.depth_at(zface, *brow))
    rig.bone("nose", "head", at=D.NOSE)
    rig.bone("mouth", "head", at=D.MOUTH)
    look.follow("nose", 1.12)                                       # the nose tip sits in front of the face surface
    look.follow("mouth", rig.depth_at(zface, *D.MOUTH))
    rig.bone("gaze", "head", at=(500, 320), color="ff8a5cff")      # second controller: where the irises point
    g = rig.bones["gaze"]
    rig.transform("gaze_follow", ["iris_L", "iris_R"], "gaze", mix_x=1.0, mix_y=1.0, x=-g.lx, y=-g.ly)

    # ------------------------------------------------------------------------------------- hair bones
    def hanging(prefix, pts, depth):
        """A lock that hangs: keeps its world angle when the head tilts, and follows the look by `depth`."""
        names = rig.chain(prefix, "head", pts, inherit_first="noRotationOrReflection", color=HAIR_COLOR)
        look.follow(names[0], depth)
        return names

    def fringe(prefix, pts, depth):
        names = rig.chain(prefix, "head", pts, color=HAIR_COLOR)
        look.follow(names[0], depth)
        return names

    bang_L = fringe("bang_L", [(426, 196), (426, 250), (426, 300)], 1.0)
    bang_C = fringe("bang_C", [(500, 192), (500, 248), (500, 298)], 1.04)
    bang_R = fringe("bang_R", [(574, 196), (574, 250), (574, 300)], 1.0)
    cheek_L = hanging("cheek_L", [(386, 236), (385, 306), (385, 376), (386, 444)], 0.5)
    cheek_R = hanging("cheek_R", [D.flip(p) for p in [(386, 236), (385, 306), (385, 376), (386, 444)]], 0.5)
    long_pts = [(378, 240), (366, 380), (358, 520), (357, 650), (364, 780), (372, 900), (378, 976)]
    side_pts = [(366, 254), (346, 390), (328, 530), (318, 670), (317, 790), (326, 904)]
    long_L = hanging("long_L", long_pts, 0.22)
    long_R = hanging("long_R", [D.flip(p) for p in long_pts], 0.22)
    side_L = hanging("side_L", side_pts, 0.08)
    side_R = hanging("side_R", [D.flip(p) for p in side_pts], 0.08)
    back_l = [(404, 300), (374, 450), (352, 600), (346, 750), (360, 900), (392, 1034)]
    back_L = hanging("back_L", back_l, -0.3)
    back_C = hanging("back_C", [(500, 300), (500, 450), (500, 600), (500, 750), (500, 900), (500, 1044)], -0.3)
    back_R = hanging("back_R", [D.flip(p) for p in back_l], -0.3)

    # ------------------------------------------------------------------------------------- parts -> slots (order comes from the art)
    head_depth = W.depth("head", "look", zface)

    def lid_field(side, bone, upper):
        """Eyelid skin: glued to the face surface at its outer edge, carried by the lid bone toward the lash line.
        The hand-over is zero at both eye corners, so closing bends the lash from an arch into a downward curve."""
        cx = (D.EYE_L if side == "L" else D.EYE_R)[0]
        x_out, x_in = (417.0, 475.0) if side == "L" else (583.0, 525.0)
        up = D.EYE_UP_L if side == "L" else D.mx(D.EYE_UP_L)
        low = D.EYE_LOW_L if side == "L" else D.mx(D.EYE_LOW_L)
        curve = sorted(up if upper else low)
        xs_c, ys_c = [p[0] for p in curve], [p[1] for p in curve]

        def mask(sx, sy):
            u = np.clip((sx - min(x_out, x_in)) / abs(x_in - x_out), 0, 1)
            across = np.sin(np.pi * u) ** 0.7
            edge = np.interp(sx, xs_c, ys_c)                      # lash line height at this x
            if upper:
                # full hand-over is reached 8 px above the lash line, so the whole lash band moves as one piece
                start = D.LID_TOP_Y + D.LID_FEATHER + 2.0            # the feathered top edge stays put (never over the eye)
                ramp = np.clip((sy - start) / np.maximum(edge - 8.0 - start, 1.0), 0, 1)
            else:
                ramp = np.clip(((edge + 16) - sy) / 14.0, 0, 1)
            return across * W.smoothstep(ramp)
        return W.blend(head_depth, W.rigid(bone), mask)

    back_field = W.layered(W.sheet([back_L, back_C, back_R], blend=0.6, root="head", root_blend=0.9), base="head", front="look", back="look_back", z=lambda sx, sy: np.full(sx.shape, -0.3))
    rig.part("hair_back", "head", mesh=dict(step=46), weights=back_field)
    rig.part("collar_back", "chest")
    rig.part("neck", "neck", mesh=dict(step=34), weights=W.chain(["chest", "neck"], blend=0.6))

    def torso_field(rig_, sx, sy):
        base = W.normalize(W.chain(["hip", "waist", "chest"], blend=0.7)(rig_, sx, sy))
        out = {k: v.copy() for k, v in base.items()}
        for s, sh in (("L", D.SHOULDER_L), ("R", D.SHOULDER_R)):
            d = np.hypot(sx - sh[0], (sy - sh[1]) * 1.3)
            m = W.smoothstep(1 - d / 120.0) * 0.85                 # shoulder caps ride the shoulder bones
            for k in out:
                out[k] = out[k] * (1 - m)
            out[f"shoulder_{s}"] = m
        return out
    rig.part("torso", "chest", mesh=dict(step=46), weights=torso_field)
    for s in "LR":
        rig.part(f"arm_{s}", f"arm_up_{s}", mesh=dict(cols=3, rows=14), weights=W.chain([f"arm_up_{s}", f"arm_low_{s}"], blend=0.5, root=f"shoulder_{s}", root_blend=0.25))
    rig.part("collar_L", "chest")
    rig.part("collar_R", "chest")
    rig.part("hair_side_L", "head", mesh=dict(cols=3, rows=22), weights=W.chain(side_L, blend=0.7, root="head", root_blend=0.5))
    rig.part("hair_side_R", "head", mesh=dict(cols=3, rows=22), weights=W.chain(side_R, blend=0.7, root="head", root_blend=0.5))
    rig.part("hair_long_L", "head", mesh=dict(cols=3, rows=26), weights=W.chain(long_L, blend=0.7, root="head", root_blend=0.5))
    rig.part("hair_long_R", "head", mesh=dict(cols=3, rows=26), weights=W.chain(long_R, blend=0.7, root="head", root_blend=0.5))
    for s in "LR":
        rig.part(f"eye_white_{s}", f"eye_{s}")
    for s in "LR":
        rig.part(f"iris_{s}", f"iris_{s}")
    rig.part("face", "head", mesh=dict(step=22), weights=head_depth)
    rig.part("blush", "head", mesh=dict(step=30), weights=head_depth, color="ffffff00")
    for s in "LR":
        rig.part(f"lower_lid_{s}", f"eye_{s}", mesh=dict(step=7, cull=False), weights=lid_field(s, f"lid_low_{s}", upper=False))
    for s in "LR":
        rig.part(f"eyelid_{s}", f"eye_{s}", mesh=dict(step=7, cull=False), weights=lid_field(s, f"lid_{s}", upper=True))
    rig.part("nose", "nose")
    rig.part("mouth_neutral", "mouth", slot="mouth")
    for k in ("smile", "open_s", "open_m", "o"):
        rig.part(f"mouth_{k}", "mouth", slot="mouth", active=False)
    rig.part("hair_cheek_L", "head", mesh=dict(cols=3, rows=14), weights=W.chain(cheek_L, blend=0.7, root="head", root_blend=0.45))
    rig.part("hair_cheek_R", "head", mesh=dict(cols=3, rows=14), weights=W.chain(cheek_R, blend=0.7, root="head", root_blend=0.45))
    rig.part("hair_top", "head", mesh=dict(step=26), weights=head_depth)
    rig.part("bang_L", "head", mesh=dict(cols=5, rows=6), weights=W.chain(bang_L, blend=0.9))
    rig.part("bang_R", "head", mesh=dict(cols=5, rows=6), weights=W.chain(bang_R, blend=0.9))
    rig.part("bang_C", "head", mesh=dict(cols=5, rows=6), weights=W.chain(bang_C, blend=0.9))
    rig.part("brow_L", "brow_L")
    rig.part("brow_R", "brow_R")

    # ------------------------------------------------------------------------------------- physics (Spine 4.2)
    for ch in (bang_L, bang_C, bang_R):
        rig.physics_chain(ch, inertia=(0.35, 0.6), strength=(190, 150), damping=(0.8, 0.82), mix=(0.6, 1.0))
    for ch in (cheek_L, cheek_R):
        rig.physics_chain(ch, inertia=(0.4, 0.7), strength=(150, 110), damping=(0.82, 0.86))
    for ch in (long_L, long_R, side_L, side_R):
        rig.physics_chain(ch, inertia=(0.4, 0.8), strength=(120, 70), damping=(0.84, 0.9))
    for ch in (back_L, back_C, back_R):
        rig.physics_chain(ch, inertia=(0.35, 0.7), strength=(110, 70), damping=(0.85, 0.9))

    # ------------------------------------------------------------------------------------- range-of-motion poses (rig gate)
    c = D.LID_CLOSE
    rig.stress("look_left", look={"look": [-1, 0]})
    rig.stress("look_right", look={"look": [1, 0]})
    rig.stress("look_up", look={"look": [0, 1]})
    rig.stress("look_down", look={"look": [0, -1]})
    rig.stress("look_down_left", look={"look": [-1, -0.8]})
    rig.stress("tilt_left", pose={"head": {"rot": 9}})
    rig.stress("tilt_right", pose={"head": {"rot": -9}})
    rig.stress("turn_tilt", pose={"head": {"rot": -6}}, look={"look": [0.8, -0.3]})
    rig.stress("lids_half", pose={"lid_L": {"y": -c * 0.5}, "lid_R": {"y": -c * 0.5}})
    rig.stress("lids_closed", pose={"lid_L": {"y": -c}, "lid_R": {"y": -c}})
    rig.stress("smile_eyes", pose={"lid_L": {"y": -c * 0.3}, "lid_R": {"y": -c * 0.3}, "lid_low_L": {"y": 5}, "lid_low_R": {"y": 5}}, slots={"mouth": "mouth_smile"})
    rig.stress("gaze_left", pose={"gaze": {"x": -5, "y": 0}})
    rig.stress("gaze_right_up", pose={"gaze": {"x": 5, "y": 2.5}})
    rig.stress("brows_up", pose={"brow_L": {"y": 6}, "brow_R": {"y": 6}})
    rig.stress("brows_sad", pose={"brow_L": {"rot": -9, "y": 2}, "brow_R": {"rot": 9, "y": 2}})
    for k in ("open_s", "open_m", "o"):
        rig.stress(f"mouth_{k}", slots={"mouth": f"mouth_{k}"})
    rig.stress("breath_in", pose={"chest": {"y": 5, "sy": 1.015}, "shoulder_L": {"y": 3}, "shoulder_R": {"y": 3}})
    rig.stress("shrug", pose={"shoulder_L": {"y": 14}, "shoulder_R": {"y": 14}})
    rig.stress("lean_left", pose={"waist": {"rot": 4}, "chest": {"rot": 3}})
    rig.stress("arms_out", pose={"arm_up_L": {"rot": -12}, "arm_up_R": {"rot": 12}, "arm_low_L": {"rot": -10}, "arm_low_R": {"rot": 10}})
    sway = lambda a: {b: {"rot": a * (0.6 + 0.2 * i)} for ch in (long_L, long_R, side_L, side_R, back_L, back_C, back_R, cheek_L, cheek_R) for i, b in enumerate(ch)}
    rig.stress("hair_sway_left", pose=sway(-7))
    rig.stress("hair_sway_right", pose=sway(7))
    rig.stress("bangs_swing", pose={b: {"rot": 10} for ch in (bang_L, bang_C, bang_R) for b in ch})

    # ------------------------------------------------------------------------------------- animations
    U = D.LOOK_UNIT
    REST = -3.5                                   # lids rest slightly lowered: the calm, half-lidded mood of the design
    hang = [long_L, long_R, side_L, side_R, back_L, back_C, back_R]
    rig.event("nod_down")
    rig.event("gust")

    # idle -- 6 s loop.  Every period divides 6 so the loop closes in position AND velocity.
    a = rig.animation("idle", duration=6.0, loop=True)
    a.osc("chest", "y", 2.2, period=3)                              # breathing, 20 / min
    a.osc("chest", "sy", 0.006, period=3)
    for s_ in "LR":
        a.osc(f"shoulder_{s_}", "y", 1.3, period=3, phase=0.08)     # shoulders arrive a little after the chest
        a.osc(f"arm_up_{s_}", "rotate", 0.35 * (1 if s_ == "L" else -1), period=3, phase=0.12)
    a.osc("waist", "rotate", 0.45, period=6)                        # slow weight shift
    a.osc("neck", "rotate", 0.5, period=6, phase=0.1)
    a.osc("head", "rotate", 0.9, period=6, phase=0.17)
    a.osc("look", "x", 0.10 * U, period=6, phase=0.2)
    a.osc("look", "y", 0.05 * U, period=3, phase=0.3)
    a.osc("gaze", "x", 0.7, period=6, phase=0.05)
    for s_ in "LR":
        a.translate(f"lid_{s_}", [(0, 0, REST), (6, 0, REST)])
        a.osc(f"lid_{s_}", "y", 0.6, period=3, phase=0.4)
    for i, ch in enumerate(hang):
        a.sway(ch, 0.4, period=3, lag=0.07, phase=0.15 + 0.05 * (i % 3), grow=1.1)
    for ch in (cheek_L, cheek_R):
        a.sway(ch, 0.4, period=3, lag=0.08, phase=0.2)
    for ch in (bang_L, bang_C, bang_R):
        a.sway(ch, 0.3, period=3, lag=0.1, phase=0.25)

    # blink -- overlay.  Starts and ends on the resting lid height so it drops in without a twitch.
    c = D.LID_CLOSE
    a = rig.animation("blink", duration=0.34)
    for s_ in "LR":
        a.translate(f"lid_{s_}", [(0, 0, REST, "in"), (0.075, 0, -c, "linear"), (0.125, 0, -c, "out"), (0.34, 0, REST)])
        a.translate(f"lid_low_{s_}", [(0, 0, 0), (0.09, 0, 1.6), (0.34, 0, 0)])
        a.translate(f"brow_{s_}", [(0, 0, 0), (0.09, 0, -1.2), (0.34, 0, 0)])

    # talk -- overlay loop of mouth shapes (swap in real visemes from audio at integration time)
    a = rig.animation("talk", duration=1.6, loop=True)
    seq = ["neutral", "open_s", "open_m", "open_s", "neutral", "o", "open_m", "open_s", "neutral", "open_s", "open_m", "o", "open_s", "neutral"]
    step = 1.6 / (len(seq) - 1)
    a.attachment("mouth", [(round(i * step, 3), f"mouth_{k}") for i, k in enumerate(seq)])
    a.osc("mouth", "y", 0.5, period=0.8)

    # nod -- pitch is look.y; the eyes hold the viewer by drifting the other way
    a = rig.animation("nod", duration=1.4)
    a.translate("look", [(0, 0, 0), (0.13, 0, 0.16 * U), (0.40, 0, -1.0 * U), (0.64, 0, 0.14 * U), (0.86, 0, -0.5 * U), (1.14, 0, 0.04 * U), (1.4, 0, 0)])
    a.translate("head", [(0, 0, 0), (0.13, 0, 1.0), (0.40, 0, -4.0), (0.64, 0, 0.6), (0.86, 0, -2.0), (1.14, 0, 0), (1.4, 0, 0)])
    a.translate("gaze", [(0, 0, 0), (0.40, 0, 2.2), (0.64, 0, -0.3), (0.86, 0, 1.2), (1.14, 0, 0), (1.4, 0, 0)])
    for s_ in "LR":
        a.translate(f"lid_{s_}", [(0, 0, REST), (0.40, 0, REST - 6.0), (0.64, 0, REST), (0.86, 0, REST - 3.0), (1.14, 0, REST), (1.4, 0, REST)])
    a.translate("chest", [(0, 0, 0), (0.40, 0, -1.2), (0.7, 0, 0.4), (1.4, 0, 0)])
    a.event(0.40, "nod_down")

    # shake -- yaw is look.x
    a = rig.animation("shake", duration=1.6)
    xs = [(0, 0), (0.20, -0.85), (0.50, 0.85), (0.78, -0.55), (1.04, 0.3), (1.30, -0.06), (1.6, 0)]
    a.translate("look", [(t, v * U, -0.08 * U * abs(v)) for t, v in xs], ease="smooth")
    a.translate("gaze", [(t, -v * 3.2, 0) for t, v in xs], ease="smooth")
    a.rotate("head", [(t, -v * 2.2) for t, v in xs], ease="smooth")
    for s_ in "LR":
        a.translate(f"lid_{s_}", [(0, 0, REST), (0.25, 0, REST - 5.5), (1.1, 0, REST - 5.5), (1.6, 0, REST)])
        a.rotate(f"brow_{s_}", [(0, 0), (0.25, -6 if s_ == "L" else 6), (1.1, -6 if s_ == "L" else 6), (1.6, 0)])

    # tilt -- curious head tilt, held, then back
    a = rig.animation("tilt", duration=2.6)
    a.pose(0.0).pose(0.14, {"head": {"rot": -1.0}}, ease="ease")
    held = {"head": {"rot": 5.5, "x": -2.0}, "look": {"x": -0.22 * U, "y": 0.16 * U}, "chest": {"rot": -1.0}, "waist": {"rot": -0.8},
            "brow_L": {"y": 3.2}, "brow_R": {"y": 3.2}, "lid_L": {"y": 1.5}, "lid_R": {"y": 1.5}, "gaze": {"x": 1.0, "y": -0.6}}
    a.pose(0.62, held).pose(1.75, held).pose(2.45, {}).pose(2.6, {})

    # look_around -- eyes lead, head follows, eyes settle
    a = rig.animation("look_around", duration=4.4)
    a.translate("gaze", [(0, 0, 0), (0.18, -4.6, 0.4), (0.75, -1.2, 0), (1.55, -1.0, 0), (1.72, 4.8, 0.8), (2.35, 1.2, 0.3), (2.95, 1.0, 0.3), (3.12, 0.5, 2.2), (3.6, 0, 0.6), (4.4, 0, 0)])
    a.translate("look", [(0, 0, 0), (0.12, 0, 0), (0.78, -0.92 * U, -0.06 * U), (1.62, -0.92 * U, -0.06 * U), (2.38, 0.92 * U, 0.05 * U), (3.02, 0.92 * U, 0.05 * U), (3.62, 0.15 * U, 0.42 * U), (4.4, 0, 0)])
    a.rotate("head", [(0, 0), (0.78, 2.0), (1.62, 2.0), (2.38, -2.0), (3.02, -2.0), (3.62, 0), (4.4, 0)])
    a.rotate("chest", [(0, 0), (0.9, 0.8), (1.62, 0.8), (2.5, -0.8), (3.02, -0.8), (3.9, 0), (4.4, 0)])

    # expressions -- overlays that hold their last pose until cleared
    a = rig.animation("smile", duration=0.5)
    for s_ in "LR":
        a.translate(f"lid_{s_}", [(0, 0, REST), (0.4, 0, -c * 0.30), (0.5, 0, -c * 0.30)])
        a.translate(f"lid_low_{s_}", [(0, 0, 0), (0.4, 0, 5.0), (0.5, 0, 5.0)])
        a.translate(f"brow_{s_}", [(0, 0, 0), (0.4, 0, 2.2), (0.5, 0, 2.2)])
        a.rotate(f"brow_{s_}", [(0, 0), (0.4, 4 if s_ == "L" else -4), (0.5, 4 if s_ == "L" else -4)])
    a.attachment("mouth", [(0, "mouth_neutral"), (0.12, "mouth_smile")])
    a.alpha("blush", [(0, 0), (0.45, 0.8), (0.5, 0.8)])

    a = rig.animation("sad", duration=0.7)
    for s_ in "LR":
        a.translate(f"lid_{s_}", [(0, 0, REST), (0.6, 0, -c * 0.40), (0.7, 0, -c * 0.40)])
        a.rotate(f"brow_{s_}", [(0, 0), (0.6, -11 if s_ == "L" else 11), (0.7, -11 if s_ == "L" else 11)])
        a.translate(f"brow_{s_}", [(0, 0, 0), (0.6, 0, 1.6), (0.7, 0, 1.6)])
    a.translate("gaze", [(0, 0, 0), (0.5, -2.6, -2.0), (0.7, -2.6, -2.0)])
    a.attachment("mouth", [(0, "mouth_neutral")])

    # surprised -- a quick gasp; physics throws the hair
    a = rig.animation("surprised", duration=1.5)
    for s_ in "LR":
        a.translate(f"lid_{s_}", [(0, 0, REST), (0.09, 0, 3.0, "ease"), (0.95, 0, 2.2), (1.4, 0, REST), (1.5, 0, REST)])
        a.translate(f"brow_{s_}", [(0, 0, 0), (0.09, 0, 7.5), (0.95, 0, 6.0), (1.4, 0, 0), (1.5, 0, 0)])
        a.translate(f"shoulder_{s_}", [(0, 0, 0), (0.11, 0, 8.0), (0.5, 0, 4.0), (1.3, 0, 0), (1.5, 0, 0)])
    a.translate("head", [(0, 0, 0), (0.10, 0, 5.0), (0.34, 0, 1.5), (1.3, 0, 0), (1.5, 0, 0)])
    a.translate("chest", [(0, 0, 0), (0.10, 0, 4.5), (0.5, 0, 2.5), (1.3, 0, 0), (1.5, 0, 0)])
    a.translate("look", [(0, 0, 0), (0.10, 0, 0.22 * U), (0.9, 0, 0.12 * U), (1.4, 0, 0), (1.5, 0, 0)])
    a.attachment("mouth", [(0, "mouth_neutral"), (0.07, "mouth_o"), (0.95, "mouth_open_s"), (1.12, "mouth_neutral")])

    # hair_wind -- a gust from screen-left: keyed so it plays on any runtime; physics only adds overshoot
    a = rig.animation("hair_wind", duration=3.4)
    env = [(0, 0), (0.55, 1.0), (1.9, 0.85), (3.0, 0), (3.4, 0)]
    gust = [(0.0, "back", [back_L, back_C, back_R], 3.2), (0.04, "long", [long_L, long_R], 4.0), (0.08, "side", [side_L, side_R], 4.8), (0.0, "cheek", [cheek_L, cheek_R], 4.2), (0.02, "bang", [bang_L, bang_C, bang_R], 3.2)]
    for delay, _, chains, amp in gust:
        for ci, ch in enumerate(chains):
            for i, b in enumerate(ch):
                k = amp * (1.13 ** i) * (0.55 if i == 0 else 1.0)
                lag = delay + 0.035 * i
                a.rotate(b, [(0, 0), (0.5 + lag, k), (1.9 + lag, k * 0.8), (3.0 + lag * 0.5, 0), (3.4, 0)], ease="smooth")
                a.osc(b, "rotate", k * 0.28, period=0.68, phase=0.11 * i + 0.17 * ci, envelope=[(0, 0), (0.6, 1), (2.0, 0.9), (3.0, 0), (3.4, 0)])
    for s_ in "LR":
        a.translate(f"lid_{s_}", [(0, 0, REST), (0.5, 0, REST - 5.0), (2.0, 0, REST - 4.0), (3.0, 0, REST), (3.4, 0, REST)])
    a.rotate("head", [(0, 0), (0.6, -1.6), (2.0, -1.2), (3.1, 0), (3.4, 0)])
    a.translate("look", [(0, 0, 0), (0.6, -0.16 * U, 0.05 * U), (2.0, -0.12 * U, 0.04 * U), (3.1, 0, 0), (3.4, 0, 0)])
    a.event(0.3, "gust")

    rig.contract(title="霜 Shuang", background="#7e8ea3", mix={"default": 0.25},
                 animations={
                     "idle": {"label": "待機", "loop": True, "track": 0, "role": "base"},
                     "nod": {"label": "點頭", "role": "action", "return": "idle"},
                     "shake": {"label": "搖頭", "role": "action", "return": "idle"},
                     "tilt": {"label": "歪頭", "role": "action", "return": "idle"},
                     "look_around": {"label": "環顧", "role": "action", "return": "idle"},
                     "surprised": {"label": "驚訝", "role": "action", "return": "idle"},
                     "hair_wind": {"label": "風", "role": "action", "return": "idle"},
                     "smile": {"label": "微笑", "role": "overlay", "track": 1, "hold": True},
                     "sad": {"label": "憂鬱", "role": "overlay", "track": 1, "hold": True},
                     "talk": {"label": "說話", "role": "overlay", "track": 2, "loop": True},
                     "blink": {"label": "眨眼", "role": "overlay", "track": 3, "auto": {"min": 2.2, "max": 5.5}},
                 },
                 controllers={"gaze": {"bone": "gaze", "unit": 4.0, "kind": "translate"}})
