# Controller Router 0.3.2

Stable release: 17 November 2026. The preceding release was 0.3.1.

## Fixes

- Reinstalling VirtualGlove or R.O.B. Vision on the UNO Q no longer leaves a lasting "No such file or directory" error on the Apps page. The portal writes each app's input lease four times a second; if an installer is replacing that app's folder at that moment, the write is skipped and the next check rewrites the lease. Lease files are written through a uniquely named private temporary file that is always removed.
- An error from the portal's background lease check clears on the next successful check. Other Apps page messages, such as two live games, are unchanged.

## Version and upgrade boundaries

The reusable library is **0.3.2**; the independent UNO Q runtime installer version is **0.3.5**. The Matrix firmware remains **0.2.0**. Product bundles that carry runtime 0.3.4 or earlier cannot replace the updated portal. Console behaviour is unchanged from 0.3.1.

## Validation

The source passed the Router suite, including new tests for a folder replaced during a lease write and for clearing a recovered heartbeat error, bundled-code synchronization, and the R.O.B. Vision and VirtualGlove suites. On the UNO Q that showed the original error, the updated portal was installed with R.O.B. Vision: both apps and the Matrix were ready, the Apps page showed no error, and both lease files were rewritten every check with private permissions and no leftover temporary files.

Use matching product installers. A library wheel alone does not install console services or the UNO Q runtime.
