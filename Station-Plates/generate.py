#!/usr/bin/env python3
"""Factory test-station plates: laser-cut acrylic generator (KiCad's Python).

Reads the released board revision of each station's DUT and writes laser-cut
SVG and DXF plates plus a contacts table:

- test pads (TP*) from the production pack's positions CSV,
  `production/boards/<SKU>/<rev>/<SKU>-<rev>_positions.csv`;
- the board outline, mount holes, contact-face pads and bottom-side parts from
  the pcbnew API on the source board at the commit named in the pack's
  `SOURCE.json` (read with `git show` into a temporary file; the KiCad file in
  the board repository is never written).

The TP positions in the CSV are cross-checked against the board and the run
stops if they disagree by more than 0.05 mm.

Run with KiCad's bundled Python (KPY in the repository AGENTS.md):

    $KPY Station-Plates/generate.py                 # all stations
    $KPY Station-Plates/generate.py ESC-20          # one station
    $KPY Station-Plates/generate.py --set swd_hole=1.4 --set kerf=0.08

Frame: every plate is drawn as seen from ABOVE the assembled station, origin
at the board centre, Y up. An ESC lies face down (its contact face, KiCad
F.Cu, on the bottom pogo plate; its MCU face with the SWD pads, KiCad B.Cu,
up under the press plate), so ESC geometry is mirrored left-right. An FC
lies face up.
"""
import argparse
import csv
import json
import math
import os
import subprocess
import sys
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
# Sibling checkouts in the workspace: OpenDrone/hardware/<board> and production/.
# From a worktree outside the workspace pass --workspace <workspace root>.
HW = os.path.normpath(os.path.join(REPO, ".."))
PRODUCTION = os.path.normpath(os.path.join(REPO, "..", "..", "..", "production"))


def set_workspace(root):
    global HW, PRODUCTION
    HW = os.path.join(root, "OpenDrone", "hardware")
    PRODUCTION = os.path.join(root, "production")

# ---------------------------------------------------------------- parameters
# All lengths in mm. Hole sizes are nominal; set `kerf` to the laser's kerf so
# a hole cut at d - kerf comes out at d. Pogo receptacle press-fit holes MUST be
# checked against the datasheet of the pin actually bought (the plan names
# P100 / P75 class pins; their receptacle outer diameters vary by vendor).
P = {
    "kerf": 0.0,                 # subtracted from every hole diameter, added to every pocket
    "pocket_clearance": 0.15,    # board outline to nest pocket wall
    "margin": 30.0,              # board bbox to plate edge
    "plate_min": 110.0,          # smallest plate side, room for the rods and the clamp
    "rod_d": 8.0,                # guide rod; base and fixed plates hold it
    "rod_inset": 10.0,           # rod centre from plate edge
    "bushing_d": 15.0,           # linear bushing OD (LM8UU) in the press plate
    "stack_screw_d": 4.3,        # M4 clearance, bolts base + fixed plates together
    "stack_screw_inset": 10.0,   # from plate edge, on the edge midpoints
    # ESC bottom pogo plate (replaces PCB-to-PCB contact, founder 12 Nov)
    "power_pins_per_pad": 2,     # BATT+ and GND solder pads: pins per pad
    "power_hole": 2.0,           # P100-class receptacle hole (verify)
    "phase_hole": 2.0,           # P100-class receptacle hole (verify)
    "signal_hole": 1.7,          # P75-class receptacle hole (verify), signal row
    "swd_hole": 1.7,             # P75-class receptacle hole (verify), press plate
    "min_web": 0.4,              # acrylic left between two pogo holes
    "dowel_under": 0.2,          # locating dowel = mount drill - this
    "dowel_clear": 1.0,          # press-plate hole over a dowel tip = dowel + this
    "wire_window": 6.0,          # base-plate window around the board bbox, for pogo tails
    # FC nest
    "fc_slots": 2,
    "fc_slot_gap": 20.0,         # between the two board pockets
    "fc_ledge": 1.0,             # support-plate ledge under the board edge
    "fc_part_clear": 0.5,        # around bottom-side parts in the support window
    "fc_usb_notch_w": 13.0,      # USB-C plug overmould width
    "fc_stand_d": 3.2,           # M3 holes for standoffs / feet
}

