"""
StructVis project format (.structvis) - a zip of JSON + npz, mirroring the
Flovis approach. Self-contained: it embeds the imported wing so the project
opens without the original .flovis file.

Members:
  manifest.json      - format/version + language + material/load summary
  structure.json     - WingboxParams + LoadCase
  source.json        - imported AircraftModel + global aero data
  result.npz         - (optional) mesh + displacement + Von Mises fields
"""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .flovis_import import AeroData, ImportedProject
from .geometry import AircraftModel, WingGeometry
from .loads import LoadCase
from .wingbox import WingboxParams
from .fea.result import FeaResult, BucklingResult

FORMAT_VERSION = 1


def save_project(path: str | Path, project: ImportedProject,
                 params: WingboxParams, case: LoadCase,
                 result: FeaResult | None = None,
                 point_masses=None,
                 buckling: BucklingResult | None = None) -> Path:
    path = Path(path)
    if path.suffix != ".structvis":
        path = path.with_suffix(".structvis")

    manifest = {
        "format": "structvis", "version": FORMAT_VERSION,
        "material": params.material,
        "load_factor": case.load_factor, "velocity": case.velocity,
        "has_result": result is not None,
        "source_name": project.model.name,
    }
    source = {
        "model": project.model.to_dict(),
        "aero": project.aero.to_dict() if project.aero else None,
        "source_path": project.source_path,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.writestr("structure.json", json.dumps(
            {"params": params.to_dict(), "load_case": asdict(case),
             "point_masses": [pm.to_dict() for pm in (point_masses or [])]},
            indent=2))
        z.writestr("source.json", json.dumps(source, ensure_ascii=False, indent=2))
        if result is not None:
            buf = io.BytesIO()
            elset = (result.elset_of_elem.astype("U16")
                     if result.elset_of_elem is not None
                     else np.array([], dtype="U16"))
            node_mat = (result.node_material.astype("U16")
                        if result.node_material is not None
                        else np.array([], dtype="U16"))
            node_yield = (result.node_yield if result.node_yield is not None
                          else np.array([], float))
            np.savez_compressed(
                buf, nodes=result.nodes, elems=result.elems,
                disp=result.disp, von_mises=result.von_mises,
                elset_of_elem=elset, node_yield=node_yield,
                node_material=node_mat,
                scalars=np.array([result.yield_strength, result.half_span,
                                  result.root_y], float))
            z.writestr("result.npz", buf.getvalue())
        if buckling is not None:
            bbuf = io.BytesIO()
            belset = (buckling.elset_of_elem.astype("U16")
                      if buckling.elset_of_elem is not None
                      else np.array([], dtype="U16"))
            np.savez_compressed(
                bbuf, factors=np.asarray(buckling.factors, float),
                nodes=buckling.nodes, elems=buckling.elems,
                mode1=(buckling.mode1 if buckling.mode1 is not None
                       else np.array([])),
                elset_of_elem=belset,
                scalars=np.array([buckling.half_span], float))
            z.writestr("buckling.npz", bbuf.getvalue())
    return path


def load_project(path: str | Path) -> dict:
    """
    Return {project, params, load_case, result}. `result` is None when the
    file was saved without a solved result.
    """
    path = Path(path)
    with zipfile.ZipFile(path, "r") as z:
        names = set(z.namelist())
        structure = json.loads(z.read("structure.json"))
        source = json.loads(z.read("source.json"))

        model = AircraftModel.from_dict(source["model"])
        aero = AeroData.from_dict(source["aero"]) if source.get("aero") else None
        wing = model.wing
        if wing is None:
            raise ValueError("Saved project has no wing surface.")
        project = ImportedProject(
            model=model, geometry=WingGeometry(wing), aero=aero,
            source_path=source.get("source_path", ""))

        params = WingboxParams.from_dict(structure["params"])
        case = LoadCase(**{k: structure["load_case"][k]
                           for k in structure["load_case"]
                           if k in LoadCase.__dataclass_fields__})
        from .loads import PointMass
        point_masses = [PointMass.from_dict(d)
                        for d in structure.get("point_masses", [])]

        result = None
        if "result.npz" in names:
            with io.BytesIO(z.read("result.npz")) as buf:
                data = np.load(buf, allow_pickle=False)
                sc = data["scalars"]
                elset = data["elset_of_elem"]
                ny = data["node_yield"] if "node_yield" in data else np.array([])
                nm = data["node_material"] if "node_material" in data else np.array([])
                result = FeaResult(
                    nodes=data["nodes"], elems=data["elems"],
                    disp=data["disp"], von_mises=data["von_mises"],
                    yield_strength=float(sc[0]), half_span=float(sc[1]),
                    root_y=float(sc[2]),
                    elset_of_elem=(elset.astype(object) if elset.size else None),
                    node_yield=(ny if ny.size else None),
                    node_material=(nm.astype(object) if nm.size else None),
                    meta={"loaded_from": str(path)})
        buckling = None
        if "buckling.npz" in names:
            with io.BytesIO(z.read("buckling.npz")) as bbuf:
                bdata = np.load(bbuf, allow_pickle=False)
                belset = bdata["elset_of_elem"]
                mode1 = bdata["mode1"]
                buckling = BucklingResult(
                    factors=bdata["factors"], nodes=bdata["nodes"],
                    elems=bdata["elems"],
                    mode1=(mode1 if mode1.size else None),
                    half_span=float(bdata["scalars"][0]),
                    elset_of_elem=(belset.astype(object) if belset.size
                                   else None),
                    meta={"loaded_from": str(path)})
    return {"project": project, "params": params, "load_case": case,
            "point_masses": point_masses, "result": result,
            "buckling": buckling}
