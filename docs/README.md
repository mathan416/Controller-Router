# Controller Router guides

Use Canadian English in project-authored documentation, Help, website copy, and release notes (for example, **behaviour**, **colour**, **centre**, and **recognise**). Preserve exact commands, code identifiers, legal text, and third-party names.

- [User Guide](USER_GUIDE.md): choose players and systems, test a pad, and recover a game.
- [Pairing Guide](PAIRING_GUIDE.md): connect a console once, check app readiness, and manage access.
- [Integration Guide](INTEGRATION_GUIDE.md): build a unique controller integration, choose an input boundary, and use assignment APIs.
- [Deployment Guide](DEPLOYMENT_GUIDE.md): package the console library, optional UNO Q runtime, upgrades, and recovery.
- [Technical Reference](TECHNICAL_REFERENCE.md): architecture, API examples, leases, Matrix protocol, storage, and extension boundaries.

R.O.B. Vision and VirtualGlove are source-cited integration examples. The guides describe Controller Router itself; product installation and gameplay instructions belong to those projects.

Printable editions are in [output/pdf](../output/pdf/). Rebuild with `python3 scripts/build_guides.py` using Python with ReportLab installed. These guides describe current source; verify the shared version included in your project's package.

- [Release review — 28 September 2026](RELEASE_REVIEW_2026-09-28.md): reviewed boundaries, fixes, automated results, and remaining live release gates.

## Documentation for players and developers

Write each guide for one reader and one purpose. Player Help answers “what do I do next?”; technical references define interfaces and failure behaviour; engineering reports preserve dated evidence.

### Player guides

- Start with the task and the result the player can expect. Use plain words, short paragraphs, and the labels shown in the app.
- Give numbered steps for a sequence. Name the page or device first, then the action. Explain what appears next when it helps the player continue.
- Explain unfamiliar terms when needed. Keep device indexes, schemas, firmware paths, protocol timing, and implementation history in technical references.
- Give troubleshooting as symptom, first check, expected result, and recovery. Do not require a reinstall before simpler checks.
- Keep controls available in text as well as screenshots or colour. Include menu and exit controls, paused-input states, and how to recover safely.
- Use concrete limits where they affect play. Keep fiction in the story, and keep experimental results in dated reports.

### Technical guides

- Provide a reading map and define component ownership before describing the data flow.
- State API inputs, outputs, validation, defaults, bounds, error behaviour, authentication, and cleanup. Show runnable minimal examples and identify placeholders.
- Separate persistent configuration from generated state, installation changes from runtime behaviour, and local APIs from network transports.
- Document version detection and fallback behaviour without treating a build as a live hardware result.
- Link source modules and evidence. Historical results keep their date; a current reference describes the current implementation.
- Check instructions against the app, links against their targets, and PDFs against their rendered pages before publishing.

### Editorial references

- [Google: audience](https://developers.google.com/tech-writing/one/audience) and [procedures](https://developers.google.com/style/procedures).
- [Microsoft: step-by-step instructions](https://learn.microsoft.com/en-us/style-guide/procedures-instructions/writing-step-by-step-instructions).
- [Diátaxis: tutorials, how-to, reference, and explanation](https://diataxis.fr/start-here/).
- [Xbox Accessibility Guideline 106: player-facing information](https://learn.microsoft.com/en-us/xbox/accessibility/xbox-accessibility-guidelines/106).
- [Google: API reference](https://developers.google.com/style/api-reference-comments).