STATIONS = {
    "ESC-20": {"kind": "esc", "sku": "OpenESC-20x20", "rev": "rev3.3", "contact_fp": "4in1ESC"},
    "ESC-30": {"kind": "esc", "sku": "OpenESC-30x30", "rev": "rev3.3", "contact_fp": "4in1ESC30x30"},
    "FC-20": {"kind": "fc", "sku": "OpenFC-Lite-Mini", "rev": "rev3.3"},
    "FC-30": {"kind": "fc", "sku": "OpenFC-Lite", "rev": "rev3.3"},
}


def mm(v):
    return pcbnew.ToMM(v)


# ------------------------------------------------------------------- sources
def load_pack(sku, rev):
    d = os.path.join(PRODUCTION, "boards", sku, rev)
    src = json.load(open(os.path.join(d, "SOURCE.json")))["source"]
    positions = os.path.join(d, "%s-%s_positions.csv" % (sku, rev))
    return d, src, positions


def load_board(src):
    repo = os.path.join(HW, os.path.basename(src["repository"]))
    blob = subprocess.check_output(["git", "-C", repo, "show", "%s:%s" % (src["commit"], src["path"])])
    tmp = tempfile.NamedTemporaryFile(suffix=".kicad_pcb", delete=False)
    tmp.write(blob)
    tmp.close()
    try:
        return pcbnew.LoadBoard(tmp.name)
    finally:
        os.unlink(tmp.name)


def read_tps(positions):
    out = {}
    with open(positions, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["Designator"].startswith("TP"):
                out[row["Designator"]] = (float(row["Mid X"]), -float(row["Mid Y"]), row["Layer"])
    return out


def check_tps(board, tps):
    """CSV vs board: both in KiCad coordinates (CSV Y is negated KiCad Y)."""
    worst = 0.0
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref in tps:
            x, y, _ = tps[ref]
            p = fp.GetPosition()
            worst = max(worst, math.hypot(mm(p.x) - x, mm(p.y) - y))
    if worst > 0.05:
        sys.exit("positions CSV and board disagree by %.3f mm on a TP: wrong pack or source" % worst)
    return worst


def outline_set(board):
    ps = pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(ps, True) or ps.OutlineCount() != 1:
        sys.exit("board outline is not one closed contour")
    return ps


def poly_points(ps):
    """Every outline and hole of a SHAPE_POLY_SET as point lists (KiCad mm)."""
    out = []
    for i in range(ps.OutlineCount()):
        chains = [ps.Outline(i)] + [ps.Hole(i, j) for j in range(ps.HoleCount(i))]
        for ch in chains:
            out.append([(mm(ch.CPoint(k).x), mm(ch.CPoint(k).y)) for k in range(ch.PointCount())])
    return out


def inflate(ps, d):
    q = pcbnew.SHAPE_POLY_SET(ps)
    q.Inflate(pcbnew.FromMM(d), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.005))
    return q


def rect_set(x0, y0, x1, y1):
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        ps.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    return ps


# ------------------------------------------------------------------ geometry
class Plate:
    def __init__(self, name, thickness, w, h, note):
        self.name, self.t, self.w, self.h, self.note = name, thickness, w, h, note
        self.polys = []    # cut contours (closed point lists, plate mm, Y up)
        self.holes = []    # (x, y, d, label)
        self.text = []     # (x, y, size, string) engraved
        self.custom_outer = False  # True: polys already hold the outer contour

    def hole(self, x, y, d, label):
        self.holes.append((x, y, max(d - P["kerf"], 0.1), label))

    def outer(self):
        w, h = self.w / 2, self.h / 2
        return [(-w, -h), (w, -h), (w, h), (-w, h)]

    def contours(self):
        return self.polys if self.custom_outer else [self.outer()] + self.polys


