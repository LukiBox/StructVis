# StructVis

Parametric wingbox generator and FEA stress viewer for wings designed in
[Flovis](https://github.com/LukiBox/Flovis). Import a `.flovis` project, define
the internal structure with sliders, and solve for stress, deflection and
buckling with the open-source CalculiX solver no meshing, no boundary-condition
setup.

## Features

- **Import and Loads** - reads a `.flovis` project (geometry + solved polar) and
  reconstructs the spanwise lift with Schrenk's approximation, scaled to
  `L = n·m·g`. Inertial relief subtracts the wing's own weight at load factor,
  point masses (motors, fuel) can be placed along the span, and an aileron
  deflection factor spikes outer-panel torsion. Live shear and bending-moment
  plots.
- **Structure** - sliders for spar positions, rib count, skin/web/cap/rib
  gauges and stringers, with independent skin and support materials (metals,
  composites, balsa, plywood, PLA, foam and more, including orthotropic woven
  and unidirectional carbon). Live 3D preview and live mass readout.
- **Analysis** - one-click linear static solve, eigenvalue buckling, and two auto-sizing optimizers: uniform scaling and per-gauge
  Fully Stressed Design that thins unloaded members and reinforces hot spots
  until the minimum Factor of Safety hits the target.
- **Results** - Von Mises / Factor of Safety / displacement / buckling-mode
  heatmaps in 3D, deflection exaggeration up to x100, interactive clip plane to
  look inside the box, Margin of Safety readout, component visibility toggles.
- **Report** - one-click PDF with a red/yellow/green rating, per-component
  stress table, charts and a plain-language assessment generated without AI.
- **Export to SimVis** - `File -> Export to SimVis` writes a
  `simvis_mass.json` (mass, CG, full inertia tensor and the structural limit
  load factor) straight from the measured wing structure plus the aircraft's
  point masses. Feed it to SimVis alongside the `.flovis` project and the
  flight simulator folds the wing at exactly the g StructVis rated.
- **AI Review** (optional) - a local Ollama model writes a second-opinion
  structural review; appended to the PDF when used. Fully offline.
- Light and dark themes (dark by default)

## Requirements

- Python 3.10+ (developed on 3.12), Windows
- [CalculiX](https://www.calculix.de/) `ccx` for the solve step
- [Ollama](https://ollama.com) only if you want the AI review

## Install

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### Solver

StructVis builds meshes, estimates mass and maps loads without `ccx`, but the
stress/buckling solve needs it. Any one of these works:

1. drop `ccx.exe` (and its DLLs) into `structvis/resources/bin/`,
2. set the `STRUCTVIS_CCX` environment variable to its full path, or
3. install CalculiX or [PrePoMax](https://prepomax.fs.um.si/) and add it to
   `PATH` - StructVis also finds `ccx` inside a `Solver` subfolder of any PATH
   entry, so adding the PrePoMax root is enough.

## Run

```
.venv\Scripts\python -m structvis.app
```

## Test

```
.venv\Scripts\python -m pytest -q
```

The physics-validation tests (cantilever box beam vs Euler–Bernoulli beam
theory) run only when `ccx` is available and are skipped otherwise.

## Build a standalone executable

```
.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller --noconfirm --clean structvis.spec
```

Produces `dist/StructVis.exe`. A `ccx` placed in `structvis/resources/bin/`
before building is bundled automatically.

## License

MIT — see [LICENSE](LICENSE). The CalculiX solver is a separate GPLv2 program
invoked as an external process; see [THIRD_PARTY.md](THIRD_PARTY.md).

---

Made by **LukiBox** - https://github.com/LukiBox - companion to
[Flovis](https://github.com/LukiBox/Flovis).
