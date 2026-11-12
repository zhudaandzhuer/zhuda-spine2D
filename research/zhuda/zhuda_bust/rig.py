"""Zhuda (豬大) bust, front -- every visible pixel comes from the user's design sheet (src/sheet_pitch.png, panels
正面平視 / 正面向上 / 正面向下), cut by extract.py.  `spk build` calls build(rig).

Look up / down swap to the sheet's own drawn up / down heads (a short cross-fade, with the level head's face already
moving that way), so the pitched poses are the designer's drawings, not a warp.  Expressions use the level head.
Canvas = the level panel at 3x (1020 x 954), x right, y down.
"""
import json
from pathlib import Path

from spinekit import weights as W

NAME = "zhuda"
HERE = Path(__file__).resolve().parent
REP = json.loads((HERE / "extract-report.json").read_text())
F = REP["features"]
EYE = {s: (F[f"eye_{s}"]["cx"], F[f"eye_{s}"]["cy"]) for s in "LR"}
BROW = {s: (F[f"brow_{s}"]["cx"], F[f"brow_{s}"]["cy"]) for s in "LR"}
MOUTH = (F["mouth"]["cx"], F["mouth"]["cy"])
PIV = {s: tuple(REP[f"arm_{s}_pivot"]) for s in "LR"}
HAND = {"L": (204, 905), "R": (818, 905)}
U = 30
EXPR = {
    "happy":     dict(eye="happy", brow="soft", mouth="open_m"),
    "laugh":     dict(eye="happy", brow="soft", mouth="laugh", shy=True),
    "angry":     dict(eye="open", brow="angry", mouth="frown"),
    "surprised": dict(eye="wide", brow="up", mouth="o"),
    "shy":       dict(eye="happy", brow="soft", mouth="flat", shy=True),
    "sad":       dict(eye="sad", brow="sad", mouth="frown"),
    "confused":  dict(eye="open", brow=("up", "soft"), mouth="flat"),
    "cry":       dict(eye="cry", brow="sad", mouth="wail", tears=True),
}
EYES = ("open", "closed", "happy", "wide", "sad", "cry")
BROWS = ("soft", "angry", "sad", "up")
MOUTHS = ("smile", "flat", "frown", "open_s", "open_m", "o", "laugh", "wail")
SLOTS_UNUSED = ["arm_L", "arm_R", "body", "wave_back_R", "wave_arm_R", "wave_body_R", "head_level", "eye_L", "eye_R", "brow_L", "brow_R", "mouth", "shy_L", "shy_R", "tear_L", "tear_R", "head_up", "head_down"]


def expr_slots(e):
    out = {}
    br = e["brow"] if isinstance(e["brow"], tuple) else (e["brow"], e["brow"])
    for s, b in zip("LR", br):
        out[f"eye_{s}"] = f"eye_{s}_{e['eye']}"
        out[f"brow_{s}"] = f"brow_{s}_{b}"
        if e.get("shy"):
            out[f"shy_{s}"] = f"shy_{s}"
        if e.get("tears"):
            out[f"tear_{s}"] = f"tear_{s}"
    out["mouth"] = f"mouth_{e['mouth']}"
    return out


