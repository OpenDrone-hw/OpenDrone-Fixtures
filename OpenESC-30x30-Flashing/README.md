# 30x30-ESC-Flashing: AM32 SWD flashing station

SWD flashing jig for the **OpenESC-30x30** (`../../OpenESC-30x30/hardware/4in1`). Retargeted copy
of `OpenESC-20x20-Flashing`: same 100 x 100 mm 4-layer layout, same
pogo pins, headers, banana jacks and M3 pattern. Only the ten pogo pins moved,
to the coordinates the 30x30 actually uses.

## Contacts

Ten 1.2 mm SMD pogo pins land on the ESC's B.Cu face, which is where the SWD
test points are:

| Net | Lands on |
|---|---|
| `/SWD1_CLK` … `/SWD4_CLK` | PA14 test point of each channel |
| `/SWD1_DIO` … `/SWD4_DIO` | PA13 test point of each channel |
| `/VBAT`, `GND` | the two battery pads, so the target is powered while flashing |

Channel numbering comes from the ESC schematic sheets (`/ESC1/` … `/ESC4/`), not
from position, so SWD1 really is channel 1.

Four 4-pin headers break out CLK, DIO and GND per channel for the ST-LINK probes.

## Layout state

**The board is unrouted**: the copper pours from the 20x20 are still in place
and no longer match the new pin positions, so redo them.

## Flashing

Two-stage, as on the 20x20: SWD once per MCU to clear readout protection and
write the AM32 bootloader, then firmware and settings over the DShot signal pin.
Host side is `../../OpenESC-20x20/hardware/flash_openesc20.sh` (OpenOCD,
AT32F421 FAP unlock, verify, `--loop` for batches).

License: hardware CERN-OHL-S-2.0, same as the ESC.
