#!/usr/bin/env python3
"""OpenMotor seesaw: parametric laser-cut generator (Python stdlib only).

Five 8 mm ply plates (base, two towers, arm, bucket plate) plus one printed
motor mount (motor_mount.scad). Writes, next to this script:
  cut/sheet-N.svg            cut sheets, red 0.01 mm hairline, 600 x 400 mm
  cut/<part>.dxf             one DXF per part, at the origin, units mm
  images/sheet-N.png         labelled preview (only if rsvg-convert exists)
  viewer/model.json          exact cut contours + assembly, read by viewer/index.html
  motor_mount_params.scad    numbers shared with motor_mount.scad

All dimensions in mm. Edit the parameter block, rerun, commit the output.
Kerf rule: only fit-critical features are compensated (holes smaller by KERF,
slots narrower by KERF, tabs wider by KERF). Outer outlines are not offset.
"""
import json
import math
import os
import shutil
import subprocess

# ------------------------------------------------------------------ parameters
PLY_T = 8.0            # plywood thickness (measure your sheet, ply varies +-0.3)
KERF = 0.15            # laser kerf; ask the cutter or cut a test slot
SLOT_FIT = 0.05        # extra slot width over PLY_T
BEARING_OD = 22.0      # 608ZZ
BEARING_ID = 8.0
BEARING_W = 7.0
PRESS_FIT = 0.10       # seat is this much smaller than the bearing OD
BOLT_D = 8.0           # M8 fully threaded bolt (ISO 4017 / DIN 933) is the axle
ARM_HOLE_CLR = 0.3     # arm hole is BOLT_D + this
NUT_H = 6.8            # M8 nut (ISO 4032)
NUT_AF = 13.0
WASHER_T = 1.6         # M8 washer ISO 7089
WASHER_OD = 16.0
HEAD_H = 5.3           # M8 hex head
BOLT_THREAD_OUT = 3.0  # bolt must stick out this far past the outer nut (2 threads)
STD_BOLT_LEN = (50, 55, 60, 65, 70, 80, 90, 100)
ARM = 250.0            # pivot axis to motor axis = pivot axis to bucket plate centre
ARM_END = 25.0         # arm length beyond the motor axis / bucket centre
ARM_H = 40.0           # arm height (plate on edge)
PIVOT_H = 190.0        # pivot axis height above the table
TRAVEL_DEG = 25.0      # design target: tip clear of the table up to this tilt
HOLE_D = 3.4           # M3 clearance
GRID_PITCH = 10.0      # mounting grid: M3, 10 mm pitch
GRID_COLS, GRID_ROWS = 4, 3
GRID_C = ARM - 40.0    # grid centre, distance from the pivot (both ends)
BASE_L, BASE_W = 300.0, 220.0
TOWER_FOOT = 160.0     # tower plate foot width
TOWER_TAB = 120.0      # tab width (one slot per tower)
BOSS_R = 22.0
BUCKET_PLATE = (130.0, 130.0)      # along the arm, across the arm
BUCKET_ROWS_Y = (14.0, 24.0)       # grid rows either side of the arm (y offsets)
# printed motor mount (see motor_mount.scad)
MOUNT_WALL = 4.0
MOUNT_CLR = 0.2        # gap each side between arm and mount side plates
MOUNT_GAP = 3.0        # platform floats this far above the arm top
MOUNT_PLAT_T = 4.0
MOUNT_PLAT_W = 32.0
MOUNT_SIDE_HALF = 21.0
MOTOR_PATTERNS = (16.0, 19.0)      # M3, slotted to cover both
CENTER_D = 14.0        # shaft and circlip clearance (estimate)
PROP_D = 127.0         # 5 inch prop disc
PROP_PLANE = 36.0      # prop plane above the platform top (ESTIMATE, measure)
MOTOR_D, MOTOR_H = 28.0, 31.0      # 2306 envelope (ESTIMATE)
SHEET_W, SHEET_H = 600.0, 400.0
SHEET_MARGIN, SHEET_GAP = 5.0, 4.0
THRUST_G = 1711.0
PLY_DENSITY = 0.68         # g/cm3 birch ply

