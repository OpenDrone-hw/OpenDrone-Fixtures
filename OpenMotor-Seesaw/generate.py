#!/usr/bin/env python3
"""OpenMotor seesaw: parametric laser-cut generator (Python stdlib only).

Writes, next to this script:
  cut/sheet-N.svg / .dxf     cut files, red 0.01 mm hairline, 600 x 400 mm sheets
  cut/optional-N.svg / .dxf  optional prop guard parts (own sheet)
  images/sheet-N.png         labelled preview (only if rsvg-convert exists)
  viewer/model.json          exact cut contours + assembly, read by viewer/index.html

All dimensions in mm. Edit the parameter block, rerun, commit the output.
Kerf rule: only fit-critical features are compensated (holes smaller by KERF,
slots narrower by KERF, tabs wider by KERF). Outer outlines are not offset.
"""
import argparse
import json
import math
import os
import shutil
import subprocess

# ------------------------------------------------------------------ parameters
PLY_T = 8.0            # plywood thickness (measure your sheet, ply varies +-0.3)
KERF = 0.15            # laser kerf; ask the cutter or cut a test slot
SLOT_FIT = 0.05        # extra slot width over PLY_T (0 = very tight, glue joints)
BEARING_OD = 22.0      # 608ZZ
BEARING_ID = 8.0
BEARING_W = 7.0
PRESS_FIT = 0.10       # seat is this much smaller than the bearing OD
ROD_D = 8.0            # M8 bolt or rod
ROD_LEN = 80.0         # M8 x 80 full thread
NUT_AF = 13.0          # M8 nut across flats (ISO 4032)
NUT_H = 6.8
HEX_CLR = 0.2          # hex pocket clearance over NUT_AF
ARM = 250.0            # pivot axis to motor axis = pivot axis to bucket hook
PIVOT_H = 250.0        # pivot axis height above the table
MAX_TILT = 20.0        # end stops, degrees each way
BEAM_H = 40.0          # beam height
BEAM_END = 22.0        # beam length beyond the motor axis / hook
BEAM_PLIES = 3         # centre ply A + two outer plies B
GAP_CLR = 3.0          # clearance beam to each upright
BASE_LAYERS = 2        # glued layers
BASE_L, BASE_W = 420.0, 240.0
UPRIGHT_BASE = 220.0
UPRIGHT_BOSS_R = 22.0
TAB_W, TAB_X = 50.0, 70.0          # upright foot tabs (width, centre offset)
TIE_Z = (60.0, 140.0)              # tie plate heights above the base top
TIE_D = 40.0
POST_X, POST_W, POST_TAB = 190.0, 60.0, 40.0   # stop posts
MOTOR_PATTERN = 16.0   # 16 x 16 mm M3 (NOT verified for the OpenMotor 2306)
M3_CLR = 3.2
MOUNT_PLATE = 44.0
MOUNT_TAB = 30.0
PROP_D = 127.0         # 5 inch prop disc
PROP_PLANE = 36.0      # prop plane above motor plate top (ESTIMATE, measure)
MOTOR_D, MOTOR_H = 28.0, 31.0      # 2306 bell envelope for the 3D model (ESTIMATE)
GUARD_ID, GUARD_OD = 134.0, 166.0
GUARD_PLATE_W = 170.0
GUARD_LEG_Y = 75.0
CW_SLOT = (115.0, 215.0)   # counterweight slot, distance from pivot, bucket side
CW_BOLT = 5.5              # M5 clearance
HOOK_D = 10.0
SHEET_W, SHEET_H = 600.0, 400.0
SHEET_MARGIN, SHEET_GAP = 5.0, 4.0
THRUST_G = 1711.0
PLY_DENSITY = 0.68         # g/cm3 birch ply
BEARING_MOUNT = "press"    # "press" or "printed" (see bearing_housing.scad)
PRINTED_HOLE = 12.0

# ------------------------------------------------------------------ derived
T = PLY_T
BEAM_T = BEAM_PLIES * T
G = BEAM_T + 2 * GAP_CLR          # inner distance between the uprights
BASE_T = BASE_LAYERS * T
TAB_LEN = BASE_T
UP_H = PIVOT_H - BASE_T           # pivot axis height above the base top
PLATE_TOP = BEAM_H / 2 + T        # motor plate top, beam frame
LEG_H = PROP_PLANE - T / 2


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def arc(cx, cy, r, a0, a1, n=24):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def rrect(cx, cy, w, h, r):
    p = []
    for sx, sy, a in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        p += arc(cx + sx * (w / 2 - r), cy + sy * (h / 2 - r), r, a, a + 90, 6)
    return p