class Frame:
    """KiCad mm -> plate frame (centre at board centre, Y up, ESC mirrored)."""

    def __init__(self, cx, cy, mirror):
        self.cx, self.cy, self.m = cx, cy, mirror

    def __call__(self, x, y):
        dx = x - self.cx
        return (-dx if self.m else dx, -(y - self.cy))

    def pts(self, chain):
        return [self(x, y) for x, y in chain]


def plate_size(bw, bh):
    s = max(max(bw, bh) + 2 * P["margin"], P["plate_min"])
    return s, s


def rods(plate, d, label):
    r = P["rod_inset"]
    for sx in (-1, 1):
        for sy in (-1, 1):
            plate.hole(sx * (plate.w / 2 - r), sy * (plate.h / 2 - r), d, label)


def stack_screws(plate):
    r = P["stack_screw_inset"]
    for x, y in ((0, plate.h / 2 - r), (0, -plate.h / 2 + r), (plate.w / 2 - r, 0), (-plate.w / 2 + r, 0)):
        plate.hole(x, y, P["stack_screw_d"], "M4 stack screw")


def label(plate, station, rev, src):
    plate.text.append((-plate.w / 2 + 26, plate.h / 2 - 8, 3.0, "%s %s" % (station, plate.name)))
    plate.text.append((-plate.w / 2 + 26, -plate.h / 2 + 4, 2.2,
                       "%s %s src %s t=%g mm, view from above" % (STATIONS[station]["sku"], rev, src["commit"][:8], plate.t)))


# ------------------------------------------------------------------ ESC
def esc_contacts(board, contact_fp):
    """Pogo targets on the contact face (KiCad F.Cu) from the contact footprint."""
    fp = [f for f in board.GetFootprints() if str(f.GetFPID().GetLibItemName()) == contact_fp]
    if len(fp) != 1:
        sys.exit("contact footprint %s not found exactly once" % contact_fp)
    groups, mounts = {}, []
    for pd in fp[0].Pads():
        bb = pd.GetBoundingBox()
        box = (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))
        if pd.GetDrillSizeX() >= pcbnew.FromMM(2.0):
            mounts.append((mm(pd.GetPosition().x), mm(pd.GetPosition().y), mm(pd.GetDrillSizeX())))
            continue
        g = groups.setdefault(pd.GetNumber(), {"net": pd.GetNetname(), "boxes": [], "drill": []})
        g["boxes"].append(box)
        if pd.GetDrillSizeX() > 0:
            g["drill"].append((mm(pd.GetPosition().x), mm(pd.GetPosition().y), mm(pd.GetDrillSizeX())))
    pins = []
    for num, g in sorted(groups.items(), key=lambda kv: int(kv[0])):
        x0 = min(b[0] for b in g["boxes"]); y0 = min(b[1] for b in g["boxes"])
        x1 = max(b[2] for b in g["boxes"]); y1 = max(b[3] for b in g["boxes"])
        w, h = x1 - x0, y1 - y0
        net = g["net"]
        if net.startswith("unconnected"):
            continue
        area = w * h
        if area >= 20:   # BATT+ / GND solder pads: several pins along the long axis
            kind = "power"
            n = int(P["power_pins_per_pad"])
            long_x = w >= h
            L = w if long_x else h
            step = (L - 5.0) / max(n - 1, 1)
            for i in range(n):
                o = -((L - 5.0) / 2) + i * step if n > 1 else 0
                px = (x0 + x1) / 2 + (o if long_x else 0)
                py = (y0 + y1) / 2 + (0 if long_x else o)
                pins.append((num, net, kind, px, py, P["power_hole"], (w, h)))
        else:
            kind = "phase" if "Motor" in net else "signal"
            hole = P["phase_hole"] if kind == "phase" else P["signal_hole"]
            pins.append((num, net, kind, (x0 + x1) / 2, (y0 + y1) / 2, hole, (w, h)))
    stagger(pins)
    return pins, mounts


