#!/usr/bin/env python3
"""小霜 (Xiaoshuang) -- chibi full-body layered art, generated in code.  Order of art.part() = draw order, back to front."""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from spinekit.svgart import Art, smooth, poly, ribbon, path, circle, ellipse, group, shift
except ImportError:
    sys.exit("run this through the kit:  python3 <kit>/spk.py art <project>")
import design as D
from design import mx, flip

SKIN, SKIN_SH, SKIN_SH2, SKIN_LINE = "#fbeee8", "#efd3d0", "#deb5b8", "#c99da2"
HAIR_A, HAIR_B, HAIR_LT, HAIR_DK, HAIR_RIM = "#2c2e3d", "#16171f", "#4d5270", "#0b0b10", "#8c9ac4"
SHIRT, SHIRT_SH, SHIRT_SH2, SHIRT_LINE = "#f6f8fc", "#d5dcea", "#b2bcd2", "#8f99b1"
NAVY, NAVY_DK, NAVY_LT = "#2f3a5e", "#1f2742", "#4a5886"
SHOE, SHOE_DK, SHOE_LT = "#4d362e", "#2e1f1a", "#8a6a5c"
LASH, IRIS_A, IRIS_B, IRIS_RING, PUPIL = "#17171f", "#34425c", "#93abca", "#232c40", "#0e1118"


def lerp_pts(a, b, t):
    return [(ax + (bx - ax) * t, ay + (by - ay) * t) for (ax, ay), (bx, by) in zip(a, b)]


