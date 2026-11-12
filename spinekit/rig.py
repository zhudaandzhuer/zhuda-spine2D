"""Rig compiler: a small declarative builder that turns layered parts into a Spine 4.2 skeleton.

All positions you pass are *source pixels* on the art canvas (x right, y DOWN) -- the coordinates you read
off the key art.  The compiler converts to Spine space (y UP, origin at `origin`), computes bone-local
transforms through real parent matrices, generates meshes and weights, packs the atlas and writes:

    build/<name>.json  .atlas  .png          the Spine 4.2 asset (only these three are the runtime payload)
    build/<name>.contract.json               controller contract (tracks, loops, mixes, look controller, frame)
    build/<name>.stress.json                 range-of-motion poses for the rig gate (not shipped)
    build/build-receipt.json                 hashes + counts; visual verdict is always NOT_EVALUATED here

Nothing in here judges how the result looks.  That is what `spk shot / sheet / stress / play` are for.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from . import curves as C
from . import weights as W
from .atlas import pack
from .meshgen import grid_mesh

SPINE_VERSION = "4.2.43"


def _r(x, nd=2):
    y = round(float(x), nd)
    return int(y) if y == int(y) else y


class RigError(Exception):
    pass


class Bone:
    def __init__(self, name, parent, at, tip=None, rot=None, length=None, inherit=None, color=None):
        self.name, self.parent = name, parent
        self.at = (float(at[0]), float(at[1]))
        self.tip = (float(tip[0]), float(tip[1])) if tip is not None else None
        self.rot_in = rot
        self.length_in = length
        self.inherit = inherit
        self.color = color
        # resolved by Rig._resolve_bones
        self.index = -1
        self.wx = self.wy = self.wrot = 0.0
        self.lx = self.ly = self.lrot = 0.0
        self.length = 0.0

    def tip_px(self) -> Tuple[float, float]:
        if self.tip is not None:
            return self.tip
        a = math.radians(self.wrot)
        L = self.length if self.length > 0 else 1.0
        return (self.at[0] + math.cos(a) * L, self.at[1] - math.sin(a) * L)

    def to_local(self, wx: float, wy: float) -> Tuple[float, float]:
        a = math.radians(-self.wrot)
        dx, dy = wx - self.wx, wy - self.wy
        return (dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a))


class Look:
    """A 2D look controller: moving one bone displaces follower bones by per-bone depth (pseudo-3D turn)."""

    def __init__(self, rig, name, unit):
        self.rig, self.name, self.unit = rig, name, unit
        self.followers: List[Tuple[str, float, float]] = []

    def follow(self, bones, mix, mix_y=None):
        for b in ([bones] if isinstance(bones, str) else bones):
            self.followers.append((b, float(mix), float(mix if mix_y is None else mix_y)))
        return self


class Animation:
    """Layered animation.  Every call adds a layer; layers on the same channel are summed.

    Values are relative to the setup pose: rotate in degrees (CCW positive), translate in pixels in the
    bone's parent space with y UP, scale as a factor (1 = unchanged).
    """

    def __init__(self, rig, name, duration=None, loop=False):
        self.rig, self.name, self.duration, self.loop = rig, name, duration, loop
        self.channels: Dict[Tuple[str, str], List[C.PP]] = {}
        self.slot_attach: Dict[str, List[Tuple[float, Optional[str]]]] = {}
        self.slot_rgba: Dict[str, List[C.PP]] = {}
        self.slot_color: Dict[str, List[Tuple[float, str]]] = {}
        self.draw_lists: List[Tuple[float, List[str]]] = []
        self.events: List[dict] = []
        self.draw_orders: List[dict] = []
        self.raw: Dict[str, dict] = {}
        self._pose_keys: Dict[Tuple[str, str], Dict[float, Tuple[float, Optional[str]]]] = {}
        self._pose_times: List[float] = []
        self._pose_ease: Dict[float, str] = {}

    # ---- low level --------------------------------------------------------------------------------
    def _add(self, bone, prop, pp):
        if bone not in self.rig.bones:
            raise RigError(f"animation '{self.name}': unknown bone '{bone}'")
        self.channels.setdefault((bone, prop), []).append(pp)
        return self

    def _end(self):
        return self.duration if self.duration is not None else 1.0

    def rotate(self, bone, keys, ease="ease"):
        """keys: [(time, degrees[, ease])]"""
        return self._add(bone, "rotate", C.keyed(keys, ease, self.loop))

    def translate(self, bone, keys, ease="ease"):
        """keys: [(time, x, y[, ease])]"""
        self._add(bone, "x", C.keyed([(k[0], k[1]) + tuple(k[3:4]) for k in keys], ease, self.loop))
        return self._add(bone, "y", C.keyed([(k[0], k[2]) + tuple(k[3:4]) for k in keys], ease, self.loop))

    def scale(self, bone, keys, ease="ease"):
        """keys: [(time, sx, sy[, ease])]   1 = unchanged"""
        self._add(bone, "sx", C.keyed([(k[0], k[1] - 1) + tuple(k[3:4]) for k in keys], ease, self.loop))
        return self._add(bone, "sy", C.keyed([(k[0], k[2] - 1) + tuple(k[3:4]) for k in keys], ease, self.loop))

    def osc(self, bone, prop, amp, period=None, phase=0.0, bias=0.0, t0=0.0, t1=None, envelope=None):
        """Sine layer.  prop: rotate | x | y | sx | sy.  phase in cycles (0.25 = a quarter period late).
        period defaults to the animation duration (one seamless cycle).  For a seamless loop the period must
        divide the duration.  envelope: [(time, gain)] keys to fade the oscillation in/out."""
        t1 = self._end() if t1 is None else t1
        period = period or self._end()
        if envelope:
            env = C.keyed(envelope, "ease")
            w = 2 * math.pi / period
            f = lambda x: bias + env.value(x) * amp * math.sin(w * x - 2 * math.pi * phase)
            n = max(2, int(math.ceil((t1 - t0) / period * 12)))
            return self._add(bone, prop, C.sampled(f, t0, t1, n))
        return self._add(bone, prop, C.oscillator(amp, period, t0, t1, phase, bias))

    def sway(self, bones, amp, period=None, lag=0.08, phase=0.0, grow=1.0, prop="rotate", envelope=None, t0=0.0, t1=None):
        """Follow-through down a chain: each bone repeats the motion later (lag, in cycles) and scaled by grow**i.
        amp may be a number or a per-bone list."""
        for i, b in enumerate(bones):
            a = amp[i] if isinstance(amp, (list, tuple)) else amp * (grow ** i)
            self.osc(b, prop, a, period, phase + lag * i, envelope=envelope, t0=t0, t1=t1)
        return self

    def fn(self, bone, prop, f, t0=0.0, t1=None, n=None):
        """Arbitrary smooth function of time, sampled into Hermite keys (n segments, default 12 per second)."""
        t1 = self._end() if t1 is None else t1
        return self._add(bone, prop, C.sampled(f, t0, t1, n or max(2, int((t1 - t0) * 12))))

    # ---- pose-to-pose -----------------------------------------------------------------------------
    def pose(self, time, pose=None, ease="ease"):
        """Key a whole pose.  pose = {bone: {rot, x, y, sx, sy}}.  Every bone that appears in any pose of this
        animation is keyed at every pose time; properties you leave out return to the setup value (0 / 1)."""
        t = float(time)
        if t not in self._pose_times:
            self._pose_times.append(t)
        self._pose_ease[t] = ease
        for bone, p in (pose or {}).items():
            if bone not in self.rig.bones:
                raise RigError(f"animation '{self.name}': unknown bone '{bone}' in pose")
            for k, v in p.items():
                prop = {"rot": "rotate", "x": "x", "y": "y", "sx": "sx", "sy": "sy"}.get(k)
                if prop is None:
                    raise RigError(f"pose property '{k}' (use rot, x, y, sx, sy)")
                self._pose_keys.setdefault((bone, prop), {})[t] = float(v) - (1.0 if k in ("sx", "sy") else 0.0)
        return self

    def _flush_poses(self):
        times = sorted(self._pose_times)
        for (bone, prop), by_time in self._pose_keys.items():
            keys = [(t, by_time.get(t, 0.0), self._pose_ease[t]) for t in times]
            self._add(bone, prop, C.keyed(keys, "ease", self.loop))
        self._pose_keys, self._pose_times = {}, []

    # ---- slots / events ---------------------------------------------------------------------------
    def attachment(self, slot, keys):
        """keys: [(time, attachment_name | None)]"""
        self.slot_attach.setdefault(slot, []).extend(keys)
        return self

    def alpha(self, slot, keys, ease="ease"):
        """keys: [(time, alpha 0..1[, ease])] -- multiplies nothing, sets the slot alpha (rgb stays at setup)."""
        self.slot_rgba.setdefault(slot, []).append(C.keyed(keys, ease, self.loop))
        return self

    def color(self, slot, keys):
        """keys: [(time, "rrggbbaa")] -- slot colour, linearly interpolated (tints, fades)."""
        self.slot_color.setdefault(slot, []).extend(keys)
        return self

    def draw_order_list(self, time, order):
        """Set the complete draw order at `time`: every slot name, back to front (stays until the next key)."""
        self.draw_lists.append((float(time), list(order)))
        return self

    def event(self, time, name, **kw):
        if name not in self.rig.events:
            raise RigError(f"event '{name}' not declared with rig.event()")
        self.events.append({"time": C.r(time), "name": name, **kw})
        return self

    def draw_order(self, time, offsets=None):
        """offsets: {slot: +n / -n} relative to setup order; None restores setup order."""
        self.draw_orders.append({"time": C.r(time), **({"offsets": [{"slot": s, "offset": o} for s, o in offsets.items()]} if offsets else {})})
        return self

    def constraint(self, kind, name, keys):
        """Raw constraint timeline keys (ik / transform / physics), written through unchanged."""
        self.raw.setdefault(kind, {})[name] = keys
        return self

    # ---- export -----------------------------------------------------------------------------------
    def export(self) -> dict:
        self._flush_poses()
        out: dict = {}
        bones: Dict[str, dict] = {}
        names = sorted({b for b, _ in self.channels}, key=lambda n: self.rig.bones[n].index)
        end = self.duration
        for b in names:
            tl = {}
            get = lambda prop: self.channels.get((b, prop))
            if get("rotate"):
                pp = C.total(get("rotate"), extra_knots=self._span(end))
                if not C.is_static(pp, 0) or getattr(self, "keep_static", False):
                    tl["rotate"] = C.export_1(pp, "value", 0)
            for pa, pb, nm, neutral in (("x", "y", "translate", 0.0), ("sx", "sy", "scale", 1.0), ("shx", "shy", "shear", 0.0)):
                la, lb = get(pa), get(pb)
                if not la and not lb:
                    continue
                knots = {round(t, 6) for L in (la or []) + (lb or []) for t in L.t} | set(self._span(end))
                A = C.total(la or [], base=neutral, extra_knots=knots)
                B = C.total(lb or [], base=neutral, extra_knots=knots)
                sa, sb = C.is_static(A, neutral), C.is_static(B, neutral)
                keep = getattr(self, "keep_static", False)       # a clip that parameter clips are laid over must key every property they add to
                if sa and sb and not keep:
                    continue
                if keep:
                    tl[nm] = C.export_2(A, B, ("x", "y"), neutral)
                elif sb:
                    tl[nm + "x"] = C.export_1(A, "value", neutral)
                elif sa:
                    tl[nm + "y"] = C.export_1(B, "value", neutral)
                else:
                    tl[nm] = C.export_2(A, B, ("x", "y"), neutral)
            if tl:
                bones[b] = tl
        if bones:
            out["bones"] = bones
        slots: Dict[str, dict] = {}
        for s, keys in self.slot_attach.items():
            if s not in self.rig.slot_names():
                raise RigError(f"animation '{self.name}': unknown slot '{s}'")
            valid = self.rig.attachments_of(s)
            for _, nm in keys:
                if nm is not None and nm not in valid:
                    raise RigError(f"animation '{self.name}': slot '{s}' has no attachment '{nm}' (has {sorted(valid)})")
            slots.setdefault(s, {})["attachment"] = [{**({"time": C.r(t)} if t else {}), "name": nm} for t, nm in sorted(keys, key=lambda k: k[0])]
        for s, layers in self.slot_rgba.items():
            if s not in self.rig.slot_names():
                raise RigError(f"animation '{self.name}': unknown slot '{s}'")
            pp = C.total(layers, extra_knots=self._span(end))
            keys = C.export_1(pp, "value", 0)
            slots.setdefault(s, {})["alpha"] = keys
        for s, keys in self.slot_color.items():
            if s not in self.rig.slot_names():
                raise RigError(f"animation '{self.name}': unknown slot '{s}'")
            slots.setdefault(s, {})["rgba"] = [{**({"time": C.r(t)} if t else {}), "color": col} for t, col in sorted(keys, key=lambda k: k[0])]
        if slots:
            out["slots"] = slots
        for kind, d in self.raw.items():
            out[kind] = d
        draw = list(self.draw_orders)
        setup = getattr(self.rig, "_slot_order", [])
        for t, order in self.draw_lists:
            if sorted(order) != sorted(setup):
                raise RigError(f"animation '{self.name}': draw_order_list must name every slot exactly once")
            pos = {n: i for i, n in enumerate(order)}
            # Only slots that move are listed (in setup order, as the format requires).  The runtime drops the rest into the
            # remaining places in their original order, and those places are exactly their own indices.
            draw.append({**({"time": C.r(t)} if t else {}), "offsets": [{"slot": n, "offset": pos[n] - i} for i, n in enumerate(setup) if pos[n] != i]})
        if draw:
            out["drawOrder"] = sorted(draw, key=lambda k: k.get("time", 0))
        if self.events:
            out["events"] = sorted(self.events, key=lambda k: k["time"])
        return out

    def _span(self, end):
        return [0.0, float(end)] if end else [0.0]


class Rig:
    def __init__(self, name: str, project: Path | str):
        self.name = name
        self.project = Path(project)
        self.bones: Dict[str, Bone] = {}
        self.parts: Dict[str, dict] = {}
        self.manifest: List[dict] = []
        self.canvas_size: Tuple[int, int] = (0, 0)
        self.origin: Tuple[float, float] = (0.0, 0.0)
        self.frame_px: Optional[Tuple[float, float, float, float]] = None
        self.slots: Dict[str, dict] = {}
        self.transforms: List[dict] = []
        self.iks: List[dict] = []
        self.physics_list: List[dict] = []
        self.looks: List[Look] = []
        self.events: Dict[str, dict] = {}
        self.animations: Dict[str, Animation] = {}
        self.stress_poses: List[dict] = []
        self.contract_data: dict = {}
        self.ignored: set = set()
        self.options = {"padding": 4, "bleed": 6, "pma": False, "max_influences": 4, "physics": True}
        self._seq = 0
        self._load_manifest()

    # ---------------------------------------------------------------------------------------- parts
    def _load_manifest(self):
        f = self.project / "parts" / "manifest.json"
        if not f.is_file():
            raise RigError(f"missing {f} (run `spk art` or provide layered parts + manifest)")
        m = json.loads(f.read_text())
        self.canvas_size = tuple(m["canvas"])
        self.origin = (self.canvas_size[0] / 2, float(self.canvas_size[1]))
        self.manifest = m["parts"]
        names = [p["name"] for p in self.manifest]
        if len(set(names)) != len(names):
            raise RigError("duplicate part names in parts/manifest.json")

    def set(self, **options):
        """padding, bleed, pma, max_influences, physics"""
        for k in options:
            if k not in self.options:
                raise RigError(f"unknown option '{k}'")
        self.options.update(options)

    def set_origin(self, x, y):
        """Source-pixel position of Spine world (0, 0).  Default: bottom centre of the canvas."""
        self.origin = (float(x), float(y))

    def frame(self, x, y, width, height):
        """Intended camera frame in source pixels (what a viewer should show).  Default: whole canvas."""
        self.frame_px = (float(x), float(y), float(width), float(height))

    def world(self, sx, sy):
        return (sx - self.origin[0], self.origin[1] - sy)

    def world_rect(self, x, y, width, height):
        """Source-pixel rect -> {x, y, width, height} in skeleton units (for extra contract frames).  Call after set_origin()."""
        wx, wy_top = self.world(x, y)
        return {"x": _r(wx), "y": _r(wy_top - height), "width": _r(width), "height": _r(height)}

    # ---------------------------------------------------------------------------------------- bones
    def bone(self, name, parent=None, at=None, tip=None, rot=None, length=None, inherit=None, color=None):
        """at / tip in source pixels.  Orientation: `tip` (bone points at it) > `rot` (world degrees, CCW, 0 = +x) > 0.
        inherit: None | 'noRotationOrReflection' (keeps world rotation when the parent rotates -- hanging hair/cloth)
                 | 'onlyTranslation' | 'noScale' | 'noScaleOrReflection'"""
        if name in self.bones:
            raise RigError(f"duplicate bone '{name}'")
        if parent is None and self.bones:
            raise RigError(f"bone '{name}' needs a parent (only the first bone is the root)")
        if parent is not None and parent not in self.bones:
            raise RigError(f"bone '{name}': parent '{parent}' must be declared first")
        if at is None:
            at = self.bones[parent].at if parent else self.origin
        b = Bone(name, parent, at, tip, rot, length, inherit, color)
        b.index = len(self.bones)
        self.bones[name] = b
        self._resolve_bone(b)
        return name

    def chain(self, prefix, parent, points, inherit_first=None, color=None, start=1):
        """Bones prefix1..n along a polyline of source-pixel points (n = len(points) - 1). Returns the names."""
        names = []
        for i in range(len(points) - 1):
            n = f"{prefix}{i + start}"
            self.bone(n, parent=parent if i == 0 else names[-1], at=points[i], tip=points[i + 1], inherit=inherit_first if i == 0 else None, color=color)
            names.append(n)
        return names

    def _resolve_bone(self, b: Bone):
        b.wx, b.wy = self.world(*b.at)
        if b.tip is not None:
            tx, ty = self.world(*b.tip)
            b.wrot = math.degrees(math.atan2(ty - b.wy, tx - b.wx))
            b.length = math.hypot(tx - b.wx, ty - b.wy)
        else:
            b.wrot = float(b.rot_in or 0.0)
            b.length = float(b.length_in or 0.0)
        if b.length_in is not None:
            b.length = float(b.length_in)
        if b.parent is None:
            b.lx, b.ly, b.lrot = b.wx, b.wy, b.wrot
        else:
            p = self.bones[b.parent]
            b.lx, b.ly = p.to_local(b.wx, b.wy)
            b.lrot = b.wrot if b.inherit in ("noRotationOrReflection", "onlyTranslation") else b.wrot - p.wrot
            b.lrot = (b.lrot + 180) % 360 - 180

    # ---------------------------------------------------------------------------------------- slots
    def part(self, name, bone, slot=None, mesh=None, weights=None, active=True, color=None, blend=None):
        """Bind one art part.

        bone     owner bone (for weighted meshes: the slot bone; any stable bone works)
        slot     defaults to the part name; give several parts the same slot for swappable attachments
        mesh     None -> region attachment.  dict(step=px | cols=, rows=, margin=, cull=) -> grid mesh
        weights  a weight field from spinekit.weights (chain/sheet/depth/blend/...) -> weighted mesh.
                 A mesh without weights is rigid on `bone` (useful only with deform or as a future-proof region).
        active   whether this attachment is shown in the setup pose (one active attachment per slot)
        """
        if name in self.parts:
            raise RigError(f"part '{name}' bound twice")
        if name not in {p["name"] for p in self.manifest}:
            raise RigError(f"part '{name}' is not in parts/manifest.json")
        if bone not in self.bones:
            raise RigError(f"part '{name}': unknown bone '{bone}'")
        if weights is not None and mesh is None:
            mesh = {}
        slot = slot or name
        s = self.slots.setdefault(slot, {"bone": bone, "attachments": [], "active": None, "color": color, "blend": blend})
        if s["bone"] != bone and weights is None:
            raise RigError(f"slot '{slot}': attachments in one slot must share the slot bone ('{s['bone']}' vs '{bone}')")
        s["attachments"].append(name)
        if active and s["active"] is None:
            s["active"] = name
        if color and not s["color"]:
            s["color"] = color
        self.parts[name] = {"bone": s["bone"], "slot": slot, "mesh": mesh, "weights": weights}
        return name

    def ignore(self, *names):
        """Parts that exist in the manifest but are intentionally not rigged."""
        self.ignored.update(names)

    def slot_names(self):
        return set(self.slots)

    def attachments_of(self, slot):
        return set(self.slots[slot]["attachments"])

    # ---------------------------------------------------------------------------------- constraints
    def transform(self, name, bones, target, mix_x=0.0, mix_y=None, mix_rotate=0.0, mix_scale_x=0.0, mix_scale_y=None, mix_shear_y=0.0,
                  local=True, relative=True, x=0.0, y=0.0, rotation=0.0):
        self._seq += 1
        self.transforms.append({"_seq": self._seq, "name": name, "bones": list(bones), "target": target, "local": local, "relative": relative, "rotation": rotation, "x": x, "y": y,
                                "mixRotate": mix_rotate, "mixX": mix_x, "mixY": mix_x if mix_y is None else mix_y,
                                "mixScaleX": mix_scale_x, "mixScaleY": mix_scale_x if mix_scale_y is None else mix_scale_y, "mixShearY": mix_shear_y})

    def counter_rotate(self, name, bones, target, mix=-1.0):
        """Make `bones` rotate by mix * (target's animated rotation).  mix=-1 keeps them world-upright."""
        t = self.bones[target]
        self.transform(name, bones, target, mix_rotate=mix, rotation=-t.lrot)

    def ik(self, name, bones, target, bend_positive=True, mix=1.0, softness=0.0, stretch=False, compress=False):
        self._seq += 1
        self.iks.append({"_seq": self._seq, "name": name, "bones": list(bones), "target": target, "bendPositive": bend_positive, "mix": mix, "softness": softness, "stretch": stretch, "compress": compress})

    def physics(self, bone, rotate=1.0, x=0.0, y=0.0, scale_x=0.0, shear_x=0.0, inertia=0.5, strength=100.0, damping=0.85, mass=1.0, wind=0.0, gravity=0.0, mix=1.0, limit=5000.0, name=None):
        """Spine 4.2 physics on one bone.  The bone needs length > 0 for rotate physics (use `tip`)."""
        self._seq += 1
        self.physics_list.append({"_seq": self._seq, "name": name or f"phys_{bone}", "bone": bone, "x": x, "y": y, "rotate": rotate, "scaleX": scale_x, "shearX": shear_x,
                                  "limit": limit, "inertia": inertia, "strength": strength, "damping": damping, "mass": mass, "wind": wind, "gravity": gravity, "mix": mix})

    def physics_chain(self, bones, inertia=(0.4, 0.8), strength=(140.0, 70.0), damping=(0.8, 0.88), rotate=(1.0, 1.0), mix=(1.0, 1.0), **kw):
        """Physics down a chain; each (root, tip) pair is interpolated along it. Softer and floppier toward the tip."""
        n = len(bones)
        for i, b in enumerate(bones):
            u = i / (n - 1) if n > 1 else 0.0
            lerp = lambda p: p[0] + (p[1] - p[0]) * u if isinstance(p, (tuple, list)) else p
            self.physics(b, rotate=lerp(rotate), inertia=lerp(inertia), strength=lerp(strength), damping=lerp(damping), mix=lerp(mix), **kw)

    def look(self, name, parent, at, unit=24.0, back=None):
        """Create a look controller bone at `at`.  Moving it by (u, v) px displaces followers by (u, v) * mix.
        back: name for an auto-created bone that moves the opposite way (for layers behind the pivot)."""
        self.bone(name, parent=parent, at=at, color="ffd24aff")
        lk = Look(self, name, unit)
        self._seq += 1
        lk.seq = self._seq
        self.looks.append(lk)
        if back:
            self.bone(back, parent=parent, at=at, color="7aa6ffff")
            lk.follow(back, -1.0)
        return lk

    # ------------------------------------------------------------------------------------ animation
    def event(self, name, **data):
        self.events[name] = data

    def animation(self, name, duration=None, loop=False):
        """duration: seconds.  Give it for loops and for anything using osc()/sway()."""
        if name in self.animations:
            raise RigError(f"duplicate animation '{name}'")
        a = Animation(self, name, duration, loop)
        self.animations[name] = a
        return a

    def stress(self, name, pose=None, slots=None, look=None, tracks=None, label=None):
        """A range-of-motion pose for the rig gate: additive bone offsets on the setup pose (or on `tracks`)."""
        self.stress_poses.append({"name": name, "label": label or name, "seek": {"tracks": tracks or [], "pose": pose or {}, "slots": slots or {}, "look": look or {}}})

    def contract(self, **kw):
        """Controller contract shipped next to the asset: animations={name:{loop,track,role,return,auto,label}}, mix, home, title."""
        self.contract_data.update(kw)

    # ---------------------------------------------------------------------------------------- utils
    def ellipsoid(self, cx, cy, rx, ry, gain=1.0, floor=0.0, power=0.5):
        """Depth function for `weights.depth`: `gain` at (cx, cy), falling to `floor` at the ellipse edge (hemisphere profile)."""
        def z(sx, sy):
            q = 1 - ((sx - cx) / rx) ** 2 - ((sy - cy) / ry) ** 2
            return floor + (gain - floor) * np.power(np.clip(q, 0, 1), power)
        return z

    def depth_at(self, zfn, x, y):
        return float(zfn(np.array([float(x)]), np.array([float(y)]))[0])

    # -------------------------------------------------------------------------------------- compile
    def compile(self, out_dir: Path | str) -> dict:
        out = Path(out_dir)
        if out.exists() and any(out.iterdir()):
            raise RigError(f"{out} already exists; build into a new directory so the previous build stays as the visual baseline")
        missing = [p["name"] for p in self.manifest if p["name"] not in self.parts and p["name"] not in self.ignored]
        if missing:
            raise RigError("parts without an owner (bind with rig.part or list in rig.ignore): " + ", ".join(missing))
        bones = list(self.bones.values())
        bone_json = []
        for b in bones:
            j = {"name": b.name}
            if b.parent:
                j["parent"] = b.parent
            if b.length > 0.01:
                j["length"] = _r(b.length)
            if abs(b.lrot) > 1e-4:
                j["rotation"] = _r(b.lrot, 3)
            if abs(b.lx) > 1e-4:
                j["x"] = _r(b.lx)
            if abs(b.ly) > 1e-4:
                j["y"] = _r(b.ly)
            if b.inherit:
                j["inherit"] = b.inherit
            if b.color:
                j["color"] = b.color
            bone_json.append(j)

        # slots in art order (manifest is back-to-front)
        order, seen = [], set()
        for p in self.manifest:
            if p["name"] in self.parts:
                s = self.parts[p["name"]]["slot"]
                if s not in seen:
                    seen.add(s)
                    order.append(s)
        self._slot_order = list(order)
        slot_json = []
        for s in order:
            d = self.slots[s]
            j = {"name": s, "bone": d["bone"]}
            if d["color"]:
                j["color"] = d["color"]
            if d["active"]:
                j["attachment"] = d["active"]
            if d["blend"]:
                j["blend"] = d["blend"]
            slot_json.append(j)

        by_name = {p["name"]: p for p in self.manifest}
        images: Dict[str, Image.Image] = {}
        skin: Dict[str, dict] = {}
        stats = {"regions": 0, "meshes": 0, "weighted_meshes": 0, "vertices": 0, "triangles": 0}
        receipts = []
        for name, cfg in self.parts.items():
            p = by_name[name]
            f = (self.project / "parts" / p["file"]).resolve()
            im = Image.open(f)
            if im.mode != "RGBA":
                raise RigError(f"part {name}: {f.name} must be RGBA with real alpha")
            if (im.width, im.height) != (p["w"], p["h"]):
                raise RigError(f"part {name}: image size {im.size} != manifest {(p['w'], p['h'])}")
            images[name] = im
            receipts.append({"part": name, "file": p["file"], "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "slot": cfg["slot"], "bone": cfg["bone"], "top_left": [p["x"], p["y"]], "size": [p["w"], p["h"]]})
            bone = self.bones[cfg["bone"]]
            if cfg["mesh"] is None:
                cx, cy = self.world(p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
                lx, ly = bone.to_local(cx, cy)
                att = {"x": _r(lx), "y": _r(ly), "width": p["w"], "height": p["h"]}
                if abs(bone.wrot) > 1e-4:
                    att["rotation"] = _r(-bone.wrot, 3)
                stats["regions"] += 1
            else:
                alpha = np.asarray(im)[..., 3]
                mopt = dict(cfg["mesh"])
                g = grid_mesh(alpha, step=mopt.get("step", 32), cols=mopt.get("cols", 0), rows=mopt.get("rows", 0), margin=mopt.get("margin", 3), cull=mopt.get("cull", True))
                sx = np.array([p["x"] + q[0] for q in g["points"]])
                sy = np.array([p["y"] + q[1] for q in g["points"]])
                wxs, wys = sx - self.origin[0], self.origin[1] - sy
                att = {"type": "mesh", "uvs": g["uvs"], "triangles": g["triangles"], "hull": g["hull"], "edges": g["edges"], "width": p["w"], "height": p["h"]}
                if cfg["weights"] is None:
                    verts = []
                    for x, y in zip(wxs, wys):
                        lx, ly = bone.to_local(float(x), float(y))
                        verts += [_r(lx), _r(ly)]
                else:
                    field = cfg["weights"](self, sx, sy)
                    for bn in field:
                        if bn not in self.bones:
                            raise RigError(f"part {name}: weight field uses unknown bone '{bn}'")
                    inf = W.finalize(field, self.options["max_influences"])
                    verts = []
                    for (x, y), row in zip(zip(wxs, wys), inf):
                        verts.append(len(row))
                        for bn, wgt in row:
                            bb = self.bones[bn]
                            lx, ly = bb.to_local(float(x), float(y))
                            verts += [bb.index, _r(lx), _r(ly), _r(wgt, 4)]
                    if len(verts) == len(g["uvs"]):  # would be misread as unweighted
                        raise RigError(f"part {name}: degenerate weighted mesh")
                    stats["weighted_meshes"] += 1
                att["vertices"] = verts
                stats["meshes"] += 1
                stats["vertices"] += len(g["points"])
                stats["triangles"] += len(g["triangles"]) // 3
            skin.setdefault(cfg["slot"], {})[name] = att

        # Constraints are applied in the order they were declared in rig.py (look controllers count from rig.look()).
        # Order matters: e.g. leg IK must run before a constraint that levels the foot, physics after everything it reacts to.
        pending = []
        for lk in self.looks:
            t = self.bones[lk.name]
            groups: Dict[Tuple[float, float], List[str]] = {}
            for bn, mx, my in lk.followers:
                if bn not in self.bones:
                    raise RigError(f"look '{lk.name}': unknown follower bone '{bn}'")
                if self.bones[bn].parent != t.parent:
                    raise RigError(f"look '{lk.name}': follower '{bn}' must share the controller's parent ('{t.parent}') so both move in the same space")
                groups.setdefault((round(mx, 3), round(my, 3)), []).append(bn)
            for gi, ((mx, my), bns) in enumerate(sorted(groups.items())):
                nm = f"{lk.name}_{'n' if mx < 0 else 'p'}{int(round(abs(mx) * 100)):03d}_{'n' if my < 0 else 'p'}{int(round(abs(my) * 100)):03d}"
                pending.append((lk.seq + gi * 1e-4, "transform", {"name": nm, "bones": bns, "target": lk.name, "local": True, "relative": True, "rotation": 0, "x": -t.lx, "y": -t.ly,
                                                                  "mixRotate": 0, "mixX": mx, "mixY": my, "mixScaleX": 0, "mixScaleY": 0, "mixShearY": 0}))
        pending += [(t["_seq"], "transform", t) for t in self.transforms]
        pending += [(t["_seq"], "ik", t) for t in self.iks]
        if self.options["physics"]:
            pending += [(t["_seq"], "physics", t) for t in self.physics_list]
        pending.sort(key=lambda x: x[0])
        transform_json, ik_json, phys_json = [], [], []
        for c_order, (_, kind, t) in enumerate(pending):
            if kind == "transform":
                for bn in t["bones"] + [t["target"]]:
                    if bn not in self.bones:
                        raise RigError(f"transform constraint '{t['name']}': unknown bone '{bn}'")
                j = {"name": t["name"], "order": c_order, "bones": t["bones"], "target": t["target"], "local": t["local"], "relative": t["relative"]}
                for k in ("rotation", "x", "y"):
                    if abs(t[k]) > 1e-6:
                        j[k] = _r(t[k], 3)
                for k in ("mixRotate", "mixX", "mixY", "mixScaleX", "mixScaleY", "mixShearY"):
                    j[k] = _r(t[k], 4)
                transform_json.append(j)
            elif kind == "ik":
                for bn in t["bones"] + [t["target"]]:
                    if bn not in self.bones:
                        raise RigError(f"ik constraint '{t['name']}': unknown bone '{bn}'")
                ik_json.append({"name": t["name"], "order": c_order, "bones": t["bones"], "target": t["target"], "mix": t["mix"], "softness": t["softness"], "bendPositive": t["bendPositive"], "stretch": t["stretch"], "compress": t["compress"]})
            else:
                b = self.bones.get(t["bone"])
                if b is None:
                    raise RigError(f"physics: unknown bone '{t['bone']}'")
                if t["rotate"] > 0 and b.length <= 0.01:
                    raise RigError(f"physics on '{b.name}' needs bone length > 0 (declare the bone with tip=)")
                j = {"name": t["name"], "order": c_order, "bone": t["bone"]}
                for k in ("x", "y", "rotate", "scaleX", "shearX", "wind", "gravity"):
                    if t[k]:
                        j[k] = _r(t[k], 4)
                j.update({"limit": _r(t["limit"]), "inertia": _r(t["inertia"], 4), "strength": _r(t["strength"], 3), "damping": _r(t["damping"], 4), "mass": _r(t["mass"], 4), "mix": _r(t["mix"], 4)})
                phys_json.append(j)

        anims = {}
        for nm, a in self.animations.items():
            anims[nm] = a.export()

        fx, fy, fw, fh = self.frame_px or (0, 0, self.canvas_size[0], self.canvas_size[1])
        wx0, wy1 = self.world(fx, fy)
        frame_world = {"x": _r(wx0), "y": _r(wy1 - fh), "width": _r(fw), "height": _r(fh)}
        doc = {"skeleton": {"hash": "", "spine": SPINE_VERSION, **frame_world, "images": "./parts/", "audio": ""}, "bones": bone_json, "slots": slot_json}
        if ik_json:
            doc["ik"] = ik_json
        if transform_json:
            doc["transform"] = transform_json
        if phys_json:
            doc["physics"] = phys_json
        doc["skins"] = [{"name": "default", "attachments": {s: skin[s] for s in order}}]
        if self.events:
            doc["events"] = self.events
        doc["animations"] = anims
        body = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
        doc["skeleton"]["hash"] = hashlib.sha1(body.encode()).hexdigest()[:11]
        body = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)

        page, atlas_text, regions = pack(images, f"{self.name}.png", padding=self.options["padding"], bleed=self.options["bleed"], pma=self.options["pma"])
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{self.name}.json").write_text(body, encoding="utf-8")
        (out / f"{self.name}.atlas").write_text(atlas_text, encoding="utf-8")
        page.save(out / f"{self.name}.png", optimize=True)

        contract = {"name": self.name, "spine": "4.2", "frame": frame_world, "home": "idle" if "idle" in self.animations else next(iter(self.animations), None),
                    "mix": {"default": 0.2}, "physics": bool(phys_json), "animations": {}, "controllers": {}}
        for nm, a in self.animations.items():
            contract["animations"][nm] = {"loop": a.loop, "track": 0, "role": "base" if a.loop else "action"}
        for lk in self.looks:
            contract["controllers"][lk.name] = {"bone": lk.name, "unit": lk.unit, "kind": "translate"}
        for k, v in self.contract_data.items():
            if k == "animations":
                for nm, meta in v.items():
                    if nm not in self.animations:
                        raise RigError(f"contract: unknown animation '{nm}'")
                    contract["animations"][nm].update(meta)
            elif k == "controllers":
                for nm, meta in v.items():
                    contract["controllers"].setdefault(nm, {}).update(meta)
            elif k == "mix":
                contract["mix"].update(v)
            else:
                contract[k] = v
        (out / f"{self.name}.contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / f"{self.name}.stress.json").write_text(json.dumps({"poses": self.stress_poses}, ensure_ascii=False, indent=1), encoding="utf-8")

        sha = lambda f: hashlib.sha256((out / f).read_bytes()).hexdigest()
        receipt = {
            "name": self.name, "spine": SPINE_VERSION,
            "counts": {"bones": len(bones), "slots": len(slot_json), "attachments": len(self.parts), **stats, "transform_constraints": len(transform_json), "ik_constraints": len(ik_json),
                       "physics_constraints": len(phys_json), "animations": len(anims), "events": len(self.events)},
            "atlas": {"page": [page.width, page.height], "pma": self.options["pma"], "padding": self.options["padding"], "bleed": self.options["bleed"]},
            "sha256": {f"{self.name}.json": sha(f"{self.name}.json"), f"{self.name}.atlas": sha(f"{self.name}.atlas"), f"{self.name}.png": sha(f"{self.name}.png")},
            "bytes": {f: (out / f).stat().st_size for f in (f"{self.name}.json", f"{self.name}.atlas", f"{self.name}.png")},
            "parts": receipts, "ignored_parts": sorted(self.ignored),
            "visual_verdict": "NOT_EVALUATED",
        }
        (out / "build-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
        if getattr(self, "skin_spec", None):
            geo = {r_["part"]: r_ for r_ in receipts}
            spec = dict(self.skin_spec, name=self.name, canvas=list(self.canvas_size))
            for at in spec["attachments"]:
                g = geo[at["attachment"]]
                bone = self.bones[g["bone"]]
                at.update(file=g["file"], size=g["size"], pivot=[round(bone.at[0] - g["top_left"][0], 2), round(bone.at[1] - g["top_left"][1], 2)])
            (out / f"{self.name}.skin.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        if getattr(self, "_bake_reports", None):
            (out / "bake-report.json").write_text(json.dumps(self._bake_reports, ensure_ascii=False, indent=1), encoding="utf-8")
        return receipt