def stagger(pins):
    """Signal row pads sit at 1.5 mm pitch: closer than two receptacles. Offset
    every other pin along its pad's long axis, staying 1 mm inside the pad."""
    sig = sorted([i for i, p in enumerate(pins) if p[2] == "signal"], key=lambda i: (round(pins[i][4], 1), pins[i][3]))
    for k, i in enumerate(sig):
        num, net, kind, x, y, d, (w, h) = pins[i]
        room = (max(w, h) / 2) - 1.0
        o = room if k % 2 else -room
        if h >= w:
            y += o
        else:
            x += o
        pins[i] = (num, net, kind, x, y, d, (w, h))


def min_web(holes):
    worst = None
    for i in range(len(holes)):
        for j in range(i + 1, len(holes)):
            a, b = holes[i], holes[j]
            web = math.hypot(a[0] - b[0], a[1] - b[1]) - (a[2] + b[2]) / 2
            if worst is None or web < worst[0]:
                worst = (web, a[3], b[3])
    return worst


def build_esc(station, cfg, board, tps, src):
    bb = board.GetBoardEdgesBoundingBox()
    cx, cy, bw, bh = mm(bb.GetCenter().x), mm(bb.GetCenter().y), mm(bb.GetWidth()), mm(bb.GetHeight())
    f = Frame(cx, cy, True)
    w, h = plate_size(bw, bh)
    pins, mounts = esc_contacts(board, cfg["contact_fp"])
    rows = []

    base = Plate("base", 8, w, h, "Base: holds the guide rods (press fit), window for the pogo wire tails")
    rods(base, P["rod_d"], "guide rod, press fit")
    stack_screws(base)
    ww = bw / 2 + P["wire_window"]
    wh = bh / 2 + P["wire_window"]
    base.polys.append([(-ww, -wh), (ww, -wh), (ww, wh), (-ww, wh)])

    pogo = Plate("pogo", 8, w, h, "Bottom pogo plate: spring pins up into the ESC's contact face; dowels locate the board")
    rods(pogo, P["rod_d"] + 0.1, "guide rod, slide fit")
    stack_screws(pogo)
    for num, net, kind, x, y, d, _ in pins:
        px, py = f(x, y)
        variant = "long (GND first)" if net == "GND" and kind in ("power", "signal") else "standard"
        pogo.hole(px, py, d, "%s %s" % (kind, net))
        rows.append(("pogo", kind, "U pad %s" % num, net, variant, px, py, d))
    dowel = None
    for x, y, drill in mounts:
        dowel = drill - P["dowel_under"]
        px, py = f(x, y)
        pogo.hole(px, py, dowel, "locating dowel")
        rows.append(("pogo", "dowel", "mount hole", "GND", "dowel %.1f + stop spacer" % dowel, px, py, dowel))

    nest = Plate("nest", 3, w, h, "Nest: board pocket, loading guide; thickness = stop spacer + 1 mm (see README)")
    rods(nest, P["rod_d"] + 0.1, "guide rod, slide fit")
    stack_screws(nest)
    pocket = inflate(outline_set(board), P["pocket_clearance"] + P["kerf"] / 2)
    for ch in poly_points(pocket):
        nest.polys.append(f.pts(ch))

    press = Plate("press", 8, w, h, "Press plate: rides on bushings, carries the SWD pogo pins onto the MCU face")
    rods(press, P["bushing_d"], "linear bushing")
    for ref in sorted(tps, key=lambda r: int(r[2:])):
        x, y, layer = tps[ref]
        if layer != "bottom":
            sys.exit("%s is on %s: an ESC TP is expected on the MCU face (bottom)" % (ref, layer))
        px, py = f(x, y)
        press.hole(px, py, P["swd_hole"], "SWD %s" % ref)
        rows.append(("press", "swd", ref, "SWD", "standard", px, py, P["swd_hole"]))
    for x, y, drill in mounts:
        px, py = f(x, y)
        press.hole(px, py, dowel + P["dowel_clear"], "dowel tip clearance")
    press.text.append((-3, -1, 2.0, "+ clamp"))

    plates = [base, pogo, nest, press]
    for pl in plates:
        label(pl, station, cfg["rev"], src)
    checks = {"pogo": min_web([h_ for h_ in pogo.holes if "stack" not in h_[3] and "rod" not in h_[3]]),
              "press": min_web([h_ for h_ in press.holes if "SWD" in h_[3]])}
    return plates, rows, checks, (bw, bh)