def poly(pts):
    return {"kind": "poly", "pts": pts}


def hole(cx, cy, d):
    return {"kind": "circle", "c": (cx, cy), "d": d - KERF}


def slot(cx, cy, w, h):
    """Rectangular slot, nominal w x h (kerf removed from the path)."""
    return poly(rect(cx - (w - KERF) / 2, cy - (h - KERF) / 2,
                     cx + (w - KERF) / 2, cy + (h - KERF) / 2))


def stadium(x0, x1, cy, w):
    r = (w - KERF) / 2
    return poly(arc(x1, cy, r, -90, 90) + arc(x0, cy, r, 90, 270))


def hexagon(cx, cy, af):
    r = (af + HEX_CLR - KERF) / math.sqrt(3)
    return poly([(cx + r * math.cos(math.radians(60 * i + 30)),
                  cy + r * math.sin(math.radians(60 * i + 30))) for i in range(6)])


def m3_ring(r=13.0):
    return [hole(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), M3_CLR)
            for a in (45, 135, 225, 315)]


class Part:
    def __init__(self, name, label, outline, holes, qty=1, optional=False, note=""):
        self.name, self.label, self.qty = name, label, qty
        self.outline, self.holes = outline, holes
        self.optional, self.note = optional, note
        xs = [p[0] for p in outline]
        ys = [p[1] for p in outline]
        self.minx, self.maxx, self.miny, self.maxy = min(xs), max(xs), min(ys), max(ys)
        self.w, self.h = self.maxx - self.minx, self.maxy - self.miny

    def area(self):
        a = 0.0
        o = self.outline
        for i in range(len(o)):
            x0, y0 = o[i]
            x1, y1 = o[(i + 1) % len(o)]
            a += x0 * y1 - x1 * y0
        a = abs(a) / 2
        for hcont in self.holes:
            if hcont["kind"] == "circle":
                a -= math.pi * (hcont["d"] / 2) ** 2
            else:
                p = hcont["pts"]
                s = 0.0
                for i in range(len(p)):
                    s += p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1]
                a -= abs(s) / 2
        return a


# ------------------------------------------------------------------ geometry
def stop_post_height():
    """Height of the stop post top above the base top so the beam bottom edge
    touches it at MAX_TILT (beam bottom edge, post at x = POST_X)."""
    th = math.radians(MAX_TILT)
    u = (POST_X + BEAM_H / 2 * math.sin(th)) / math.cos(th)
    z_world = PIVOT_H - (u * math.sin(th) + BEAM_H / 2 * math.cos(th))
    return z_world - BASE_T


