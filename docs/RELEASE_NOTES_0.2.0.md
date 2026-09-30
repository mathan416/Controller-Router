# Controller Router 0.2.0

Controller Router is the shared console input, pairing, app selection, and Matrix display service used by VirtualGlove and R.O.B. Vision. The product installers include it; the wheel alone installs the reusable Python library.

## What's new

- Assign physical and maker controllers to stable players, with a per-system choice between **Controller Router** and **My existing setup**. New installations enable NES; upgrades retain their saved choices.
- Pair a console once through secure Setup and provision separate access for each installed app. The console list shows connection and app readiness in a compact layout.
- Select the right app when a registered game starts, without opening a browser. One input lease prevents the other app from sending controls. The shared service owns the 13×8 Matrix display.
- Resolve merged controllers by identity at game launch. Legacy RetroArch builds use a temporary numeric assignment; supported newer builds use native reservations. Runtime routing does not rewrite saved `retroarch.cfg` files.
- Support RetroPie, Batocera, and Recalbox integrations through the product installers. The Help page gives player-facing pairing, assignment, testing, and recovery steps.

For install and upgrade steps, use the matching VirtualGlove or R.O.B. Vision release. The [User Guide](USER_GUIDE.md), [Pairing Guide](PAIRING_GUIDE.md), and [Technical Reference](TECHNICAL_REFERENCE.md) describe this version's controls and interfaces.
