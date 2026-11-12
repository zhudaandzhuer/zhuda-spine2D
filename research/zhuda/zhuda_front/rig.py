"""Zhuda (豬大) -- front view rig, built from the design sheet (key art gen/keyart.png).  `spk build` calls build(rig).

Body plan follows the design, not a human: a big round head sitting on a pear-shaped body (no neck),
short stubby arms and legs with hooves, floppy ears.  Head and body are deforming meshes, the face is a set of
swappable parts on a pseudo-3D look controller, ears have physics, legs stand on IK targets.
Canvas pixels (x right, y down), same as the art.
"""
import math

from spinekit import weights as W

NAME = "zhuda"
GROUND = (512, 1478)
EYE = {"L": (301, 477), "R": (719, 477)}
ARM = {"L": [(300, 905), (232, 1010), (172, 1105)], "R": [(724, 905), (792, 1010), (852, 1105)]}
LEG = {"L": [(365, 1290), (366, 1468)], "R": [(633, 1290), (632, 1468)]}     # one stubby bone per leg: squashes / stretches on IK
EAR = {"L": [(290, 182), (80, 330)], "R": [(734, 182), (944, 330)]}
EXPR = {          # expression -> eyes, brows (L, R), mouth, extras
    "happy":     dict(eye="happy", brow=(None, None), mouth="open_m"),
    "laugh":     dict(eye="happy", brow=(None, None), mouth="laugh", blush=True),
    "angry":     dict(eye="open", brow=("angry", "angry"), mouth="frown"),
    "surprised": dict(eye="wide", brow=("up", "up"), mouth="o"),
    "shy":       dict(eye="happy", brow=("soft", "soft"), mouth="flat", blush=True),
    "sad":       dict(eye="sad", brow=("sad", "sad"), mouth="frown"),
    "confused":  dict(eye="open", brow=("up", "soft"), mouth="flat"),
    "cry":       dict(eye="cry", brow=("sad", "sad"), mouth="wail", tears=True),
}
EYES = ("open", "closed", "happy", "wide", "sad", "cry")
BROWS = ("soft", "angry", "sad", "up")
MOUTHS = ("smile", "flat", "frown", "laugh", "open_s", "open_m", "o", "wail")
U = 34                                   # look controller unit (px)


def _expr_slots(e):
    slots = {}
    for s, i in (("L", 0), ("R", 1)):
        slots[f"eye_{s}"] = f"eye_{s}_{e['eye']}"
        b = e["brow"][i]
        if b:
            slots[f"brow_{s}"] = f"brow_{s}_{b}"
        if e.get("tears"):
            slots[f"tear_{s}"] = f"tear_{s}"
    slots["mouth"] = f"mouth_{e['mouth']}"
    if e.get("blush"):
        slots["blush_shy"] = "blush_shy"
    return slots