def make_parts():
    parts = []
    # base (two glued layers)
    holes = []
    for sy in (-1, 1):
        for tx in (-TAB_X, TAB_X):
            holes.append(slot(tx, sy * (G / 2 + T / 2), TAB_W, T + SLOT_FIT))
    for sx in (-1, 1):
        holes.append(slot(sx * POST_X, 0, T + SLOT_FIT, POST_TAB))
    for sx in (-1, 1):
        for sy in (-1, 1):
            holes.append(hole(sx * 195, sy * 100, 6.5))          # clamp / bolt holes
    for x in (-20, 20):
        for y in (55, 90):
            holes.append(slot(x, y, 12, 3.5))                     # ESC zip tie slots
    parts.append(Part("base", "Base (glue %d layers)" % BASE_LAYERS,
                      rrect(0, 0, BASE_L, BASE_W, 12), holes, qty=BASE_LAYERS))

    # uprights (A-frame plate)
    pts = [(-UPRIGHT_BASE / 2, 0)]
    for tc in (-TAB_X, TAB_X):
        tw = (TAB_W + KERF) / 2
        pts += [(tc - tw, 0), (tc - tw, -TAB_LEN), (tc + tw, -TAB_LEN), (tc + tw, 0)]
    pts += [(UPRIGHT_BASE / 2, 0), (UPRIGHT_BOSS_R, UP_H)]
    pts += arc(0, UP_H, UPRIGHT_BOSS_R, 0, 180, 24)[1:-1]
    pts += [(-UPRIGHT_BOSS_R, UP_H)]
    holes = [slot(0, zt, TIE_D, T + SLOT_FIT) for zt in TIE_Z]
    if BEARING_MOUNT == "press":
        holes.append(hole(0, UP_H, BEARING_OD - PRESS_FIT))
    else:
        holes.append(hole(0, UP_H, PRINTED_HOLE))
        for a in (45, 135, 225, 315):
            holes.append(hole(16 * math.cos(math.radians(a)), UP_H + 16 * math.sin(math.radians(a)), M3_CLR))
    parts.append(Part("upright", "Upright", pts, holes, qty=2))

    # tie plates
    tl = (G + 2 * T) / 2
    td = (TIE_D + KERF) / 2
    parts.append(Part("tie", "Tie plate", rect(-tl, -td, tl, td), [], qty=len(TIE_Z)))

    # stop posts
    hp = stop_post_height()
    tw = (POST_TAB + KERF) / 2
    pts = [(-POST_W / 2, 0), (-tw, 0), (-tw, -TAB_LEN), (tw, -TAB_LEN), (tw, 0),
           (POST_W / 2, 0), (POST_W / 2, hp), (-POST_W / 2, hp)]
    parts.append(Part("post", "End stop post (felt on top)", pts, [], qty=2))

    # beam plies
    def beam(kind):
        half = ARM + BEAM_END if kind == "A" else ARM - BEAM_END
        if kind == "A":
            tw2 = (MOUNT_TAB + KERF) / 2
            pts = [(-half, -BEAM_H / 2), (half, -BEAM_H / 2), (half, BEAM_H / 2),
                   (ARM + tw2, BEAM_H / 2), (ARM + tw2, BEAM_H / 2 + T),
                   (ARM - tw2, BEAM_H / 2 + T), (ARM - tw2, BEAM_H / 2), (-half, BEAM_H / 2)]
        else:
            pts = rect(-half, -BEAM_H / 2, half, BEAM_H / 2)
        holes = m3_ring()
        holes.append(hole(0, 0, ROD_D + 0.4) if kind == "A" else hexagon(0, 0, NUT_AF))
        holes.append(stadium(-CW_SLOT[1], -CW_SLOT[0], 0, CW_BOLT))
        for u in (205, 150, 95):
            holes.append(slot(u, 0, 3.5, 8))
        if kind == "A":
            holes.append(hole(-ARM, 0, HOOK_D))
        return pts, holes

    pa, ha = beam("A")
    parts.append(Part("beam_A", "Beam centre ply", pa, ha, qty=1))
    pb, hb = beam("B")
    parts.append(Part("beam_B", "Beam outer ply (nut pocket)", pb, hb, qty=2))

    # motor plate, plain
    def plate(width, guard):
        holes = [hole(sx * MOTOR_PATTERN / 2, sy * MOTOR_PATTERN / 2, M3_CLR)
                 for sx in (-1, 1) for sy in (-1, 1)]
        holes.append(slot(0, 0, MOUNT_TAB, T + SLOT_FIT))
        holes.append(slot(0, 16, 12, 8))
        if guard:
            for sy in (-1, 1):
                holes.append(slot(0, sy * GUARD_LEG_Y, 20, T + SLOT_FIT))
        return rect(-MOUNT_PLATE / 2, -width / 2, MOUNT_PLATE / 2, width / 2), holes

    o, h = plate(MOUNT_PLATE, False)
    parts.append(Part("motor_plate", "Motor plate", o, h, qty=1))

    # optional prop guard
    o, h = plate(GUARD_PLATE_W, True)
    parts.append(Part("motor_plate_guard", "Motor plate for guard (use instead of plain)", o, h,
                      qty=1, optional=True))
    ring_o = arc(0, 0, GUARD_OD / 2, 0, 360, 120)[:-1]
    ring_h = [hole(0, 0, GUARD_ID)] + [slot(0, sy * GUARD_LEG_Y, 20, T + SLOT_FIT) for sy in (-1, 1)]
    parts.append(Part("guard_ring", "Prop guard ring", ring_o, ring_h, qty=1, optional=True))
    lt = (20 + KERF) / 2
    leg = [(-12, 0), (-lt, 0), (-lt, -T), (lt, -T), (lt, 0), (12, 0), (12, LEG_H),
           (lt, LEG_H), (lt, LEG_H + T), (-lt, LEG_H + T), (-lt, LEG_H), (-12, LEG_H)]
    parts.append(Part("guard_leg", "Prop guard leg", leg, [], qty=2, optional=True))
    return parts