# ------------------------------------------------------------------ derived
T = PLY_T
INNER_STACK = 2 * (NUT_H + NUT_H + WASHER_T) + T      # between the two inner race faces
G = INNER_STACK - 2 * (T - BEARING_W)                 # inner distance between the towers
TOWER_Y = G / 2 + T / 2
UP_H = PIVOT_H - T                                    # pivot height above the base top
TAB_LEN = T
BOLT_LEN_MIN = (G + 2 * T) + 2 * WASHER_T + NUT_H + BOLT_THREAD_OUT   # head underside to tip
BOLT_LEN = min(l for l in STD_BOLT_LEN if l >= BOLT_LEN_MIN)
MOTOR_X = ARM - GRID_C                                # motor axis from the grid centre
PLAT_X1 = MOTOR_X + 22.0
SIDE_Z0 = -ARM_H / 2 - 16.0                           # side plate bottom, arm top = 0
PLAT_TOP = ARM_H / 2 + MOUNT_GAP + MOUNT_PLAT_T       # beam frame, above the pivot axis


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
def radial_slot(cx, cy, r0, r1, ang, w):
    """Slot along a ray from (cx,cy): centres at radius r0..r1, width w (actual)."""
    c0 = (cx + r0 * math.cos(math.radians(ang)), cy + r0 * math.sin(math.radians(ang)))
    c1 = (cx + r1 * math.cos(math.radians(ang)), cy + r1 * math.sin(math.radians(ang)))
    return poly(arc(c1[0], c1[1], w / 2, ang - 90, ang + 90) + arc(c0[0], c0[1], w / 2, ang + 90, ang + 270))


def grid_cols():
    return [(c - (GRID_COLS - 1) / 2) * GRID_PITCH for c in range(GRID_COLS)]


def grid_rows():
    return [(r - (GRID_ROWS - 1) / 2) * GRID_PITCH for r in range(GRID_ROWS)]


def make_parts():
    parts = []
    # 1 base
    holes = [slot(0, sy * TOWER_Y, TOWER_TAB, T + SLOT_FIT) for sy in (-1, 1)]
    parts.append(Part("base", "Base plate", rrect(0, 0, BASE_L, BASE_W, 12), holes))

    # 2, 3 towers
    def tower(name, label):
        tw = (TOWER_TAB + KERF) / 2
        pts = [(-TOWER_FOOT / 2, 0), (-tw, 0), (-tw, -TAB_LEN), (tw, -TAB_LEN), (tw, 0),
               (TOWER_FOOT / 2, 0), (BOSS_R, UP_H)]
        pts += arc(0, UP_H, BOSS_R, 0, 180, 24)[1:-1]
        pts += [(-BOSS_R, UP_H)]
        return Part(name, label, pts, [hole(0, UP_H, BEARING_OD - PRESS_FIT)])
    parts.append(tower("tower_left", "Tower plate, left"))
    parts.append(tower("tower_right", "Tower plate, right"))

    # 4 arm
    half = ARM + ARM_END
    holes = [hole(0, 0, BOLT_D + ARM_HOLE_CLR)]
    parts.append(Part("arm", "Arm (single plate on edge)", rect(-half, -ARM_H / 2, half, ARM_H / 2), holes))

    # 5 bucket plate
    bw, bh = BUCKET_PLATE
    holes = []
    parts.append(Part("bucket_plate", "Bucket plate (sits on top of the arm end)", rect(-bw / 2, -bh / 2, bw / 2, bh / 2), holes))
    return parts


# ------------------------------------------------------------------ printed mount (viewer + scad)
def mount_platform():
    holes = []
    for pat in MOTOR_PATTERNS:
        pass
    r0, r1 = MOTOR_PATTERNS[0] * math.sqrt(2) / 2, MOTOR_PATTERNS[-1] * math.sqrt(2) / 2
    for a in (45, 135, 225, 315):
        holes.append(radial_slot(MOTOR_X, 0, r0, r1, a, HOLE_D))
    holes.append({"kind": "circle", "c": (MOTOR_X, 0), "d": CENTER_D})
    holes.append(poly(rect(MOTOR_X - 18, -4, MOTOR_X, 4)))        # wire slot toward the arm
    outline = rect(-MOUNT_SIDE_HALF, -MOUNT_PLAT_W / 2, PLAT_X1, MOUNT_PLAT_W / 2)
    return outline, holes


def mount_side():
    top = MOUNT_GAP + MOUNT_PLAT_T
    outline = rect(-MOUNT_SIDE_HALF, SIDE_Z0, MOUNT_SIDE_HALF, top)
    holes = [{"kind": "circle", "c": (u, z - ARM_H / 2), "d": HOLE_D} for u in grid_cols() for z in grid_rows()]
    return outline, holes


