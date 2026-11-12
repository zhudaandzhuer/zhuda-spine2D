"""Zhuda (豬大) battle, full body.  Pose drawings (registered on snout + floor by extract.py) are swapped like hand-drawn
key frames, with squash / stretch on the swaps, camera-free shake on impact, and drawn effects on their own bones.
`spk build` calls build(rig).  Canvas 1024 x 1536, x right, y down.
"""
import json
from pathlib import Path

NAME = "zhuda_battle"
HERE = Path(__file__).resolve().parent
REP = json.loads((HERE / "extract-report.json").read_text())
GX, GY = REP["ground_x"], REP["ground_y"]
IMP = REP["impact_c"]
SL = REP["slash_c"]
ORB = REP["orb_c"]
ORB_UP = REP["orb_raise_c"]
POSES = ["base", "stance", "windup", "smash", "cast_raise", "cast_push"]


def build(rig):
    rig.set_origin(GX, GY)
    rig.frame(-60, 140, 1640, 1240)

    rig.bone("root", at=(GX, GY))
    rig.bone("fig", "root", at=(GX, GY), rot=90, length=60)          # squash / stretch about the feet (local x = up)
    rig.bone("fx_slash", "root", at=tuple(SL), rot=0)
    rig.bone("fx_impact", "root", at=tuple(IMP), rot=0)
    rig.bone("fx_dust_L", "root", at=(GX - 230, GY - 50), rot=0)
    rig.bone("fx_dust_R", "root", at=(GX + 230, GY - 50), rot=0)
    rig.bone("circle_floor", "root", at=(GX, GY - 10), rot=0)        # flattened: the circle lies on the floor
    rig.bone("fx_circle", "circle_floor", at=(GX, GY - 10), rot=0)   # spins inside the flattened space
    rig.bone("fx_sparkles", "root", at=(GX, GY - 260), rot=0)
    rig.bone("fx_orb", "root", at=tuple(ORB), rot=0)
    rig.bone("fx_burst", "root", at=(ORB[0] + 520, ORB[1]), rot=0)

    rig.part("shadow", "root")
    rig.part("fx_circle", "fx_circle", color="ffffff00", blend="additive")
    rig.part("fx_slash", "fx_slash", color="ffffff00")              # behind the figure: the arc sweeps behind the head
    for n in POSES:
        rig.part(f"pose_{n}", "fig", slot="fig", active=(n == "base"))
    rig.part("fx_dust_L", "fx_dust_L", color="ffffff00")
    rig.part("fx_dust_R", "fx_dust_R", color="ffffff00")
    rig.part("fx_impact", "fx_impact", color="ffffff00", blend="additive")
    rig.part("fx_sparkles", "fx_sparkles", color="ffffff00", blend="additive")
    rig.part("fx_orb", "fx_orb", color="ffffff00", blend="additive")
    rig.part("fx_burst", "fx_burst", color="ffffff00", blend="additive")

    for n in POSES:
        rig.stress(f"pose_{n}", slots={"fig": f"pose_{n}"})
    rig.stress("squash", slots={"fig": "pose_smash"}, pose={"fig": {"sx": 0.9, "sy": 1.08}})
    rig.stress("stretch", slots={"fig": "pose_windup"}, pose={"fig": {"sx": 1.06, "sy": 0.96}})

    rig.event("hit")
    rig.event("cast")

    # ---------------------------------------------------------------- idle (calm) and battle idle
    a = rig.animation("idle", duration=2.0, loop=True)
    a.attachment("fig", [(0, "pose_base")])
    a.osc("fig", "sx", 0.012, period=2.0)                 # fig's local x points up: sx = height
    a.osc("fig", "sy", 0.008, period=2.0, phase=0.5)

    a = rig.animation("battle_idle", duration=1.2, loop=True)
    a.attachment("fig", [(0, "pose_stance")])
    a.osc("fig", "sx", 0.022, period=0.6)
    a.osc("fig", "sy", 0.014, period=0.6, phase=0.5)
    a.osc("fig", "y", 4, period=1.2)                       # weight shifts side to side (fig y = screen x)

    # ---------------------------------------------------------------- stick attack
    # stance -> anticipation squash -> wind-up (stretch, hold) -> smash (squash, slash arc, impact, dust, shake) -> recover
    a = rig.animation("attack", duration=1.5)
    a.attachment("fig", [(0, "pose_stance"), (0.14, "pose_windup"), (0.42, "pose_smash"), (1.05, "pose_stance")])
    a.scale("fig", [(0, 1, 1), (0.1, 0.94, 1.04, "out"), (0.14, 1.07, 0.95), (0.22, 1.0, 1.0), (0.36, 1.03, 0.98),
                    (0.42, 0.9, 1.08, "out"), (0.5, 0.96, 1.03), (0.62, 1, 1), (1.0, 1, 1), (1.05, 0.96, 1.03), (1.16, 1.02, 0.99), (1.3, 1, 1), (1.5, 1, 1)])
    a.translate("root", [(0, 0, 0), (0.42, 0, 0), (0.45, 12, -6), (0.48, -10, 4), (0.51, 7, -3), (0.54, -4, 2), (0.58, 0, 0), (1.5, 0, 0)])
    a.alpha("fx_slash", [(0, 0), (0.37, 0), (0.41, 1), (0.5, 0.9), (0.64, 0), (1.5, 0)])
    a.scale("fx_slash", [(0, 0.85, 0.85), (0.37, 0.85, 0.85), (0.5, 1.04, 1.04), (0.64, 1.08, 1.08), (1.5, 1.08, 1.08)])
    a.rotate("fx_slash", [(0, 18), (0.37, 18), (0.5, -4), (0.64, -10), (1.5, -10)])
    a.alpha("fx_impact", [(0, 0), (0.42, 0), (0.44, 1), (0.56, 0.7), (0.66, 0), (1.5, 0)])
    a.scale("fx_impact", [(0, 0.3, 0.3), (0.42, 0.3, 0.3), (0.5, 1.15, 1.15), (0.78, 1.35, 1.35), (1.5, 1.35, 1.35)])
    a.rotate("fx_impact", [(0, 0), (0.42, 0), (0.78, 25), (1.5, 25)])
    for s, sx in (("L", -1), ("R", 1)):
        a.alpha(f"fx_dust_{s}", [(0, 0), (0.43, 0), (0.48, 1), (0.8, 0.6), (1.0, 0), (1.5, 0)])
        a.scale(f"fx_dust_{s}", [(0, 0.4, 0.4), (0.43, 0.4, 0.4), (0.6, 1.0, 1.0), (1.0, 1.25, 1.1), (1.5, 1.25, 1.1)])
        a.translate(f"fx_dust_{s}", [(0, 0, 0), (0.43, 0, 0), (1.0, sx * 70, 18), (1.5, sx * 70, 18)])
    a.event(0.44, "hit")

    # ---------------------------------------------------------------- spell cast
    # stance -> raise (stretch): magic circle opens on the floor and spins, sparkles rise, an orb grows above the hooves
    # -> push (squash): the orb drops to the hooves and shoots right -> burst -> recover
    oy = -(ORB_UP[1] - ORB[1])
    ox = ORB_UP[0] - ORB[0]
    a = rig.animation("cast", duration=2.6)
    a.attachment("fig", [(0, "pose_base"), (0.12, "pose_cast_raise"), (1.3, "pose_cast_push"), (2.15, "pose_base")])
    a.scale("fig", [(0, 1, 1), (0.09, 0.95, 1.03, "out"), (0.12, 1.06, 0.96), (0.24, 1, 1), (0.8, 1.02, 0.99), (1.24, 1.03, 0.98),
                    (1.3, 0.92, 1.06, "out"), (1.42, 0.98, 1.01), (1.55, 1, 1), (2.1, 1, 1), (2.15, 0.96, 1.03), (2.3, 1.01, 0.99), (2.45, 1, 1), (2.6, 1, 1)])
    a.osc("fig", "sx", 0.01, period=0.24, envelope=[(0, 0), (0.4, 0), (0.5, 1), (1.2, 1), (1.26, 0), (2.6, 0)])     # trembling with power
    a.scale("circle_floor", [(0, 1, 0.32), (2.6, 1, 0.32)])
    a.alpha("fx_circle", [(0, 0), (0.12, 0), (0.4, 1), (1.6, 1), (2.1, 0), (2.6, 0)])
    a.scale("fx_circle", [(0, 0.3, 0.3), (0.12, 0.3, 0.3), (0.45, 1.0, 1.0, "out"), (1.3, 1.0, 1.0), (1.36, 1.12, 1.12), (1.6, 1.05, 1.05), (2.6, 1.05, 1.05)])
    a.rotate("fx_circle", [(0, 0), (2.6, -200, "linear")])
    a.alpha("fx_sparkles", [(0, 0), (0.25, 0), (0.45, 1), (1.2, 1), (1.5, 0), (2.6, 0)])
    a.translate("fx_sparkles", [(0, 0, 0), (0.25, 0, -60), (1.5, 0, 180, "linear"), (2.6, 0, 180)])
    a.alpha("fx_orb", [(0, 0), (0.3, 0), (0.45, 1), (1.62, 1), (1.7, 0), (2.6, 0)])
    a.scale("fx_orb", [(0, 0.1, 0.1), (0.3, 0.1, 0.1), (1.1, 1.0, 1.0), (1.24, 1.15, 1.15), (1.32, 0.8, 0.8), (1.45, 1.1, 1.1), (1.7, 1.2, 1.2), (2.6, 1.2, 1.2)])
    a.osc("fx_orb", "sx", 0.06, period=0.2, envelope=[(0, 0), (0.5, 0), (0.6, 1), (1.2, 1), (1.25, 0), (2.6, 0)])
    a.osc("fx_orb", "sy", 0.06, period=0.2, phase=0.5, envelope=[(0, 0), (0.5, 0), (0.6, 1), (1.2, 1), (1.25, 0), (2.6, 0)])
    a.translate("fx_orb", [(0, ox, oy), (1.26, ox, oy), (1.32, 0, 0, "in"), (1.38, 0, 0), (1.66, 760, 0, "in"), (2.6, 760, 0)])
    a.alpha("fx_burst", [(0, 0), (1.62, 0), (1.66, 1), (1.85, 0.8), (2.15, 0), (2.6, 0)])
    a.scale("fx_burst", [(0, 0.3, 0.3), (1.62, 0.3, 0.3), (1.75, 1.1, 1.1, "out"), (2.15, 1.4, 1.4), (2.6, 1.4, 1.4)])
    a.translate("fx_burst", [(0, 240, 0), (2.6, 240, 0)])
    a.translate("root", [(0, 0, 0), (1.3, 0, 0), (1.33, -8, 0), (1.38, 4, 0), (1.44, 0, 0), (2.6, 0, 0)])
    a.event(1.32, "cast")

    rig.contract(
        title="豬大 Zhuda（戰鬥）",
        animations={
            "idle": {"role": "base", "loop": True, "track": 0},
            "battle_idle": {"role": "base", "loop": True, "track": 0},
            "attack": {"role": "action", "return": "battle_idle", "track": 0},
            "cast": {"role": "action", "return": "idle", "track": 0},
        },
        mix={"default": 0.0},
    )
