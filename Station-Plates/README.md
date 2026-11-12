# Station-Plates

Laser-cut acrylic plates for the factory test stations, one station per
product. Generated from the released board revision, so a new board revision
is a rerun, not a redraw. Not a KiCad project. Stations: one per design
(ESC, FC and RX).

| Station | DUT | Plates (thickness) | Contacts |
|---|---|---|---|
| `ESC-20/` | [OpenESC-20x20](https://github.com/OpenDrone-hw/OpenESC-20x20) rev3.3 | base 8, pogo 8, nest 3, press 8 | 23 bottom pogo pins on the contact face, 8 SWD pogo pins in the press plate, 4 locating dowels |
| `ESC-30/` | [OpenESC-30x30](https://github.com/OpenDrone-hw/OpenESC-30x30) rev3.3 | base 8, pogo 8, nest 3, press 8 | same layout, its own pad map |
| `FC-20/` | OpenFC-Lite-Mini rev3.3 | base 8, support 3, nest 3, cable bar 8 | none: the FC is tested through its USB-C and ESC plug; 2 board pockets |
| `FC-30/` | OpenFC-Lite rev3.3 | base 8, support 3, nest 3, cable bar 8 | same, 2 board pockets |
| `RX-LITE/`, `RX-LITE-UFL/`, `RX-MONO/`, `RX-GEMINI/` | OpenRX-Lite, -Lite-UFL, -Mono, -Gemini rev2 (test pads unchanged up to rev2.3) | base 8, pogo 8, support 3, nest 3, press 8 | 5 bottom pogo pins (RX, TX, 5V, GND, BOOT), one receiver per jig |

Per station: `<station>_<plate>.svg` and `.dxf` (one per plate, cut and
engrave layers), `<station>_contacts.csv` (every pogo pin, dowel and notch
with net, pin variant, position and hole size) and `manifest.json` (source
commit, positions file, parameters, the narrowest acrylic web between two
holes).

## ESC station stack

The ESC lies **face down**: its contact face (phase, power and signal pads) on
spring pins from below, its MCU face (SWD test pads TP1 to TP8) up under the
press plate. Every plate is drawn as seen from above, so the ESC geometry is
mirrored left-right against the KiCad top view.

```
        toggle clamp (centre mark "+ clamp" on the press plate)
              |
   ===o=======+=======o===  PRESS 8 mm, linear bushings on 4 rods, 8 SWD pogo pins down
      |    | | | | |  |     dowel tips pass through clearance holes
      |  [ ESC, face down ] board rests on 4 stop spacers on the dowels
   ---o--+-----------+--o---  NEST 3 mm, pocket = outline + 0.15 mm (loading guide)
   ===o==|=|=|=|=|=|=|==o===  POGO 8 mm, receptacles: 2+2 power, 12 phase, 7 signal; dowels in the 4 mount holes
   ===o==|___________|==o===  BASE 8 mm, rods press fit, window for the receptacle wire tails
      rod               rod
```

| Pin group | Pads (contact face) | Pins | Hole default | Variant |
|---|---|---|---|---|
| Power | BATT+ (shunt side) and GND solder pads | 2 per pad | 2.0 mm (P100 class) | GND long, so ground makes first |
| Phase | 12 motor pads | 1 per pad | 2.0 mm (P100 class) | standard |
| Signal | 8-pin row: BATT+, GND, CURR, M1 to M4 (TX unconnected, skipped) | 1 per pad, staggered +-1 mm along the pad because the row pitch is 1.5 mm | 1.7 mm (P75 class) | GND long |
| SWD | TP1 to TP8 (MCU face, press plate) | 1 per pad | 1.7 mm (P75 class) | standard |
| Locating | the 4 mount holes | dowel = drill - 0.2 mm, with a stop spacer | | |

Why bottom pogo pins: the 23 Oct ESC runs failed mostly on contact, not on
the boards; flat copper-to-copper contact also makes BATT+ and GND in random
order. Spring pins with a longer GND fix both.

## FC station stack

The FC lies **face up** in one of two pockets; nothing touches its pads. The
support plate has a 1 mm ledge under the board edge and a window around every
bottom-side part. A notch for the USB-C plug runs from each pocket to the
plate edge; the slots are placed across the notch direction so no notch
crosses the other slot.

```
   [ FC ]  [ FC ]    NEST 3 mm, two pockets = outline + 0.15 mm, USB notches open to the edge
   ==ledge===ledge=  SUPPORT 3 mm, ledge 1 mm, windows clear bottom parts and the USB plug
   ================  BASE 8 mm, rubber feet; all three screwed at the corners (M4)
   cable bar 8 mm screws across the USB and ESC cables
```

## RX jig stack

One receiver per jig, every test pad down on spring pins (founder 12 Nov:
a simple press jig per RX design instead of the 64-place RX-flasher). TP1 to
TP4 are castellations on both sides; the single-side BOOT pad TP5 decides
which side goes down.

| Jig | Side down | Mirrored | BOOT (TP5) | Note |
|---|---|---|---|---|
| RX-LITE, RX-LITE-UFL | F (face down) | yes | F pad 1.2 x 1.0 | TP4 and TP5 pins pushed apart inside their pads for 0.44 mm acrylic; U.FL faces down into the support window |
| RX-MONO | B | no | B pad 1.0 x 1.3 | same push, 0.45 mm |
| RX-GEMINI | F (face down) | yes | F round 1.5 mm | TP5 is missing from the positions file and is taken from the board |

```
   ===o=======+=======o===  PRESS 8 mm on bushings, 3 mm foam pad (outline + 2 mm) under it
      |    [ receiver ]  |  NEST 3 mm, pocket = outline + 0.1 mm: its wall puts the castellated edge over the pin row
   ===o====|=|=|=|=|====o===  SUPPORT 3 mm, windows clear the down-facing parts, holes pass the pins
   ===o====|=|=|=|=|====o===  POGO 8 mm, 5 receptacles
   ===o====|_______|====o===  BASE 8 mm, rods press fit, window for the wire tails
```

| Landing | Rule |
|---|---|
| Castellation (TP1 to TP4) | middle of the pad's copper on the board, off the half hole by 0.1 mm and 0.25 mm inside the edge: about 1.25 mm in from the half-hole centre. The 8x8 RX-flasher's 0.7 to 0.8 mm was forced by its BOOT pad position; here every pin follows its own pad |
| BOOT (TP5) | the pad centre from the receiver board, never the 8x8 flasher's coordinates (0.54 mm off on Lite) |
| Moved pins | when two receptacles leave less than `min_web`, both move apart inside their pads, keeping `rx_tip_r` (0.35 mm) of pad round the tip; a castellation pin moves only along the edge |

Parts cover both sides of these boards up to the edges, so nothing rigid can
press the board: the foam pad does, and the board rests on the pins and on
what the support windows leave. Check the first cut with a board before a
batch.

Wiring rule for the station (not part of the plates): power the receiver (5V)
before driving RX or BOOT, or put series resistors in RX and BOOT, so an
unpowered receiver is never fed through its I/O pins.

## Sources

| What | From |
|---|---|
| Test pads TP* | the production pack's positions CSV for the revision (`production/boards/<SKU>/<rev>/<SKU>-<rev>_positions.csv` in the Incutec workspace) |
| Outline, mount holes, contact-face pads, bottom-side parts, USB position | the pcbnew API on the source board at the commit in the pack's `SOURCE.json`, read with `git show` into a temporary file; the board repository is never written |
| Cross-check | TP positions from the CSV against the board; the run stops above 0.05 mm |

## Run

```sh
# KPY: KiCad's bundled Python (repository AGENTS.md). From the repository root
# inside the workspace; from a worktree elsewhere add --workspace <workspace root>.
$KPY Station-Plates/generate.py                       # all four stations
$KPY Station-Plates/generate.py ESC-30 --set swd_hole=1.4 --set kerf=0.08
```

Every parameter (`kerf`, pocket clearance, rod and bushing size, pin hole
sizes per group, pins per power pad, FC ledge and notch width) is in the `P`
block at the top of `generate.py` and can be set with `--set`. The run exits
non-zero when two holes leave less than `min_web` (0.4 mm) of acrylic.

## Not decided here

| Item | Who |
|---|---|
| Pogo pin and receptacle part numbers; set the hole sizes from their datasheet before cutting | buyer of the pins |
| Stop spacer height (board rests on it; sets the pin stroke) and nest thickness (spacer + 1 mm) | from the chosen pin's working stroke |
| Toggle clamp model and its screw pattern on the press plate | drill to the clamp bought |
| ESC-20 press plate: TP pairs 2.2 mm apart leave 0.5 mm acrylic between two 1.7 mm holes | acceptable in cast acrylic; use a smaller receptacle if it cracks |