def write_scad(path):
    vals = [("ARM_T", T), ("ARM_H", ARM_H), ("CLR", MOUNT_CLR), ("WALL", MOUNT_WALL), ("GAP", MOUNT_GAP),
            ("PLAT_T", MOUNT_PLAT_T), ("PLAT_W", MOUNT_PLAT_W), ("SIDE_HALF", MOUNT_SIDE_HALF),
            ("SIDE_Z0", SIDE_Z0), ("PLAT_X1", PLAT_X1), ("MOTOR_X", MOTOR_X), ("HOLE_D", HOLE_D),
            ("GRID_PITCH", GRID_PITCH), ("GRID_COLS", GRID_COLS), ("GRID_ROWS", GRID_ROWS),
            ("PATTERN_A", MOTOR_PATTERNS[0]), ("PATTERN_B", MOTOR_PATTERNS[-1]), ("CENTER_D", CENTER_D)]
    with open(path, "w") as f:
        f.write("// Written by generate.py, do not edit. x along the arm (toward the motor), y across, z up,\n"
                "// arm top surface at z = 0, grid centre at x = 0.\n")
        for k, v in vals:
            f.write("%s = %s;\n" % (k, fmt(float(v))))


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


def write_dxf(path, sheet, height=None):
    height = SHEET_H if height is None else height
    E = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",   # 4 = millimetres
         "0", "SECTION", "2", "ENTITIES"]
    for p, ox, oy in sheet:
        for c in contours_for(p, ox, oy):
            if c[0] == "poly":
                E += ["0", "POLYLINE", "8", "CUT", "66", "1", "70", "1"]
                for a, b in c[1]:
                    E += ["0", "VERTEX", "8", "CUT", "10", fmt(a), "20", fmt(height - b), "30", "0"]
                E += ["0", "SEQEND", "8", "CUT"]
            else:
                (cx, cy), dd = c[1], c[2]
                E += ["0", "CIRCLE", "8", "CUT", "10", fmt(cx), "20", fmt(height - cy), "30", "0", "40", fmt(dd / 2)]
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


def cont_json(outline, holes):
    out = [[[round(x, 3), round(y, 3)] for x, y in outline]]
    for hc in holes:
        if hc["kind"] == "circle":
            cx, cy = hc["c"]
            r = hc["d"] / 2
            out.append([[round(cx + r * math.cos(2 * math.pi * i / 32), 3),
                         round(cy + r * math.sin(2 * math.pi * i / 32), 3)] for i in range(32)])
        else:
            out.append([[round(x, 3), round(y, 3)] for x, y in hc["pts"]])
    return out


