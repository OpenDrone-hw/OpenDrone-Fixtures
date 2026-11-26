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

The [Board rules](#board-rules) at the end of this file apply, a CI-checked copy of the [hardware-template](https://github.com/OpenDrone-hw/hardware-template/blob/main/AGENTS.md#board-rules) section. Only what differs for this board is listed here.

- Libraries are project-local per fixture directory; there is no `KiCad-Library` submodule, so the shared library rules do not apply.

## By task

Fixture paths are in the Repo table and Environment above; `KPY` is KiCad's
bundled Python named in Board rules, Commands.

- Check a fixture: run the ERC and DRC commands in Environment for the directory you changed, before every pull request.
- Render a fixture for its README: `$KPY <hardware-tooling>/hardware/kicad/render_board.py <dir>/<stem>.kicad_pcb --outdir <dir>/images`, KiCad closed.
- Verify contact positions: read the ESC pad coordinates from its `.kicad_pcb` with `kicad-cli` or the pcbnew API under `KPY`, compare with the fixture footprint in `<dir>/*.pretty/`; never modify the ESC design from here.
- Add a part: import it into the directory's local library with `$KPY <hardware-tooling>/hardware/kicad/import_part.py --repo <dir>` (read `--help` first), KiCad closed.

## Board rules

Shared by every OpenDrone KiCad board repository, byte for byte, and checked
in CI against [hardware-template](https://github.com/OpenDrone-hw/hardware-template/blob/main/AGENTS.md#board-rules).
Edit them there, never in a board.

### Files

Every board has this layout; its Repo table lists only what differs.

| | |
|---|---|
| Designed in | KiCad 10 |
| Status | The `status-*` topic on the repository, never written in a file |
| Local library | `hardware/lib.kicad_sym`, `hardware/lib.pretty/`, `hardware/lib.3dshapes/`, nickname `lib` |
| Shared library | `hardware/KiCad-Library/`, submodule of [OpenDrone-hw/KiCad-Library](https://github.com/OpenDrone-hw/KiCad-Library), nickname `OpenDrone`; 3D models and exact component datasheets resolve through the project text variable `OPENDRONE_LIB` |
| Fab config | `hardware/fabrication-toolkit-options.json` |
| Board setup | 6 layers, 0.09 mm clearance and track, via 0.35 on 0.20 drill |
| License | CERN-OHL-S-2.0 |

A repository holds design files only. Sourcing (suppliers, prices, quotes, RFQs, contacts) is handled by Incutec and never lives in OpenDrone repositories.

### Parts and datasheets

- **Per-repository part index:** the root schematic and its listed sub-sheets
  are authoritative for what this board fits. Export the netlist with the
  command below when a script-readable board index is needed; do not maintain
  a second hand-written BOM.
- **Proven shared parts:**
  `hardware/KiCad-Library/PARTS-USED.md` is the catalogue index. Its `Boards`
  column identifies every repository using each LCSC part; filter that column
  for the repository name to get its proven shared-part view.
- **Exact datasheets:**
  `hardware/KiCad-Library/datasheet/manifest.json` maps shared symbols to the
  committed PDFs and their SHA-256 hashes. The PDFs live in
  `hardware/KiCad-Library/datasheet/`, and symbol links resolve there through
  `OPENDRONE_LIB`.
- **Local-only parts:** inspect `hardware/lib.kicad_sym`,
  `hardware/lib.pretty/`, and `hardware/lib.3dshapes/`, then verify supplier
  fields in the board schematic. Do not duplicate a shared part or datasheet.

### Commands

`<name>` is the KiCad project named in the board's Repo table.

```sh
# schematic and board checks
kicad-cli sch erc hardware/<name>.kicad_sch
kicad-cli pcb drc --schematic-parity --refill-zones hardware/<name>.kicad_pcb

# netlist, for scripted analysis
kicad-cli sch export netlist --format kicadsexpr -o /tmp/<name>.net hardware/<name>.kicad_sch
```

On macOS `kicad-cli` is at
`/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`, and `pcbnew` imports
only under KiCad's bundled Python, `KPY`:
`/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`.
Reusable scripts for renders, STEP export and packaging art come from Incutec
hardware tooling. The OpenDrone release standard is
[RELEASES.md](https://github.com/OpenDrone-hw/.github/blob/main/RELEASES.md).
Board-specific scripts, where a board has any, live in `hardware/tools/`.

### Rules

- **Never text-edit** `.kicad_sch`, `.kicad_pcb` or `.kicad_dru`. Use KiCad, or
  kicad-skip / the pcbnew API for scripted changes. `.kicad_pro` is JSON and may
  be edited directly for metadata.
  kicad-skip cannot round-trip KiCad 10 schematics: use a full S-expression
  parser, `kicad-cli sch upgrade --force`, then an ERC and netlist diff.
- **Metadata yes, connections no.** An agent may write BOM and documentation
  fields (MPN, Manufacturer, LCSC, Cost, Datasheet, text variables). An agent
  may not change nets, wiring, routing, placement, footprint assignment, or any
  value that changes the circuit.
- **Close KiCad before any write to a KiCad file.** KiCad caches library tables
  at process start and overwrites files on save.
- **Reuse before you draw.** Check the `OpenDrone` library and its
  `PARTS-USED.md` first. If the part is there we have already sourced,
  footprinted and shipped it, and its symbol links to the exact committed
  datasheet: place it from `OpenDrone`. Draw a new part into `lib` only when
  the catalogue has nothing that fits, imported with
  `easyeda2kicad` from its LCSC number. Pulling a newer catalogue is a
  deliberate, reviewed commit: `git submodule update --remote
  hardware/KiCad-Library`, then DRC.
- **One person holds a board layout at a time.** KiCad files do not merge. Say
  on Discord that you are taking it. See [CONTRIBUTING.md](CONTRIBUTING.md).
- **Run ERC and DRC before every pull request.** Existing approved findings
  may remain; a new type or increased count must be reviewed before merge.
  The commands are under Commands.

### By task

- Check the design: run the ERC and DRC commands in Commands before every pull request.
- Add a part: place it from the `OpenDrone` library if `hardware/KiCad-Library/PARTS-USED.md` lists it; otherwise import it into `lib` with `$KPY <hardware-tooling>/hardware/kicad/import_part.py` (read `--help` first), KiCad closed.
- Render the board for the README: `$KPY <hardware-tooling>/hardware/kicad/render_board.py hardware/<name>.kicad_pcb --outdir images`, KiCad closed.
- Analyse the netlist: export it with the netlist command in Commands, then read it with a script; never hand-write a second BOM.
- Update the shared library: `git submodule update --remote hardware/KiCad-Library`, run DRC, commit as its own reviewed change.