def build(rig):
    rig.set_origin(*GROUND)
    rig.frame(-40, -160, 1104, 1700)                 # room above the head for the jump

    # ------------------------------------------------------------------ skeleton
    rig.bone("root", at=GROUND)
    rig.bone("hip", "root", at=(512, 1300), rot=0)
    rig.bone("belly", "hip", at=(512, 1300), tip=(512, 1080))
    rig.bone("chest", "belly", at=(512, 1080), tip=(512, 900))
    rig.bone("head", "chest", at=(512, 890), rot=0)
    for s in "LR":
        a, b, c = ARM[s]
        rig.bone(f"arm_up_{s}", "chest", at=a, tip=b)
        rig.bone(f"arm_low_{s}", f"arm_up_{s}", at=b, tip=c)
        h, f = LEG[s]
        rig.bone(f"leg_{s}", "hip", at=h, tip=f)
        rig.bone(f"ik_{s}", "root", at=f, rot=0, length=30, color="ff5c5cff")
        rig.bone(f"ear_{s}", "head", at=EAR[s][0], tip=EAR[s][1])

    # face on a pseudo-3D surface: moving `look` turns the head a little (near features slide further than far ones)
    zhead = rig.ellipsoid(cx=510, cy=540, rx=470, ry=400)
    look = rig.look("look", parent="head", at=(510, 560), unit=U, back="look_back")
    for s, (x, y) in EYE.items():
        rig.bone(f"eye_{s}", "head", at=(x, y))
        rig.bone(f"brow_{s}", "head", at=(x, y - 62))
        rig.bone(f"tear_{s}", "head", at=(x, y + 110))
        look.follow(f"eye_{s}", rig.depth_at(zhead, x, y))
        look.follow(f"brow_{s}", rig.depth_at(zhead, x, y - 62))
        look.follow(f"tear_{s}", rig.depth_at(zhead, x, y + 110))
        look.follow(f"ear_{s}", 0.35)
    rig.bone("snout", "head", at=(510, 576))
    rig.bone("mouth", "head", at=(509, 744))
    rig.bone("blush", "head", at=(512, 592))
    look.follow("snout", 1.15)
    look.follow("mouth", rig.depth_at(zhead, 509, 744))
    look.follow("blush", 0.9)

    for s in "LR":
        rig.ik(f"leg_ik_{s}", [f"leg_{s}"], f"ik_{s}", stretch=True, compress=True)

    # ------------------------------------------------------------------ parts (manifest order = draw order)
    head_depth = W.depth("head", "look", zhead)
    for s in "LR":
        rig.part(f"leg_{s}", f"leg_{s}", mesh=dict(cols=3, rows=8), weights=W.chain([f"leg_{s}"], root="hip", root_blend=0.3))
    for s in "LR":
        rig.part(f"arm_{s}", f"arm_up_{s}", mesh=dict(cols=4, rows=10), weights=W.chain([f"arm_up_{s}", f"arm_low_{s}"], blend=1.3))
    rig.part("body", "belly", mesh=dict(step=44), weights=W.chain(["belly", "chest"], blend=1.0, root="hip", root_blend=0.6))
    rig.part("head", "head", mesh=dict(step=44), weights=head_depth)
    for s in "LR":
        rig.part(f"ear_{s}", f"ear_{s}", mesh=dict(cols=6, rows=6), weights=W.chain([f"ear_{s}"], root="head", root_blend=0.35))
    rig.part("blush_shy", "blush", active=False)
    for s in "LR":
        for k in EYES:
            rig.part(f"eye_{s}_{k}", f"eye_{s}", slot=f"eye_{s}", active=(k == "open"))
        for k in BROWS:
            rig.part(f"brow_{s}_{k}", f"brow_{s}", slot=f"brow_{s}", active=False)
    rig.part("snout", "snout")
    for k in MOUTHS:
        rig.part(f"mouth_{k}", "mouth", slot="mouth", active=(k == "smile"))
    for s in "LR":
        rig.part(f"tear_{s}", f"tear_{s}", active=False)

    for s in "LR":
        rig.physics(f"ear_{s}", rotate=1, inertia=0.45, strength=110, damping=0.86, mass=1.2, gravity=0)

    # ------------------------------------------------------------------ stress poses
    rig.stress("look_left", look={"look": [-1, 0]})
    rig.stress("look_right", look={"look": [1, 0]})
    rig.stress("look_up", look={"look": [0, 1]})
    rig.stress("look_down", look={"look": [0, -1]})
    rig.stress("crouch", pose={"hip": {"y": -60}, "belly": {"sx": 1.08, "sy": 0.9}})
    rig.stress("hop_tuck", pose={"hip": {"y": 120}, "ik_L": {"y": 90}, "ik_R": {"y": 90}})
    rig.stress("arms_lift", pose={"arm_up_L": {"rot": -64}, "arm_low_L": {"rot": -26}, "arm_up_R": {"rot": 64}, "arm_low_R": {"rot": 26}})
    rig.stress("arms_out", pose={"arm_up_L": {"rot": -60}, "arm_up_R": {"rot": 60}})
    rig.stress("lean_left", pose={"belly": {"rot": 6}, "chest": {"rot": 5}, "head": {"rot": 8}})
    rig.stress("step_L", pose={"ik_L": {"y": 50}, "hip": {"y": -10}})
    for name, e in EXPR.items():
        rig.stress(f"face_{name}", slots=_expr_slots(e))

    # ------------------------------------------------------------------ animations
    rig.event("step")
    rig.event("land")

    a = rig.animation("idle", duration=4.0, loop=True)
    a.osc("hip", "y", 3.0, period=2, phase=0.0)
    a.osc("belly", "sx", 0.012, period=2, phase=0.5)
    a.osc("belly", "sy", 0.012, period=2, phase=0.0)
    a.osc("head", "rotate", 1.4, period=4, phase=0.1)
    a.osc("head", "y", 2.5, period=2, phase=0.12)
    a.osc("look", "x", 0.08 * U, period=4, phase=0.3)
    for s, k in (("L", 1), ("R", -1)):
        a.osc(f"arm_up_{s}", "rotate", 2.5 * k, period=2, phase=0.2)
        a.osc(f"arm_low_{s}", "rotate", 2.0 * k, period=2, phase=0.3)
        a.osc(f"ear_{s}", "rotate", 2.0 * k, period=2, phase=0.25)

    a = rig.animation("blink", duration=0.26)
    for s in "LR":
        a.attachment(f"eye_{s}", [(0, f"eye_{s}_open"), (0.07, f"eye_{s}_closed"), (0.17, f"eye_{s}_open")])

    a = rig.animation("talk", duration=0.96, loop=True)
    a.attachment("mouth", [(0, "mouth_smile"), (0.06, "mouth_open_m"), (0.18, "mouth_open_s"), (0.3, "mouth_smile"), (0.4, "mouth_open_m"), (0.54, "mouth_o"),
                           (0.66, "mouth_open_s"), (0.78, "mouth_open_m"), (0.9, "mouth_smile")])
    a.osc("head", "rotate", 1.2, period=0.48)
    a.osc("look", "y", 0.06 * U, period=0.48, phase=0.2)

    # wave: screen-right arm comes up and waves, head tilts toward it, happy eyes
    a = rig.animation("wave", duration=2.4)
    # the head is huge and the arm short: lift it out to the side so the hoof waves beside the cheek
    a.rotate("arm_up_R", [(0, 0), (0.12, -8), (0.45, 64), (1.9, 64), (2.25, 0), (2.4, 0)])
    a.rotate("arm_low_R", [(0, 0), (0.45, 22), (1.9, 22), (2.25, 0), (2.4, 0)])
    env = [(0, 0), (0.45, 0), (0.6, 1), (1.75, 1), (1.9, 0), (2.4, 0)]
    a.osc("arm_low_R", "rotate", 18, period=0.4, envelope=env)
    a.osc("arm_up_R", "rotate", 5, period=0.4, phase=0.15, envelope=env)
    a.rotate("head", [(0, 0), (0.5, -5), (1.9, -5), (2.3, 0), (2.4, 0)])
    a.rotate("chest", [(0, 0), (0.5, -2), (1.9, -2), (2.3, 0), (2.4, 0)])
    a.translate("look", [(0, 0, 0), (0.4, 0.25 * U, 0.15 * U), (1.9, 0.25 * U, 0.15 * U), (2.3, 0, 0), (2.4, 0, 0)])
    a.translate("hip", [(0, 0, 0), (0.18, 0, -8), (0.42, 0, 4), (0.6, 0, 0), (2.4, 0, 0)])
    a.osc("hip", "y", 3, period=0.4, envelope=env)
    a.rotate("arm_up_L", [(0, 0), (0.5, -10), (1.9, -10), (2.3, 0), (2.4, 0)])
    for s in "LR":
        a.attachment(f"eye_{s}", [(0, f"eye_{s}_open"), (0.45, f"eye_{s}_happy"), (1.9, f"eye_{s}_open")])
    a.attachment("mouth", [(0, "mouth_smile"), (0.45, "mouth_open_m"), (1.9, "mouth_smile")])
    a.draw_order(0.26, {"arm_R": 2})            # a lifted arm is drawn in front of body and head (behind the ears)
    a.draw_order(2.12)

    # jump: anticipation squash -> stretch launch -> airborne tuck -> squash landing -> settle
    a = rig.animation("jump", duration=1.5)
    H = 170
    a.translate("hip", [(0, 0, 0), (0.24, 0, -48, "out"), (0.36, 0, 40, "out"), (0.62, 0, H, "in"), (0.88, 0, 30, "in"), (0.96, 0, -46, "out"), (1.2, 0, 6), (1.35, 0, 0), (1.5, 0, 0)])
    for s in "LR":
        a.translate(f"ik_{s}", [(0, 0, 0), (0.33, 0, 0, "out"), (0.62, 0, H - 30, "in"), (0.9, 0, 0), (1.5, 0, 0)])
    a.scale("belly", [(0, 1, 1), (0.24, 1.12, 0.86, "out"), (0.36, 0.92, 1.12), (0.6, 1.0, 1.02), (0.88, 0.96, 1.06), (0.98, 1.14, 0.84, "out"), (1.18, 0.98, 1.03), (1.35, 1, 1), (1.5, 1, 1)])
    a.translate("head", [(0, 0, 0), (0.24, 0, -14), (0.4, 0, 10), (0.62, 0, 4), (0.98, 0, -18), (1.2, 0, 4), (1.4, 0, 0), (1.5, 0, 0)])
    for s, k in (("L", -1), ("R", 1)):
        a.rotate(f"arm_up_{s}", [(0, 0), (0.24, -18 * k), (0.42, 70 * k), (0.66, 62 * k), (0.95, 20 * k), (1.2, -6 * k), (1.4, 0), (1.5, 0)])
        a.rotate(f"arm_low_{s}", [(0, 0), (0.42, 22 * k), (0.66, 26 * k), (0.95, 10 * k), (1.4, 0), (1.5, 0)])
        a.attachment(f"eye_{s}", [(0, f"eye_{s}_open"), (0.22, f"eye_{s}_closed"), (0.36, f"eye_{s}_wide"), (0.95, f"eye_{s}_happy"), (1.35, f"eye_{s}_open")])
    a.attachment("mouth", [(0, "mouth_smile"), (0.22, "mouth_flat"), (0.36, "mouth_o"), (0.95, "mouth_laugh"), (1.35, "mouth_smile")])
    a.event(0.96, "land")
    a.draw_order(0.32, {"arm_L": 2, "arm_R": 2})
    a.draw_order(1.02)

    # walk in place (front view): stepping with body sway; feet lift on IK, the hip drops at each contact
    D = 0.9
    a = rig.animation("walk_front", duration=D, loop=True)

    def lift(phase):
        return lambda t: 42 * max(0.0, math.sin(2 * math.pi * (t / D + phase))) ** 1.5
    a.fn("ik_L", "y", lift(0.0), 0, D)
    a.fn("ik_R", "y", lift(0.5), 0, D)
    a.osc("hip", "y", 6, period=D / 2, phase=0.25, bias=-4)
    a.osc("hip", "x", 7, period=D, phase=0.0)
    a.osc("belly", "rotate", 3.5, period=D, phase=0.5)
    a.osc("head", "rotate", 2.5, period=D, phase=0.0)
    a.osc("head", "y", 3, period=D / 2, phase=0.35)
    for s, k in (("L", 1), ("R", -1)):
        a.osc(f"arm_up_{s}", "rotate", 14 * k, period=D, phase=0.25 if s == "L" else 0.75)
        a.osc(f"ear_{s}", "rotate", 4, period=D / 2, phase=0.1)
    a.event(0.0, "step")
    a.event(round(D / 2, 3), "step")

    # expressions: hold overlays on track 1 (eyes / brows / mouth / blush / tears + a small attitude)
    for name, e in EXPR.items():
        a = rig.animation(f"face_{name}", duration=0.2)
        for slot, att in _expr_slots(e).items():
            a.attachment(slot, [(0, att)])
        if name == "confused":
            a.rotate("head", [(0, 0), (0.2, 7)])
        if name == "shy":
            a.translate("look", [(0, 0, 0), (0.2, -0.35 * U, -0.3 * U)])
        if name == "laugh":
            a.rotate("head", [(0, 0), (0.2, -3)])
            a.translate("head", [(0, 0, 0), (0.2, 0, 6)])
        if name == "sad":
            a.translate("look", [(0, 0, 0), (0.2, 0, -0.35 * U)])

    rig.contract(
        title="豬大 Zhuda（正面）",
        animations={
            "idle": {"role": "base", "loop": True, "track": 0},
            "walk_front": {"role": "base", "loop": True, "track": 0},
            "wave": {"role": "action", "return": "idle", "track": 0},
            "jump": {"role": "action", "return": "idle", "track": 0},
            "talk": {"role": "overlay", "loop": True, "track": 2},
            "blink": {"role": "overlay", "track": 3, "auto": {"min": 2.0, "max": 5.0}},
            **{f"face_{n}": {"role": "overlay", "hold": True, "track": 1} for n in EXPR},
        },
        controllers={"look": {"bone": "look", "unit": U}},
        mix={"default": 0.15},
    )