def build_model(parts):
    P = {p.name: p for p in parts}
    X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    items = []

    def plate(pid, label, grp, m, expl, outline, holes, thick, material="wood"):
        items.append({"id": pid, "type": "plate", "group": grp, "label": label, "thickness": thick,
                      "contours": cont_json(outline, holes), "matrix": m, "explode": expl, "material": material})

    def cyl(pid, label, grp, material, center, axis, r, h, segs=48, hollow=0.0, expl=(0, 0, 0),
            opacity=1.0, rbot=None):
        items.append({"id": pid, "type": "cyl", "group": grp, "label": label, "material": material,
                      "center": list(center), "axis": axis, "r": r, "rbot": rbot if rbot is not None else r,
                      "h": h, "segs": segs, "hollow": hollow, "explode": list(expl), "opacity": opacity})

    p = P["base"]
    plate("base", "Base plate (%.0f x %.0f x %.0f mm)" % (BASE_L, BASE_W, T), "static",
          mat((0, T / 2, 0), X, Z), [0, -30, 0], p.outline, p.holes, T)
    for s, name in ((-1, "tower_left"), (1, "tower_right")):
        p = P[name]
        plate(name, "%s, 608ZZ press-fit seat %.2f mm" % (p.label, BEARING_OD - PRESS_FIT), "static",
              mat((0, T, s * TOWER_Y), X, Y), [0, 0, s * 110], p.outline, p.holes, T)
    p = P["arm"]
    plate("arm", "Arm, 550 x 40 x 8 mm, M8 hole", "beam",
          mat((0, 0, 0), X, Y), [0, 60, 0], p.outline, p.holes, T)
    p = P["bucket_plate"]
    plate("bucket", "Bucket plate (bucket stands on it)", "beam",
          mat((-ARM, ARM_H / 2 + T / 2, 0), X, Z), [0, 120, 0], p.outline, p.holes, T)
    # printed motor mount: platform + two side plates
    o, h = mount_platform()
    plate("mount_plat", "Printed motor mount (platform, slotted 16/19 mm M3)", "beam",
          mat((GRID_C, ARM_H / 2 + MOUNT_GAP + MOUNT_PLAT_T / 2, 0), X, Z), [0, 140, 0], o, h, MOUNT_PLAT_T, "print")
    o, h = mount_side()
    for s in (-1, 1):
        plate("mount_side%d" % s, "Printed motor mount (side plate)", "beam",
              mat((GRID_C, ARM_H / 2, s * (T / 2 + MOUNT_CLR + MOUNT_WALL / 2)), X, Y),
              [0, 140, s * 40], o, h, MOUNT_WALL, "print")
    # bearings (flush with the outer tower face)
    zb = G / 2 + T - BEARING_W / 2
    for s in (-1, 1):
        cyl("bearing%d" % s, "608ZZ bearing", "static", "metal", (0, PIVOT_H, s * zb), "z",
            BEARING_OD / 2, BEARING_W, hollow=BEARING_ID / 2, expl=(0, 0, s * 150))
    # bolt stack, in the beam frame (origin = pivot axis); z = lateral, left = -z
    zo = G / 2 + T                      # outer tower face
    zin = INNER_STACK / 2               # inner race face
    hx = NUT_AF / math.sqrt(3)
    z_head_under = -(zo + WASHER_T)
    cyl("bolt", "M8 x %d full-thread bolt" % BOLT_LEN, "beam", "metal",
        (0, 0, z_head_under + BOLT_LEN / 2), "z", BOLT_D / 2, BOLT_LEN, expl=(0, 0, 0))
    cyl("head", "Bolt head", "beam", "metal", (0, 0, z_head_under - HEAD_H / 2), "z", hx, HEAD_H, segs=6,
        expl=(0, 0, -260))
    def ring(pid, label, z, h, r, segs, expl, hollow=BOLT_D / 2):
        cyl(pid, label, "beam", "metal", (0, 0, z), "z", r, h, segs=segs, hollow=hollow, expl=(0, 0, expl))
    ring("wash_out_l", "M8 washer (outside)", -(zo + WASHER_T / 2), WASHER_T, WASHER_OD / 2, 32, -200, 4.2)
    ring("wash_out_r", "M8 washer (outside)", zo + WASHER_T / 2, WASHER_T, WASHER_OD / 2, 32, 200, 4.2)
    ring("nut_out", "M8 nut (outside)", zo + WASHER_T + NUT_H / 2, NUT_H, hx, 6, 260)
    for s in (-1, 1):
        z = s * (zin - NUT_H / 2)
        ring("spacer%d" % s, "M8 nut as spacer against the inner race", z, NUT_H, hx, 6, s * 110)
        z = s * (zin - NUT_H - NUT_H / 2)
        ring("clamp%d" % s, "M8 clamp nut", z, NUT_H, hx, 6, s * 70)
        z = s * (zin - 2 * NUT_H - WASHER_T / 2)
        ring("clampw%d" % s, "M8 clamp washer", z, WASHER_T, WASHER_OD / 2, 32, s * 35, 4.2)
    # motor and prop (envelopes)
    mx = GRID_C + MOTOR_X
    cyl("motor", "OpenMotor 2306 (envelope, size estimated)", "beam", "motor",
        (mx, PLAT_TOP + MOTOR_H / 2, 0), "y", MOTOR_D / 2, MOTOR_H, expl=(0, 200, 0))
    cyl("prop", "5 inch prop disc (%.0f mm)" % PROP_D, "beam", "prop",
        (mx, PLAT_TOP + PROP_PLANE, 0), "y", PROP_D / 2, 1.5, segs=96, expl=(0, 240, 0), opacity=0.25)
    return {"params": {"ply": T, "kerf": KERF, "arm": ARM, "pivot_h": PIVOT_H, "travel": TRAVEL_DEG,
                       "gap": round(G, 2), "bolt_len": BOLT_LEN}, "items": items}


# ------------------------------------------------------------------ checks
def tip_contact_deg():
    lo, hi = 0.0, 80.0
    tip = ARM + ARM_END
    for _ in range(60):
        mid = (lo + hi) / 2
        th = math.radians(mid)
        if tip * math.sin(th) + ARM_H / 2 * math.cos(th) < PIVOT_H:
            lo = mid
        else:
            hi = mid
    return lo


