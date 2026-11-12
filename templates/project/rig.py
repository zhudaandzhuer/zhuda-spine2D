"""__NAME__ -- rig.  `spk build` imports this file and calls build(rig).  API: docs/20-rig.md, docs/30-animation.md.

All positions are canvas pixels (x right, y down), the same space as the art.
"""
from spinekit import weights as W

NAME = "__NAME__"


def build(rig):
    rig.frame(60, 30, 480, 640)                                   # what a viewer should show (source px)

    # bones: parent first.  tip= points the bone; rot=0 keeps it axis-aligned.
    rig.bone("root", at=(300, 620))
    rig.bone("body", "root", at=(300, 600), tip=(300, 360))
    rig.bone("head", "body", at=(300, 340), rot=0)
    for s, x in (("L", 215), ("R", 385)):
        rig.bone(f"ear_{s}", "head", at=(x, 190), tip=(x, 80))
    tail = rig.chain("tail", "body", [(380, 520), (440, 500), (490, 450), (510, 390), (500, 340)])

    # parts: every part in parts/manifest.json needs exactly one owner (or rig.ignore)
    rig.part("tail", "body", mesh=dict(cols=8, rows=8), weights=W.chain(tail, blend=0.8, root="body", root_blend=0.3))
    rig.part("body", "body", mesh=dict(step=40), weights=W.chain(["root", "body"], blend=1.2))
    for s in "LR":
        rig.part(f"ear_{s}", f"ear_{s}")
    rig.part("head", "head")
    for s in "LR":
        rig.part(f"eye_{s}_open", "head", slot=f"eye_{s}")
        rig.part(f"eye_{s}_closed", "head", slot=f"eye_{s}", active=False)

    rig.physics_chain(tail, inertia=(0.4, 0.8), strength=(120, 70), damping=(0.82, 0.9))
    for s in "LR":
        rig.physics(f"ear_{s}", inertia=0.5, strength=160, damping=0.82)

    # range-of-motion poses: looked at with `spk stress` BEFORE animating
    rig.stress("head_left", pose={"head": {"rot": 12}})
    rig.stress("head_right", pose={"head": {"rot": -12}})
    rig.stress("squash", pose={"body": {"sy": 0.92}, "head": {"y": -6}})
    rig.stress("tail_curl", pose={b: {"rot": 14} for b in tail})
    rig.stress("eyes_closed", slots={"eye_L": "eye_L_closed", "eye_R": "eye_R_closed"})

    # animations: idle first, then one required action at a time
    rig.event("hop")
    a = rig.animation("idle", duration=3.0, loop=True)            # every period divides the duration -> seamless loop
    a.osc("body", "sy", 0.02, period=3)
    a.osc("head", "y", 2.0, period=3, phase=0.1)
    a.osc("head", "rotate", 1.5, period=3, phase=0.2)
    a.sway(tail, 3.0, period=1.5, lag=0.12, grow=1.2)
    for s, k in (("L", 1), ("R", -1)):
        a.osc(f"ear_{s}", "rotate", 2.0 * k, period=3, phase=0.3)

    a = rig.animation("blink", duration=0.2)
    for s in "LR":
        a.attachment(f"eye_{s}", [(0, f"eye_{s}_closed"), (0.12, f"eye_{s}_open")])

    a = rig.animation("hop", duration=0.9)
    a.pose(0.0).pose(0.18, {"body": {"sy": 0.88}, "head": {"y": -8}}).pose(0.42, {"root": {"y": 46}, "body": {"sy": 1.06}}, ease="out")
    a.pose(0.66, {"body": {"sy": 0.9}, "head": {"y": -6}}, ease="in").pose(0.9)
    a.event(0.3, "hop")

    rig.contract(title="__NAME__", animations={
        "idle": {"loop": True, "track": 0, "role": "base"},
        "hop": {"role": "action", "return": "idle"},
        "blink": {"role": "overlay", "track": 1, "auto": {"min": 2.0, "max": 5.0}},
    })
