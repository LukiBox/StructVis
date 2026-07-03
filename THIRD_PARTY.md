# Third-party components

StructVis itself is MIT-licensed. It relies on the following third-party
components, each under its own license.

## CalculiX (ccx) — the FEA solver

StructVis calls the **CalculiX** solver (`ccx`) as an external process to run
the finite-element analysis. CalculiX is:

- Copyright © Guido Dhondt and contributors
- Licensed under the **GNU General Public License v2 (GPLv2)**
- Project page: https://www.calculix.de/ / https://www.dhondt.de/

CalculiX is **not bundled** in this source tree. StructVis invokes whatever
`ccx` binary the user supplies (via `structvis/resources/bin/`, the
`STRUCTVIS_CCX` environment variable, or the system `PATH`). Because StructVis
communicates with `ccx` only through separate-process invocation and plain text
files (`.inp` in, `.frd` out), the two are independent programs.

If you distribute a build that includes a `ccx` binary, you must comply with the
GPLv2 for that binary (ship its license text and provide access to its source).

## Python libraries

| Library    | License            |
|------------|--------------------|
| PySide6/Qt | LGPLv3 / GPL       |
| PyVista    | MIT                |
| pyvistaqt  | MIT                |
| pyqtgraph  | MIT                |
| NumPy      | BSD-3-Clause       |
| SciPy      | BSD-3-Clause       |
| ollama     | MIT                |

## Ported from Flovis

The theming, i18n scaffolding, NACA airfoil generator, and the local-Ollama
client pattern are adapted from the author's own **Flovis** project (MIT).