def checks(parts):
    P = {p.name: p for p in parts}
    th = math.radians(TRAVEL_DEG)
    area_g = lambda n: P[n].area() * T * PLY_DENSITY / 1000.0
    print("sheets: %d x %.0f x %.0f" % (len(SHEETS), SHEET_W, SHEET_H))
    print("ply %.1f kerf %.2f; bearing seat actual %.2f (cut path %.2f); bearing recess %.1f mm"
          % (T, KERF, BEARING_OD - PRESS_FIT, BEARING_OD - PRESS_FIT - KERF, T - BEARING_W))
    print("tower gap G %.1f mm; inner stack %.1f mm (spacer nut, clamp nut, washer, arm, washer, clamp nut, spacer nut)"
          % (G, INNER_STACK))
    print("bolt: head underside to tip at least %.1f mm -> M8 x %d fully threaded" % (BOLT_LEN_MIN, BOLT_LEN))
    tip = ARM + ARM_END
    print("arm %.0f mm each side to axis/centre; pivot %.0f mm; plate length %.0f" % (ARM, PIVOT_H, 2 * tip))
    drop = tip * math.sin(th) + ARM_H / 2 * math.cos(th)
    print("arm tip height above table at %.0f deg: %.1f mm" % (TRAVEL_DEG, PIVOT_H - drop))
    tc = tip_contact_deg()
    print("arm tip reaches the table at %.1f deg (this is the travel limit, there are no stops)" % tc)
    thc = math.radians(tc)
    xb = BASE_L / 2
    u = (xb + ARM_H / 2 * math.sin(thc)) / math.cos(thc)
    print("arm underside height over the base edge at that tilt: %.0f mm (base top %.0f)"
          % (PIVOT_H - (u * math.sin(thc) + ARM_H / 2 * math.cos(thc)), T))
    pc = PIVOT_H - ARM * math.sin(th) + PLAT_TOP * math.cos(th) + PROP_PLANE * math.cos(th)
    print("prop centre height with the motor end down at %.0f deg: %.0f mm; lowest blade edge %.0f mm"
          % (TRAVEL_DEG, pc, pc - PROP_D / 2 * math.sin(th)))
    xn = ARM * math.cos(th) - (PLAT_TOP + PROP_PLANE) * math.sin(th) - PROP_D / 2 * math.cos(th)
    print("nearest prop disc edge to the pivot plane: %.0f mm; towers span +-%.0f mm" % (xn, TOWER_FOOT / 2))
    m_plate = area_g("bucket_plate")
    m_mount = 25.0
    m_motor_end = 33.0 + m_mount + 5.0 + 2.0
    print("end masses (estimates): bucket plate %.0f g at the bucket end; motor 33 + mount %.0f + prop 5 + screws 2 = %.0f g"
          % (m_plate, m_mount, m_motor_end))
    print("imbalance: %.0f g at %.0f mm (bucket end heavier if positive); plus the founder's bracket"
          % (m_plate - m_motor_end, ARM))
    F = THRUST_G / 1000.0 * 9.81
    Fc = F * ARM / tip
    print("thrust against the table at the tip: table %.1f N up, pivot %.1f N (beam on the bearings); "
          "free case loads the pivot with the weight only" % (Fc, F - Fc))
    print("balanced case: pivot load = thrust + payload weight, centred on the base (no overturning moment)")


def main():
    global SHEETS
    here = os.path.dirname(os.path.abspath(__file__))
    cut, img, view = (os.path.join(here, d) for d in ("cut", "images", "viewer"))
    for d in (cut, img, view):
        os.makedirs(d, exist_ok=True)
    for d in (cut, img):
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
    parts = make_parts()
    SHEETS = nest(parts)
    png = shutil.which("rsvg-convert")
    for i, s in enumerate(SHEETS):
        name = "sheet-%d" % (i + 1)
        write_svg(os.path.join(cut, name + ".svg"), s)
        pv = os.path.join(img, name + ".svg")
        write_svg(pv, s, preview=True)
        if png:
            subprocess.run([png, "-w", "1800", pv, "-o", os.path.join(img, name + ".png")], check=True)
        os.remove(pv)
        print("wrote", name, ", ".join(p.name for p, _, _ in s))
    for p in parts:
        write_dxf(os.path.join(cut, p.name + ".dxf"), [(p, 0, 0)], height=p.h)   # one part per file, at the origin
        print("wrote %s.dxf (%.0f x %.0f mm)" % (p.name, p.w, p.h))
    if not png:
        print("rsvg-convert not found: no PNG previews")
    with open(os.path.join(view, "model.json"), "w") as f:
        json.dump(build_model(parts), f, separators=(",", ":"))
    write_scad(os.path.join(here, "motor_mount_params.scad"))
    checks(parts)


if __name__ == "__main__":
    main()
