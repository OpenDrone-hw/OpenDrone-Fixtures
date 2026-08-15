# OpenDrone-Fixtures

Test fixtures, flashing jigs and other bench boards for the OpenDrone hardware
line. None of these is a product: each one exists to build, flash or test a
board that is. Product repos link here instead of carrying them.

One KiCad 10 project per directory, named `<Board>-<Purpose>`, with its own
project-local libraries. Each directory's README says what the fixture
contacts, how it was generated and which script regenerates it.

| Directory | For | What |
|---|---|---|
| `OpenESC-20x20-QC/` | [OpenESC-20x20](https://github.com/OpenDrone-hw/OpenESC-20x20) | Press-contact QC fixture, a negative of the ESC contact face |
| `OpenESC-20x20-Flashing/` | [OpenESC-20x20](https://github.com/OpenDrone-hw/OpenESC-20x20) | ST-LINK pogo-pin SWD flashing station, fabbed as `20x20-flashing-V0.1` |
| `OpenESC-30x30-QC/` | [OpenESC-30x30](https://github.com/OpenDrone-hw/OpenESC-30x30) | Same fixture rebuilt on the 30x30 pad geometry, unrouted |
| `OpenESC-30x30-Flashing/` | [OpenESC-30x30](https://github.com/OpenDrone-hw/OpenESC-30x30) | The 20x20 station retargeted to the 30x30 test points, unrouted |

The READMEs reference the ESC designs as `../../<ESC repo>/hardware/`, so
they assume this repo is checked out next to the ESC repos.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Hardware licensed under [CERN-OHL-S-2.0](https://ohwr.org/cern_ohl_s_v2.txt),
see [LICENSE](LICENSE).
