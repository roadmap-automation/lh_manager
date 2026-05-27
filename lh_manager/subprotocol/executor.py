"""Subprotocol expansion and submission helpers for lh_manager.

Provides two entry points called from broker_worker._on_run_subprotocol:

  expand_subprotocol     — synchronous, pure expansion of a subprotocol
                           definition into a flat list of ExpandedStep dicts.
                           DB lookups for nested subprotocol / method_group
                           steps are synchronous; wrap with asyncio.to_thread.

  _submit_expanded_steps — submit all expanded steps to autocontrol in a
                           single synchronous call; wrap with asyncio.to_thread.

Context resolution:
  $ref input.<name>  — resolved from caller-supplied input_params
  $alloc <handle>    — resolved to a UUID minted at subprotocol start
  Nested dicts/lists — resolved recursively

NOTE: output_alias (step N's result feeds step N+1) is not implemented.
If that feature is ever needed, a separate mechanism will be required because
all steps are submitted before any complete.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_DEPTH = 5


def expand_subprotocol(
    defn: Dict[str, Any],
    context: Dict[str, Any],
    depth: int = 0,
) -> List[Dict[str, Any]]:
    """Expand a sequential subprotocol into a flat list of ExpandedStep dicts.

    Each entry has:
      - ``type``        : "method" | "method_group"
      - ``step_id``     : str

    For ``type == "method"``:
      - ``method_name`` : str
      - ``params``      : dict  (all $ref/$alloc resolved)

    For ``type == "method_group"``:
      - ``method_type`` : str
      - ``group``       : list of {"method_name": ..., ...}

    Nested sequential subprotocols are recursively flattened into the parent
    list.  Nested parallel subprotocols become a single method_group entry
    keyed by the parent step's id.
    """
    if depth > _MAX_DEPTH:
        raise RuntimeError(
            f"Nested subprotocol depth limit ({_MAX_DEPTH}) exceeded"
        )

    steps: list = json.loads(defn["steps"])
    result: List[Dict[str, Any]] = []

    for step in steps:
        step_type: str = step.get("type", "method")
        step_id: str = step["id"]
        resolved = _resolve_step_params(step, context)

        if step_type == "method":
            result.append({
                "type": "method",
                "step_id": step_id,
                "method_name": step["method_name"],
                "params": resolved,
            })

        elif step_type == "method_group":
            from ..method_group.db import get_method_group_by_name

            mg_name: str = step["method_group_name"]
            mg_defn = get_method_group_by_name(mg_name)
            if mg_defn is None:
                raise ValueError(
                    f"MethodGroup {mg_name!r} (step {step_id!r}) not found in DB"
                )
            mg_steps: list = json.loads(mg_defn["steps"])
            # Build method-group context.  Three layers, each only filling gaps:
            #   1. parent context (subprotocol-level inputs — highest priority)
            #   2. call-site params exposed as input.<key> (direct name match)
            #   3. reverse-mapped: if the group step says
            #        "device_param": {"$ref": "input.exposed_name"}
            #      and the subprotocol provided "device_param": value, propagate
            #      that value to "input.exposed_name" so the $ref resolves even
            #      when the GUI uses device param names rather than exposed names.
            mg_context = dict(context)
            for k, v in resolved.items():
                mg_context.setdefault(f"input.{k}", v)
            for mg_step in mg_steps:
                for param_name, param_val in mg_step.get("parameters", {}).items():
                    if (isinstance(param_val, dict) and "$ref" in param_val
                            and param_name in resolved):
                        mg_context.setdefault(param_val["$ref"], resolved[param_name])
            group = _build_method_group(mg_steps, mg_context)
            result.append({
                "type": "method_group",
                "step_id": step_id,
                "method_type": mg_defn.get("method_type") or "prepare",
                "group": group,
            })

        elif step_type == "subprotocol":
            from .db import get_subprotocol_by_name

            child_name: str = step["subprotocol_name"]
            child_defn = get_subprotocol_by_name(child_name)
            if child_defn is None:
                raise ValueError(
                    f"Nested subprotocol {child_name!r} (step {step_id!r}) not found in DB"
                )

            child_context: Dict[str, Any] = dict(context)
            child_context.update({f"input.{k}": v for k, v in resolved.items()})
            for alloc_name in json.loads(child_defn.get("allocations") or "[]"):
                child_context[f"alloc.{alloc_name}"] = str(uuid.uuid4())

            child_execution: str = child_defn.get("execution") or "sequential"
            if child_execution == "parallel":
                child_steps: list = json.loads(child_defn["steps"])
                group = _build_method_group(child_steps, child_context)
                result.append({
                    "type": "method_group",
                    "step_id": step_id,
                    "method_type": child_defn.get("method_type") or "prepare",
                    "group": group,
                })
            else:
                # Sequential child: flatten into parent's step list.
                child_expanded = expand_subprotocol(child_defn, child_context, depth + 1)
                result.extend(child_expanded)

        else:
            logger.warning(
                "Unknown step type %r in step %r — skipping.", step_type, step_id
            )

    return result


def _submit_expanded_steps(
    sample_id: str, expanded_steps: List[Dict[str, Any]]
) -> None:
    """Submit all expanded steps to autocontrol in a single synchronous call."""
    for step in expanded_steps:
        if step["type"] == "method":
            _submit_method_sync(
                sample_id, step["step_id"], step["method_name"], step["params"]
            )
        elif step["type"] == "method_group":
            _submit_method_group_sync(
                sample_id, step["step_id"], step["method_type"], step["group"]
            )


# ---------------------------------------------------------------------------
# Module-level resolution helpers (pure functions, no state)
# ---------------------------------------------------------------------------

def _resolve_step_params(step: dict, context: Dict[str, Any]) -> Dict[str, Any]:
    step_id = step.get("id") or step.get("method_name", "<unknown>")
    return {k: _resolve_value(v, context, step_id) for k, v in step.get("parameters", {}).items()}


def _resolve_value(v: Any, context: Dict[str, Any], step_id: str) -> Any:
    if isinstance(v, dict):
        if "$ref" in v:
            ref_key = v["$ref"]
            if ref_key not in context:
                raise ValueError(f"Step {step_id!r}: ref {ref_key!r} not in context")
            return context[ref_key]
        if "$alloc" in v:
            alloc_key = f"alloc.{v['$alloc']}"
            if alloc_key not in context:
                raise ValueError(
                    f"Step {step_id!r}: alloc {v['$alloc']!r} not declared in allocations"
                )
            return context[alloc_key]
        return {k: _resolve_value(vv, context, step_id) for k, vv in v.items()}
    if isinstance(v, list):
        return [_resolve_value(item, context, step_id) for item in v]
    return v


def _build_method_group(steps: list, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"method_name": step["method_name"], **_resolve_step_params(step, context)}
        for step in steps
    ]


# ---------------------------------------------------------------------------
# Sync helpers — called from _submit_expanded_steps (via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _create_sample_sync(name: str, channel: int) -> str:
    from ..liquid_handler.samplelist import Sample
    from ..liquid_handler.state import samples

    sample_id = str(uuid.uuid4())
    new_sample = Sample(id=sample_id, name=name, description="", channel=channel)
    samples.addSample(new_sample)
    return sample_id


def _submit_method_sync(
    sample_id: str, step_id: str, method_name: str, params: Dict[str, Any]
) -> None:
    """Create a RawMethod for a single device method and submit it via autocontrol."""
    from ..liquid_handler.state import samples
    from ..liquid_handler.samplelist import MethodList
    from ..liquid_handler.methods import RawMethod, MethodType
    from ..liquid_handler.methods import method_manager
    from ..autocontrol.autocontrol import _submit_raw_method

    _, sample = samples.getSampleById(sample_id)
    if sample is None:
        raise RuntimeError(f"Sample {sample_id!r} not found in lh_manager")

    if "methods" not in sample.stages:
        sample.stages["methods"] = MethodList()

    # Infer method_type from registered schema so autocontrol picks the right TaskType.
    schema = method_manager._remote_schemas.get(method_name, {})
    type_str = schema.get("method_type", "none")
    try:
        method_type = MethodType(type_str)
    except ValueError:
        method_type = MethodType.NONE

    raw_method = RawMethod(
        id=step_id,
        method_name=method_name,
        display_name=method_name,
        method_type=method_type,
        method_data={"method_name": method_name, **params},
    )
    method_index = len(sample.stages["methods"].methods)
    sample.stages["methods"].methods.append(raw_method)
    _submit_raw_method(sample, "methods", method_index, raw_method)


def _submit_method_group_sync(
    sample_id: str, step_id: str, method_type_str: str, group: List[Dict[str, Any]]
) -> None:
    """Create a method-group RawMethod (parallel dispatch) and submit via autocontrol."""
    from ..liquid_handler.state import samples
    from ..liquid_handler.samplelist import MethodList
    from ..liquid_handler.methods import RawMethod, MethodType
    from ..autocontrol.autocontrol import _submit_raw_method_group

    _, sample = samples.getSampleById(sample_id)
    if sample is None:
        raise RuntimeError(f"Sample {sample_id!r} not found in lh_manager")

    if "methods" not in sample.stages:
        sample.stages["methods"] = MethodList()

    try:
        method_type = MethodType(method_type_str)
    except ValueError:
        method_type = MethodType.PREPARE

    raw_method = RawMethod(
        id=step_id,
        method_name="__method_group__",
        display_name=f"method_group:{step_id}",
        method_type=method_type,
        method_data={
            "method_name": "__method_group__",
            "method_group": group,
        },
    )
    method_index = len(sample.stages["methods"].methods)
    sample.stages["methods"].methods.append(raw_method)
    _submit_raw_method_group(sample, "methods", method_index, raw_method)