# ------------------------------------------------------------------ FC
def chains_to_set(chains):
    ps = pcbnew.SHAPE_POLY_SET()
    for ch in chains:
        ps.NewOutline()
        for x, y in ch:
            ps.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    ps.Simplify()
    return ps


def cut_plate(plate, chains):
    """Subtract windows from the plate rectangle; a window that reaches the
    edge becomes an open notch in the outer contour."""
    w, h = plate.w / 2, plate.h / 2
    ps = rect_set(-w, -h, w, h)
    ps.BooleanSubtract(chains_to_set(chains))
    plate.custom_outer = True
    plate.polys.extend(poly_points(ps))


def build_fc(station, cfg, board, tps, src):
    bb = board.GetBoardEdgesBoundingBox()
    cx, cy, bw, bh = mm(bb.GetCenter().x), mm(bb.GetCenter().y), mm(bb.GetWidth()), mm(bb.GetHeight())
    outline = outline_set(board)

    # Bottom-side parts the support ledge must clear, and the USB plug notch.
    window = inflate(outline, -P["fc_ledge"])
    usb = None
    for fp in board.GetFootprints():
        if fp.GetLayer() != pcbnew.B_Cu:
            continue
        fb = fp.GetBoundingBox(False)
        c = P["fc_part_clear"]
        window.BooleanAdd(rect_set(mm(fb.GetLeft()) - c, mm(fb.GetTop()) - c, mm(fb.GetRight()) + c, mm(fb.GetBottom()) + c))
        if "USB" in fp.GetReference().upper() or "TYPE-C" in str(fp.GetFPID().GetLibItemName()).upper():
            usb = fp
    pocket = inflate(outline, P["pocket_clearance"] + P["kerf"] / 2)
    rows = []
    side = "left"
    notch = None
    if usb:
        p = usb.GetPosition()
        ux, uy = mm(p.x), mm(p.y)
        bx0, by0, bx1, by1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
        d = {"left": ux - bx0, "right": bx1 - ux, "top": uy - by0, "bottom": by1 - uy}
        side = min(d, key=d.get)
        nw = P["fc_usb_notch_w"] / 2
        far = 500.0
        notch = {"left": (bx0 - far, uy - nw, ux, uy + nw), "right": (ux, uy - nw, bx1 + far, uy + nw),
                 "top": (ux - nw, by0 - far, ux + nw, uy), "bottom": (ux - nw, uy, ux + nw, by1 + far)}[side]
        window.BooleanAdd(rect_set(*notch))
        pocket.BooleanAdd(rect_set(*notch))
        f0 = Frame(cx, cy, False)
        ux_, uy_ = f0(ux, uy)
        rows.append(("support+nest", "usb notch", usb.GetReference(), "", "opens %s" % side, ux_, uy_, P["fc_usb_notch_w"]))

    # Slots side by side across the notch direction, so no notch crosses another slot.
    n = int(P["fc_slots"])
    across_x = side in ("top", "bottom")
    pitch = (bw if across_x else bh) + P["fc_slot_gap"]
    offs = [((i - (n - 1) / 2) * pitch, 0.0) if across_x else (0.0, -(i - (n - 1) / 2) * pitch) for i in range(n)]
    span = n * (bw if across_x else bh) + (n - 1) * P["fc_slot_gap"]
    w = max((span if across_x else bw) + 2 * P["margin"], P["plate_min"])
    h = max((bh if across_x else span) + 2 * P["margin"], P["plate_min"])

    base = Plate("base", 8, w, h, "Base: flat, rubber feet; support and nest plates screw on at the corners")
    support = Plate("support", 3, w, h, "Support: ledge under the board edge, window clears bottom-side parts and the USB plug")
    nest = Plate("nest", 3, w, h, "Nest: board pocket, keeps both boards still for the gyro checks")
    for pl in (base, support, nest):
        r = P["stack_screw_inset"]
        for sx in (-1, 1):
            for sy in (-1, 1):
                pl.hole(sx * (w / 2 - r), sy * (h / 2 - r), P["stack_screw_d"], "M4 stack screw")
    sup_chains, nest_chains = [], []
    for i, (ox, oy) in enumerate(offs):
        fr = Frame(cx, cy, False)
        shift = lambda ch: [(x + ox, y + oy) for x, y in fr.pts(ch)]
        sup_chains += [shift(ch) for ch in poly_points(window)]
        nest_chains += [shift(ch) for ch in poly_points(pocket)]
        tx = ox - 4 if across_x else ox + bw / 2 + 3
        ty = oy + bh / 2 + 4 if across_x else oy
        for pl in (support, nest):
            pl.text.append((tx, ty, 3.0, "SLOT %d" % (i + 1)))
        rows.append(("nest", "pocket", "slot %d" % (i + 1), "", "outline + %.2f" % P["pocket_clearance"], ox, oy, 0.0))
    cut_plate(support, sup_chains)
    cut_plate(nest, nest_chains)

    clampbar = Plate("cable-bar", 8, max(w, h), 16.0, "Cable clamp bar: screws over the USB and ESC cables")
    for x in (-clampbar.w / 2 + 8, clampbar.w / 2 - 8):
        clampbar.hole(x, 0, P["stack_screw_d"], "M4")
    plates = [base, support, nest, clampbar]
    for pl in plates:
        label(pl, station, cfg["rev"], src)
    return plates, rows, {}, (bw, bh)


