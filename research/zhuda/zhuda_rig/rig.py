"""Zhuda (豬大) -- skeletal battle rig.  One set of parts cut from the full-body base; every move is bones.

Body-first animation for a big-head, short-limb character:
  * the body does the acting (lean, lunge, crouch, squash / stretch); limbs are short rigid nubs that accent it
  * arms never go over the head: they lift to the side or swing across the belly (draw order flips them in front)
  * the club extends the reach: it draws the big arcs the arms cannot
  * rolling = the whole figure is a ball turning about its centre of mass, limbs tucked
Canvas pixels (1024 x 1536), x right, y down.  `spk build` calls build(rig).
"""
import json
import math
from pathlib import Path

from spinekit import weights as W

NAME = "zhuda_rig"
HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "extract-report.json").read_text())
F = R["features"]
GX, GY = R["ground"]
CX = 507
CHIN = R["chin_center"]
COM = (CX, 860)                       # centre of mass: the roll pivot
HIP = (CX, 1000)
SH = {s: tuple(R[f"arm_{s}"]["shoulder"]) for s in "LR"}
HAND = {s: tuple(R[f"arm_{s}"]["hand"]) for s in "LR"}
LEG = {s: (R[f"leg_{s}"][0], 1000) for s in "LR"}
FOOT = {s: (R[f"leg_{s}"][0], GY) for s in "LR"}
GRIP = tuple(R["club_grip"])
CLUB_ANG = R["club_ang"]              # the club rests pointing up and out from the right hoof
CLUB_LEN = R["club_len"]
U = 26                                # look controller unit
EYES = ("open", "closed", "happy", "squeeze", "wide")
MOUTHS = ("smile", "shout", "grit", "o", "open_s")
ORDER = ["shadow", "fx_circle", "fx_slash", "leg_L", "leg_R", "arm_L", "arm_R", "torso", "head", "eye_L", "eye_R", "brow_L", "brow_R",
         "mouth", "club", "fx_dust_L", "fx_dust_R", "fx_impact", "fx_sparkles", "fx_orb", "fx_burst"]


def front(*slots):
    """draw order with the given slots moved in front of the head (arms swinging across the body)"""
    o = [s for s in ORDER if s not in slots]
    i = o.index("mouth") + 1
    return o[:i] + list(slots) + o[i:]


def behind_head(*slots):
    o = [s for s in ORDER if s not in slots]
    i = o.index("head")
    return o[:i] + list(slots) + o[i:]


def face(a, t, eye=None, brow=None, mouth=None):
    for s in "LR":
        if eye:
            a.attachment(f"eye_{s}", [(t, f"eye_{s}_{eye}")])
        if brow:
            a.attachment(f"brow_{s}", [(t, f"brow_{s}_{brow}")])
    if mouth:
        a.attachment("mouth", [(t, f"mouth_{mouth}")])


