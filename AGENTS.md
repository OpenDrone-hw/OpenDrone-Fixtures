# OpenDrone-Fixtures

Bench boards for the OpenESC line: a press-contact QC fixture and an ST-LINK
pogo-pin SWD flashing station for each of OpenESC-20x20 and OpenESC-30x30.
Four independent KiCad 10 projects, one per directory, plus one non-KiCad filming jig (`OpenMotor-Seesaw/`, its README is its brief). Each directory's
README is that fixture's brief: contact geometry, parts, layout state. Read it
before touching the fixture, and keep it correct when you do.

## Repo

| Directory | Project | Serves |
|---|---|---|
| `OpenESC-20x20-QC/` | `20x20-ESC-QC.kicad_pro` (a second project file, `20x20-ESC-MotorTest.kicad_pro`, sits beside it) | [OpenESC-20x20](https://github.com/OpenDrone-hw/OpenESC-20x20) |
| `OpenESC-20x20-Flashing/` | `20x20-ESC-Flashing.kicad_pro` | OpenESC-20x20 |
| `OpenESC-30x30-QC/` | `30x30-ESC-QC.kicad_pro` | [OpenESC-30x30](https://github.com/OpenDrone-hw/OpenESC-30x30) |
| `OpenESC-30x30-Flashing/` | `30x30-ESC-Flashing.kicad_pro` | OpenESC-30x30 |
| `OpenMotor-Seesaw/` | none (no KiCad); `generate.py` writes laser-cut SVG/DXF, previews and `viewer/model.json` | [OpenMotor](https://github.com/OpenDrone-hw/OpenMotor) filming and demo jig |

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
footprint; the two Flashing projects have a real schematic. On macOS
`kicad-cli` is at `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`;
`KPY` is KiCad's bundled Python,
`/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`.
Never text-edit `.kicad_sch`, `.kicad_pcb` or `.kicad_dru`; use KiCad, or
kicad-skip and the pcbnew API, with KiCad closed.

## Rules

Identical in every OpenDrone board repo. Do not edit here; edit the template.

- **Never text-edit** `.kicad_sch`, `.kicad_pcb` or `.kicad_dru`. Use KiCad, or
  kicad-skip / the pcbnew API for scripted changes. `.kicad_pro` is JSON and may
  be edited directly for metadata.
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
  Commands are in Environment above.

## By task

Fixture paths are in the Repo table and Environment above. `KPY` is KiCad's
bundled Python named there.

- Check a fixture: run the ERC and DRC commands in Environment for the directory you changed, before every pull request.
- Render a fixture for its README: `$KPY <hardware-tooling>/hardware/kicad/render_board.py <dir>/<stem>.kicad_pcb --outdir <dir>/images`, KiCad closed.
- Verify contact positions: read the ESC pad coordinates from its `.kicad_pcb` with `kicad-cli` or the pcbnew API under `KPY`, compare with the fixture footprint in `<dir>/*.pretty/`; never modify the ESC design from here.
- Add a part: import it into the directory's local library with `$KPY <hardware-tooling>/hardware/kicad/import_part.py --repo <dir>` (read `--help` first), KiCad closed.