def build() -> Art:
    art = Art(D.W, D.H)
    soft1, soft2, soft4, soft8 = art.blur(1), art.blur(2), art.blur(4), art.blur(8)
    M = lambda pts: [flip(p) for p in pts]                       # mirror keeping order (for open centre lines)

    def hair(d, y0, y1, strands=(), rim=None, extra=""):
        g = art.linear(0, y0, 0, y1, [(0, HAIR_A), (1, HAIR_B)])
        inner = [path(smooth(pts, closed=False), stroke=col, sw=sw, opacity=op) for pts, col, sw, op in strands]
        if rim:
            inner.append(path(smooth(rim, closed=False), stroke=HAIR_RIM, sw=5, opacity=0.42, filter=soft2))
        return path(d, fill=g) + group(*inner, clip_path=art.clip(d)) + extra

    def flow(left, right, fracs, col=HAIR_LT, sw=1.6, op=0.45):
        return [(lerp_pts(left, right, t), col, sw, op) for t in fracs]

    # ------------------------------------------------------------------ hair_back
    hb_r = [(400, 158), (462, 164), (514, 196), (537, 250), (542, 320), (538, 400), (530, 470), (520, 540), (504, 600), (484, 636)]
    hb_bottom = [(460, 650), (436, 636), (400, 652), (364, 636), (340, 650)]
    hb_d = smooth(hb_r + hb_bottom + mx(hb_r)[:-1])
    lcol, rcol = [(270, 300), (264, 420), (272, 540), (300, 632)], [(530, 300), (536, 420), (528, 540), (500, 632)]
    art.part("hair_back", hair(hb_d, 158, 652, strands=flow(lcol, rcol, (0.1, 0.24, 0.38, 0.5, 0.62, 0.76, 0.9), HAIR_LT, 2.0, 0.33) + flow(lcol, rcol, (0.17, 0.44, 0.7, 0.84), HAIR_DK, 3.0, 0.5),
                               rim=[(262, 300), (259, 420), (267, 540), (295, 628)]))

    # ------------------------------------------------------------------ limbs (near = screen-left; far = mirrored, drawn behind)
    def arm(far):
        center = [(346, 440), (343, 478), (339, 520), (336, 556)]
        cuff = [(324, 547), (336, 550), (348, 547)]
        fold = [(331, 492), (340, 500), (350, 494)]
        cap = (346, 446)
        if far:
            center, cuff, fold, cap = M(center), M(cuff), M(fold), flip(cap)
        d = ribbon(center, [25, 25.5, 24.5, 23.5], tension=0.4)
        cap_d = f"M{cap[0] - 13},{cap[1]}a13,13 0 1,0 26,0a13,13 0 1,0 -26,0Z"
        c = art.clip(d + cap_d)
        wx, wy = flip((336, 560)) if far else (336, 560)
        return (ellipse(wx, wy, 8.5, 10, fill=SKIN, stroke=SKIN_LINE, stroke_width=1.1)            # wrist: hidden under the hand until the hand bends
                + path(d + cap_d, fill=SHIRT)
                + group(path(smooth(shift(center, 6 if not far else -6, 0), closed=False), stroke=SHIRT_SH, sw=11, opacity=0.9, filter=soft4),
                        path(smooth(fold, closed=False), stroke=SHIRT_SH2, sw=3, opacity=0.6, filter=soft1),
                        path(smooth(cuff, closed=False), stroke=SHIRT_LINE, sw=1.3, opacity=0.8), clip_path=c)
                + path(d, stroke=SHIRT_LINE, sw=1.5, opacity=0.9) + path(cap_d, stroke=SHIRT_LINE, sw=1.5, opacity=0.0))

    def hand(far, opened=False):
        f_ = (lambda p: flip(p)) if far else (lambda p: p)
        out = []
        if opened:
            for cx_, top, tip in ((324.5, 570, 590), (330.5, 572, 595), (337, 572, 595.5), (343, 570, 591)):
                out.append(path(ribbon([f_((cx_, top)), f_((cx_, (top + tip) / 2)), f_((cx_, tip))], [7.6, 7.6, 6.4], tension=0.5), fill=SKIN, stroke=SKIN_LINE, sw=1.1))
            out.append(path(ribbon([f_((343, 562)), f_((349, 566)), f_((353, 573))], [8, 7.6, 6.2], tension=0.5), fill=SKIN, stroke=SKIN_LINE, sw=1.1))
            cx_, cy_ = f_((334, 565))
            out.append(ellipse(cx_, cy_, 13, 12, fill=SKIN, stroke=SKIN_LINE, stroke_width=1.2))
            out.append(ellipse(cx_, cy_ + 1, 8, 6, fill=SKIN_SH, opacity=0.55, filter=soft2))
        else:
            tx, ty = f_((344, 566))
            out.append(ellipse(tx, ty, 5.5, 7.5, fill=SKIN, stroke=SKIN_LINE, stroke_width=1.1))
            cx_, cy_ = f_((334, 568))
            out.append(ellipse(cx_, cy_, 11.5, 13.5, fill=SKIN, stroke=SKIN_LINE, stroke_width=1.2))
            out.append(ellipse(cx_ + (2 if not far else -2), cy_ + 3, 6, 6, fill=SKIN_SH, opacity=0.6, filter=soft2))
        return "".join(out)

    def leg(far):
        pts = [(363, 592), (391, 592), (391.5, 700), (389.5, 760), (387.5, 809), (366.5, 809), (364.5, 760), (362.5, 700)]
        if far:
            pts = mx(pts)
        x0 = 377 if not far else 423
        d = smooth(pts, tension=0.25)
        c = art.clip(d)
        return (path(d, fill=SKIN)
                + group(path(poly([(x0 - 20, 736), (x0 + 20, 736), (x0 + 20, 812), (x0 - 20, 812)]), fill="#fafbfd"),
                        path(poly([(x0 + 4, 590), (x0 + 20, 590), (x0 + 20, 812), (x0 + 4, 812)]), fill=art.linear(x0 + 2, 0, x0 + 15, 0, [(0, SKIN_SH2, 0), (1, SKIN_SH2, 0.55)])),
                        ellipse(x0 - 1, 708, 9, 5, fill=SKIN_SH, opacity=0.55, filter=soft2),
                        path(poly([(x0 - 20, 736), (x0 + 20, 736)], closed=False), stroke=SHIRT_LINE, sw=1.4, opacity=0.9),
                        path(poly([(x0 - 20, 741), (x0 + 20, 741)], closed=False), stroke=SHIRT_SH2, sw=1.0, opacity=0.6), clip_path=c)
                + path(d, stroke=SKIN_LINE, sw=1.3, opacity=0.85))

    def shoe(far, front):
        x0 = 377 if not far else 423
        if front:
            pts = [(x0 - 17, 803), (x0 + 17, 803), (x0 + 21, 824), (x0 + 19, 838), (x0 - 19, 838), (x0 - 21, 824)]
            d = smooth(pts, tension=0.3)
            return (path(d, fill=SHOE) + ellipse(x0, 808, 13, 5, fill=SHOE_DK) + ellipse(x0 - 6, 826, 6, 4, fill=SHOE_LT, opacity=0.45, filter=soft2)
                    + path(poly([(x0 - 19, 836), (x0 + 19, 836)], closed=False), stroke=SHOE_DK, sw=3) + path(d, stroke=SHOE_DK, sw=1.4))
        pts = [(x0 - 14, 801), (x0 + 13, 800), (x0 + 20, 811), (x0 + 38, 817), (x0 + 49, 827), (x0 + 49, 838), (x0 - 17, 838), (x0 - 19, 820)]
        d = smooth(pts, tension=0.3)
        return (path(d, fill=SHOE) + ellipse(x0, 805, 12, 4.6, fill=SHOE_DK)
                + ellipse(x0 + 30, 824, 10, 4, fill=SHOE_LT, opacity=0.5, filter=soft2)
                + path(poly([(x0 - 17, 836), (x0 + 49, 836)], closed=False), stroke=SHOE_DK, sw=3.2) + path(d, stroke=SHOE_DK, sw=1.4))

    art.part("arm_f", arm(True))
    art.part("hand_f", hand(True))
    art.part("leg_f", leg(True))
    art.part("shoe_f_side", shoe(True, False))
    art.part("shoe_f_front", shoe(True, True), hidden=True)
    art.part("leg_n", leg(False))
    art.part("shoe_n_side", shoe(False, False))
    art.part("shoe_n_front", shoe(False, True), hidden=True)

    # ------------------------------------------------------------------ neck, torso, skirt
    neck = [(385, 394), (415, 394), (417, 442), (383, 442)]
    art.part("neck", path(smooth(neck, tension=0.2), fill=SKIN), group(ellipse(400, 410, 22, 14, fill=SKIN_SH2, opacity=0.9, filter=soft4), clip_path=art.clip(smooth(neck, tension=0.2))))

    torso = [(384, 426), (366, 431), (347, 442), (338, 462), (345, 500), (352, 530), (351, 556), (449, 556), (448, 530), (455, 500), (462, 462), (453, 442), (434, 431), (416, 426)]
    td = smooth(torso, tension=0.35)
    tc = art.clip(td)
    collar_l = [(398, 428), (382, 426), (366, 438), (374, 462), (398, 450)]
    bow_l = [(398, 452), (376, 442), (372, 468), (398, 460)]
    art.part("torso",
             path(td, fill=SHIRT),
             group(path(smooth([(346, 450), (350, 500), (354, 556)], closed=False), stroke=SHIRT_SH, sw=16, opacity=0.9, filter=soft4),
                   path(smooth([(456, 450), (452, 500), (448, 556)], closed=False), stroke=SHIRT_SH2, sw=20, opacity=0.75, filter=soft4),
                   path(smooth([(372, 500), (400, 508), (428, 500)], closed=False), stroke=SHIRT_SH, sw=5, opacity=0.6, filter=soft2),
                   path(poly([(400, 462), (400, 556)], closed=False), stroke=SHIRT_LINE, sw=1.1, opacity=0.6),
                   circle(400, 496, 3, fill="#e6eaf2", stroke=SHIRT_LINE, stroke_width=1), circle(400, 526, 3, fill="#e6eaf2", stroke=SHIRT_LINE, stroke_width=1),
                   ellipse(400, 434, 30, 9, fill=SHIRT_SH2, opacity=0.7, filter=soft2), clip_path=tc),
             path(td, stroke=SHIRT_LINE, sw=1.5, opacity=0.9),
             path(smooth(collar_l, tension=0.2), fill=SHIRT, stroke=SHIRT_LINE, sw=1.4), path(smooth(mx(collar_l), tension=0.2), fill=SHIRT, stroke=SHIRT_LINE, sw=1.4),
             path(smooth(bow_l, tension=0.25), fill=NAVY, stroke=NAVY_DK, sw=1.2), path(smooth(mx(bow_l), tension=0.25), fill=NAVY, stroke=NAVY_DK, sw=1.2),
             path(smooth([(392, 462), (386, 484), (396, 480), (400, 466)], tension=0.2), fill=NAVY, stroke=NAVY_DK, sw=1.1),
             path(smooth([(408, 462), (414, 484), (404, 480), (400, 466)], tension=0.2), fill=NAVY, stroke=NAVY_DK, sw=1.1),
             ellipse(400, 456, 6.5, 6, fill=NAVY_LT, stroke=NAVY_DK, stroke_width=1.1),
             path(smooth([(380, 448), (386, 452)], closed=False), stroke=NAVY_LT, sw=1.6, opacity=0.8), path(smooth([(420, 448), (414, 452)], closed=False), stroke=NAVY_LT, sw=1.6, opacity=0.8))

    skirt = [(352, 512), (448, 512), (472, 562), (496, 626), (472, 634), (448, 627), (424, 636), (400, 629), (376, 636), (352, 627), (328, 634), (304, 626), (328, 562)]
    sd = smooth(skirt, tension=0.3)
    sc = art.clip(sd)
    pleats = [((368 + i * 16, 520), (316 + i * 42, 632)) for i in range(5)]
    art.part("skirt",
             path(sd, fill=art.linear(0, 512, 0, 636, [(0, NAVY_LT), (0.25, NAVY), (1, NAVY_DK)])),
             group(*[path(poly([a, b], closed=False), stroke=NAVY_DK, sw=2.2, opacity=0.75) for a, b in pleats],
                   *[path(poly([(a[0] + 5, a[1]), (b[0] + 9, b[1])], closed=False), stroke=NAVY_LT, sw=1.4, opacity=0.5) for a, b in pleats],
                   path(poly([(346, 520), (454, 520)], closed=False), stroke=NAVY_DK, sw=2, opacity=0.6),
                   path(smooth([(456, 530), (476, 580), (492, 628)], closed=False), stroke=NAVY_DK, sw=18, opacity=0.5, filter=soft4), clip_path=sc),
             path(sd, stroke=NAVY_DK, sw=1.5))

    # ------------------------------------------------------------------ front locks, eyes, face
    def lock(side):
        center = [(304, 262), (297, 340), (292, 420), (295, 496), (303, 556)]
        if side == "R":
            center = M(center)
        d = ribbon(center, [22, 30, 32, 26, 0])
        s_ = -1 if side == "R" else 1
        return hair(d, 262, 556, strands=[(shift(center[:-1], dx * s_, 0), HAIR_LT, 1.6, 0.45) for dx in (-7, 5)] + [(shift(center[:-1], 0, 0), HAIR_DK, 2.2, 0.45)],
                    rim=shift(center[:-1], -11, 0))
    art.part("long_L", lock("L"))
    art.part("long_R", lock("R"))

    def eye_white(side):
        hole = D.EYE_HOLE_L if side == "L" else mx(D.EYE_HOLE_L)
        cx, cy = D.EYE_L if side == "L" else D.EYE_R
        d = smooth([(cx + (x - cx) * 1.28, cy + (y - cy) * 1.3) for x, y in hole])
        return path(d, fill="#f3f5fb") + group(ellipse(cx, cy - 26, 36, 13, fill="#a3adc7", opacity=0.9, filter=soft4), clip_path=art.clip(d))

    def iris(side):
        cx, cy = D.EYE_L if side == "L" else D.EYE_R
        cy += 1
        r = 20.5
        g = art.linear(0, cy - r, 0, cy + r, [(0, IRIS_A), (0.5, "#566a8a"), (1, IRIS_B)])
        c = art.clip(f"M{cx - r},{cy}a{r},{r} 0 1,0 {2 * r},0a{r},{r} 0 1,0 {-2 * r},0Z")
        return (circle(cx, cy, r, fill=g)
                + group(ellipse(cx, cy - 15, 24, 12, fill="#161d2c", opacity=0.8, filter=soft2), ellipse(cx, cy + 12, 13, 6.5, fill="#d3e4f8", opacity=0.65, filter=soft2), clip_path=c)
                + circle(cx, cy, r - 1, stroke=IRIS_RING, stroke_width=2.0, opacity=0.9)
                + ellipse(cx, cy + 1, 7.5, 9, fill=PUPIL)
                + ellipse(cx - 7.5, cy - 8.5, 6.2, 5.2, fill="#ffffff", opacity=0.97) + circle(cx + 8, cy + 9, 2.6, fill="#ffffff", opacity=0.9))
    for s_ in "LR":
        art.part(f"eye_white_{s_}", eye_white(s_))
    for s_ in "LR":
        art.part(f"iris_{s_}", iris(s_))

    face_d = smooth(D.FACE, tension=0.42)
    holes = smooth(D.EYE_HOLE_L) + smooth(mx(D.EYE_HOLE_L))
    fclip = art.clip(face_d + holes, rule="evenodd")
    bang_shadow = art.linear(0, 214, 0, 322, [(0, SKIN_SH2, 0.95), (0.6, SKIN_SH, 0.55), (1, SKIN_SH, 0)])
    far_shadow = art.linear(462, 0, 512, 0, [(0, SKIN_SH, 0), (1, SKIN_SH2, 0.75)])
    near_shadow = art.linear(288, 0, 326, 0, [(0, SKIN_SH, 0.6), (1, SKIN_SH, 0)])

    def face_shading():
        return (path(poly([(280, 170), (520, 170), (520, 322), (280, 322)]), fill=bang_shadow)
                + path(poly([(455, 170), (520, 170), (520, 420), (455, 420)]), fill=far_shadow)
                + path(poly([(280, 170), (336, 170), (336, 420), (280, 420)]), fill=near_shadow)
                + ellipse(400, 420, 60, 16, fill=SKIN_SH, opacity=0.55, filter=soft8)
                + ellipse(334, 366, 24, 12, fill="#f6aeb0", opacity=0.42, filter=soft8) + ellipse(466, 366, 24, 12, fill="#f6aeb0", opacity=0.42, filter=soft8))
    art.part("face", path(face_d + holes, fill=SKIN, fill_rule="evenodd"), group(face_shading(), clip_path=fclip),
             path(smooth(D.FACE[3:14], closed=False, tension=0.42), stroke=SKIN_LINE, sw=1.5, opacity=0.85))
    art.part("blush", ellipse(334, 366, 24, 11, fill="#f08f98", opacity=0.6, filter=soft8), ellipse(466, 366, 24, 11, fill="#f08f98", opacity=0.6, filter=soft8), hidden=True)

    def eyelid(side):
        top = D.LID_TOP_Y
        up = D.EYE_UP_L
        patch = [(314, 332), (316, top + 16), (330, top + 3), (348, top), (366, top + 4), (380, 328)] + [(x, y + 0.6) for x, y in reversed(up)]
        lash = [(315, 329), (326, 310), (343.5, 299.5), (361, 303), (375, 325), (372.5, 327.5), (360, 309), (344, 306), (329.5, 315), (322.5, 332.5)]
        crease = [(330, 302), (345, 295.5), (360, 298)]
        if side == "R":
            patch, lash, crease = mx(patch), mx(lash), mx(crease)
        d = smooth(patch, tension=0.4)
        fade = art.mask_fade(0, top, 0, top + D.LID_FEATHER, [(0, "#000"), (1, "#fff")])
        return (group(path(d, fill=SKIN), group(face_shading(), clip_path=art.clip(d)), mask=fade)
                + path(smooth(crease, closed=False), stroke="#c9979d", sw=1.2, opacity=0.7) + path(smooth(lash, tension=0.45), fill=LASH))
    for s_ in "LR":
        art.part(f"eyelid_{s_}", eyelid(s_))

    art.part("nose", ellipse(402, 365, 2.6, 1.8, fill="#d79ea3", opacity=0.9), ellipse(399, 361, 2, 2.4, fill="#ffffff", opacity=0.5, filter=soft1))
    mx0, my0 = D.MOUTH
    art.part("mouth_neutral", path(smooth([(mx0 - 9, my0 - 0.5), (mx0 - 3, my0 + 2.4), (mx0 + 3, my0 + 2.4), (mx0 + 9, my0 - 0.5)], closed=False), stroke="#a95c68", sw=2.0))
    smile_d = smooth([(mx0 - 11, my0 - 2), (mx0 + 11, my0 - 2), (mx0 + 7, my0 + 7), (mx0, my0 + 10), (mx0 - 7, my0 + 7)], tension=0.3)
    art.part("mouth_smile", path(smile_d, fill="#7a2f3b"), group(ellipse(mx0, my0 + 9, 7, 4, fill="#e58a93"), path(poly([(mx0 - 9, my0 - 2), (mx0 + 9, my0 - 2), (mx0 + 8, my0 + 1), (mx0 - 8, my0 + 1)]), fill="#ffffff"), clip_path=art.clip(smile_d)),
             path(smile_d, stroke="#a95c68", sw=1.5), hidden=True)
    art.part("mouth_o", ellipse(mx0, my0 + 2, 4.6, 5.4, fill="#7a2f3b", stroke="#a95c68", stroke_width=1.4), hidden=True)

    # ------------------------------------------------------------------ cheek locks, cap, fringe, brows
    def cheek(side):
        shape = [(290, 222), (284, 300), (284, 370), (286, 414), (290, 421), (301, 422), (310, 420.5), (318, 422), (325, 419), (326, 370), (325, 300), (323, 222)]
        l, r_ = [(292, 250), (289, 340), (291, 418)], [(315, 250), (318, 340), (319, 418)]
        rim = [(288.5, 268), (286.5, 340), (288.5, 412)]
        if side == "R":
            shape, l, r_, rim = mx(shape), M(l), M(r_), [(509.5, 268), (511.5, 340), (509.5, 412)]
        d = smooth(shape, tension=0.22)
        return hair(d, 232, 422, strands=flow(l, r_, (0.35, 0.7)) + flow(l, r_, (0.52,), HAIR_DK, 2.2, 0.5), rim=rim)
    art.part("cheek_L", cheek("L"))
    art.part("cheek_R", cheek("R"))

    sheen = art.radial(338, 206, 170, [(0, "#4f5576", 0.75), (1, "#4f5576", 0)])
    halo_a, halo_b = [(318, 250), (352, 232), (392, 226)], [(410, 225), (450, 231), (486, 248)]

    def gloss():
        return (path(poly([(250, 140), (550, 140), (550, 330), (250, 330)]), fill=sheen)
                + path(smooth(halo_a, closed=False), stroke=HAIR_RIM, sw=11, opacity=0.30, filter=soft4) + path(smooth(halo_b, closed=False), stroke=HAIR_RIM, sw=9, opacity=0.22, filter=soft4)
                + path(smooth(shift(halo_a, 0, -2), closed=False), stroke="#cdd6f0", sw=2.8, opacity=0.36, filter=soft2) + path(smooth(shift(halo_b[:2], 0, -2), closed=False), stroke="#cdd6f0", sw=2.2, opacity=0.24, filter=soft2))
    cap_r = [(400, 156), (466, 162), (521, 196), (541, 252), (543, 306), (530, 300), (510, 262), (470, 246), (400, 240)]
    cap_d = smooth(cap_r + mx(cap_r)[1:-1], tension=0.4)
    crown = (400, 178)
    rs = [([crown, ((crown[0] + x) / 2 + (x - 400) * 0.12, 208), (x, 300)], HAIR_LT, 1.5, 0.4) for x in (286, 316, 350, 384, 416, 450, 484, 514)]
    rs += [([crown, ((crown[0] + x) / 2 + (x - 400) * 0.12, 210), (x, 300)], HAIR_DK, 2.2, 0.45) for x in (300, 366, 434, 500)]
    art.part("hair_top", hair(cap_d, 156, 306, strands=rs, rim=[(262, 300), (260, 250), (282, 198), (336, 164)], extra=group(gloss(), clip_path=art.clip(cap_d))))

    top = [(294, 208), (348, 190), (400, 186), (452, 190), (506, 208)]
    bottom = [(510, 296), (490, 301), (474, 296), (458, 303), (442, 297), (424, 304), (408, 298), (392, 304), (376, 297), (358, 303), (342, 296), (326, 301), (310, 296), (290, 300)]
    bd = smooth(top + bottom, tension=0.3)
    bl, br = [(304, 214), (300, 258), (298, 298)], [(496, 214), (500, 258), (502, 298)]
    fade = art.mask_fade(0, 190, 0, 226, [(0, "#000"), (1, "#fff")])
    art.part("bangs", group(hair(bd, 186, 304, strands=flow(bl, br, (0.1, 0.22, 0.34, 0.46, 0.58, 0.7, 0.82, 0.92), HAIR_LT, 1.5, 0.5) + flow(bl, br, (0.16, 0.4, 0.64, 0.87), HAIR_DK, 2.2, 0.5),
                                 extra=group(gloss(), path(smooth(bottom, closed=False), stroke=HAIR_DK, sw=6, opacity=0.5, filter=soft2), clip_path=art.clip(bd))), mask=fade))

    def brow(side):
        c = [(326, 291), (340, 286), (356, 286), (368, 289)]
        if side == "R":
            c = M(c)[::-1]
        return path(ribbon(c, [1.4, 3.6, 3.8, 1.6]), fill="#8b93b4", opacity=0.8)
    art.part("brow_L", brow("L"))
    art.part("brow_R", brow("R"))

    # ------------------------------------------------------------------ near arm on top of everything
    art.part("arm_n", arm(False))
    art.part("hand_n", hand(False))
    art.part("hand_n_open", hand(False, opened=True), hidden=True)
    return art


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "art" / "character.svg"))
    a = ap.parse_args()
    build().save(a.out)
    print(a.out)
