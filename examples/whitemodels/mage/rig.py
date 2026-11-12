"""White model "mage" -- body preset + the standard motion set, baked from 3D.  `spk build` calls build(rig)."""
from spinekit import figure3d as F
from spinekit import motions3d

NAME = "mage"
ORIGIN = (380, 770)            # canvas position of the ground point between the feet = skeleton (0, 0)


def build(rig):
    B = F.Body("mage")
    F.build_rig(rig, B, ORIGIN)
    top = B.height * 1.34
    rig.frame(ORIGIN[0] - 620, ORIGIN[1] - top, 1240, top + 50)
    motions3d.standard_set(rig, B)
    rig.contract(frame_portrait=rig.world_rect(ORIGIN[0] - B.height * 0.5, ORIGIN[1] - top, B.height, top + 50))