# ------------------------------------------------------------------ writers
def fmt(v):
    return ("%.3f" % v).rstrip("0").rstrip(".")


def write_svg(path, plate):
    pad = 2
    W, H = plate.w + 2 * pad, plate.h + 2 * pad

    def t(x, y):
        return fmt(x + W / 2), fmt(H / 2 - y)

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<svg xmlns="http://www.w3.org/2000/svg" width="%smm" height="%smm" viewBox="0 0 %s %s">' % (fmt(W), fmt(H), fmt(W), fmt(H)),
           '<!-- %s. Red: cut. Blue: engrave. Units mm. -->' % plate.note,
           '<g fill="none" stroke="#ff0000" stroke-width="0.1">']
    for ch in plate.contours():
        out.append('<polygon points="%s"/>' % " ".join(",".join(t(x, y)) for x, y in ch))
    for x, y, d, _ in plate.holes:
        cx_, cy_ = t(x, y)
        out.append('<circle cx="%s" cy="%s" r="%s"/>' % (cx_, cy_, fmt(d / 2)))
    out.append('</g><g fill="#0000ff" font-family="sans-serif">')
    for x, y, s, txt in plate.text:
        tx_, ty_ = t(x, y)
        out.append('<text x="%s" y="%s" font-size="%s">%s</text>' % (tx_, ty_, fmt(s), txt.replace("&", "&amp;").replace("<", "&lt;")))
    out.append('</g></svg>')
    open(path, "w").write("\n".join(out) + "\n")


