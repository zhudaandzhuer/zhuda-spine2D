"""spinekit -- compile layered 2D parts into Spine 4.2 skeletons (bones, weighted meshes, constraints, animations).

    from spinekit import Rig, weights as W

See docs/20-rig.md and docs/30-animation.md, or examples/ for a complete character.
"""
from .rig import Rig, RigError, Animation, SPINE_VERSION  # noqa: F401
from . import weights, curves, meshgen, atlas, figure3d, motions3d, skins  # noqa: F401

__version__ = "2.7.0"