def build(rig):
    rig.set_origin(510, 930)
    rig.frame(-60, -40, 1140, 980)

    rig.bone("root", at=(510, 930))
    rig.bone("body", "root", at=(510, 930), tip=(510, 700))
    rig.bone("head", "body", at=(510, 690), rot=0)
    rig.bone("wave_arm_R", "body", at=(858, 720), tip=(900, 560))     # shoulder of the drawn raised arm
    for s in "LR":
        px, py = PIV[s]
        hx, hy = HAND[s]
        mx, my = (px + hx) / 2 + (8 if s == "R" else -8), (py + hy) / 2
        rig.bone(f"arm_up_{s}", "body", at=(px, py), tip=(mx, my))
        rig.bone(f"arm_low_{s}", f"arm_up_{s}", at=(mx, my), tip=(hx, hy))

    zhead = rig.ellipsoid(cx=510, cy=420, rx=420, ry=330)
    look = rig.look("look", parent="head", at=(510, 470), unit=U, back="look_back")
    for s in "LR":
        rig.bone(f"eye_{s}", "head", at=EYE[s])
        rig.bone(f"brow_{s}", "head", at=BROW[s])
        rig.bone(f"tear_{s}", "head", at=(EYE[s][0], EYE[s][1] + 80))
        rig.bone(f"shy_{s}", "head", at=(262 if s == "L" else 762, 488))
        look.follow(f"eye_{s}", rig.depth_at(zhead, *EYE[s]))
        look.follow(f"brow_{s}", rig.depth_at(zhead, *BROW[s]))
        look.follow(f"tear_{s}", rig.depth_at(zhead, EYE[s][0], EYE[s][1] + 80))
        look.follow(f"shy_{s}", rig.depth_at(zhead, 262 if s == "L" else 762, 488))
    rig.bone("mouth", "head", at=MOUTH)
    look.follow("mouth", rig.depth_at(zhead, *MOUTH))

    # ------------------------------------------------------------------ parts
    for s in "LR":
        rig.part(f"arm_{s}", f"arm_up_{s}", mesh=dict(cols=4, rows=10), weights=W.chain([f"arm_up_{s}", f"arm_low_{s}"], blend=1.2))
    rig.part("body", "body", mesh=dict(step=40), weights=W.chain(["root", "body"], blend=1.2))
    # wave: two drawn frames (arm near the cheek / tilted outward), each = skin behind + raised arm + body side
    for suf in ("", "2"):
        rig.part(f"wave_back_R{suf}", "body", slot="wave_back_R", active=False)
    for suf in ("", "2"):
        rig.part(f"wave_arm_R{suf}", "wave_arm_R", slot="wave_arm_R", active=False)
    for suf in ("", "2"):
        rig.part(f"wave_body_R{suf}", "body", slot="wave_body_R", active=False)
    rig.part("head_level", "head", mesh=dict(step=36), weights=W.depth("head", "look", zhead))
    for s in "LR":
        for k in EYES:
            rig.part(f"eye_{s}_{k}", f"eye_{s}", slot=f"eye_{s}", active=(k == "open"))
    for s in "LR":
        for k in BROWS:
            rig.part(f"brow_{s}_{k}", f"brow_{s}", slot=f"brow_{s}", active=(k == "soft"))
    for k in MOUTHS:
        rig.part(f"mouth_{k}", "mouth", slot="mouth", active=(k == "smile"))
    for s in "LR":
        rig.part(f"shy_{s}", f"shy_{s}", active=False)
    for s in "LR":
        rig.part(f"tear_{s}", f"tear_{s}", active=False)
    rig.part("head_up", "head", active=False)              # the sheet's own drawn heads for the pitched poses
    rig.part("head_down", "head", active=False)
    # turning: whole-figure drawings -- the sheet's own side view and a generated 3/4 in between (mirrored for the right)
    for n in ("turn_q", "turn_q_R", "turn_side", "turn_side_R"):
        rig.part(n, "body", slot="turn", active=False)

    # ------------------------------------------------------------------ stress
    rig.stress("look_left", look={"look": [-1, 0]})
    rig.stress("look_right", look={"look": [1, 0]})
    rig.stress("look_up_mesh", look={"look": [0, 1]})
    rig.stress("look_down_mesh", look={"look": [0, -1]})
    WAVE = {"arm_R": None, "wave_arm_R": "wave_arm_R", "wave_body_R": "wave_body_R", "wave_back_R": "wave_back_R"}
    rig.stress("wave_pose", slots=WAVE)
    rig.stress("wave_pose2", slots={"arm_R": None, "wave_arm_R": "wave_arm_R2", "wave_body_R": "wave_body_R2", "wave_back_R": "wave_back_R2"})
    rig.stress("tilt", pose={"head": {"rot": 7}})
    rig.stress("head_up", slots={"head_level": None, "head_up": "head_up", "eye_L": None, "eye_R": None, "brow_L": None, "brow_R": None, "mouth": None})
    rig.stress("head_down", slots={"head_level": None, "head_down": "head_down", "eye_L": None, "eye_R": None, "brow_L": None, "brow_R": None, "mouth": None})
    for n, e in EXPR.items():
        rig.stress(f"face_{n}", slots=expr_slots(e))

    # ------------------------------------------------------------------ animations
    a = rig.animation("idle", duration=4.0, loop=True)
    a.osc("body", "sy", 0.012, period=2)
    a.osc("body", "sx", 0.006, period=2, phase=0.5)
    a.osc("head", "y", 3.0, period=2, phase=0.1)
    a.osc("head", "rotate", 1.4, period=4, phase=0.2)
    a.osc("look", "x", 0.1 * U, period=4, phase=0.35)
    for s, k in (("L", 1), ("R", -1)):
        a.osc(f"arm_up_{s}", "rotate", 2.0 * k, period=2, phase=0.2)

    a = rig.animation("blink", duration=0.26)
    for s in "LR":
        a.attachment(f"eye_{s}", [(0, f"eye_{s}_open"), (0.07, f"eye_{s}_closed"), (0.17, f"eye_{s}_open")])

    a = rig.animation("talk", duration=0.96, loop=True)
    a.attachment("mouth", [(0, "mouth_smile"), (0.06, "mouth_open_m"), (0.18, "mouth_open_s"), (0.3, "mouth_smile"), (0.4, "mouth_open_m"),
                           (0.54, "mouth_o"), (0.66, "mouth_open_s"), (0.78, "mouth_open_m"), (0.9, "mouth_smile")])
    a.osc("head", "rotate", 1.0, period=0.48)
    a.osc("look", "y", 0.08 * U, period=0.48, phase=0.2)

    # wave: the hanging arm lifts a little, then swaps to drawn raised arms -- two drawings alternated like hand-drawn
    # animation (no bending, no rotation of a drawing); reverse at the end
    a = rig.animation("wave", duration=2.6)
    a.rotate("arm_up_R", [(0, 0), (0.08, -3), (0.2, 26), (2.36, 26), (2.5, 0), (2.6, 0)])
    a.attachment("arm_R", [(0, "arm_R"), (0.2, None), (2.36, "arm_R")])
    seq = [(0, None)]
    t_, k = 0.2, 0
    while t_ < 2.36 - 1e-6:
        seq.append((round(t_, 3), "2" if k % 2 == 0 else ""))
        t_ += 0.12 if k == 0 else 0.21
        k += 1
    seq.append((2.36, None))
    for slot in ("wave_arm_R", "wave_body_R", "wave_back_R"):
        a.attachment(slot, [(tt, None if v is None else slot + v) for tt, v in seq])
    env = [(0, 0), (0.46, 0), (0.58, 1), (1.9, 1), (2.06, 0), (2.6, 0)]
    a.rotate("head", [(0, 0), (0.45, 0), (2.6, 0)])                               # head stays upright: the raised arm is tucked behind its edge
    a.translate("look", [(0, 0, 0), (0.4, 0.15 * U, 0.1 * U), (2.05, 0.15 * U, 0.1 * U), (2.4, 0, 0), (2.6, 0, 0)])
    a.osc("head", "y", 1.5, period=0.42, envelope=env)
    for s in "LR":
        a.attachment(f"eye_{s}", [(0, f"eye_{s}_open"), (0.4, f"eye_{s}_happy"), (2.05, f"eye_{s}_open")])
    a.attachment("mouth", [(0, "mouth_smile"), (0.4, "mouth_open_m"), (2.05, "mouth_smile")])

    # look up / down: the level face slides that way on the head mesh, then -- on the fastest frame -- the head is
    # swapped for the sheet's own drawn up / down head (a clean cut, no cross-fade: two heads half-visible read as a ghost)
    FACE = ["eye_L", "eye_R", "brow_L", "brow_R", "mouth"]

    def swap(a, t_in, t_out, slot):
        a.attachment(slot, [(0, None), (t_in, slot), (t_out, None)])
        a.alpha(slot, [(0, 1), (t_out + 0.01, 1)])
        a.attachment("head_level", [(0, "head_level"), (t_in, None), (t_out, "head_level")])
        for f_ in FACE:
            rest = {"eye_L": "eye_L_open", "eye_R": "eye_R_open", "brow_L": "brow_L_soft", "brow_R": "brow_R_soft", "mouth": "mouth_smile"}[f_]
            a.attachment(f_, [(0, rest), (t_in, None), (t_out, rest)])

    for name, sign, slot in (("look_up", 1, "head_up"), ("look_down", -1, "head_down")):
        a = rig.animation(name, duration=2.0)
        a.translate("look", [(0, 0, 0), (0.16, 0, sign * 0.7 * U, "in"), (0.2, 0, 0), (1.6, 0, 0), (1.64, 0, sign * 0.7 * U, "out"), (1.8, 0, 0), (2.0, 0, 0)])
        a.translate("head", [(0, 0, 0), (0.18, 0, sign * 5), (0.3, 0, sign * 7), (1.6, 0, sign * 7), (1.8, 0, 0), (2.0, 0, 0)])
        a.scale("head", [(0, 1, 1), (0.16, 1.0, 0.985), (0.24, 1.0, 1.01), (0.34, 1, 1), (1.58, 1, 1), (1.66, 1.0, 0.985), (1.76, 1, 1), (2.0, 1, 1)])
        swap(a, 0.18, 1.62, slot)

    a = rig.animation("nod", duration=1.3)            # down -> back up, using the drawn down head
    a.translate("look", [(0, 0, 0), (0.12, 0, -0.7 * U, "in"), (0.15, 0, 0), (0.5, 0, 0), (0.53, 0, -0.7 * U, "out"), (0.66, 0, 0), (1.3, 0, 0)])
    a.translate("head", [(0, 0, 0), (0.14, 0, -7), (0.5, 0, -7), (0.66, 0, 2), (0.85, 0, 0), (1.3, 0, 0)])
    swap(a, 0.13, 0.52, "head_down")

    # turn left / right: anticipation (eyes lead, small squash) -> 3/4 drawing -> side drawing with a soft settle;
    # hold, then the same way back.  Each swap lands on a squash/stretch frame so the change of drawing reads as motion.
    FRONT = ["arm_L", "arm_R", "body", "head_level", "eye_L", "eye_R", "brow_L", "brow_R", "mouth"]
    REST = {"arm_L": "arm_L", "arm_R": "arm_R", "body": "body", "head_level": "head_level", "eye_L": "eye_L_open", "eye_R": "eye_R_open",
            "brow_L": "brow_L_soft", "brow_R": "brow_R_soft", "mouth": "mouth_smile"}
    for name, suf, sx in (("turn_left", "", -1), ("turn_right", "_R", 1)):
        a = rig.animation(name, duration=3.0)
        t_q, t_s, t_bq, t_bf = 0.16, 0.30, 2.36, 2.50
        a.translate("look", [(0, 0, 0), (0.14, sx * 0.6 * U, 0), (t_q, sx * 0.6 * U, 0), (t_bf, sx * 0.6 * U, 0), (2.7, 0, 0), (3.0, 0, 0)])
        for f_ in FRONT:
            a.attachment(f_, [(0, REST[f_]), (t_q, None), (t_bf, REST[f_])])
        a.attachment("turn", [(0, None), (t_q, "turn_q" + suf), (t_s, "turn_side" + suf), (t_bq, "turn_q" + suf), (t_bf, None)])
        a.scale("root", [(0, 1, 1), (0.12, 1.0, 0.975), (t_q, 1.025, 0.985), (0.24, 1.0, 1.0), (t_s, 1.02, 0.985), (0.42, 0.995, 1.008), (0.56, 1, 1),
                         (t_bq - 0.04, 1, 1), (t_bq, 1.02, 0.985), (t_bq + 0.08, 1, 1), (t_bf, 1.02, 0.985), (t_bf + 0.12, 0.995, 1.006), (2.8, 1, 1), (3.0, 1, 1)])
        a.translate("root", [(0, 0, 0), (0.12, 0, -4), (t_s, 0, 3), (0.5, 0, 0), (1.0, 0, 2), (1.5, 0, 0), (2.0, 0, 2), (t_bq, 0, 0), (3.0, 0, 0)])

    for n, e in EXPR.items():
        a = rig.animation(f"face_{n}", duration=0.2)
        for slot, att in expr_slots(e).items():
            a.attachment(slot, [(0, att)])
        if n == "confused":
            a.rotate("head", [(0, 0), (0.2, 7)])
        if n == "shy":
            a.translate("look", [(0, 0, 0), (0.2, -0.4 * U, -0.25 * U)])
        if n == "sad":
            a.translate("look", [(0, 0, 0), (0.2, 0, -0.3 * U)])

    rig.contract(
        title="豬大 Zhuda（半身・正面）",
        animations={
            "idle": {"role": "base", "loop": True, "track": 0},
            "wave": {"role": "action", "return": "idle", "track": 0},
            "look_up": {"role": "action", "return": "idle", "track": 0},
            "look_down": {"role": "action", "return": "idle", "track": 0},
            "nod": {"role": "action", "return": "idle", "track": 0},
            "turn_left": {"role": "action", "return": "idle", "track": 0},
            "turn_right": {"role": "action", "return": "idle", "track": 0},
            "talk": {"role": "overlay", "loop": True, "track": 2},
            "blink": {"role": "overlay", "track": 3, "auto": {"min": 2.0, "max": 5.0}},
            **{f"face_{n}": {"role": "overlay", "hold": True, "track": 1} for n in EXPR},
        },
        controllers={"look": {"bone": "look", "unit": U}},
        mix={"default": 0.15},
    )