def write_dxf(path, plate):
    """DXF R12, layers CUT (lines, circles) and ENGRAVE (text)."""
    e = []
    for ch in plate.contours():
        for i in range(len(ch)):
            (x0, y0), (x1, y1) = ch[i], ch[(i + 1) % len(ch)]
            e += ["0", "LINE", "8", "CUT", "10", fmt(x0), "20", fmt(y0), "11", fmt(x1), "21", fmt(y1)]
    for x, y, d, _ in plate.holes:
        e += ["0", "CIRCLE", "8", "CUT", "10", fmt(x), "20", fmt(y), "40", fmt(d / 2)]
    for x, y, s, txt in plate.text:
        e += ["0", "TEXT", "8", "ENGRAVE", "10", fmt(x), "20", fmt(y), "40", fmt(s), "1", txt]
    head = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
            "0", "SECTION", "2", "ENTITIES"]
    open(path, "w").write("\n".join(head + e + ["0", "ENDSEC", "0", "EOF"]) + "\n")


def write_station(station, cfg, plates, rows, checks, size, src, worst_tp, positions):
    d = os.path.join(HERE, station)
    os.makedirs(d, exist_ok=True)
    for pl in plates:
        stem = "%s_%s" % (station, pl.name)
        write_svg(os.path.join(d, stem + ".svg"), pl)
        write_dxf(os.path.join(d, stem + ".dxf"), pl)
    with open(os.path.join(d, "%s_contacts.csv" % station), "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["plate", "kind", "ref", "net", "pin", "x_mm", "y_mm", "hole_mm"])
        for r in rows:
            wr.writerow([r[0], r[1], r[2], r[3], r[4], fmt(r[5]), fmt(r[6]), fmt(r[7])])
    manifest = {
        "generated_by": "Station-Plates/generate.py",
        "station": station, "sku": cfg["sku"], "revision": cfg["rev"],
        "source": src, "positions_csv": os.path.relpath(positions, PRODUCTION),
        "tp_csv_vs_board_mm": round(worst_tp, 4),
        "board_bbox_mm": [round(size[0], 3), round(size[1], 3)],
        "plates": [{"name": pl.name, "thickness_mm": pl.t, "size_mm": [pl.w, pl.h], "note": pl.note} for pl in plates],
        "min_web_mm": {k: (None if v is None else {"web": round(v[0], 3), "between": [v[1], v[2]]}) for k, v in checks.items()},
        "params": P,
    }
    json.dump(manifest, open(os.path.join(d, "manifest.json"), "w"), indent=1, sort_keys=True)
    open(os.path.join(d, "manifest.json"), "a").write("\n")
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("stations", nargs="*", default=list(STATIONS))
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="override a parameter")
    ap.add_argument("--workspace", help="workspace root holding OpenDrone/hardware/<board> and production/")
    a = ap.parse_args()
    if a.workspace:
        set_workspace(os.path.abspath(a.workspace))
    for kv in a.set:
        k, v = kv.split("=", 1)
        if k not in P:
            sys.exit("unknown parameter %s" % k)
        P[k] = float(v)
    bad = 0
    for st in a.stations:
        cfg = STATIONS[st]
        _, src, positions = load_pack(cfg["sku"], cfg["rev"])
        board = load_board(src)
        tps = read_tps(positions)
        worst = check_tps(board, tps)
        build = build_esc if cfg["kind"] == "esc" else build_fc
        plates, rows, checks, size = build(st, cfg, board, tps, src)
        m = write_station(st, cfg, plates, rows, checks, size, src, worst, positions)
        webs = ", ".join("%s %s" % (k, "-" if v is None else "%.2f mm" % v["web"]) for k, v in m["min_web_mm"].items())
        print("%-6s %s %s  plates %s  holes %d  TP check %.3f mm  min web: %s" % (
            st, cfg["sku"], cfg["rev"], "/".join(p.name for p in plates),
            sum(len(p.holes) for p in plates), worst, webs or "n/a"))
        for k, v in m["min_web_mm"].items():
            if v is not None and v["web"] < P["min_web"]:
                print("  FAIL %s: %.2f mm acrylic between %s and %s" % (k, v["web"], v["between"][0], v["between"][1]))
                bad = 1
    sys.exit(bad)


if __name__ == "__main__":
    main()
