# Controller Router 0.4.1

Stable release: 24 November 2026. The preceding release was 0.4.0.

## One App Lab base image on the UNO Q

- The UNO Q portal and the VirtualGlove and R.O.B. Vision runtimes now run on the python-apps-base image that App Lab runs Controller Router on, read from App Lab's own container, instead of a separately pinned tag. Only release tags from 0.12.0 up are accepted; otherwise the runtime falls back to 0.13.2.
- The runtime compose overrides a stale base image left in an App Lab cache, and the Router entry moves onto the current image when it changes.
- After the runtimes start, and at the end of a full install, older python-apps-base tags that no container uses are removed, with exited containers left by the products' own App Lab projects. Removal is never forced, newer tags are kept, and a tag whose image any container still uses is skipped. On one UNO Q this freed about 900 MB of its system disk.

## Disk space and safer installs

- Every portal page warns when the UNO Q's system disk has less than 1 GB free, and Help gains a **Free up space on the UNO Q** section. While the disk is low, a single installed product is not opened automatically, so the warning is seen.
- A second Router installation started while one is running stops straight away with a message. Overlapping runs could interleave the swap of the portal folder and its `.previous` copy.
- Retired files (a top-level `app.yaml` and the old `host_bridge` brick) and local `*.before-…` copies in a product's bundled copy of the portal are no longer copied into the installed Router, no longer force a full install, and are removed from the installed Router if present.
- Flashing the shared Matrix sketch is retried up to three times after "Upload port detection failed", and App Lab's sketch build cache is kept across upgrades.

## Version and upgrade boundaries

The reusable library is **0.4.1**; the independent UNO Q runtime installer version is **0.4.1**, so product bundles carrying runtime 0.4.0 or earlier keep the newer portal. The Matrix firmware remains **0.2.0**. Console-side code is unchanged apart from its version, so a console refreshes its pairing software on its next product install.

## Validation

The source passed the Router suite on Python 3.10, 3.12 and 3.13, the console tests on Python 3.7, the standalone package build, and bundled-code synchronization, plus the R.O.B. Vision and VirtualGlove suites. New tests cover the base-image lookup and its limits, image retirement (including a tag shared with an image in use), the disk warning, the install lock, and keeping retired files out of the installed Router; image-side code is checked to use only the standard library and App Lab's Bridge.

The portal was installed on two UNO Q boards and a RetroPie console, first from development builds and then through VirtualGlove 0.8.3 and R.O.B. Vision 0.4.3 pre-releases using their published install commands. Each board ended on a single base image with both products ready, the installed portal matching this source exactly, and its tokens, keys and pairing files unchanged; the console's pairing was retained. Moving to a new App Lab image was simulated with additional local tags of the same image rather than a real App Lab update. Halting on console shutdown was not retested in this release.