# ------------------------------------------------------------------ nesting
def nest(parts_list):
    """Shelf packing. Returns list of sheets, each a list of (part, ox, oy)."""
    items = []
    for p in parts_list:
        items += [p] * p.qty
    items.sort(key=lambda p: (-p.h, -p.w))
    sheets = []
    for p in items:
        placed = False
        for sh in sheets:
            for shelf in sh["shelves"]:
                if p.h <= shelf["h"] and shelf["x"] + p.w <= SHEET_W - SHEET_MARGIN:
                    sh["items"].append((p, shelf["x"], shelf["y"]))
                    shelf["x"] += p.w + SHEET_GAP
                    placed = True
                    break
                if p.h > shelf["h"]:
                    pass
            if placed:
                break
            ny = sh["next_y"]
            if ny + p.h <= SHEET_H - SHEET_MARGIN:
                sh["shelves"].append({"x": SHEET_MARGIN + p.w + SHEET_GAP, "y": ny, "h": p.h})
                sh["items"].append((p, SHEET_MARGIN, ny))
                sh["next_y"] = ny + p.h + SHEET_GAP
                placed = True
                break
        if not placed:
            if p.w > SHEET_W - 2 * SHEET_MARGIN or p.h > SHEET_H - 2 * SHEET_MARGIN:
                raise SystemExit("part %s does not fit the sheet" % p.name)
            sheets.append({"shelves": [{"x": SHEET_MARGIN + p.w + SHEET_GAP, "y": SHEET_MARGIN, "h": p.h}],
                           "items": [(p, SHEET_MARGIN, SHEET_MARGIN)],
                           "next_y": SHEET_MARGIN + p.h + SHEET_GAP})
    return [s["items"] for s in sheets]


def tx(p, ox, oy):
    return lambda x, y: (ox + (x - p.minx), oy + (p.maxy - y))


def contours_for(p, ox, oy):
    f = tx(p, ox, oy)
    out = [("poly", [f(*q) for q in p.outline])]
    for hc in p.holes:
        if hc["kind"] == "circle":
            out.append(("circle", f(*hc["c"]), hc["d"]))
        else:
            out.append(("poly", [f(*q) for q in hc["pts"]]))
    return out


def fmt(v):
    return ("%.3f" % v).rstrip("0").rstrip(".")


def write_svg(path, sheet, preview=False):
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="%smm" height="%smm" viewBox="0 0 %s %s">'
         % (fmt(SHEET_W), fmt(SHEET_H), fmt(SHEET_W), fmt(SHEET_H))]
    if preview:
        L.append('<rect width="%s" height="%s" fill="#f4f1ea"/>' % (fmt(SHEET_W), fmt(SHEET_H)))
        stroke, sw, fill = "#7a1f1f", "0.4", "#e2c595"
    else:
        stroke, sw, fill = "#ff0000", "0.01", "none"
    for i, (p, ox, oy) in enumerate(sheet):
        L.append('<g id="%s-%d" fill="%s" fill-rule="evenodd" stroke="%s" stroke-width="%s">' % (p.name, i, fill, stroke, sw))
        d = ""
        for c in contours_for(p, ox, oy):
            if c[0] == "poly":
                d += "M" + " L".join("%s %s" % (fmt(a), fmt(b)) for a, b in c[1]) + " Z "
            elif preview:
                (cx, cy), dd = c[1], c[2]
                r = dd / 2
                d += "M%s %s a%s %s 0 1 0 %s 0 a%s %s 0 1 0 %s 0 Z " % (
                    fmt(cx - r), fmt(cy), fmt(r), fmt(r), fmt(2 * r), fmt(r), fmt(r), fmt(-2 * r))
            else:
                (cx, cy), dd = c[1], c[2]
                L.append('<circle cx="%s" cy="%s" r="%s" fill="none"/>' % (fmt(cx), fmt(cy), fmt(dd / 2)))
        L.append('<path d="%s" %s/>' % (d.strip(), 'fill="%s"' % fill if preview else 'fill="none"'))
        L.append("</g>")
        if preview:
            L.append('<text x="%s" y="%s" font-family="Helvetica,Arial,sans-serif" font-size="6" fill="#333">%s</text>'
                     % (fmt(ox + 2), fmt(oy + 8), "%s  %.0f x %.0f" % (p.label, p.w, p.h)))
    L.append("</svg>")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")


