#!/usr/bin/env python3
"""霜 (Shuang) -- layered art, generated in code.  `spk art` runs this and rasterises one PNG per part.

Order of art.part() calls = draw order, back to front.  Every part is drawn complete (underpaint included).
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:                                                               # `spk art` puts the kit on PYTHONPATH
    from spinekit.svgart import Art, smooth, poly, ribbon, path, circle, ellipse, group, shift
except ImportError:
    sys.exit("run this through the kit:  python3 <kit>/spk.py art <project>")
import design as D  # noqa: E402
from design import mx, flip, CX  # noqa: E402

# ---- palette ---------------------------------------------------------------------------------------
SKIN, SKIN_SH, SKIN_SH2, SKIN_LINE = "#f9ebe5", "#edd0ce", "#dcb1b6", "#c79ca1"
HAIR_A, HAIR_B, HAIR_LT, HAIR_DK, HAIR_RIM = "#2a2c3a", "#15161d", "#4a4f6c", "#0b0b10", "#8c9ac4"
SHIRT, SHIRT_SH, SHIRT_SH2, SHIRT_LINE = "#f5f7fb", "#d3dae8", "#aeb8cf", "#8f99b1"
LASH, IRIS_A, IRIS_B, IRIS_RING, PUPIL = "#17171f", "#3b4860", "#8fa5c2", "#262f42", "#0f1219"
LIP, LIP_LINE = "#e3959d", "#a95c68"


def lerp_pts(a, b, t):
    return [(ax + (bx - ax) * t, ay + (by - ay) * t) for (ax, ay), (bx, by) in zip(a, b)]


def build() -> Art:
    art = Art(D.W, D.H)
    soft2, soft4, soft8, soft14 = art.blur(2), art.blur(4), art.blur(8), art.blur(14)

    def hair(d, y0, y1, strands=(), rim=None, halo=None, extra=""):
        """Hair piece: vertical base gradient, flowing strand lines, cool rim light, optional halo band."""
        clip = art.clip(d)
        g = art.linear(0, y0, 0, y1, [(0, HAIR_A), (1, HAIR_B)])
        inner = []
        for pts, col, sw, op in strands:
            inner.append(path(smooth(pts, closed=False), stroke=col, sw=sw, opacity=op))
        if halo:
            inner.append(path(smooth(halo, closed=False), stroke=HAIR_RIM, sw=13, opacity=0.33, filter=soft4))
            inner.append(path(smooth(shift(halo, 0, -2), closed=False), stroke="#c7d1ee", sw=3.2, opacity=0.30, filter=soft2))
        if rim:
            inner.append(path(smooth(rim, closed=False), stroke=HAIR_RIM, sw=5, opacity=0.42, filter=soft2))
        return path(d, fill=g) + group(*inner, clip_path=clip) + extra

    def flow(left, right, fracs, col=HAIR_LT, sw=1.6, op=0.5):
        return [(lerp_pts(left, right, t), col, sw, op) for t in fracs]

    # =============================================================================== hair_back
    hb_right = [(500, 122), (566, 128), (618, 158), (646, 212), (660, 290), (672, 380), (684, 470), (692, 560), (694, 660), (688, 760), (676, 860), (658, 950), (634, 1024)]
    hb_bottom = [(606, 1044), (580, 1018), (552, 1050), (526, 1022), (500, 1054), (474, 1022), (448, 1050), (420, 1018), (394, 1044)]
    hb = hb_right + hb_bottom + mx(hb_right)[:-1]
    hb_d = smooth(hb)
    lcol = [(352, 300), (326, 470), (308, 660), (322, 860), (368, 1020)]
    rcol = mx(lcol)[::-1]
    art.part("hair_back", hair(hb_d, 120, 1050,
                               strands=flow(lcol, rcol, (0.06, 0.16, 0.27, 0.38, 0.5, 0.62, 0.73, 0.84, 0.94), HAIR_LT, 2.2, 0.33) + flow(lcol, rcol, (0.11, 0.33, 0.56, 0.79), HAIR_DK, 3.2, 0.5),
                               rim=[(338, 300), (314, 470), (300, 660), (310, 860), (350, 1000)]))

    # =============================================================================== collar_back (stand, behind the neck)
    cb = [(444, 506), (466, 486), (500, 481), (534, 486), (556, 506), (550, 548), (500, 556), (450, 548)]
    art.part("collar_back", path(smooth(cb), fill=art.linear(0, 480, 0, 556, [(0, SHIRT_SH2), (1, SHIRT_SH)]), stroke=SHIRT_LINE, sw=1.4))

    # =============================================================================== neck (+ chest skin shown in the shirt opening)
    neck = [(459, 418), (541, 418), (543, 470), (549, 518), (600, 556), (576, 700), (424, 700), (400, 556), (451, 518), (457, 470)]
    neck_d = smooth(neck, tension=0.35)
    nclip = art.clip(neck_d)
    art.part("neck",
             path(neck_d, fill=SKIN),
             group(
                 ellipse(500, 442, 66, 48, fill=SKIN_SH2, opacity=0.9, filter=soft8),                     # shadow cast by the jaw
                 path(smooth([(455, 420), (449, 520), (414, 566)], closed=False), stroke=SKIN_SH, sw=16, opacity=0.8, filter=soft4),
                 path(smooth([(545, 420), (551, 520), (586, 566)], closed=False), stroke=SKIN_SH2, sw=20, opacity=0.7, filter=soft4),
                 path(smooth([(448, 572), (472, 581), (494, 576)], closed=False), stroke=SKIN_SH2, sw=3, opacity=0.6, filter=soft2),   # clavicles
                 path(smooth([(552, 572), (528, 581), (506, 576)], closed=False), stroke=SKIN_SH2, sw=3, opacity=0.6, filter=soft2),
                 ellipse(500, 650, 44, 44, fill=SKIN_SH, opacity=0.5, filter=soft8),
                 clip_path=nclip),
             path(smooth([(458, 448), (455, 482), (450, 518)], closed=False), stroke=SKIN_LINE, sw=1.3, opacity=0.8),
             path(smooth([(542, 448), (545, 482), (550, 518)], closed=False), stroke=SKIN_LINE, sw=1.3, opacity=0.8))

    # =============================================================================== torso (shirt body with the V opening)
    t_left = [(466, 510), (432, 524), (384, 546), (336, 570), (304, 596), (298, 640), (326, 690), (350, 760), (364, 840), (376, 920), (364, 1000), (350, 1080), (344, 1200)]
    torso_outer = t_left + mx(t_left)
    v_open = [(466, 510), (478, 566), (500, 672), (522, 566), (534, 510)]                                   # shirt opening (hole)
    outer_d = smooth(torso_outer, tension=0.4)
    torso_d = outer_d + poly(v_open)
    tclip = art.clip(torso_d, rule="evenodd")
    shade = group(
        path(smooth([(330, 640), (358, 780), (382, 920), (356, 1080), (348, 1200)], closed=False), stroke=SHIRT_SH, sw=50, opacity=0.9, filter=soft14),
        path(smooth([(670, 640), (642, 780), (618, 920), (644, 1080), (652, 1200)], closed=False), stroke=SHIRT_SH2, sw=58, opacity=0.75, filter=soft14),
        ellipse(448, 772, 48, 30, fill=SHIRT_SH, opacity=0.5, filter=soft14),                                # soft bust form
        ellipse(552, 772, 48, 30, fill=SHIRT_SH, opacity=0.6, filter=soft14),
        path(smooth([(392, 812), (444, 830), (500, 820), (556, 830), (608, 812)], closed=False), stroke=SHIRT_SH2, sw=9, opacity=0.45, filter=soft8),
        path(smooth([(424, 852), (416, 950), (404, 1070), (400, 1200)], closed=False), stroke=SHIRT_SH, sw=11, opacity=0.8, filter=soft4),
        path(smooth([(576, 852), (586, 950), (598, 1070), (602, 1200)], closed=False), stroke=SHIRT_SH2, sw=12, opacity=0.6, filter=soft4),
        path(smooth([(462, 890), (452, 1010), (458, 1200)], closed=False), stroke=SHIRT_SH, sw=6, opacity=0.6, filter=soft4),
        path(smooth([(544, 900), (552, 1020), (548, 1200)], closed=False), stroke=SHIRT_SH2, sw=6, opacity=0.4, filter=soft4),
        path(smooth([(410, 548), (452, 612), (486, 684)], closed=False), stroke=SHIRT_SH2, sw=16, opacity=0.55, filter=soft4),   # shadow under the collar leaves
        path(smooth([(590, 548), (548, 612), (514, 684)], closed=False), stroke=SHIRT_SH2, sw=16, opacity=0.6, filter=soft4),
        path(smooth([(336, 574), (372, 600), (398, 650)], closed=False), stroke=SHIRT_SH, sw=10, opacity=0.6, filter=soft4),     # shoulder drape
        path(smooth([(664, 574), (628, 600), (602, 650)], closed=False), stroke=SHIRT_SH2, sw=10, opacity=0.6, filter=soft4),
        clip_path=tclip)
    pocket = [(552, 716), (606, 712), (608, 766), (581, 778), (554, 768)]
    placket = group(
        path(poly([(490, 676), (490, 1200)], closed=False), stroke=SHIRT_LINE, sw=1.3, opacity=0.75),
        path(poly([(510, 676), (510, 1200)], closed=False), stroke=SHIRT_LINE, sw=1.3, opacity=0.75),
        path(smooth(pocket, tension=0.15), stroke=SHIRT_LINE, sw=1.2, opacity=0.6),
        *[circle(500, y, 5.2, fill="#e9edf5", stroke=SHIRT_LINE, stroke_width=1.2) + circle(498.6, y - 1.2, 1.1, fill="#9aa4bb") + circle(501.6, y + 1.2, 1.1, fill="#9aa4bb") for y in (716, 816, 916, 1016, 1116)],
        clip_path=tclip)
    art.part("torso",
             path(torso_d, fill=art.linear(0, 520, 0, 1200, [(0, SHIRT), (1, "#e6ebf4")]), fill_rule="evenodd"),
             shade, placket,
             path(outer_d, stroke=SHIRT_LINE, sw=1.6, opacity=0.9),
             path(poly(v_open, closed=False), stroke=SHIRT_LINE, sw=1.4, opacity=0.9))

    # =============================================================================== arms (long sleeves, hanging)
    def arm(side):
        outer = [(346, 574), (312, 590), (290, 632), (280, 720), (275, 800), (272, 866), (270, 970), (268, 1090), (266, 1200)]
        inner = [(338, 1200), (340, 1090), (342, 970), (344, 876), (350, 800), (356, 724), (362, 664), (366, 612)]
        pts = outer + inner
        fold = [[(292, 660), (318, 716), (346, 730)], [(280, 826), (308, 854), (340, 846)], [(276, 904), (304, 890), (338, 908)], [(272, 1050), (304, 1072), (336, 1052)]]
        hl = [(298, 630), (288, 720), (282, 810), (280, 910), (276, 1100)]
        core = [(332, 640), (328, 770), (320, 910), (318, 1110)]
        seam = [(318, 588), (336, 610), (352, 622), (364, 618)]
        if side == "R":
            pts, fold, hl, core, seam = mx(pts), [mx(f_) for f_ in fold], mx(hl), mx(core), mx(seam)
        d = smooth(pts, tension=0.4)
        c = art.clip(d)
        dark = SHIRT_SH2 if side == "R" else SHIRT_SH
        return (path(d, fill=SHIRT)
                + group(path(smooth(core, closed=False), stroke=dark, sw=36, opacity=0.8, filter=soft14),
                        *[path(smooth(f_, closed=False), stroke=SHIRT_SH2, sw=4, opacity=0.6, filter=soft2) for f_ in fold],
                        path(smooth(hl, closed=False), stroke="#ffffff", sw=8, opacity=0.8, filter=soft4),
                        path(smooth(seam, closed=False), stroke=SHIRT_LINE, sw=1.1, opacity=0.55),
                        clip_path=c)
                + path(d, stroke=SHIRT_LINE, sw=1.6, opacity=0.9))
    art.part("arm_L", arm("L"))
    art.part("arm_R", arm("R"))

    # =============================================================================== collar leaves
    def collar(side):
        leaf = [(467, 488), (442, 502), (404, 556), (430, 632), (480, 584), (473, 526)]
        fold = [(448, 506), (420, 556), (436, 616)]
        if side == "R":
            leaf, fold = mx(leaf), mx(fold)
        d = smooth(leaf, tension=0.25)
        c = art.clip(d)
        return (path(d, fill=SHIRT)
                + group(path(smooth(fold, closed=False), stroke=SHIRT_SH if side == "L" else SHIRT_SH2, sw=14, opacity=0.8, filter=soft4), clip_path=c)
                + path(d, stroke=SHIRT_LINE, sw=1.6, opacity=0.95))
    art.part("collar_L", collar("L"))
    art.part("collar_R", collar("R"))

    # =============================================================================== locks falling in front of the shoulders
    def lock(center, widths, side, dxs_lt, dxs_dk, rim_dx):
        if side == "R":
            center = [flip(p) for p in center]
            dxs_lt, dxs_dk, rim_dx = [-v for v in dxs_lt], [-v for v in dxs_dk], rim_dx
        d = ribbon(center, widths)
        body = center[:-1]
        strands = [(shift(body, dx, 0), HAIR_LT, 1.7, 0.45) for dx in dxs_lt] + [(shift(body, dx, 0), HAIR_DK, 2.6, 0.5) for dx in dxs_dk]
        return hair(d, center[0][1], center[-1][1], strands=strands, rim=shift(body, rim_dx, 0))
    side_c = [(366, 250), (352, 350), (338, 450), (326, 550), (318, 650), (316, 750), (320, 840), (326, 904)]
    side_w = [24, 32, 36, 38, 36, 30, 18, 0]
    long_c = [(378, 236), (370, 330), (362, 430), (356, 530), (356, 630), (362, 730), (368, 830), (374, 920), (378, 976)]
    long_w = [30, 40, 46, 50, 50, 46, 38, 22, 0]
    art.part("hair_side_L", lock(side_c, side_w, "L", (-8, 4), (-2, 10), -15))
    art.part("hair_side_R", lock(side_c, side_w, "R", (-8, 4), (-2, 10), -17))
    art.part("hair_long_L", lock(long_c, long_w, "L", (-13, -3, 9), (-8, 14), -20))
    art.part("hair_long_R", lock(long_c, long_w, "R", (-13, -3, 9), (-8, 14), -22))

    # =============================================================================== eyes behind the face: whites + irises
    def eye_white(side):
        hole = D.EYE_HOLE_L if side == "L" else mx(D.EYE_HOLE_L)
        cx, cy = D.EYE_L if side == "L" else D.EYE_R
        big = [(cx + (x - cx) * 1.3, cy + (y - cy) * 1.55) for x, y in hole]
        d = smooth(big)
        c = art.clip(d)
        return path(d, fill="#f1f4fa") + group(ellipse(cx, cy - 15, 42, 13, fill="#a3adc7", opacity=0.9, filter=soft4), clip_path=c)
    art.part("eye_white_L", eye_white("L"))
    art.part("eye_white_R", eye_white("R"))

    def iris(side):
        cx, cy = D.EYE_L if side == "L" else D.EYE_R
        cx += 1.0 if side == "L" else -1.0
        cy += 0.6
        r = 15.0
        g = art.linear(0, cy - r, 0, cy + r, [(0, IRIS_A), (0.5, "#566884"), (1, IRIS_B)])
        c = art.clip(f"M{cx - r},{cy}a{r},{r} 0 1,0 {2 * r},0a{r},{r} 0 1,0 {-2 * r},0Z")
        return (circle(cx, cy, r, fill=g)
                + group(ellipse(cx, cy - 12, 19, 10, fill="#182030", opacity=0.8, filter=soft2),               # shadow from the upper lid
                        ellipse(cx, cy + 9.5, 10, 5, fill="#cfe0f4", opacity=0.6, filter=soft2),                # reflected light
                        clip_path=c)
                + circle(cx, cy, r - 0.9, stroke=IRIS_RING, stroke_width=1.8, opacity=0.9)
                + circle(cx, cy + 0.5, 6.0, fill=PUPIL)
                + ellipse(cx - 5.6, cy - 6.4, 4.5, 3.5, fill="#ffffff", opacity=0.96)
                + circle(cx + 6.0, cy + 6.6, 1.8, fill="#ffffff", opacity=0.85))
    art.part("iris_L", iris("L"))
    art.part("iris_R", iris("R"))

    # =============================================================================== face (skin with two eye openings)
    face_d = smooth(D.FACE)
    holes = smooth(D.EYE_HOLE_L) + smooth(mx(D.EYE_HOLE_L))
    fclip = art.clip(face_d + holes, rule="evenodd")
    bang_shadow = art.linear(0, 200, 0, 320, [(0, SKIN_SH2, 0.95), (0.6, SKIN_SH, 0.6), (1, SKIN_SH, 0)])
    far_shadow = art.linear(562, 0, 618, 0, [(0, SKIN_SH, 0), (1, SKIN_SH2, 0.8)])
    near_shadow = art.linear(384, 0, 426, 0, [(0, SKIN_SH, 0.7), (1, SKIN_SH, 0)])

    def face_shading():
        """Everything painted on top of the flat skin colour.  Lid patches reuse it so they match the face exactly."""
        return (path(poly([(370, 140), (630, 140), (630, 320), (370, 320)]), fill=bang_shadow)                 # shadow under the fringe
                + path(poly([(556, 140), (640, 140), (640, 470), (556, 470)]), fill=far_shadow)                 # far-side form shadow
                + path(poly([(360, 140), (436, 140), (436, 470), (360, 470)]), fill=near_shadow)
                + ellipse(500, 464, 66, 22, fill=SKIN_SH, opacity=0.6, filter=soft8)                            # under-chin turn
                + ellipse(434, 368, 28, 14, fill="#f4b9b6", opacity=0.28, filter=soft8)                         # cheek warmth
                + ellipse(566, 368, 28, 14, fill="#f4b9b6", opacity=0.28, filter=soft8)
                + ellipse(447, 324, 42, 26, fill=SKIN_SH, opacity=0.38, filter=soft8)                           # eye sockets
                + ellipse(553, 324, 42, 26, fill=SKIN_SH, opacity=0.38, filter=soft8)
                + ellipse(500, 426, 19, 6, fill=SKIN_SH, opacity=0.5, filter=soft4))                            # under the lower lip

    art.part("face",
             path(face_d + holes, fill=SKIN, fill_rule="evenodd"),
             group(face_shading(), clip_path=fclip),
             path(smooth(D.FACE[4:17], closed=False), stroke=SKIN_LINE, sw=1.5, opacity=0.85))

    art.part("blush",
             ellipse(434, 366, 26, 11, fill="#f08f98", opacity=0.6, filter=soft8),
             ellipse(566, 366, 26, 11, fill="#f08f98", opacity=0.6, filter=soft8), hidden=True)

    # =============================================================================== lids (skin patches that own the lashes)
    def lower_lid(side):
        patch = D.EYE_LOW_L + [(412, 330), (425, 342), (452, 348.5), (472, 343.5), (482.5, 329.5)]
        lash = [(417, 322.5), (426, 329.3), (438, 332.8), (452, 333.3)]
        if side == "R":
            patch, lash = mx(patch), mx(lash)
        d = smooth(patch, tension=0.4)
        fade = art.mask_fade(0, 337, 0, 348, [(0, "#fff"), (1, "#000")])
        return (group(path(d, fill=SKIN), group(face_shading(), clip_path=art.clip(d)), mask=fade)
                + path(smooth(lash, closed=False), stroke="#7a5d66", sw=1.3, opacity=0.8))
    art.part("lower_lid_L", lower_lid("L"))
    art.part("lower_lid_R", lower_lid("R"))

    def eyelid(side):
        up = D.EYE_UP_L
        # Skin patch above the eye.  Its top D.LID_FEATHER px are feathered and never travel over the opening;
        # everything below is opaque and carries the same shading as the face, so it is invisible while open
        # and a solid eyelid when it stretches down over the eye.
        top = D.LID_TOP_Y
        patch = [(408, 323), (410, top + 14), (424, top + 2), (452, top), (474, top + 4), (483, 324)] + [(x, y + 0.6) for x, y in reversed(up)]
        lash = [(410.5, 322.2), (423, 309.6), (436.5, 303.6), (451, 302.8), (464.6, 307.6), (476.4, 322.6), (475, 324.6), (464, 312), (451, 308.2), (437.2, 309.2), (424.6, 314.8), (417.6, 323.6)]
        crease = [(425, 304), (438, 298.2), (452, 297.6), (466, 302.4)]
        if side == "R":
            patch, lash, crease = mx(patch), mx(lash), mx(crease)
        d = smooth(patch, tension=0.4)
        fade = art.mask_fade(0, top, 0, top + D.LID_FEATHER, [(0, "#000"), (1, "#fff")])
        tint = art.linear(0, 296, 0, 312, [(0, "#efcfd0", 0), (1, "#efcfd0", 0.55)])
        return (group(path(d, fill=SKIN), group(face_shading(), path(d, fill=tint), clip_path=art.clip(d)), mask=fade)
                + path(smooth(crease, closed=False), stroke="#c9979d", sw=1.2, opacity=0.75)
                + path(smooth(lash, tension=0.45), fill=LASH))
    art.part("eyelid_L", eyelid("L"))
    art.part("eyelid_R", eyelid("R"))

    # =============================================================================== nose
    art.part("nose",
             path(smooth([(504, 358), (508, 372), (505, 382)], closed=False), stroke="#d9a8ab", sw=2.0, opacity=0.75, filter=art.blur(0.6)),
             path(smooth([(494, 386), (500, 388.6), (506, 386)], closed=False), stroke="#bf8c92", sw=1.5, opacity=0.9),
             ellipse(497.5, 375, 2.6, 3.4, fill="#ffffff", opacity=0.55, filter=art.blur(1)))

    # =============================================================================== mouth shapes (one slot, swapped)
    def mouth(kind):
        mx0, my0 = D.MOUTH
        out = []
        if kind in ("neutral", "smile"):
            dy = (1.0, -0.9, 0.4, -0.9, 1.0) if kind == "neutral" else (-2.8, 0.6, 1.9, 0.6, -2.8)
            line = [(mx0 - 19, my0 + dy[0]), (mx0 - 9, my0 + dy[1]), (mx0, my0 + dy[2]), (mx0 + 9, my0 + dy[3]), (mx0 + 19, my0 + dy[4])]
            out.append(path(smooth([(mx0 - 14, my0 - 1), (mx0 - 6.5, my0 - 4.8), (mx0, my0 - 3.1), (mx0 + 6.5, my0 - 4.8), (mx0 + 14, my0 - 1), (mx0, my0 + 1)]), fill=LIP, opacity=0.55, filter=art.blur(0.7)))
            out.append(path(smooth([(mx0 - 13, my0 + 2), (mx0, my0 + 9.2), (mx0 + 13, my0 + 2), (mx0, my0 + 3)]), fill=LIP, opacity=0.8, filter=art.blur(0.8)))
            out.append(ellipse(mx0 - 2, my0 + 5.0, 4.4, 1.3, fill="#ffffff", opacity=0.5, filter=art.blur(0.7)))
            out.append(path(smooth(line, closed=False), stroke=LIP_LINE, sw=1.8))
        else:
            rx, ry = {"open_s": (9.0, 4.4), "open_m": (11.0, 8.2), "o": (6.8, 7.8)}[kind]
            cy = my0 + ry * 0.55
            inner = f"M{mx0 - rx},{cy}a{rx},{ry} 0 1,0 {2 * rx},0a{rx},{ry} 0 1,0 {-2 * rx},0Z"
            c = art.clip(inner)
            out.append(path(smooth([(mx0 - rx - 5, my0 - 1), (mx0 - 6, my0 - 5.3), (mx0, my0 - 3.5), (mx0 + 6, my0 - 5.3), (mx0 + rx + 5, my0 - 1), (mx0, my0 + 1)]), fill=LIP, opacity=0.6, filter=art.blur(0.7)))
            out.append(ellipse(mx0, cy + ry + 1.5, rx + 3, 4.4, fill=LIP, opacity=0.85, filter=art.blur(0.8)))
            out.append(path(inner, fill="#6f2c38"))
            out.append(group(ellipse(mx0, cy - ry + 1.2, rx * 0.8, 2.6, fill="#ffffff", opacity=0.92),
                             ellipse(mx0, cy + ry - 0.5, rx * 0.72, ry * 0.5, fill="#d9767f", opacity=0.9), clip_path=c))
            out.append(path(inner, stroke=LIP_LINE, sw=1.5))
        return "".join(out)
    art.part("mouth_neutral", mouth("neutral"))
    for k in ("smile", "open_s", "open_m", "o"):
        art.part(f"mouth_{k}", mouth(k), hidden=True)

    # =============================================================================== cheek locks (hime cut)
    def cheek_lock(side):
        shape = [(380, 220), (372, 280), (368, 340), (366.5, 400), (366.5, 438), (368, 444.5), (376, 446), (385, 444.2), (394, 446), (402, 444.5), (403.5, 438), (403, 392), (401, 330), (399, 270), (398, 220)]
        l = [(374, 240), (370, 340), (372, 440)]
        r = [(396, 240), (399, 340), (400, 440)]
        rim = [(371.5, 262), (368.5, 340), (369.5, 436)]
        if side == "R":
            shape, l, r = mx(shape), [flip(p) for p in l], [flip(p) for p in r]
            rim = [(598.5, 262), (596, 340), (597.5, 436)]
        d = smooth(shape, tension=0.22)
        return hair(d, 220, 446, strands=flow(l, r, (0.3, 0.62), HAIR_LT, 1.5, 0.45) + flow(l, r, (0.46, 0.85), HAIR_DK, 2.2, 0.5), rim=rim)
    art.part("hair_cheek_L", cheek_lock("L"))
    art.part("hair_cheek_R", cheek_lock("R"))

    # =============================================================================== hair_top (cap) and bangs
    halo_a = [(392, 226), (436, 206), (486, 198)]
    halo_b = [(506, 197), (556, 204), (604, 224)]
    sheen = art.radial(430, 176, 190, [(0, "#4d5372", 0.75), (1, "#4d5372", 0)])

    def halo_marks():
        return (path(smooth(halo_a, closed=False), stroke=HAIR_RIM, sw=12, opacity=0.30, filter=soft4)
                + path(smooth(halo_b, closed=False), stroke=HAIR_RIM, sw=10, opacity=0.22, filter=soft4)
                + path(smooth(shift(halo_a, 0, -2), closed=False), stroke="#cdd6f0", sw=3.0, opacity=0.36, filter=soft2)
                + path(smooth(shift(halo_b[:2], 0, -2), closed=False), stroke="#cdd6f0", sw=2.4, opacity=0.24, filter=soft2))

    cap_right = [(500, 122), (562, 127), (612, 154), (638, 204), (646, 262), (644, 318), (630, 312), (612, 268), (572, 246), (500, 240)]
    cap = cap_right + mx(cap_right)[1:-1]
    cap_d = smooth(cap, tension=0.4)
    crown = (500, 146)
    radial_strands = [([crown, ((crown[0] + x) / 2 + (x - 500) * 0.12, 180), (x, 300)], HAIR_LT, 1.6, 0.4) for x in (378, 408, 442, 478, 522, 558, 592, 622)]
    radial_strands += [([crown, ((crown[0] + x) / 2 + (x - 500) * 0.12, 182), (x, 300)], HAIR_DK, 2.4, 0.45) for x in (392, 460, 540, 608)]
    cap_clip = art.clip(cap_d)
    art.part("hair_top", hair(cap_d, 122, 320, strands=radial_strands, rim=[(356, 300), (355, 250), (366, 200), (402, 152), (460, 128)],
                              extra=group(path(poly([(340, 110), (660, 110), (660, 340), (340, 340)]), fill=sheen), halo_marks(), clip_path=cap_clip)))

    def bang(top, bottom, strand_fracs):
        """A fringe panel: `top` (left->right) melts into the cap, `bottom` (right->left) is the blunt cut."""
        shape = top + bottom
        d = smooth(shape, tension=0.3)
        left, right = [top[0], bottom[-1]], [top[-1], bottom[0]]
        lm = [left[0], ((left[0][0] + left[1][0]) / 2 - 2, (left[0][1] + left[1][1]) / 2), left[1]]
        rm = [right[0], ((right[0][0] + right[1][0]) / 2 + 2, (right[0][1] + right[1][1]) / 2), right[1]]
        fade = art.mask_fade(0, top[0][1], 0, top[0][1] + 36, [(0, "#000"), (1, "#fff")])
        clip = art.clip(d)
        body = hair(d, 170, 300, strands=flow(lm, rm, strand_fracs, HAIR_LT, 1.5, 0.5) + flow(lm, rm, [t + 0.09 for t in strand_fracs[::2]], HAIR_DK, 2.2, 0.5),
                    extra=group(path(poly([(340, 110), (660, 110), (660, 340), (340, 340)]), fill=sheen), halo_marks(),
                                path(smooth(bottom, closed=False), stroke=HAIR_DK, sw=6, opacity=0.5, filter=soft2), clip_path=clip))
        return group(body, mask=fade)
    art.part("bang_L", bang([(386, 180), (424, 172), (464, 170)], [(467, 296), (453, 300.5), (439, 296.5), (425, 301), (411, 297), (399, 302), (389, 298.5), (384, 290)], (0.2, 0.42, 0.62, 0.82)))
    art.part("bang_R", bang([(536, 170), (576, 172), (614, 180)], [(616, 290), (611, 298.5), (601, 302), (589, 297), (575, 301.5), (561, 296.5), (547, 300.5), (533, 296)], (0.18, 0.38, 0.58, 0.8)))
    art.part("bang_C", bang([(450, 168), (500, 166), (550, 168)], [(549, 295), (535, 299.5), (521, 295.5), (509, 300), (497, 296), (485, 300), (473, 295.5), (459, 299.5), (451, 295)], (0.15, 0.33, 0.5, 0.67, 0.85)))

    # =============================================================================== brows (drawn over the fringe, anime convention)
    def brow(side):
        c = [(424, 285.5), (439, 280.3), (456, 279.6), (472, 282.6)]
        if side == "R":
            c = [flip(p) for p in c][::-1]
        return path(ribbon(c, [1.4, 3.8, 4.0, 1.6]), fill="#8b93b4", opacity=0.8)
    art.part("brow_L", brow("L"))
    art.part("brow_R", brow("R"))
    return art


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "art" / "character.svg"))
    a = ap.parse_args()
    build().save(a.out)
    print(a.out)
