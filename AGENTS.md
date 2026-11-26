# OpenDrone-Fixtures

Bench boards for the OpenESC line: a press-contact QC fixture and an ST-LINK
pogo-pin SWD flashing station for each of OpenESC-20x20 and OpenESC-30x30.
Four independent KiCad 10 projects, one per directory. Each directory's
README is that fixture's brief: contact geometry, parts, layout state. Read it
before touching the fixture, and keep it correct when you do.

`OpenMotor-Seesaw/` and `Station-Plates/` are the non-KiCad directories: a filming jig for OpenMotor, and the laser-cut test-station plates generated from the released ESC, FC and RX boards; each README is its brief.

## Repo

| Directory | Project | Serves |
|---|---|---|
| `OpenESC-20x20-QC/` | `20x20-ESC-QC.kicad_pro` (a second project file, `20x20-ESC-MotorTest.kicad_pro`, sits beside it) | [OpenESC-20x20](https://github.com/OpenDrone-hw/OpenESC-20x20) |
| `OpenESC-20x20-Flashing/` | `20x20-ESC-Flashing.kicad_pro` | OpenESC-20x20 |
| `OpenESC-30x30-QC/` | `30x30-ESC-QC.kicad_pro` | [OpenESC-30x30](https://github.com/OpenDrone-hw/OpenESC-30x30) |
| `OpenESC-30x30-Flashing/` | `30x30-ESC-Flashing.kicad_pro` | OpenESC-30x30 |
| `OpenMotor-Seesaw/` | none (no KiCad); `generate.py` writes laser-cut SVG/DXF, previews, `viewer/model.json`, `motor_mount_params.scad` | [OpenMotor](https://github.com/OpenDrone-hw/OpenMotor) filming and demo jig |
| `Station-Plates/` | none (no KiCad); `generate.py` (run with `KPY`) writes per-station plate SVG/DXF, `<station>_contacts.csv`, `manifest.json` | factory test stations for OpenESC-20x20, OpenESC-30x30, OpenFC-Lite-Mini, OpenFC-Lite, OpenRX-Lite, -Lite-UFL, -Mono, -Gemini |

Libraries are project-local in each directory (`*.kicad_sym`, `*.pretty/`,
`*.3dshapes/`, declared in its `sym-lib-table` and `fp-lib-table`); the 20x20
QC fixture also uses KiCad's stock `TestPoint` footprints. There is no
`KiCad-Library` submodule. Fab config is `fabrication-toolkit-options.json`
per directory. License CERN-OHL-S-2.0.

Contact geometry is extracted read-only from the ESC board a fixture serves
(`../OpenESC-20x20/hardware/4in1-mini.kicad_pcb` and
`../OpenESC-30x30/hardware/4in1.kicad_pcb` from this repository's root, sibling checkouts). Keep each
fixture traceable to the DUT revision it was extracted from, and verify pin
and connector mappings against both designs before a change.

## Environment

```sh
# per fixture, from the repository root; <dir> and <stem> from the Repo table
kicad-cli sch erc <dir>/<stem>.kicad_sch
kicad-cli pcb drc --schematic-parity --refill-zones <dir>/<stem>.kicad_pcb
```

The two QC schematics are empty stubs (the fixture is laid out directly on
the board), so for them ERC is empty and schematic parity lists every
footprint; the two Flashing projects have a real schematic.

## Rules

The shared [Board rules](https://github.com/OpenDrone-hw/hardware-template/blob/main/AGENTS.md#board-rules) apply. Only what differs for this board is listed here.

- Libraries are project-local per fixture directory; there is no `KiCad-Library` submodule, so the shared library rules do not apply.

## By task

- Check a fixture: run the ERC and DRC commands in Environment for the directory you changed, before every pull request.
- Verify contact positions: read the ESC pad coordinates from its `.kicad_pcb` with `kicad-cli` or the pcbnew API under `KPY`, compare with the fixture footprint in `<dir>/*.pretty/`; never modify the ESC design from here.
- Add a part: import it into the directory's local library with `$KPY <hardware-tooling>/hardware/kicad/import_part.py --repo <dir>` (read `--help` first), KiCad closed.