def write_dxf(path, sheet):
    E = ["0", "SECTION", "2", "ENTITIES"]
    for p, ox, oy in sheet:
        for c in contours_for(p, ox, oy):
            if c[0] == "poly":
                E += ["0", "POLYLINE", "8", "CUT", "66", "1", "70", "1"]
                for a, b in c[1]:
                    E += ["0", "VERTEX", "8", "CUT", "10", fmt(a), "20", fmt(SHEET_H - b), "30", "0"]
                E += ["0", "SEQEND", "8", "CUT"]
            else:
                (cx, cy), dd = c[1], c[2]
                E += ["0", "CIRCLE", "8", "CUT", "10", fmt(cx), "20", fmt(SHEET_H - cy), "30", "0", "40", fmt(dd / 2)]
    E += ["0", "ENDSEC", "0", "EOF"]
    with open(path, "w") as f:
        f.write("\n".join(E) + "\n")


# ------------------------------------------------------------------ 3D model
def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def mat(origin, a, b):
    c = cross(a, b)
    return [a[0], a[1], a[2], 0, b[0], b[1], b[2], 0, c[0], c[1], c[2], 0,
            origin[0], origin[1], origin[2], 1]


def contour_json(p):
    out = [[[round(x, 3), round(y, 3)] for x, y in p.outline]]
    for hc in p.holes:
        if hc["kind"] == "circle":
            cx, cy = hc["c"]
            r = hc["d"] / 2
            out.append([[round(cx + r * math.cos(2 * math.pi * i / 48), 3),
                         round(cy + r * math.sin(2 * math.pi * i / 48), 3)] for i in range(48)])
        else:
            out.append([[round(x, 3), round(y, 3)] for x, y in hc["pts"]])
    return out


