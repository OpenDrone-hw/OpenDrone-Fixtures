# OpenDrone-Fixtures

Bench boards for the OpenESC line: a QC fixture and an SWD flashing station for each of OpenESC-20x20 and OpenESC-30x30, four independent KiCad projects.

Validate: `kicad-cli sch erc <dir>/<stem>.kicad_sch && kicad-cli pcb drc --schematic-parity --refill-zones <dir>/<stem>.kicad_pcb`

## Boundaries

- Never text-edit `.kicad_sch`, `.kicad_pcb` or `.kicad_dru`: use KiCad, or kicad-skip / the pcbnew API with KiCad closed.
- Contact geometry is read from the sibling ESC boards: never modify the ESC design from here.
- KiCad libraries stay project-local in each directory; there is no `KiCad-Library` submodule.

## Pointers

- Projects (`<dir>/<stem>`): `OpenESC-20x20-QC/20x20-ESC-QC`, `OpenESC-20x20-Flashing/20x20-ESC-Flashing`, `OpenESC-30x30-QC/30x30-ESC-QC`, `OpenESC-30x30-Flashing/30x30-ESC-Flashing`
- The QC schematics are empty stubs: ERC is empty and parity lists every footprint.
- Each directory's README is that fixture's brief.