def build(rig):
    rig.set_origin(GX, GY)
    rig.frame(-200, 150, 1500, 1200)

    # ------------------------------------------------------------------ skeleton
    rig.bone("root", at=(GX, GY))
    rig.bone("com", "root", at=COM, rot=0)                                   # roll / lean pivot
    rig.bone("hip", "com", at=HIP, rot=90, length=40)                          # squash about the hips (local x = up)
    rig.bone("belly", "hip", at=HIP, tip=(CX, 890))
    rig.bone("chest", "belly", at=(CX, 890), tip=(CX, CHIN))
    rig.bone("head", "chest", at=(CX, CHIN), rot=0)
    for s in "LR":
        rig.bone(f"arm_{s}", "chest", at=SH[s], tip=HAND[s])
        rig.bone(f"leg_{s}", "hip", at=LEG[s], tip=FOOT[s])
        rig.bone(f"ik_{s}", "root", at=FOOT[s], rot=0, length=30, color="ff5c5cff")
    ca = math.radians(CLUB_ANG)
    rig.bone("club", "arm_R", at=GRIP, tip=(GRIP[0] + CLUB_LEN * math.cos(ca), GRIP[1] - CLUB_LEN * math.sin(ca)))
    rig.bone("club_tip", "club", at=(GRIP[0] + CLUB_LEN * 0.82 * math.cos(ca), GRIP[1] - CLUB_LEN * 0.82 * math.sin(ca)), rot=0)

    zhead = rig.ellipsoid(cx=CX, cy=560, rx=300, ry=260)
    look = rig.look("look", parent="head", at=(CX, 600), unit=U, back="look_back")
    for k in ("eye_L", "eye_R", "brow_L", "brow_R", "mouth"):
        rig.bone(k, "head", at=(F[k]["cx"], F[k]["cy"]))
        look.follow(k, rig.depth_at(zhead, F[k]["cx"], F[k]["cy"]))

    for s in "LR":
        rig.ik(f"leg_ik_{s}", [f"leg_{s}"], f"ik_{s}", stretch=True, compress=True)

    # effects
    rig.bone("fx_slash", "root", at=(SH["R"][0] + 40, 700), rot=0)
    rig.bone("fx_impact", "club_tip", at=(GRIP[0] + CLUB_LEN * 0.82 * math.cos(ca), GRIP[1] - CLUB_LEN * 0.82 * math.sin(ca)), rot=0)
    for s, sx in (("L", -1), ("R", 1)):
        rig.bone(f"fx_dust_{s}", "root", at=(GX + sx * 230, GY - 50), rot=0)
    rig.bone("circle_floor", "root", at=(GX, GY - 10), rot=0)
    rig.bone("fx_circle", "circle_floor", at=(GX, GY - 10), rot=0)
    rig.bone("fx_sparkles", "root", at=(GX, GY - 260), rot=0)
    rig.bone("fx_orb", "root", at=(CX, 300), rot=0)
    rig.bone("fx_burst", "root", at=(CX + 760, 820), rot=0)

    # ------------------------------------------------------------------ parts (manifest order = setup draw order)
    rig.part("shadow", "root")
    rig.part("fx_circle", "fx_circle", color="ffffff00", blend="additive")
    rig.part("fx_slash", "fx_slash", color="ffffff00")
    for s in "LR":
        rig.part(f"leg_{s}", f"leg_{s}")
    for s in "LR":
        rig.part(f"arm_{s}", f"arm_{s}")
    rig.part("torso", "belly", mesh=dict(step=40), weights=W.chain(["hip", "belly", "chest"], blend=1.0))
    rig.part("head", "head", mesh=dict(step=40), weights=W.depth("head", "look", zhead))
    for s in "LR":
        for k in EYES:
            rig.part(f"eye_{s}_{k}", f"eye_{s}", slot=f"eye_{s}", active=(k == "open"))
    for s in "LR":
        for k in ("soft", "angry", "up"):
            rig.part(f"brow_{s}_{k}", f"brow_{s}", slot=f"brow_{s}", active=(k == "soft"))
    for k in MOUTHS:
        rig.part(f"mouth_{k}", "mouth", slot="mouth", active=(k == "smile"))
    rig.part("club", "club")
    for s in "LR":
        rig.part(f"fx_dust_{s}", f"fx_dust_{s}", color="ffffff00")
    rig.part("fx_impact", "fx_impact", color="ffffff00", blend="additive")
    rig.part("fx_sparkles", "fx_sparkles", color="ffffff00", blend="additive")
    rig.part("fx_orb", "fx_orb", color="ffffff00", blend="additive")
    rig.part("fx_burst", "fx_burst", color="ffffff00", blend="additive")

    # ------------------------------------------------------------------ stress: every joint at its extreme
    rig.stress("crouch", pose={"hip": {"x": -40, "sx": 0.9, "sy": 1.07}})
    rig.stress("stretch", pose={"hip": {"sx": 1.1, "sy": 0.94}})
    rig.stress("lean_back", pose={"com": {"rot": 12}})
    rig.stress("lean_fwd", pose={"com": {"rot": -14}})
    rig.stress("windup", pose={"arm_R": {"rot": 72}, "club": {"rot": 100 - CLUB_ANG - 72}, "com": {"rot": 11}})
    rig.stress("chop", pose={"arm_R": {"rot": -26}, "club": {"rot": -28 - CLUB_ANG + 26}, "com": {"rot": -16}})
    rig.stress("arms_open", pose={"arm_L": {"rot": -50}, "arm_R": {"rot": 50}})
    rig.stress("release", pose={"arm_L": {"rot": 62}, "arm_R": {"rot": 58}, "com": {"rot": -12}})
    rig.stress("legs_tuck", pose={"leg_L": {"x": 58, "rot": -12}, "leg_R": {"x": 58, "rot": 12}})
    rig.stress("head_tilt", pose={"head": {"rot": 10}})
    rig.stress("look_L", look={"look": [-1, 0]})
    rig.stress("look_R", look={"look": [1, 0]})
    rig.stress("roll_90", pose={"com": {"rot": -90}})

    rig.event("hit")
    rig.event("cast")

    # ------------------------------------------------------------------ idle
    a = rig.animation("idle", duration=2.4, loop=True)
    a.osc("hip", "sx", 0.014, period=2.4)                               # breathing (hip local x = up)
    a.osc("hip", "sy", 0.009, period=2.4, phase=0.5)
    a.osc("head", "y", 3, period=2.4, phase=0.12)
    a.osc("head", "rotate", 1.2, period=2.4, phase=0.3)
    a.osc("arm_L", "rotate", -2.5, period=2.4, phase=0.2)
    a.osc("arm_R", "rotate", 2.5, period=2.4, phase=0.25)
    a.osc("club", "rotate", -1.5, period=2.4, phase=0.35)
    a.osc("look", "x", 0.12 * U, period=2.4, phase=0.4)

    # ------------------------------------------------------------------ battle idle: low, springy, ready
    a = rig.animation("battle_idle", duration=0.8, loop=True)
    face(a, 0, brow="angry", mouth="grit")
    a.translate("hip", [(0, -22, 0), (0.8, -22, 0)])                     # crouched (hip local x = up)
    a.osc("hip", "x", 7, period=0.4)
    a.osc("hip", "sx", 0.018, period=0.4, phase=0.5)
    a.osc("hip", "sy", 0.012, period=0.4)
    a.rotate("com", [(0, -3), (0.8, -3)])
    a.osc("com", "rotate", 1.2, period=0.8)
    a.rotate("arm_R", [(0, 18), (0.8, 18)])
    a.rotate("club", [(0, 8), (0.8, 8)])
    a.osc("arm_R", "rotate", 3, period=0.4, phase=0.2)
    a.rotate("arm_L", [(0, 24), (0.8, 24)])                             # left hoof forward (across the belly)
    a.osc("arm_L", "rotate", 4, period=0.4, phase=0.3)
    a.osc("head", "y", 3, period=0.4, phase=0.15)
    a.translate("look", [(0, 0.3 * U, 0), (0.8, 0.3 * U, 0)])
    a.draw_order_list(0, front("arm_L"))

    # ------------------------------------------------------------------ attack: the body throws the club
    a = rig.animation("attack", duration=1.3)
    face(a, 0, brow="angry", mouth="grit")
    face(a, 0.22, eye="open", mouth="shout")
    face(a, 0.36, eye="squeeze")
    face(a, 0.8, eye="open", mouth="grit")
    #   anticipation: sink, lean away, club drawn back behind the head-side
    #   strike: spring up and forward, the lean flips, the club whips over and down in front of the belly
    #   impact: squash, shake, hold; recover to the ready stance
    a.translate("hip", [(0, -22, 0), (0.22, -48, 0, "out"), (0.34, 6, 0, "in"), (0.38, -40, 0), (0.6, -36, 0), (1.0, -22, 0), (1.3, -22, 0)])
    a.scale("hip", [(0, 1, 1), (0.22, 0.9, 1.07, "out"), (0.32, 1.1, 0.94, "in"), (0.38, 0.86, 1.1, "out"), (0.5, 0.97, 1.02), (0.62, 1, 1), (1.3, 1, 1)])
    a.rotate("com", [(0, -3), (0.22, 11, "out"), (0.36, -16, "in"), (0.6, -14), (1.0, -3), (1.3, -3)])
    a.translate("com", [(0, 0, 0), (0.22, -24, 0), (0.36, 46, 0, "in"), (0.62, 40, 0), (1.05, 0, 0), (1.3, 0, 0)])
    # club world angle = CLUB_ANG + arm + club.  wind-up: hoof out at shoulder height, club straight up beside the head;
    # strike: the arm drops down-right and the club chops from straight up to down-right on the target side
    a.rotate("arm_R", [(0, 18), (0.22, 72, "out"), (0.3, 66), (0.37, -26, "in"), (0.6, -22), (0.95, 18), (1.3, 18)])
    a.rotate("club", [(0, 8), (0.22, 100 - CLUB_ANG - 72), (0.3, 112 - CLUB_ANG - 66), (0.37, -28 - CLUB_ANG + 26, "in"), (0.45, -20 - CLUB_ANG + 26), (0.6, -24 - CLUB_ANG + 22), (0.95, 8), (1.3, 8)])
    a.draw_order_list(0.1, behind_head("club", "arm_L") if False else [s for s in front("arm_L") if s != "club"][:front("arm_L").index("head")] + ["club"] + [s for s in front("arm_L") if s != "club"][front("arm_L").index("head"):])
    a.draw_order_list(0.32, front("arm_L"))
    a.rotate("arm_L", [(0, 24), (0.22, -30), (0.37, 40), (0.6, 36), (1.0, 24), (1.3, 24)])
    a.rotate("head", [(0, 0), (0.22, 4), (0.36, -6), (0.6, -5), (1.0, 0), (1.3, 0)])
    a.translate("look", [(0, 0.3 * U, 0), (0.22, -0.2 * U, 0.2 * U), (0.36, 0.6 * U, -0.3 * U), (0.8, 0.5 * U, -0.2 * U), (1.1, 0.3 * U, 0), (1.3, 0.3 * U, 0)])
    a.translate("root", [(0, 0, 0), (0.38, 0, 0), (0.41, 10, -6), (0.44, -8, 4), (0.47, 5, -2), (0.5, 0, 0), (1.3, 0, 0)])
    a.draw_order_list(0, front("arm_L"))
    a.alpha("fx_slash", [(0, 0), (0.31, 0), (0.35, 1), (0.44, 0.8), (0.58, 0), (1.3, 0)])
    a.rotate("fx_slash", [(0, -40), (0.31, -40), (0.44, -58), (0.58, -62), (1.3, -62)])
    a.scale("fx_slash", [(0, 0.62, 0.62), (0.31, 0.62, 0.62), (0.44, 0.75, 0.75), (0.58, 0.78, 0.78), (1.3, 0.78, 0.78)])
    a.translate("fx_slash", [(0, 0, 0), (0.31, 0, 0), (0.37, 46, 0), (1.3, 46, 0)])
    a.alpha("fx_impact", [(0, 0), (0.37, 0), (0.39, 1), (0.5, 0.7), (0.6, 0), (1.3, 0)])
    a.scale("fx_impact", [(0, 0.3, 0.3), (0.37, 0.3, 0.3), (0.46, 1.1, 1.1), (0.6, 1.3, 1.3), (1.3, 1.3, 1.3)])
    for s, sx in (("L", -1), ("R", 1)):
        a.alpha(f"fx_dust_{s}", [(0, 0), (0.38, 0), (0.43, 1), (0.75, 0.5), (0.9, 0), (1.3, 0)])
        a.scale(f"fx_dust_{s}", [(0, 0.4, 0.4), (0.38, 0.4, 0.4), (0.55, 1.0, 1.0), (0.9, 1.2, 1.1), (1.3, 1.2, 1.1)])
        a.translate(f"fx_dust_{s}", [(0, 0, 0), (0.38, 40 if s == "R" else 0, 0), (0.9, sx * 70 + (40 if s == "R" else 0), 16), (1.3, sx * 70, 16)])
    a.event(0.38, "hit")

    # ------------------------------------------------------------------ cast: gather (lean back, arms out wide), release (lunge, both hooves to the target)
    a = rig.animation("cast", duration=2.6)
    face(a, 0, eye="open", brow="soft", mouth="smile")
    face(a, 0.15, eye="closed", mouth="o")
    face(a, 1.28, eye="wide", brow="angry", mouth="shout")
    face(a, 2.1, eye="open", brow="soft", mouth="smile")
    a.translate("hip", [(0, 0, 0), (0.12, -20, 0, "out"), (0.3, 10, 0), (1.15, 14, 0), (1.25, -30, 0, "out"), (1.34, 6, 0), (1.6, -6, 0), (2.2, 0, 0), (2.6, 0, 0)])
    a.scale("hip", [(0, 1, 1), (0.12, 0.93, 1.05), (0.3, 1.06, 0.96), (1.15, 1.08, 0.95), (1.25, 0.9, 1.07), (1.34, 1.06, 0.96), (1.5, 1, 1), (2.6, 1, 1)])
    a.osc("hip", "sx", 0.012, period=0.16, envelope=[(0, 0), (0.4, 0), (0.5, 1), (1.1, 1), (1.2, 0), (2.6, 0)])     # trembling with power
    a.rotate("com", [(0, 0), (0.3, 7), (1.2, 8), (1.32, -12, "in"), (1.7, -10), (2.2, 0), (2.6, 0)])
    a.translate("com", [(0, 0, 0), (1.22, -10, 0), (1.34, 40, 0, "in"), (1.8, 34, 0), (2.25, 0, 0), (2.6, 0, 0)])
    a.rotate("arm_L", [(0, 0), (0.3, -46, "out"), (1.2, -50), (1.32, 62, "in"), (1.8, 58), (2.25, 0), (2.6, 0)])
    a.rotate("arm_R", [(0, 0), (0.3, 46, "out"), (1.2, 50), (1.32, 58, "in"), (1.8, 55), (2.25, 0), (2.6, 0)])
    a.osc("arm_L", "rotate", 4, period=0.16, envelope=[(0, 0), (0.4, 0), (0.5, 1), (1.1, 1), (1.2, 0), (2.6, 0)])
    a.osc("arm_R", "rotate", -4, period=0.16, phase=0.5, envelope=[(0, 0), (0.4, 0), (0.5, 1), (1.1, 1), (1.2, 0), (2.6, 0)])
    a.attachment("club", [(0, "club"), (0.12, None), (2.3, "club")])
    a.draw_order_list(0, ORDER)
    a.draw_order_list(1.3, front("arm_L"))
    a.draw_order_list(2.2, ORDER)
    a.rotate("head", [(0, 0), (0.3, 3), (1.2, 4), (1.32, -5), (1.8, -4), (2.2, 0), (2.6, 0)])
    a.translate("look", [(0, 0, 0), (0.3, 0, 0.5 * U), (1.2, 0, 0.6 * U), (1.32, 0.7 * U, -0.1 * U), (1.9, 0.6 * U, 0), (2.25, 0, 0), (2.6, 0, 0)])
    a.scale("circle_floor", [(0, 1, 0.32), (2.6, 1, 0.32)])
    a.alpha("fx_circle", [(0, 0), (0.12, 0), (0.4, 1), (1.6, 1), (2.1, 0), (2.6, 0)])
    a.scale("fx_circle", [(0, 0.3, 0.3), (0.12, 0.3, 0.3), (0.45, 1.0, 1.0, "out"), (1.3, 1.0, 1.0), (1.36, 1.12, 1.12), (1.6, 1.05, 1.05), (2.6, 1.05, 1.05)])
    a.rotate("fx_circle", [(0, 0), (2.6, -200, "linear")])
    a.alpha("fx_sparkles", [(0, 0), (0.25, 0), (0.45, 1), (1.2, 1), (1.5, 0), (2.6, 0)])
    a.translate("fx_sparkles", [(0, 0, -60), (0.25, 0, -60), (1.5, 0, 200, "linear"), (2.6, 0, 200)])
    # the orb gathers above the head, drops to the hooves on release and flies at the target
    a.alpha("fx_orb", [(0, 0), (0.3, 0), (0.45, 1), (1.62, 1), (1.7, 0), (2.6, 0)])
    a.scale("fx_orb", [(0, 0.1, 0.1), (0.3, 0.1, 0.1), (1.1, 1.0, 1.0), (1.24, 1.15, 1.15), (1.32, 0.8, 0.8), (1.45, 1.05, 1.05), (2.6, 1.05, 1.05)])
    a.osc("fx_orb", "sx", 0.07, period=0.18, envelope=[(0, 0), (0.5, 0), (0.6, 1), (1.2, 1), (1.25, 0), (2.6, 0)])
    a.translate("fx_orb", [(0, 0, 0), (1.26, 0, 0), (1.34, 360, -520, "in"), (1.4, 360, -520), (1.66, 1050, -520, "in"), (2.6, 1050, -520)])
    a.alpha("fx_burst", [(0, 0), (1.62, 0), (1.66, 1), (1.85, 0.8), (2.15, 0), (2.6, 0)])
    a.scale("fx_burst", [(0, 0.3, 0.3), (1.62, 0.3, 0.3), (1.75, 1.1, 1.1, "out"), (2.15, 1.4, 1.4), (2.6, 1.4, 1.4)])
    a.translate("root", [(0, 0, 0), (1.3, 0, 0), (1.33, -8, 0), (1.38, 4, 0), (1.44, 0, 0), (2.6, 0, 0)])
    a.event(1.32, "cast")

    # ------------------------------------------------------------------ roll: crouch, hop, tuck into a ball and spin a full turn, land squashed
    a = rig.animation("roll", duration=1.5)
    face(a, 0, eye="open", mouth="smile")
    face(a, 0.2, eye="squeeze", mouth="o")
    face(a, 1.12, eye="happy", mouth="open_s")
    face(a, 1.45, eye="open", mouth="smile")
    for s in "LR":
        a.constraint("ik", f"leg_ik_{s}", [{"time": 0, "mix": 1}, {"time": 0.24, "mix": 1}, {"time": 0.3, "mix": 0}, {"time": 0.96, "mix": 0}, {"time": 1.04, "mix": 1}, {"time": 1.5, "mix": 1}])
    a.translate("hip", [(0, 0, 0), (0.2, -50, 0, "out"), (0.3, 10, 0), (1.06, 0, 0), (1.12, -50, 0, "out"), (1.3, 6, 0), (1.5, 0, 0)])
    a.scale("hip", [(0, 1, 1), (0.2, 0.86, 1.1, "out"), (0.3, 1.08, 0.94), (0.42, 0.94, 1.04), (0.9, 0.94, 1.04), (1.04, 1.06, 0.96), (1.12, 0.84, 1.12, "out"), (1.3, 1.03, 0.98), (1.5, 1, 1)])
    a.translate("com", [(0, 0, 0), (0.24, 0, 0), (0.62, 0, 260, "out"), (1.0, 0, 0, "in"), (1.5, 0, 0)])
    a.rotate("com", [(0, 0), (0.28, 0), (0.98, -360, "linear"), (1.5, -360)])
    for s, k in (("L", -1), ("R", 1)):
        a.rotate(f"arm_{s}", [(0, 0), (0.2, k * 30), (0.32, k * -25), (0.96, k * -25), (1.1, k * 45), (1.3, 0), (1.5, 0)])
        # tuck: the leg slides up into the body (its rounded top stays hidden behind the torso), only the hoof peeks out
        a.rotate(f"leg_{s}", [(0, 0), (0.3, 0), (0.36, k * 12), (0.96, k * 12), (1.04, 0), (1.5, 0)])
        a.translate(f"leg_{s}", [(0, 0, 0), (0.3, 0, 0), (0.36, 58, 0), (0.96, 58, 0), (1.04, 0, 0), (1.5, 0, 0)])
    a.attachment("club", [(0, "club"), (0.1, None), (1.4, "club")])
    for s, sx in (("L", -1), ("R", 1)):
        a.alpha(f"fx_dust_{s}", [(0, 0), (1.04, 0), (1.1, 1), (1.4, 0), (1.5, 0)])
        a.scale(f"fx_dust_{s}", [(0, 0.4, 0.4), (1.04, 0.4, 0.4), (1.2, 1.0, 1.0), (1.5, 1.2, 1.1)])
        a.translate(f"fx_dust_{s}", [(0, 0, 0), (1.04, 0, 0), (1.45, sx * 60, 14), (1.5, sx * 60, 14)])

    # ------------------------------------------------------------------ hit: knocked back, jelly wobble
    a = rig.animation("hit", duration=0.9)
    face(a, 0, eye="squeeze", brow="up", mouth="o")
    face(a, 0.75, eye="open", brow="soft", mouth="smile")
    a.rotate("com", [(0, 0), (0.06, 16, "out"), (0.3, -4), (0.5, 3), (0.7, 0), (0.9, 0)])
    a.translate("com", [(0, 0, 0), (0.06, -50, 10, "out"), (0.4, -20, 0), (0.7, 0, 0), (0.9, 0, 0)])
    a.scale("hip", [(0, 1, 1), (0.06, 0.86, 1.12), (0.16, 1.08, 0.94), (0.26, 0.95, 1.04), (0.38, 1.03, 0.98), (0.5, 1, 1), (0.9, 1, 1)])
    a.rotate("head", [(0, 0), (0.08, 8), (0.25, -4), (0.4, 2), (0.6, 0), (0.9, 0)])
    a.rotate("arm_L", [(0, 0), (0.08, -50), (0.4, -10), (0.7, 0), (0.9, 0)])
    a.rotate("arm_R", [(0, 0), (0.08, 22), (0.4, 6), (0.7, 0), (0.9, 0)])
    a.rotate("club", [(0, 0), (0.08, -30), (0.25, 8), (0.45, -4), (0.7, 0), (0.9, 0)])

    rig.contract(
        title="豬大 Zhuda（骨骼戰鬥）",
        animations={
            "idle": {"role": "base", "loop": True, "track": 0},
            "battle_idle": {"role": "base", "loop": True, "track": 0},
            "attack": {"role": "action", "return": "battle_idle", "track": 0},
            "cast": {"role": "action", "return": "idle", "track": 0},
            "roll": {"role": "action", "return": "idle", "track": 0},
            "hit": {"role": "action", "return": "idle", "track": 0},
        },
        controllers={"look": {"bone": "look", "unit": U}},
        mix={"default": 0.12},
    )
