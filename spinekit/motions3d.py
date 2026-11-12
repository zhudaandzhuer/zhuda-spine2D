"""motions3d -- a motion library for figure3d bodies.  Everything scales with the body: strides and jumps with leg
length, stance and sway with hip width, foot roll with foot size.  One library, any proportion.

    M = Motions(B)
    standard_set(rig, B)          # bakes idle / walk / run / jump / wave / pick / turn / turntable / kungfu / dance
"""
from __future__ import annotations

import math

from . import figure3d as F
from .figure3d import Pose, mirror

TAU = 2 * math.pi


def sm(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def lerp(a, b, t):
    return a + (b - a) * t


def keyf(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return lerp(v0, v1, sm((t - t0) / (t1 - t0)))
    return keys[-1][1]


def curve(pts, u):
    if u <= pts[0][0]:
        return pts[0][1]
    if u >= pts[-1][0]:
        return pts[-1][1]
    for i in range(len(pts) - 1):
        (u0, v0), (u1, v1) = pts[i], pts[i + 1]
        if u <= u1:
            m0 = (v1 - pts[i - 1][1]) / (u1 - pts[i - 1][0]) if i > 0 else (v1 - v0) / (u1 - u0)
            m1 = (pts[i + 2][1] - v0) / (pts[i + 2][0] - u0) if i + 2 < len(pts) else (v1 - v0) / (u1 - u0)
            h, s = u1 - u0, (u - u0) / (u1 - u0)
            return (2 * s**3 - 3 * s**2 + 1) * v0 + (s**3 - 2 * s**2 + s) * h * m0 + (-2 * s**3 + 3 * s**2) * v1 + (s**3 - s**2) * h * m1


def bump(t, a, b):
    return math.sin(math.pi * (t - a) / (b - a)) ** 2 if a < t < b else 0.0


GUARD_L, GUARD_R, DOWN = (60, 12, 0, 115), (48, 18, 0, 125), (0, 8, 0, 10)
ZERO = dict(syaw=0.0, pyaw=0.0, spitch=0.0, ppitch=0.0, hpitch=0.0, py=0.0, pz=0.0)


def K(L, R, **body):
    """One key of an upper-body action: both arms as (flex, abd, twist, elbow) plus body deltas on top of the stance."""
    d = dict(ZERO)
    d.update(body)
    d.update(Lf=L[0], La=L[1], Lt=L[2], Le=L[3], Rf=R[0], Ra=R[1], Rt=R[2], Re=R[3])
    return d


def kf(t, keys):
    """keys: [(time, K(...), ease-arriving)] -> interpolated dict."""
    if t <= keys[0][0]:
        return dict(keys[0][1])
    for (t0, a, _), (t1, b, e) in zip(keys, keys[1:]):
        if t <= t1:
            w = F.EASES[e]((t - t0) / (t1 - t0))
            return {k: a[k] + (b[k] - a[k]) * w for k in a}
    return dict(keys[-1][1])


class Motions:
    def __init__(self, B: F.Body):
        self.B = B
        s = B.s
        cadence = max(0.62, s ** 0.5)                     # short legs step faster
        self.WALK_T, self.RUN_T = 1.0 * cadence, 0.68 * max(0.7, s ** 0.5)
        self.WALK_V, self.RUN_V = 403.0 * s / self.WALK_T, 598.0 * s / self.RUN_T
        self.JUMP_T, self.WAVE_T, self.PICK_T, self.TURN_T, self.TURN_MID = 1.5, 2.8, 3.0, 1.5, 0.75
        self._kungfu = self._build_kungfu()
        self._dance = self._build_dance()
        self.KUNGFU_T, self.DANCE_T = self._kungfu.duration, self._dance.duration

    # ---- foot roll on the ground
    def toe_rocker(self, b_deg, ball_z):
        b, B = math.radians(b_deg), self.B
        return ball_z - B.ball * math.cos(b) + B.ankle_h * math.sin(b), B.ball * math.sin(b) + B.ankle_h * math.cos(b)

    def heel_rocker(self, a_deg, heel_z):
        a, B = math.radians(a_deg), self.B
        return heel_z + B.heel * math.cos(a) - B.ankle_h * math.sin(a), B.heel * math.sin(a) + B.ankle_h * math.cos(a)

    # ---- what the body carries
    def held(self, p: Pose) -> Pose:
        """Blend the carrying arms toward their hold pose (by anatomy: apply it AFTER mirroring a clip)."""
        for sd, (f_, a_, t_, e_, w) in self.B.hold.items():
            arm = p.arm[sd]
            arm.update(flex=lerp(arm["flex"], f_, w), abd=lerp(arm["abd"], a_, w), twist=lerp(arm["twist"], t_, w), elbow=lerp(arm["elbow"], e_, w))
        return p

    def hold_pose(self, sd):
        return tuple(self.B.hold[sd][:4]) if sd in self.B.hold else DOWN

    def action(self, t, keys, left=False):
        """Upper-body action on top of the stance.  `left` turns the whole body to face left; the SAME anatomical arms act
        (a sword stays in the right hand), unlike mirror() which would hand the action to the other arm."""
        p = self.held(self.stance(left))
        v, s = kf(t, keys), self.B.s
        p.arm["L"].update(flex=v["Lf"], abd=v["La"], twist=v["Lt"], elbow=v["Le"])
        p.arm["R"].update(flex=v["Rf"], abd=v["Ra"], twist=v["Rt"], elbow=v["Re"])
        p.syaw += v["syaw"]; p.pyaw += v["pyaw"]; p.spitch += v["spitch"]; p.ppitch += v["ppitch"]; p.hpitch += v["hpitch"]
        p.py += v["py"] * s; p.pz += v["pz"] * s
        return p

    # ---- shield warrior
    BLOCK_T, SLASH_T, BASH_T = 1.6, 1.5, 1.2

    def block(self, t, left=False):
        HL, HR = self.hold_pose("L"), self.hold_pose("R")
        up = K((20, 70, -90, 100), (-25, 18, 0, 70), py=-30, ppitch=10, spitch=6, syaw=-10, hpitch=-6)       # elbow out, forearm up: shield before the face, still facing forward
        return self.action(t, [(0, K(HL, HR), "smooth"), (0.26, up, "snap"), (1.0, up, "linear"), (1.45, K(HL, HR), "smooth"), (self.BLOCK_T, K(HL, HR), "linear")], left)

    def slash(self, t, left=False):
        HL, HR = self.hold_pose("L"), self.hold_pose("R")
        return self.action(t, [(0, K(HL, HR), "smooth"),
                               (0.40, K(HL, (150, 20, 0, 80), syaw=-28, pyaw=-10, spitch=-6, py=-8), "smooth"),            # wind up over the shoulder
                               (0.56, K(HL, (40, 8, 0, 8), syaw=32, pyaw=12, spitch=14, pz=22, py=-24), "snap"),            # cut
                               (0.78, K(HL, (-10, 25, 0, 20), syaw=40, pyaw=14, spitch=10, pz=18, py=-20), "out"),          # follow through
                               (self.SLASH_T, K(HL, HR), "smooth")], left)

    def bash(self, t, left=False):
        HL, HR = self.hold_pose("L"), self.hold_pose("R")
        hit = K((28, 35, -90, 85), (-15, 16, 0, 50), syaw=-34, pyaw=-12, pz=46, py=-22, ppitch=14)                 # the body drives the shield forward, left shoulder leading
        return self.action(t, [(0, K(HL, HR), "smooth"), (0.24, K((10, 18, -90, 112), HR, syaw=18, pz=-10, py=-14), "smooth"), (0.38, hit, "snap"), (0.62, hit, "linear"), (self.BASH_T, K(HL, HR), "smooth")], left)

    # ---- mage
    CAST_T, CHANNEL_T = 2.4, 2.4

    def cast(self, t, left=False):
        HL, HR = self.hold_pose("L"), self.hold_pose("R")
        out = K((80, 10, 0, 20), (85, 8, 0, 12), spitch=12, pz=16, py=-12, hpitch=4)
        return self.action(t, [(0, K(HL, HR), "smooth"), (0.70, K((60, 35, 0, 50), (120, 15, 0, 35), spitch=-10, hpitch=-8, py=4), "smooth"), (0.95, out, "snap"), (1.5, out, "linear"),
                               (self.CAST_T, K(HL, HR), "smooth")], left)

    def channel(self, t, left=False):
        w = TAU * t / self.CHANNEL_T
        k = K((55 + 6 * math.sin(w), 60 + 5 * math.sin(w + 0.8), 0, 40), (62 + 4 * math.sin(w + 0.4), 22, 0, 28 - 4 * math.sin(w)),          # staff held upright in front
              spitch=-4 + 3 * math.sin(w), hpitch=-6 + 2 * math.sin(w + 1.0), py=5 * math.sin(w))
        return self.action(0.0, [(0, k, "linear"), (1, k, "linear")], left)

    # ---- facing the camera: showcase / streamer performance
    FRONT_T = dict(front_idle=4.0, talk=3.2, idol=4.0, greet=3.2, bow=2.6, cheer=2.4, present=3.2, heart=2.8, spin=2.0)

    def front(self) -> Pose:
        p = self.B.pose(0.0)
        for sd in "LR":
            p.arm[sd].update(flex=4.0, abd=10.0, twist=0.0, elbow=14.0)
        p.spitch = 1.0
        return p

    def front_idle(self, t):
        p, w, s, wd = self.front(), TAU * t / 4.0, self.B.s, self.B.w
        p.py += (-1.5 + 1.5 * math.sin(2 * w)) * s
        p.spitch += 1.0 * math.sin(2 * w)
        p.px += 5 * wd * math.sin(w)
        p.proll, p.sroll = 1.3 * math.sin(w), -0.8 * math.sin(w)
        p.hyaw, p.hroll = 2.5 * math.sin(w + 1.0), 1.5 * math.sin(w + 0.5)
        for i, sd in enumerate("LR"):
            p.arm[sd]["elbow"] += 2 * math.sin(2 * w + 0.6)
            p.arm[sd]["abd"] += 1.0 * math.sin(w + i)
        return p

    def talk(self, t):
        p, w = self.front(), TAU * t / 1.6
        p.arm["L"].update(flex=18 + 6 * math.sin(w), abd=13, twist=-35, elbow=80 + 10 * math.sin(w + 0.5))
        p.arm["R"].update(flex=18 + 6 * math.sin(w + 2.0), abd=13, twist=35, elbow=80 + 10 * math.sin(w + 2.4))
        p.hpitch, p.hyaw, p.hroll = 3.5 * math.sin(w), 4 * math.sin(w / 2), 2 * math.sin(w / 2 + 1)
        p.spitch += 1.5 * math.sin(w)
        p.py += -2 * self.B.s * (0.5 - 0.5 * math.cos(w))
        return p

    def idol(self, t):
        p, s, wd = self.front(), self.B.s, self.B.w
        beat, half, full = TAU * t / 0.5, TAU * t / 2.0, TAU * t / 4.0
        l_, r_ = sm(max(0.0, math.sin(half)) * 1.25), sm(max(0.0, -math.sin(half)) * 1.25)      # left arm up for a bar, then the right (eased: no kink where it starts)
        p.arm["L"].update(abd=lerp(32, 148, l_), flex=6, twist=lerp(-90, 30, l_), elbow=lerp(78, 34, l_))
        p.arm["R"].update(abd=lerp(32, 148, r_), flex=6, twist=lerp(90, -30, r_), elbow=lerp(78, 34, r_))
        p.py += -9 * s * (0.5 - 0.5 * math.cos(beat))
        p.px += 12 * wd * math.sin(half)
        p.proll, p.sroll, p.hroll = 5 * math.sin(half), -7 * math.sin(half), 5 * math.sin(half + 0.6)
        p.pyaw, p.syaw = 6 * math.sin(full), -10 * math.sin(full)
        step = TAU * t / 1.0
        for sd, v in (("L", max(0.0, math.sin(step)) ** 2), ("R", max(0.0, -math.sin(step)) ** 2)):
            p.foot[sd].update(y=self.B.ankle_h + 16 * s * v, pitch=-20 * v)
        p.face.update(smile=1.0, cheek=0.5)
        return p

    def greet(self, t):
        p, T = self.front(), self.FRONT_T["greet"]
        k = keyf([(0, 0), (0.45, 1), (2.2, 1), (2.75, 0), (T, 0)], t)
        env = keyf([(0, 0), (0.5, 0), (0.7, 1), (2.0, 1), (2.2, 0), (T, 0)], t)
        nod = bump(t, 2.3, 2.95)
        p.arm["R"].update(abd=lerp(10, 112, k), twist=-90 * k, flex=lerp(4, 6, k), elbow=lerp(14, 74, k) + 20 * env * math.sin(TAU * (t - 0.6) / 0.42))
        p.hroll, p.sroll, p.px = -5 * k, 2 * k, 4 * k * self.B.w
        p.hpitch, p.spitch = 10 * nod, p.spitch + 4 * nod
        p.face.update(smile=1.0 if k > 0.3 else 0.0, cheek=0.7 * k, open=1 - 0.8 * nod)
        return p

    def bow(self, t):
        p, T, s = self.front(), self.FRONT_T["bow"], self.B.s
        k = keyf([(0, 0), (0.8, 1), (1.5, 1), (2.3, 0), (T, 0)], t)
        p.ppitch, p.spitch, p.hpitch = 26 * k, p.spitch + 20 * k, 8 * k
        p.pz, p.py = -18 * k * s, -6 * k * s
        p.arm["L"].update(flex=lerp(4, 24, k), abd=lerp(10, 4, k), twist=-90 * k, elbow=lerp(14, 62, k))       # hands meet in front
        p.arm["R"].update(flex=lerp(4, 24, k), abd=lerp(10, 4, k), twist=90 * k, elbow=lerp(14, 62, k))
        p.face.update(smile=1.0 if k > 0.2 else 0.0, open=1 - 0.9 * k)
        return p

    def cheer(self, t):
        T = self.FRONT_T["cheer"]
        p = self.jump(t / T * self.JUMP_T)
        p.heading, p.pyaw, p.syaw, p.hyaw = 0.0, 0.0, 0.0, 0.0
        u = keyf([(0, 0), (0.5, 0), (0.95, 1), (1.7, 1), (2.2, 0), (T, 0)], t)
        wind = bump(t, 0.1, 0.8)
        for sd in "LR":
            p.arm[sd].update(abd=lerp(10, 150, u), flex=lerp(4, 10, u) - 30 * wind, twist=0.0, elbow=lerp(14, 12, u) + 20 * wind)
        p.face.update(smile=1.0 if t > 0.5 else 0.0, mouth=0.9 * u, cheek=0.6 * u)
        return p

    def present(self, t):
        p, T = self.front(), self.FRONT_T["present"]
        k = keyf([(0, 0), (0.6, 1), (2.4, 1), (3.0, 0), (T, 0)], t)
        nod = bump(t, 1.2, 1.85)
        p.pyaw, p.syaw, p.hyaw = -8 * k, -16 * k, 20 * k                        # the body opens to its right, the face stays on the viewer
        p.px, p.proll = -8 * k * self.B.w, 2 * k
        p.arm["R"].update(abd=lerp(10, 84, k), flex=lerp(4, 14, k), twist=0.0, elbow=lerp(14, 10, k))       # shows what is beside it
        p.arm["L"].update(abd=lerp(10, 38, k), flex=lerp(4, -5, k), twist=-90 * k, elbow=lerp(14, 100, k))  # other hand on the hip
        p.hpitch = 8 * nod
        p.face.update(smile=1.0 if k > 0.3 else 0.0, cheek=0.4 * k)
        return p

    def heart(self, t):
        p, T = self.front(), self.FRONT_T["heart"]
        k = keyf([(0, 0), (0.6, 1), (2.1, 1), (2.6, 0), (T, 0)], t)
        sway = math.sin(TAU * (t - 0.6) / 0.9) * keyf([(0, 0), (0.6, 0), (0.8, 1), (1.9, 1), (2.1, 0), (T, 0)], t)
        p.arm["L"].update(abd=lerp(10, 138, k), flex=lerp(4, 8, k), twist=90 * k, elbow=lerp(14, 96, k))      # arms arch over the head
        p.arm["R"].update(abd=lerp(10, 138, k), flex=lerp(4, 8, k), twist=-90 * k, elbow=lerp(14, 96, k))
        p.proll, p.px, p.hroll = 5 * sway, 9 * sway * self.B.w, 6 * sway
        p.face.update(smile=1.0 if k > 0.3 else 0.0, cheek=k)
        return p

    def spin(self, t):
        """A hop with one full turn: every side of the head passes the camera, so face parts must hide and return."""
        B, s, T = self.B, self.B.s, self.FRONT_T["spin"]
        p = self.front()
        T0, T1, T2, T3 = 0.35, 0.55, 1.25, 1.42
        if t < T0:
            py = -40 * sm(t / T0)
        elif t < T1:
            py = -40 + 50 * ((t - T0) / (T1 - T0)) ** 2
        elif t < T2:
            u = (t - T1) / (T2 - T1)
            py = 10 + 4 * 60 * u * (1 - u)
        elif t < T3:
            py = 10 - 42 * (1 - (1 - (t - T2) / (T3 - T2)) ** 2)
        else:
            py = -32 * (1 - sm((t - T3) / (T - T3)))
        p.py = py * s
        p.heading = 360.0 * sm((t - T1 + 0.04) / (T2 - T1 + 0.08))
        air = 1.0 if T1 <= t < T2 else 0.0
        hip_y = B.hip_h - B.hip_drop
        for sd in "LR":
            if air:
                u = (t - T1) / (T2 - T1)
                p.foot[sd].update(y=max(B.ankle_h + 3 * s, hip_y + p.py - (262 - 4 * 26 * u * (1 - u)) * s), pitch=lerp(-42, -14, sm(u)))
        tuck = keyf([(0, 0), (T0, 0.3), (T1 + 0.1, 1), (T2 - 0.1, 1), (T3, 0), (T, 0)], t)
        open_ = bump(t, T2 - 0.05, T - 0.1)
        for sd, sg in (("L", 1.0), ("R", -1.0)):
            p.arm[sd].update(flex=lerp(4, 38, tuck), abd=lerp(10, 14, tuck) + 62 * open_, twist=-sg * 60 * tuck, elbow=lerp(14, 108, tuck))
        p.face.update(smile=1.0 if t > T2 else 0.0, cheek=0.5 * open_)
        return p

    # ---- live parameters (streamer): each one is a pose change from the rest pose, baked as a clip to be laid over others
    def parameters(self):
        B = self.B

        def P(setter):
            def fn(v):
                p = F.rest_pose(B)
                setter(p, v)
                return p
            return fn
        return [("AngleX", "頭左右", -30, 30, 0, P(lambda p, v: (setattr(p, "hyaw", v), setattr(p, "syaw", 0.12 * v)))),
                ("AngleY", "頭上下", -20, 20, 0, P(lambda p, v: setattr(p, "hpitch", -v))),
                ("AngleZ", "頭傾斜", -20, 20, 0, P(lambda p, v: (setattr(p, "hroll", -v), setattr(p, "sroll", -0.15 * v)))),
                ("BodyAngleX", "身體左右", -15, 15, 0, P(lambda p, v: (setattr(p, "pyaw", 0.4 * v), setattr(p, "syaw", 0.6 * v)))),
                ("BodyAngleZ", "身體傾斜", -10, 10, 0, P(lambda p, v: (setattr(p, "proll", -0.5 * v), setattr(p, "sroll", -0.5 * v), setattr(p, "px", 1.0 * v * B.w)))),
                ("EyeBallX", "視線左右", -1, 1, 0, P(lambda p, v: p.face.update(gx=v))),
                ("EyeBallY", "視線上下", -1, 1, 0, P(lambda p, v: p.face.update(gy=v))),
                ("BrowY", "眉毛", -1, 1, 0, P(lambda p, v: p.face.update(brow=v))),
                ("Cheek", "臉紅", 0, 1, 0, P(lambda p, v: p.face.update(cheek=v))),
                ("Smile", "微笑", 0, 1, 0, P(lambda p, v: p.face.update(smile=v))),
                ("MouthOpen", "張嘴", 0, 1, 0, P(lambda p, v: p.face.update(mouth=v))),
                ("Blink", "閉眼", 0, 1, 0, P(lambda p, v: p.face.update(open=1 - v)))]

    # ---- stance / idle
    def stance(self, left=False) -> Pose:
        m_ = -1.0 if left else 1.0
        p = self.B.pose(-90.0 if left else 90.0)
        p.pyaw, p.syaw, p.hyaw, p.spitch = -8.0 * m_, -14.0 * m_, -14.0 * m_, 2.0          # opened toward the camera either way
        return p

    def idle(self, t, T=4.0):
        p, w, s = self.stance(), TAU * t / T, self.B.s
        p.py += (-1.5 + 1.5 * math.sin(2 * w)) * s
        p.spitch += 1.0 * math.sin(2 * w)
        p.px += 5 * self.B.w * math.sin(w)
        p.proll += 1.2 * math.sin(w)
        p.hyaw += 3 * math.sin(w + 1.0)
        p.hroll = 1.5 * math.sin(w + 0.5)
        for i, sd in enumerate("LR"):
            p.arm[sd]["elbow"] += 2 * math.sin(2 * w + 0.6)
            p.arm[sd]["flex"] += 1.5 * math.sin(w + i)
        return p

    # ---- walk
    def _walk_foot(self, q):
        B, s = self.B, self.B.s
        ST, LEAD, adv = 0.62, 105.0 * s, self.WALK_V * self.WALK_T
        heel_z, ball_z = LEAD - B.heel, LEAD + B.ball
        if q < ST:
            u = q / ST
            if u < 0.14:
                a = 16.0 * (1 - sm(u / 0.14))
                z, y = self.heel_rocker(a, heel_z)
                pitch = a
            elif u < 0.60:
                z, y, pitch = LEAD, B.ankle_h, 0.0
            else:
                b = 52.0 * sm((u - 0.60) / 0.40)
                z, y = self.toe_rocker(b, ball_z)
                pitch = -b
            return z - adv * q, y, pitch
        u = (q - ST) / (1 - ST)
        z0, y0 = self.toe_rocker(52.0, ball_z)
        z0 -= adv * ST
        z1, y1 = self.heel_rocker(16.0, heel_z)
        m = -adv * (1 - ST)
        z = (2 * u**3 - 3 * u**2 + 1) * z0 + (u**3 - 2 * u**2 + u) * m + (-2 * u**3 + 3 * u**2) * z1 + (u**3 - u**2) * m
        return z, lerp(y0, y1, sm(u)) + 30 * s * math.sin(math.pi * u) ** 1.3, lerp(-52.0, 16.0, sm(u))

    def walk(self, t, heading=90.0):
        B, s, wd = self.B, self.B.s, self.B.w
        p = B.pose(heading)
        ph = (t / self.WALK_T) % 1.0
        w = TAU * ph
        for sd, off, sign in (("L", 0.0, 1), ("R", 0.5, -1)):
            z, y, pitch = self._walk_foot((ph - off) % 1.0)
            p.foot[sd].update(x=sign * 26.0 * wd, y=y, z=z, pitch=pitch, yaw=sign * 6.0)
        p.py = (-13 + 9 * (0.5 - 0.5 * math.cos(2 * w - TAU * 0.12))) * s
        p.px = 7 * wd * math.sin(w - TAU * 0.06)
        p.proll = 3.5 * math.sin(w - TAU * 0.06)
        p.pyaw = -5 * math.cos(w)
        p.ppitch, p.spitch = 3.0, 4.0
        p.syaw = 9 * math.cos(w)
        p.sroll = -3 * math.sin(w - TAU * 0.06)
        p.hyaw, p.hpitch = -0.9 * (p.pyaw + p.syaw), -4.0
        p.arm["L"].update(flex=2 - 22 * math.cos(w), elbow=22 - 12 * math.cos(w), abd=7)
        p.arm["R"].update(flex=2 + 22 * math.cos(w), elbow=22 + 12 * math.cos(w), abd=7)
        return p

    def turntable(self, t, T=4.0):
        cycles = max(1, round(T / self.WALK_T))
        return self.walk((t / T) * cycles * self.WALK_T + 0.33 * self.WALK_T, heading=90.0 + 360.0 * t / T)

    # ---- run
    def _run_foot(self, q):
        B, s = self.B, self.B.s
        ST, adv, lead = 0.36, self.RUN_V * self.RUN_T, 62.0 * s
        if q < ST:
            u = q / ST
            if u < 0.5:
                k = 1 - sm(u / 0.25)
                z, y, pitch = lead, B.ankle_h + 4 * s * k, -6 * k
            else:
                b = 48.0 * sm((u - 0.5) / 0.5)
                z, y = self.toe_rocker(b, lead + B.ball)
                pitch = -b
            return z - adv * q, y, pitch
        u = (q - ST) / (1 - ST)
        z0, y0 = self.toe_rocker(48.0, lead + B.ball)
        z0 -= adv * ST
        return (curve([(0, z0), (0.25, -195 * s), (0.52, -70 * s), (0.8, 95 * s), (1.0, lead)], u),
                curve([(0, y0), (0.25, B.ankle_h + 124 * s), (0.52, B.ankle_h + 146 * s), (0.8, B.ankle_h + 86 * s), (1.0, B.ankle_h + 4 * s)], u),
                curve([(0, -48), (0.25, -75), (0.55, -25), (1.0, -6)], u))

    def run(self, t):
        B, s, wd = self.B, self.B.s, self.B.w
        p = B.pose(90.0)
        ph = (t / self.RUN_T) % 1.0
        w = TAU * ph
        for sd, off, sign in (("L", 0.0, 1), ("R", 0.5, -1)):
            z, y, pitch = self._run_foot((ph - off) % 1.0)
            p.foot[sd].update(x=sign * 20.0 * wd, y=y, z=z, pitch=pitch, yaw=sign * 4.0)
        p.py = (-10 - 12 * math.cos(2 * w - TAU * 0.36)) * s
        p.px = 4 * wd * math.sin(w - TAU * 0.18)
        p.proll = 3 * math.sin(w - TAU * 0.18)
        p.pyaw, p.syaw = -8 * math.cos(w), 17 * math.cos(w)
        p.ppitch, p.spitch = 8.0, 10.0
        p.hyaw, p.hpitch = -0.9 * (p.pyaw + p.syaw), -12.0
        p.arm["L"].update(flex=6 - 40 * math.cos(w), elbow=88 - 8 * math.cos(w), abd=10)
        p.arm["R"].update(flex=6 + 40 * math.cos(w), elbow=88 + 8 * math.cos(w), abd=10)
        return p

    # ---- jump
    def jump(self, t):
        B, s = self.B, self.B.s
        p = self.stance()
        T0, T1, T2, T3, JT = 0.36, 0.52, 1.00, 1.14, self.JUMP_T
        if t < T0:
            py = -95 * sm(t / T0)
        elif t < T1:
            py = -95 + 107 * ((t - T0) / (T1 - T0)) ** 2
        elif t < T2:
            u = (t - T1) / (T2 - T1)
            py = 12 + 4 * 138 * u * (1 - u)
        elif t < T3:
            u = (t - T2) / (T3 - T2)
            py = 12 - 84 * (1 - (1 - u) ** 2)
        else:
            py = -72 * (1 - sm((t - T3) / (JT - T3)))
        py *= s
        p.py = py
        p.pz = keyf([(0, 0), (T0, -34), (T1, 0), (T2, 0), (T3, -26), (JT, 0)], t) * s
        p.ppitch = keyf([(0, 0), (T0, 30), (T1, 4), (0.76, -2), (T2, 10), (T3, 26), (JT, 0)], t)
        p.spitch += keyf([(0, 0), (T0, 22), (T1, -4), (0.76, 0), (T2, 6), (T3, 18), (JT, 0)], t)
        p.hpitch = keyf([(0, 0), (T0, -18), (T1, -6), (T3, -14), (JT, 0)], t)
        hip_y = B.hip_h - B.hip_drop
        for sd in "LR":
            if t < 0.44:
                z, y, pitch = 0.0, B.ankle_h, 0.0
            elif t < T1:
                b = 50 * sm((t - 0.44) / (T1 - 0.44))
                z, y = self.toe_rocker(b, B.ball)
                pitch = -b
            elif t < T2:
                u = (t - T1) / (T2 - T1)
                leg = (262 - 4 * 46 * u * (1 - u)) * s
                z, y, pitch = lerp(16.0, 10.0, u) * s, max(B.ankle_h + 4 * s, hip_y + py - leg), lerp(-50, -16, sm(u))
            elif t < 1.08:
                b = 16 * (1 - sm((t - T2) / 0.08))
                z, y = self.toe_rocker(b, B.ball)
                pitch = -b
            else:
                z, y, pitch = 0.0, B.ankle_h, 0.0
            p.foot[sd].update(z=z, y=y, pitch=pitch)
            p.arm[sd].update(flex=keyf([(0, 0), (0.34, -55), (T1, 125), (0.76, 150), (T2, 60), (T3, -15), (JT, 0)], t),
                             elbow=keyf([(0, 10), (0.34, 28), (T1, 20), (0.76, 16), (T3, 40), (JT, 10)], t))
        return p

    # ---- wave / pick
    def wave(self, t):
        p, WT = self.stance(), self.WAVE_T
        k = keyf([(0, 0), (0.5, 1), (2.15, 1), (2.7, 0), (WT, 0)], t)
        k2 = keyf([(0, 0), (0.12, 0), (0.6, 1), (2.05, 1), (2.6, 0), (WT, 0)], t)
        env = keyf([(0, 0), (0.6, 0), (0.8, 1), (1.9, 1), (2.1, 0), (WT, 0)], t)
        p.pyaw, p.syaw, p.hyaw = lerp(-8, -26, k), lerp(-14, -38, k), lerp(-14, -24, k)
        p.hroll, p.py, p.px = 5 * k, -3 * k * self.B.s, -4 * k * self.B.w
        p.arm["R"].update(abd=lerp(8, 112, k2), twist=-90 * k2, flex=6 * k2, elbow=lerp(10, 74, k2) + 20 * env * math.sin(TAU * (t - 0.7) / 0.42))
        p.arm["L"]["elbow"] += 6 * k
        return p

    def pick(self, t):
        p, s, PT = self.stance(), self.B.s, self.PICK_T
        k = keyf([(0, 0), (0.95, 1), (1.5, 1), (2.5, 0), (PT, 0)], t)
        reach = keyf([(0, 0), (0.25, 0), (1.05, 1), (1.45, 1), (2.2, 0.25), (PT, 0)], t)
        carry = keyf([(0, 0), (1.45, 0), (2.0, 1), (2.6, 0), (PT, 0)], t)
        p.py, p.pz = -138 * k * s, -44 * k * s
        p.ppitch, p.spitch = 34 * k, 2 + 46 * k
        p.pyaw, p.syaw, p.hyaw = lerp(-8, -2, k), lerp(-14, -6, k), lerp(-14, -4, k)
        p.hpitch = -30 * k
        p.arm["R"].update(flex=88 * reach + 20 * carry, elbow=lerp(10, 22, reach) + 55 * carry)
        p.arm["L"].update(flex=30 * k, elbow=10 + 30 * k)
        return p

    # ---- turn around
    def turn_true(self, t):
        """The real motion: a stepping turn from facing right, through facing the camera, to facing left."""
        B = self.B
        w = sm((t - 0.06) / (self.TURN_T - 0.12))
        st = self.stance()
        p = B.pose(90.0 - 180.0 * w)
        tw = 1 - 2 * w
        p.pyaw, p.syaw = st.pyaw * tw, st.syaw * tw
        p.hyaw = st.hyaw * tw - 18 * math.sin(TAU * w) ** 2
        p.spitch = st.spitch
        steps = {"R": ((0.08, 0.36), (0.80, 1.08)), "L": ((0.38, 0.66), (1.10, 1.38))}
        air = {}
        for sd, sign in (("L", 1), ("R", -1)):
            (a0, a1), (b0, b1) = steps[sd]
            th = 90.0 - 90.0 * sm((t - a0) / (a1 - a0)) - 90.0 * sm((t - b0) / (b1 - b0))
            air[sd] = bump(t, a0, a1) + bump(t, b0, b1)
            r = math.radians(th)
            p.foot[sd] = dict(x=sign * B.stance_x * math.cos(r), y=B.ankle_h + 34 * B.s * air[sd], z=-sign * B.stance_x * math.sin(r), pitch=-14 * air[sd], yaw=th + sign * 7, world=True)
        p.px = 12 * B.w * (air["R"] - air["L"])
        p.py = -5 * B.s * (air["R"] + air["L"])
        return p

    def turn(self, t):
        """For symmetric bodies: the true motion up to the instant the figure squarely faces the camera, then its mirror
        image; the controller flips the skeleton at that instant (event `flip`)."""
        return self.turn_true(t) if t <= self.TURN_MID else mirror(self.turn_true(t))

    # ---- choreographies
    def _build_kungfu(self) -> F.Choreo:
        B, s, wd = self.B, self.B.s, self.B.w
        d, l, hp = (lambda x: x * s), (lambda x: x * wd), B.hip_w * 0.94
        c = F.Choreo(B, heading=90)
        c.key(0.00, pyaw=-8, syaw=-14, hyaw=-14, spitch=2)
        c.key(0.22, heading=82, py=d(-14), armL=(40, 10, 0, 90), armR=(30, 14, 0, 90), footL=("step", d(72), l(20), 0))
        c.key(0.45, heading=75, py=d(-30), pyaw=-22, syaw=-8, hyaw=30, spitch=6, armL=GUARD_L, armR=GUARD_R, footR=("step", d(-72), l(-24), -40))
        c.key(0.70, py=d(-26))
        c.key(0.84, ease="snap", armL=(88, 6, 0, 4), syaw=-30, hyaw=52, pz=d(12), ppitch=4)
        c.key(1.00, armL=GUARD_L, syaw=-8, hyaw=30, pz=0, ppitch=0)
        c.key(1.16, ease="snap", armR=(90, 5, 0, 4), pyaw=14, syaw=30, hyaw=-44, pz=d(14), footR=("pivot", -75))
        c.key(1.36, armR=GUARD_R, pyaw=-22, syaw=-8, hyaw=30, pz=0, footR=("pivot", -40))
        c.key(1.56, py=d(-16), px=l(10), pyaw=-6, syaw=0, hyaw=6, footR=("fk", 95, 6, 0, 118, 0))
        c.key(1.70, ease="snap", ppitch=-12, spitch=0, armL=(40, 20, 0, 100), armR=(20, 25, 0, 95), footR=("fk", 94, 4, 0, 6, -20))
        c.key(1.86, ppitch=-4, spitch=6, armL=GUARD_L, armR=GUARD_R, footR=("fk", 96, 6, 0, 112, 0))
        c.key(2.08, advance=(d(95), 0), py=d(-30), px=0, ppitch=0, pyaw=22, syaw=8, hyaw=-30, footR=("step", d(75), l(-22), 0), footL=("pivot", 40))
        r_a = c.cur["root"]
        c.key(2.30, heading=30, root=c.spot("R"), px=hp, py=d(-20), pyaw=0, syaw=10, hyaw=42, proll=10, armL=(-10, 30, 0, 60), footR=("pivot", -50), footL=("fk", 35, 55, -20, 115, 0))
        c.key(2.44, ease="snap", heading=8, py=d(-16), proll=26, sroll=8, syaw=22, hyaw=52, armL=(-35, 35, 0, 25), armR=(55, 20, 0, 120), footR=("pivot", -80), footL=("fk", 15, 86, 0, 4, -25))
        c.key(2.60, heading=20, proll=12, sroll=0, armL=GUARD_L, footL=("fk", 30, 60, -10, 112, 0))
        h75 = math.radians(75)
        r_b = (r_a[0] + d(147) * math.sin(h75), r_a[1] + d(147) * math.cos(h75))
        c.key(2.84, heading=75, root=r_b, py=d(-30), px=0, proll=0, pyaw=-22, syaw=-8, hyaw=30, armR=GUARD_R, footL=("step", d(72), l(20), 0), footR=("pivot", -40))
        c.key(3.05, heading=20, root=c.spot("L"), px=-hp, py=d(-24), pyaw=-10, syaw=-25, hyaw=-55, footL=("pivot", -30), footR=("fk", 30, 10, 0, 95, 0))
        c.key(3.22, heading=-95, py=d(-22), ppitch=28, spitch=10, pyaw=0, syaw=-10, hyaw=-70, footL=("pivot", -20), footR=("fk", 55, 0, 0, 120, 0))
        c.key(3.34, ease="snap", heading=-105, py=d(-16), ppitch=52, spitch=6, hyaw=-75, armL=(50, 20, 0, 110), armR=(30, 25, 0, 90), footR=("fk", -72, 0, 0, 4, -30))
        c.key(3.50, heading=-150, ppitch=25, hyaw=-40, armL=GUARD_L, armR=GUARD_R, footR=("fk", 20, 0, 0, 110, 0))
        c.key(3.74, heading=-285, root=r_b, py=d(-30), px=0, ppitch=0, spitch=6, pyaw=-22, syaw=-8, hyaw=30, footL=("pivot", 0), footR=("step", d(-72), l(-24), -40))
        c.key(4.00, py=d(-34))
        c.key(4.22, ease="snap", pz=d(42), py=d(-62), pyaw=20, syaw=26, hyaw=-46, spitch=4, armR=(92, 4, 0, 3), armL=(-25, 10, 0, 125), footR=("pivot", -65))
        c.key(4.75, py=d(-58))
        c.key(5.05, heading=-278, root=(r_b[0] * 0.5, r_b[1] * 0.5), pz=0, py=d(-24), pyaw=-8, syaw=-10, hyaw=10, spitch=4, armL=(30, 10, 0, 70), armR=(30, 10, 0, 70), footL=("step", d(-20), B.stance_x * 0.9, 7))
        c.key(5.32, heading=-270, root=(r_b[0] * 0.22, r_b[1] * 0.22), py=d(-22), syaw=-14, hyaw=-14, spitch=2, armL=(12, 9, 0, 30), armR=(12, 9, 0, 30), footR=("step", d(-10), -B.stance_x, -7))
        c.key(5.58, root=(0, 0), py=d(-20), armL=DOWN, armR=DOWN, footL=("step", 0, B.stance_x, 7))
        c.key(5.84, py=d(-8), footR=("step", 0, -B.stance_x, -7))
        c.key(6.10, py=0)
        return c

    def _build_dance(self) -> F.Choreo:
        B, s = self.B, self.B.s
        sw = (B.w + s) / 2
        d, l, hp, sx = (lambda x: x * s), (lambda x: x * sw), B.hip_w, B.stance_x
        c = F.Choreo(B, heading=90)
        c.key(0.00, pyaw=-8, syaw=-14, hyaw=-14, spitch=2)
        c.key(0.25, heading=55, pyaw=-4, syaw=-6, hyaw=-6, footR=("step", 0, -sx * 1.15, -10))
        c.key(0.50, heading=20, pyaw=0, syaw=0, hyaw=0, py=d(-8), footL=("step", 0, sx * 1.15, 10), footR=("pivot", -10))
        c.key(1.00, px=l(-40), py=d(-14), proll=6, sroll=-10, hroll=-5, armL=(10, 75, 0, 25), armR=(25, 20, 0, 85), footR=("step", 0, l(-84), -14))
        c.key(1.50, px=l(-46), py=d(-6), proll=0, sroll=0, hroll=0, armL=(45, 28, 0, 95), armR=(45, 28, 0, 95), footL=("step", 0, l(-14), 6, 22 * s))
        c.key(2.00, px=l(30), py=d(-14), proll=-6, sroll=10, hroll=5, armR=(10, 75, 0, 25), armL=(25, 20, 0, 85), footL=("step", 0, l(78), 14))
        c.key(2.50, px=l(38), py=d(-6), proll=0, sroll=0, hroll=0, armL=(45, 28, 0, 95), armR=(45, 28, 0, 95), footR=("step", 0, l(8), -6, 22 * s))
        c.key(3.00, py=d(-34), ppitch=12, spitch=-16, hpitch=-12, armL=(150, 22, 0, 18), armR=(150, 22, 0, 18))
        c.key(3.40, py=d(-6), ppitch=-4, spitch=10, hpitch=4, armL=(60, 40, 0, 75), armR=(60, 40, 0, 75))
        c.key(3.70, root=c.spot("L"), px=-hp, py=d(-3), ppitch=0, spitch=2, hpitch=0, armL=(50, 25, 0, 105), armR=(50, 25, 0, 105), footR=("fk", 62, 38, 30, 118, -30))
        c.key(4.30, ease="linear", heading=380, footL=("pivot", 10))
        c.key(4.60, root=(0, 0), px=l(6), py=d(-18), proll=-5, sroll=6, hroll=-6, armL=(15, 95, 0, 8), armR=(165, 18, 0, 8), footR=("step", 0, l(-76), -14))
        c.key(5.10, px=l(-26), py=d(-20), proll=8, sroll=-12, hroll=6, armR=(40, 60, 0, 60), armL=(10, 35, 0, 45))
        c.key(5.60, px=l(26), proll=-8, sroll=12, hroll=-6, armL=(40, 60, 0, 60), armR=(10, 35, 0, 45))
        c.key(5.95, heading=420, px=0, py=d(-8), proll=0, sroll=0, hroll=0, pyaw=-4, syaw=-8, hyaw=-8, armL=(10, 12, 0, 30), armR=(10, 12, 0, 30), footR=("step", 0, -sx, -7))
        c.key(6.25, heading=450, pyaw=-8, syaw=-14, hyaw=-14, spitch=2, armL=DOWN, armR=DOWN, footL=("step", 0, sx, 7), footR=("pivot", -7))
        c.key(6.60, py=0)
        return c

    def kungfu(self, t):
        return self._kungfu.pose(t)

    def dance(self, t):
        p = self._dance.pose(t)
        env = min(1.0, max(0.0, (t - 0.5) / 0.3)) * min(1.0, max(0.0, (5.9 - t) / 0.3))
        p.py -= 7 * self.B.s * env * (0.5 - 0.5 * math.cos(TAU * (t - 0.5) / 0.5))
        return p


LABELS = {"front_idle": "待機", "talk": "說話手勢", "idol": "偶像舞步", "greet": "打招呼", "bow": "鞠躬", "cheer": "歡呼跳", "present": "介紹", "heart": "比愛心", "spin": "轉一圈",
          "block": "舉盾格擋", "slash": "揮砍", "bash": "盾擊", "cast": "施法", "channel": "引導",
          "idle": "待機", "walk": "走", "run": "跑", "jump": "跳", "wave": "揮手", "pick": "撿東西", "turn": "轉身", "turntable": "360° 走", "kungfu": "武打", "dance": "跳舞"}


def front_set(rig, B: F.Body, fps: int = 30) -> Motions:
    """Showcase / streamer set: clips that face the camera, plus live parameters.

    Clips play on track 0.  Each parameter is a one-second clip whose time means "value": the controller holds it at the
    time for the current value on its own track with additive blending, so head turns, gaze, blinks and mouth shapes lay
    over whatever clip is playing.  Hair links are simulated by the runtime, so they react to live input too."""
    M = Motions(B)
    for ev_name in ("flip", "step", "hit", "cast"):
        rig.event(ev_name)
    loops = ("front_idle", "talk", "idol")
    for name in ("front_idle", "talk", "idol", "greet", "bow", "cheer", "present", "heart", "spin"):
        fn = getattr(M, name)
        if name == "idol":
            fn = (lambda t, fn=fn: fn(t + 0.37))             # keep the loop seam off the instant the arms change over
        F.bake(rig, name, fn, M.FRONT_T[name], B, loop=name in loops, fps=fps, key_all=True)      # parameters are laid over these
    params = []
    for i, (pid, label, lo, hi, default, fn) in enumerate(M.parameters()):
        F.bake(rig, f"p_{pid}", (lambda t, fn=fn, lo=lo, hi=hi: fn(lo + (hi - lo) * t)), 1.0, B, fps=12, param=True)
        params.append({"id": pid, "label": label, "min": lo, "max": hi, "default": default, "clip": f"p_{pid}", "track": 10 + i})
    shots = [("greet_wave", "greet", 1.2, {}), ("bow_low", "bow", 1.2, {}), ("cheer_apex", "cheer", 1.2, {}), ("present", "present", 1.5, {}), ("heart", "heart", 1.4, {}),
             ("idol_a", "idol", 0.5, {}), ("idol_b", "idol", 1.5, {}), ("talk", "talk", 0.4, {"MouthOpen": 0.8}), ("spin_side", "spin", 0.75, {}), ("spin_back", "spin", 0.9, {}),
             ("head_left", "front_idle", 0.0, {"AngleX": -30, "EyeBallX": -1}), ("head_right", "front_idle", 0.0, {"AngleX": 30, "EyeBallX": 1}),
             ("head_up", "front_idle", 0.0, {"AngleY": 20}), ("head_down", "front_idle", 0.0, {"AngleY": -20}), ("head_tilt", "front_idle", 0.0, {"AngleZ": 20, "BodyAngleZ": 10}),
             ("combo", "front_idle", 0.0, {"AngleX": 25, "AngleY": 12, "AngleZ": -10, "BodyAngleX": 12}), ("blink", "front_idle", 0.0, {"Blink": 1}), ("half", "front_idle", 0.0, {"Blink": 0.5}),
             ("smile", "front_idle", 0.0, {"Smile": 1, "Cheek": 1, "BrowY": 0.5}), ("angry", "front_idle", 0.0, {"BrowY": -1}), ("mouth_s", "front_idle", 0.0, {"MouthOpen": 0.3}),
             ("mouth_l", "front_idle", 0.0, {"MouthOpen": 1, "BrowY": 1})]
    for label, anim, t, pv in shots:
        rig.stress(label, tracks=[{"track": 0, "anim": anim, "time": t, "loop": False}])
        if pv:
            rig.stress_poses[-1]["seek"]["params"] = pv
    meta = {}
    for name in rig.animations:
        if name.startswith("p_"):
            meta[name] = {"label": name, "role": "param", "hidden": True}
        else:
            meta[name] = {"label": LABELS.get(name, name), "loop": name in loops, "role": "base" if name in loops else "action", **({} if name in loops else {"return": "front_idle"})}
    h = B.height
    rig.contract(title=f"白模 {F.PRESET_ZH.get(B.preset, B.preset)}", background="#5b6878", mix={"default": 0.2}, follow=False, home="front_idle", animations=meta, parameters=params,
                 facing={"mode": "flip"}, events={"flip": {"action": "toggle_facing"}}, body={"preset": B.preset, "height": round(h), "asymmetric": B.asymmetric})
    return M


def standard_set(rig, B: F.Body, clips=None, fps: int = 30) -> Motions:
    """Bake the standard clip set for a body and write its controller contract.

    Symmetric bodies face left by mirroring the skeleton (the `turn` clip fires `flip` at its symmetric instant).
    Asymmetric bodies (a bag on one shoulder, a club in one hand) must not be mirrored -- the bag would jump to the other
    shoulder -- so every clip is baked twice, facing right and facing left (`_L`), and the controller picks by facing."""
    if B.clipset == "front":
        return front_set(rig, B, fps=fps)
    M = Motions(B)
    rig.event("flip")
    rig.event("step")
    w_off, r_off = 0.33 * M.WALK_T, 0.21 * M.RUN_T
    for ev_name in ("hit", "cast"):
        rig.event(ev_name)
    base = [("idle", M.idle, 4.0, True, []),
            ("walk", lambda t: M.walk(t + w_off), M.WALK_T, True, [(round(M.WALK_T - w_off, 3), "step"), (round(M.WALK_T / 2 - w_off, 3), "step")]),
            ("run", lambda t: M.run(t + r_off), M.RUN_T, True, [(round(M.RUN_T - r_off, 3), "step"), (round(M.RUN_T / 2 - r_off, 3), "step")]),
            ("jump", M.jump, M.JUMP_T, False, [])]
    acts = []
    if B.clipset == "knight":
        acts = [("block", M.block, M.BLOCK_T, False, []), ("slash", M.slash, M.SLASH_T, False, [(0.56, "hit")]), ("bash", M.bash, M.BASH_T, False, [(0.38, "hit")])]
    elif B.clipset == "mage":
        acts = [("cast", M.cast, M.CAST_T, False, [(0.95, "cast")]), ("channel", M.channel, M.CHANNEL_T, True, [])]
    else:
        base += [("wave", M.wave, M.WAVE_T, False, []), ("pick", M.pick, M.PICK_T, False, []), ("kungfu", M.kungfu, M.KUNGFU_T, False, []), ("dance", M.dance, M.DANCE_T, False, [])]
    base = [row for row in base if clips is None or row[0] in clips]
    acts = [row for row in acts if clips is None or row[0] in clips]
    asym = B.asymmetric
    # Locomotion: facing left is the mirrored clip, with whatever is carried put back in the hands that carry it.
    for name, fn, dur, loop, ev in base:
        F.bake(rig, name, (lambda t, fn=fn: M.held(fn(t))), dur, B, loop=loop, fps=fps, events=ev)
        if asym:
            F.bake(rig, name + "_L", (lambda t, fn=fn: M.held(mirror(fn(t)))), dur, B, loop=loop, fps=fps, events=ev)
    # Class actions: facing left is the same action by the same arms, body turned round.
    for name, fn, dur, loop, ev in acts:
        F.bake(rig, name, (lambda t, fn=fn: fn(t, False)), dur, B, loop=loop, fps=fps, events=ev)
        if asym:
            F.bake(rig, name + "_L", (lambda t, fn=fn: fn(t, True)), dur, B, loop=loop, fps=fps, events=ev)
    if clips is None or "turntable" in clips:
        F.bake(rig, "turntable", lambda t: M.held(M.turntable(t)), 4.0, B, loop=True, fps=24)
    if clips is None or "turn" in clips:
        if asym:
            # `flip` fires as the body passes the front, not at the very end: the tail of a clip is mixed out, and events of
            # a clip that is being mixed out are not delivered.
            F.bake(rig, "turn", lambda t: M.held(M.turn_true(t)), M.TURN_T, B, fps=fps, events=[(M.TURN_MID, "flip")])
            F.bake(rig, "turn_L", lambda t: M.held(mirror(M.turn_true(t))), M.TURN_T, B, fps=fps, events=[(M.TURN_MID, "flip")])
        else:
            F.bake(rig, "turn", M.turn, M.TURN_T, B, fps=fps, events=[(M.TURN_MID, "flip")])
    for label, anim, t in (("walk_contact", "walk", round(M.WALK_T * 0.67, 3)), ("run_flight", "run", round(M.RUN_T * 0.28, 3)), ("jump_apex", "jump", 0.76), ("wave_up", "wave", 1.2),
                           ("pick_low", "pick", 1.2), ("kick_front", "kungfu", 1.70), ("kick_round", "kungfu", 2.44), ("kick_back", "kungfu", 3.34), ("dance_spin", "dance", 4.0), ("dance_pose", "dance", 4.6),
                           ("block_up", "block", 0.6), ("slash_wind", "slash", 0.40), ("slash_cut", "slash", 0.56), ("bash_hit", "bash", 0.40), ("cast_raise", "cast", 0.70), ("cast_release", "cast", 1.0),
                           ("channel", "channel", 0.6), ("facing_left_idle", "idle_L", 0.0), ("slash_cut_left", "slash_L", 0.56), ("cast_release_left", "cast_L", 1.0)):
        if anim in rig.animations:
            rig.stress(label, tracks=[{"track": 0, "anim": anim, "time": t, "loop": False}])
    meta = {}
    for name in rig.animations:
        base = name[:-2] if name.endswith("_L") else name
        loops = ("idle", "walk", "run", "turntable", "channel")
        m = {"label": LABELS.get(base, base), "loop": base in loops, "role": "base" if base in loops else "action"}
        if m["role"] == "action":
            m["return"] = "idle"
        if base == "walk":
            m.update(speed=round(M.WALK_V, 2), feet=["ankle_L", "ankle_R"], contactHeight=0.4)
        if base == "run":
            m.update(speed=round(M.RUN_V, 2), feet=["ankle_L", "ankle_R"], contactHeight=0.4)
        if base == "turn":
            m["turns"] = True
        if name.endswith("_L"):
            m.update(hidden=True, facing="left", alias=base)
        meta[name] = m
    h = B.height
    rig.contract(title=f"白模 {F.PRESET_ZH.get(B.preset, B.preset)}", background="#5b6878", mix={"default": 0.18}, follow=False, animations=meta,
                 facing={"mode": "clips", "suffix": "_L"} if asym else {"mode": "flip"},
                 events={"flip": {"action": "toggle_facing"}},
                 patrol={"walk": "walk", "turn": "turn", "min": -380, "max": 380, "portrait": {"min": -0.18 * h, "max": 0.18 * h}},
                 body={"preset": B.preset, "height": round(h), "asymmetric": asym})
    return M
