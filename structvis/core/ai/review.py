"""
AI structural review via a local Ollama model (ported from Flovis).

Feeds the FEA summary (mass, max Von Mises + location, min FoS, tip
deflection/twist, per-component stress) to the model and returns a written
engineering review: overall verdict, critical locations, weight-saving advice.
Fully offline; streams like the Flovis client.
"""
from __future__ import annotations

import json

from ..i18n import get_language

DEFAULT_MODEL = "qwen3:30b-a3b"
DEFAULT_HOST = "http://localhost:11434"

_BASE_SYSTEM = (
    "You are an experienced aerospace stress engineer reviewing a preliminary "
    "wing structural analysis for a model-aircraft builder. Explain results in "
    "plain, concrete language, technically correct, without heavy math. Use "
    "ONLY the numbers given - never invent values. Write in paragraphs, no "
    "markdown headings.")

PRESETS = {
    "full": (
        "Full review",
        "Structure your answer:\n"
        "1. Overall verdict: is the structure safe (min FoS vs target) and is "
        "it over- or under-built.\n"
        "2. Critical locations: where the peak stress is and why.\n"
        "3. Stiffness: comment on tip deflection and tip twist.\n"
        "4. Weight-saving recommendations: which components are lightly loaded "
        "and could be thinned, which need reinforcing. Be specific and "
        "actionable. 4 short paragraphs."),
    "short": (
        "Short verdict",
        "Write 3-4 sentences: is it safe, is it too heavy or too weak, and the "
        "single most important change to make."),
    "weight": (
        "Weight optimization",
        "Focus only on saving mass while keeping the target Factor of Safety. "
        "Rank the components from most over-built to most critical and give a "
        "concrete resizing plan."),
}


def is_available(host: str = DEFAULT_HOST) -> bool:
    try:
        import ollama
        ollama.Client(host=host).list()
        return True
    except Exception:  # noqa: BLE001
        return False


def list_models(host: str = DEFAULT_HOST) -> list[str]:
    try:
        import ollama
        data = ollama.Client(host=host).list()
        return [m.get("model") or m.get("name") for m in data.get("models", [])]
    except Exception:  # noqa: BLE001
        return []


def model_available(model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST) -> bool:
    models = list_models(host)
    return any(m == model or m.split(":")[0] == model.split(":")[0]
              for m in models)


def missing_model_hint(model: str = DEFAULT_MODEL) -> str:
    return (f"Model '{model}' was not found in Ollama.\nPull it with:\n\n"
            f"    ollama pull {model}\n\nand make sure 'ollama serve' is running.")


def _language_directive() -> str:
    if get_language() == "pl":
        return "\nRespond in Polish (odpowiadaj po polsku)."
    return "\nRespond in English."


def _system_prompt(preset: str) -> str:
    _, structure = PRESETS.get(preset, PRESETS["full"])
    return _BASE_SYSTEM + "\n" + structure + _language_directive()


def build_context(fea_result, params, load_case, design=None,
                  mass_breakdown=None, buckling=None) -> dict:
    """Assemble the review payload from a FeaResult + design inputs."""
    from .. import materials
    mat = materials.get(params.material)
    supp = materials.get(params.effective_support_material)
    payload = {
        "skin_material": mat.name,
        "skin_yield_MPa": round(mat.yield_strength / 1e6, 1),
        "support_material": supp.name,
        "support_yield_MPa": round(supp.yield_strength / 1e6, 1),
        "load_case": {
            "load_factor_g": load_case.load_factor,
            "velocity_ms": load_case.velocity,
            "target_FoS": load_case.target_fos,
        },
        "wingbox": {
            "front_spar_pct": round(params.front_spar * 100, 1),
            "rear_spar_pct": round(params.rear_spar * 100, 1),
            "n_ribs": params.n_ribs,
            "skin_mm": round(params.skin_t * 1000, 2),
            "spar_web_mm": round(params.web_t * 1000, 2),
            "spar_cap_mm": round(params.cap_t * 1000, 2),
            "rib_mm": round(params.rib_t * 1000, 2),
            "n_stringers": params.n_stringers,
        },
        "results": fea_result.summary(),
        "component_peak_stress_MPa": {
            k: round(v / 1e6, 1)
            for k, v in fea_result.component_max_vm().items()},
        "component_min_FoS": {
            k: round(v, 2)
            for k, v in fea_result.component_min_fos().items()},
        "margin_of_safety": round(
            fea_result.min_fos / max(load_case.target_fos, 1e-6) - 1.0, 3),
    }
    if buckling is not None:
        payload["buckling"] = {
            "critical_factor": round(buckling.critical_factor, 2),
            "buckles_below_applied_load": bool(buckling.critical_factor < 1.0),
            "note": "thin skins often buckle before they yield",
        }
    if design is not None:
        payload["design_point"] = {
            "CL": round(design.CL_design, 3),
            "total_lift_N": round(design.lift_total, 1),
        }
    if mass_breakdown is not None:
        payload["mass_kg"] = {k: round(v, 4) for k, v in mass_breakdown.items()}
        payload["total_mass_kg"] = round(sum(mass_breakdown.values()), 4)
    return payload


def _build_prompt(payload: dict) -> str:
    return ("Review the following wing structural analysis and write an "
            "assessment for the builder.\n\nDATA (JSON):\n"
            + json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _msg_get(msg, key):
    """Read a field from an ollama message (dict or pydantic object)."""
    if hasattr(msg, "get"):
        try:
            return msg.get(key)
        except Exception:  # noqa: BLE001
            pass
    return getattr(msg, key, None)


def interpret_stream(payload: dict, model: str = DEFAULT_MODEL,
                     host: str = DEFAULT_HOST, preset: str = "full",
                     think: bool = False):
    """
    Streaming generator yielding ('thinking'|'content', text).

    think=False (default) tells reasoning models (e.g. qwen3) to answer
    directly instead of streaming a long chain of thought first - otherwise
    the answer pane can sit empty for minutes while the model reasons.
    """
    import ollama
    client = ollama.Client(host=host)
    kwargs = dict(
        model=model,
        messages=[{"role": "system", "content": _system_prompt(preset)},
                  {"role": "user", "content": _build_prompt(payload)}],
        options={"temperature": 0.4}, stream=True)
    try:
        stream = client.chat(think=think, **kwargs)
    except TypeError:
        # older ollama client without the `think` parameter
        stream = client.chat(**kwargs)
    for chunk in stream:
        msg = chunk["message"]
        th = _msg_get(msg, "thinking")
        if th:
            yield ("thinking", th)
        ct = _msg_get(msg, "content")
        if ct:
            yield ("content", ct)


def interpret(payload: dict, model: str = DEFAULT_MODEL,
              host: str = DEFAULT_HOST, preset: str = "full",
              think: bool = False) -> str:
    import ollama
    client = ollama.Client(host=host)
    kwargs = dict(
        model=model,
        messages=[{"role": "system", "content": _system_prompt(preset)},
                  {"role": "user", "content": _build_prompt(payload)}],
        options={"temperature": 0.4})
    try:
        resp = client.chat(think=think, **kwargs)
    except TypeError:
        resp = client.chat(**kwargs)
    return _msg_get(resp["message"], "content").strip()