def build_model(parts):
    P = {p.name: p for p in parts}
    X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    items = []

    def plate(pid, name, label, grp, m, expl, variant=None):
        p = P[name]
        items.append({"id": pid, "type": "plate", "group": grp, "label": label,
                      "thickness": T, "contours": contour_json(p), "matrix": m,
                      "explode": expl, "material": "wood", "variant": variant})

    for k in range(BASE_LAYERS):
        plate("base%d" % k, "base", "Base layer %d (%.0f x %.0f x %.0f mm)" % (k + 1, BASE_L, BASE_W, T),
              "static", mat((0, (2 * k + 1) * T / 2, 0), X, Z), [0, -50 + 40 * k, 0])
    for s in (-1, 1):
        plate("upright%d" % s, "upright", "Upright, 608ZZ press-fit seat %.2f mm" % (BEARING_OD - PRESS_FIT),
              "static", mat((0, BASE_T, s * (G / 2 + T / 2)), X, Y), [0, 0, s * 90])
    for i, zt in enumerate(TIE_Z):
        plate("tie%d" % i, "tie", "Tie plate", "static", mat((0, BASE_T + zt, 0), Z, X), [0, 20 + 15 * i, 0])
    for s in (-1, 1):
        plate("post%d" % s, "post", "End stop post (+-%.0f deg)" % MAX_TILT,
              "static", mat((s * POST_X, BASE_T, 0), Z, Y), [s * 40, 40, 0])
    plate("beamA", "beam_A", "Beam centre ply (hook hole, motor tab)", "beam", mat((0, 0, 0), X, Y), [0, 70, 0])
    for s in (-1, 1):
        plate("beamB%d" % s, "beam_B", "Beam outer ply (M8 nut pocket)", "beam",
              mat((0, 0, s * T), X, Y), [0, 70, s * 45])
    plate("mplate", "motor_plate", "Motor plate, 16 x 16 M3", "beam",
          mat((ARM, BEAM_H / 2 + T / 2, 0), X, Z), [0, 90, 0], "plain")
    plate("mplateg", "motor_plate_guard", "Motor plate for guard", "beam",
          mat((ARM, BEAM_H / 2 + T / 2, 0), X, Z), [0, 90, 0], "guard")
    plate("gring", "guard_ring", "Prop guard ring (optional)", "beam",
          mat((ARM, PLATE_TOP + PROP_PLANE, 0), X, Z), [0, 190, 0], "guard")
    for s in (-1, 1):
        plate("gleg%d" % s, "guard_leg", "Prop guard leg (optional)", "beam",
              mat((ARM, PLATE_TOP, s * GUARD_LEG_Y), X, Y), [0, 130, s * 20], "guard")

    def cyl(pid, label, grp, material, center, axis, r, h, segs=48, hollow=0.0, variant=None,
            expl=(0, 0, 0), opacity=1.0, rbot=None):
        items.append({"id": pid, "type": "cyl", "group": grp, "label": label, "material": material,
                      "center": list(center), "axis": axis, "r": r, "rbot": rbot if rbot is not None else r,
                      "h": h, "segs": segs, "hollow": hollow, "variant": variant,
                      "explode": list(expl), "opacity": opacity})

    zb = G / 2 + T - BEARING_W / 2    # bearing flush with the outer face
    for s in (-1, 1):
        cyl("bearing%d" % s, "608ZZ bearing", "static", "metal", (0, PIVOT_H, s * zb), "z",
            BEARING_OD / 2, BEARING_W, hollow=BEARING_ID / 2, expl=(0, 0, s * 150))
        cyl("nut%d" % s, "M8 nut", "static", "metal", (0, PIVOT_H, s * (G / 2 + T + NUT_H / 2)), "z",
            NUT_AF / math.sqrt(3), NUT_H, segs=6, hollow=ROD_D / 2, expl=(0, 0, s * 200))
    cyl("rod", "M8 x %.0f rod" % ROD_LEN, "static", "metal", (0, PIVOT_H, 0), "z", ROD_D / 2, ROD_LEN,
        expl=(0, 0, 0))
    cyl("motor", "OpenMotor 2306 (envelope, size estimated)", "beam", "motor",
        (ARM, PLATE_TOP + MOTOR_H / 2, 0), "y", MOTOR_D / 2, MOTOR_H, expl=(0, 130, 0))
    cyl("prop", "5 inch prop disc (%.0f mm)" % PROP_D, "beam", "prop",
        (ARM, PLATE_TOP + PROP_PLANE, 0), "y", PROP_D / 2, 1.5, segs=96, expl=(0, 160, 0), opacity=0.25)
    cyl("bucket", "Bucket (hangs from the hook)", "hang", "bucket", (0, -40, 0), "y",
        55, 80, hollow=-1, expl=(0, -120, 0), rbot=42)
    hp = stop_post_height()
    return {
        "params": {"ply": T, "kerf": KERF, "arm": ARM, "pivot_h": PIVOT_H, "max_tilt": MAX_TILT,
                   "gap": G, "base_t": BASE_T, "beam_h": BEAM_H, "post_h": round(hp, 2),
                   "hook": [-ARM, 0, 0]},
        "items": items,
    }


