"""White model "vtuber" -- front-facing showcase / streamer figure: a face made of parts, live parameters, runtime hair.
`spk build` calls build(rig)."""
from spinekit import figure3d as F
from spinekit import motions3d

NAME = "vtuber"
ORIGIN = (380, 770)            # canvas position of the ground point between the feet = skeleton (0, 0)


def build(rig):
    B = F.Body("vtuber")
    F.build_rig(rig, B, ORIGIN)
    top = B.height * 1.34
    full = (ORIGIN[0] - B.height * 0.62, ORIGIN[1] - top, B.height * 1.24, top + 50)
    bust = (ORIGIN[0] - B.height * 0.3, ORIGIN[1] - B.height * 1.06, B.height * 0.6, B.height * 0.62)
    rig.frame(*full)
    motions3d.standard_set(rig, B)
    rig.contract(frames={"全身": rig.world_rect(*full), "半身": rig.world_rect(*bust)}, frame_portrait=rig.world_rect(ORIGIN[0] - B.height * 0.42, ORIGIN[1] - top, B.height * 0.84, top + 50))