# ------------------------------------------------------------------ checks
def checks(parts):
    th = math.radians(MAX_TILT)
    P = {p.name: p for p in parts}
    mass = lambda names: sum(P[n].area() * T * PLY_DENSITY / 1000.0 * P[n].qty for n in names)
    m_static = mass(["base", "upright", "tie", "post"])
    m_beam = mass(["beam_A", "beam_B", "motor_plate"])
    F = THRUST_G / 1000.0 * 9.81
    Fs = F * ARM / POST_X                  # stop reaction with the motor end against its stop
    Fp = Fs - F                            # uplift at the pivot
    W = m_static / 1000.0 * 9.81
    half = BASE_L / 2
    over = Fp * half - Fs * (half - POST_X)
    sf = W * half / over if over > 0 else float("inf")
    print("sheets: %d x %.0f x %.0f (+%d optional)" % (len(SHEETS), SHEET_W, SHEET_H, len(OPT_SHEETS)))
    print("ply thickness %.1f  kerf %.2f  gap between uprights %.1f  rod %.0f" % (T, KERF, G, ROD_LEN))
    print("bearing seat cut path dia %.2f (actual %.2f)" % (BEARING_OD - PRESS_FIT - KERF, BEARING_OD - PRESS_FIT))
    print("bearing %.1f mm in %.1f mm ply: recess %.1f mm" % (BEARING_W, T, T - BEARING_W))
    print("hex pocket actual AF %.2f for %.1f nut, nut %.1f in %.1f pocket (recess %.1f)"
          % (NUT_AF + HEX_CLR, NUT_AF, NUT_H, T, T - NUT_H))
    print("arm %.0f mm both sides; pivot height %.0f mm; stop post height %.1f above base top" % (ARM, PIVOT_H, stop_post_height()))
    drop = PIVOT_H - ARM * math.sin(th)
    print("beam end / hook height at the stop: %.1f mm above table -> bucket may hang %.0f mm below the hook"
          % (drop, drop - 10))
    pc = PIVOT_H - ARM * math.sin(th) + (PLATE_TOP + PROP_PLANE) * math.cos(th)
    print("prop centre height with the motor end at its lowest: %.0f mm; lowest blade edge %.0f mm above table"
          % (pc, pc - PROP_D / 2 * math.sin(th)))
    xn = ARM * math.cos(th) - (PLATE_TOP + PROP_PLANE) * math.sin(th) - PROP_D / 2 * math.cos(th)
    print("nearest prop disc edge to the pivot plane (worst tilt): %.0f mm; uprights span +-%.0f mm at the base"
          % (xn, UPRIGHT_BASE / 2))
    print("mass estimate: static %.0f g, beam+plate %.0f g (ply %.2f g/cm3)" % (m_static, m_beam, PLY_DENSITY))
    print("tip-over: stop reaction %.1f N at x=%.0f, pivot uplift %.1f N, jig weight %.1f N, base +-%.0f"
          % (Fs, POST_X, Fp, W, half))
    print("tip-over safety factor %s (stop posts inside the footprint: %s)"
          % ("%.1f" % sf if sf != float("inf") else "inf", POST_X < half))
    print("lifted mass at level = thrust; at full tilt the same thrust balances %.0f g (weight arm shrinks by cos)"
          % (THRUST_G / math.cos(th)))


def main():
    global BEARING_MOUNT, SHEETS, OPT_SHEETS
    ap = argparse.ArgumentParser()
    ap.add_argument("--bearing", choices=("press", "printed"), default=BEARING_MOUNT)
    a = ap.parse_args()
    BEARING_MOUNT = a.bearing
    here = os.path.dirname(os.path.abspath(__file__))
    cut, img, view = (os.path.join(here, d) for d in ("cut", "images", "viewer"))
    for d in (cut, img, view):
        os.makedirs(d, exist_ok=True)
    for f in os.listdir(cut):
        os.remove(os.path.join(cut, f))
    parts = make_parts()
    SHEETS = nest([p for p in parts if not p.optional])
    OPT_SHEETS = nest([p for p in parts if p.optional])
    suffix = "" if BEARING_MOUNT == "press" else "-printed"
    named = [("sheet-%d%s" % (i + 1, suffix), s) for i, s in enumerate(SHEETS)] + \
            [("optional-%d%s" % (i + 1, suffix), s) for i, s in enumerate(OPT_SHEETS)]
    png = shutil.which("rsvg-convert")
    for name, s in named:
        write_svg(os.path.join(cut, name + ".svg"), s)
        write_dxf(os.path.join(cut, name + ".dxf"), s)
        pv = os.path.join(img, name + ".svg")
        write_svg(pv, s, preview=True)
        if png:
            subprocess.run([png, "-w", "1800", pv, "-o", os.path.join(img, name + ".png")], check=True)
        os.remove(pv)
        print("wrote", name, ", ".join("%s" % p.name for p, _, _ in s))
    if not png:
        print("rsvg-convert not found: no PNG previews")
    with open(os.path.join(view, "model.json"), "w") as f:
        json.dump(build_model(parts), f, separators=(",", ":"))
    checks(parts)


if __name__ == "__main__":
    main()
