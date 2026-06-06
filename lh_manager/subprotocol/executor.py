"""Subprotocol expansion and submission helpers for lh_manager.

Provides two entry points called from broker_worker._on_run_subprotocol:

  expand_subprotocol     — synchronous, pure expansion of a subprotocol
                           definition into a flat list of ExpandedStep dicts
                           and a mapping of output names to prefixed leaf
                           step_ids.  DB lookups for nested subprotocol /
                           method_group steps are synchronous; wrap with
                           asyncio.to_thread.

  _submit_expanded_steps — submit all expanded steps to autocontrol in a
                           single synchronous call; wrap with asyncio.to_thread.

Context resolution:
  $ref input.<name>  — resolved from caller-supplied input_params
  $alloc <handle>    — resolved to a UUID minted at subprotocol start
  Nested dicts/lists — resolved recursively

Step-id prefixing:
  When recursing into a nested subprotocol step whose parent step_id is
  "solvent_phase", all child steps are emitted with step_ids prefixed as
  "solvent_phase.<child_id>".  This eliminates collisions when the same child
  subprotocol is used multiple times (e.g. three QCMD measurement phases).

output_leaf_map:
  expand_subprotocol returns a second value mapping each output name declared
  at this subprotocol level to the fully-prefixed leaf method step_id that
  will produce the retrieval_uri.  The caller uses this to look up results
  in _step_retrieval_uris after execution.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MAX_DEPTH = 5


def expand_subprotocol(
    defn: Dict[str, Any],
    context: Dict[str, Any],
    depth: int = 0,
    step_prefix: str = "",
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Expand a sequential subprotocol into a flat list of ExpandedStep dicts.

    Returns ``(expanded_steps, output_leaf_map)`` where:

    ``expanded_steps`` — list of dicts, each with:
      - ``type``        : "method" | "method_group"
      - ``step_id``     : str  (prefixed to disambiguate repeated child use)

      For ``type == "method"``:
        - ``method_name`` : str
        - ``params``      : dict  (all $ref/$alloc resolved)

      For ``type == "method_group"``:
        - ``method_type`` : str
        - ``group``       : list of {"method_name": ..., ...}

    ``output_leaf_map`` — maps each declared output name at this subprotocol
      level to the fully-prefixed leaf method step_id that will produce its
      retrieval_uri.  Used by the caller to look up results after execution.

    Nested sequential subprotocols are recursively flattened into the parent
    list.  Nested parallel subprotocols become a single method_group entry
    keyed by the parent step's id.
    """
    if depth > _MAX_DEPTH:
        raise RuntimeError(
            f"Nested subprotocol depth limit ({_MAX_DEPTH}) exceeded"
        )

    steps: list = json.loads(defn["steps"])
    outputs_defn: dict = json.loads(defn.get("outputs") or "{}")

    # Seed static/default inputs.  is_static inputs are caller-opaque: their
    # static_value is always applied unconditionally, even if the caller already
    # set the key, because callers must never override a static input.
    # default_value inputs fill gaps only (caller-supplied values win).
    inputs_defn_top: dict = json.loads(defn.get("inputs") or "{}")
    if inputs_defn_top:
        context = dict(context)  # don't mutate caller's dict
        for inp_name, inp_def in inputs_defn_top.items():
            key = f"input.{inp_name}"
            if isinstance(inp_def, dict) and inp_def.get("is_static") and "static_value" in inp_def:
                context[key] = inp_def["static_value"]  # always wins
            elif key not in context:
                if isinstance(inp_def, dict) and "default_value" in inp_def:
                    context[key] = inp_def["default_value"]

    result: List[Dict[str, Any]] = []
    # Maps output_name (at this level) → fully-prefixed leaf step_id.
    # Populated bottom-up as nested subprotocols are expanded.
    output_leaf_map: Dict[str, str] = {}

    # outputs_defn is the GUI-editable source of truth.  Build a reverse lookup
    # so we know which parent output name(s) each step is declared to produce.
    # output_alias on individual steps is a legacy field that is NOT updated by
    # the GUI; outputs_defn takes priority whenever it claims a step.
    step_to_parent_outputs: Dict[str, List[str]] = {}
    for out_name, out_def in outputs_defn.items():
        sid = out_def.get("step_id") if isinstance(out_def, dict) else None
        if sid:
            step_to_parent_outputs.setdefault(sid, []).append(out_name)

    for step in steps:
        step_type: str = step.get("type", "method")
        step_id: str = step["id"]
        prefixed_id: str = f"{step_prefix}{step_id}"
        resolved = _resolve_step_params(step, context)

        if step_type == "method":
            result.append({
                "type": "method",
                "step_id": prefixed_id,
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
                "step_id": prefixed_id,
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
            # Seed static_value / default_value for child inputs.
            # is_static inputs are caller-opaque: always applied unconditionally so
            # a parent that accidentally passes an empty or wrong value cannot win.
            # default_value inputs fill gaps only (parent-supplied values win).
            child_inputs = json.loads(child_defn.get("inputs") or "{}")
            for inp_name, inp_def in child_inputs.items():
                key = f"input.{inp_name}"
                if isinstance(inp_def, dict) and inp_def.get("is_static") and "static_value" in inp_def:
                    child_context[key] = inp_def["static_value"]  # always wins
                elif key not in child_context:
                    if isinstance(inp_def, dict) and "default_value" in inp_def:
                        child_context[key] = inp_def["default_value"]

            child_execution: str = child_defn.get("execution") or "sequential"
            if child_execution == "parallel":
                child_steps: list = json.loads(child_defn["steps"])
                group = _build_method_group(child_steps, child_context)
                result.append({
                    "type": "method_group",
                    "step_id": prefixed_id,
                    "method_type": child_defn.get("method_type") or "prepare",
                    "group": group,
                })
            else:
                # Sequential child: flatten into parent's step list, then map
                # its outputs to parent-level names.
                #
                # Priority: outputs_defn at THIS level (GUI-editable) wins over
                # output_alias on the step (legacy, not updated by GUI).
                child_expanded, child_leaf_map = expand_subprotocol(
                    child_defn, child_context, depth + 1, f"{prefixed_id}."
                )
                result.extend(child_expanded)

                parent_out_names: List[str] = step_to_parent_outputs.get(step_id, [])
                if parent_out_names:
                    # outputs_defn claims this step.  Map child outputs to the
                    # declared parent name(s).
                    child_leaves = list(child_leaf_map.items())  # [(name, leaf), ...]
                    if len(parent_out_names) == 1 and len(child_leaves) == 1:
                        # Common case: one declared output, one child output — 1:1.
                        output_leaf_map[parent_out_names[0]] = child_leaves[0][1]
                    elif len(parent_out_names) == len(child_leaves):
                        # Same count but ambiguous which child output is which.
                        # Fall back to output_alias for the renaming, then remap
                        # to the parent names by matching via alias result.
                        alias: dict = step.get("output_alias", {})
                        aliased = {alias.get(cn, cn): leaf for cn, leaf in child_leaves}
                        for p_name in parent_out_names:
                            if p_name in aliased:
                                output_leaf_map[p_name] = aliased[p_name]
                            else:
                                logger.warning(
                                    "Step %r: outputs_defn declares %r but output_alias "
                                    "has no matching key; output will be missing.",
                                    step_id, p_name,
                                )
                    else:
                        logger.warning(
                            "Step %r: outputs_defn declares %d output(s) but child "
                            "subprotocol %r produced %d — skipping output mapping.",
                            step_id, len(parent_out_names), child_name, len(child_leaves),
                        )
                else:
                    # No outputs_defn claim for this step: use output_alias (legacy).
                    alias = step.get("output_alias", {})
                    for child_out_name, leaf_id in child_leaf_map.items():
                        parent_out_name = alias.get(child_out_name, child_out_name)
                        output_leaf_map[parent_out_name] = leaf_id

        else:
            logger.warning(
                "Unknown step type %r in step %r — skipping.", step_type, step_id
            )

    # Fill in outputs from direct method/method_group steps at this level that
    # are not yet in output_leaf_map.  Subprotocol steps are handled above
    # during expansion and must not use this fallback (their step_id is not a
    # leaf method step — it's an intermediate grouping id).
    subprotocol_step_ids = {s["id"] for s in steps if s.get("type") == "subprotocol"}
    for out_name, out_def in outputs_defn.items():
        if out_name not in output_leaf_map:
            declared_sid = out_def.get("step_id") if isinstance(out_def, dict) else None
            if declared_sid and declared_sid not in subprotocol_step_ids:
                output_leaf_map[out_name] = f"{step_prefix}{declared_sid}"

    return result, output_leaf_map


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
# Broker-path sentinel submission
# (called via asyncio.to_thread from broker_worker._on_run_subprotocol)
# ---------------------------------------------------------------------------

def _submit_expanded_steps_via_sentinel(
    sample_id: str,
    subprotocol_name: str,
    sentinel_id: str,
    expanded_steps: List[Dict[str, Any]],
    input_params: Optional[Dict[str, Any]] = None,
) -> None:
    """Create a __subprotocol__ sentinel and submit all expanded steps under it.

    One sentinel RawMethod appears in the sample's method list (matching the GUI
    path), so the GUI shows a single subprotocol row instead of individual steps.

    Each task's AutocontrolItem.method_id is the individual step_id — NOT the
    sentinel's id — so broker-path completion events and output URI collection
    remain accurate for per-step tracking.
    """
    from ..liquid_handler.state import samples
    from ..liquid_handler.samplelist import MethodList
    from ..liquid_handler.methods import RawMethod, MethodType, method_manager
    from ..autocontrol.autocontrol import (
        _build_raw_method_task,
        _build_method_group_task,
        _register_and_submit_tasks,
    )

    _, sample = samples.getSampleById(sample_id)
    if sample is None:
        raise RuntimeError(f"Sample {sample_id!r} not found in lh_manager")

    if "methods" not in sample.stages:
        sample.stages["methods"] = MethodList()

    sentinel = RawMethod(
        id=sentinel_id,
        method_name="__subprotocol__",
        display_name=subprotocol_name,
        method_type=MethodType.NONE,
        method_data={
            "method_name": "__subprotocol__",
            "display_name": subprotocol_name,
            "subprotocol_name": subprotocol_name,
            **(input_params or {}),
        },
    )
    method_index = len(sample.stages["methods"].methods)
    sample.stages["methods"].methods.append(sentinel)

    tasks_with_step_ids: List[Tuple[str, Any]] = []
    for step in expanded_steps:
        if step["type"] == "method":
            schema = method_manager._remote_schemas.get(step["method_name"]) or {}
            try:
                mtype = MethodType(schema.get("method_type", "none"))
            except ValueError:
                mtype = MethodType.NONE
            task = _build_raw_method_task(sample, step["method_name"], mtype, step["params"])
        elif step["type"] == "method_group":
            try:
                mtype = MethodType(step.get("method_type", "none"))
            except ValueError:
                mtype = MethodType.NONE
            task = _build_method_group_task(sample, step["group"], mtype)
        else:
            task = None
        if task is None:
            raise RuntimeError(f"Failed to build task for step {step.get('step_id')!r}")
        tasks_with_step_ids.append((step["step_id"], task))  # individual step_ids — broker path

    _register_and_submit_tasks(sample, "methods", method_index, sentinel, tasks_with_step_ids)


def _submit_parallel_subprotocol_via_sentinel(
    sample_id: str,
    subprotocol_name: str,
    sentinel_id: str,
    step_id: str,
    group: List[Dict[str, Any]],
    method_type_str: str = "prepare",
    input_params: Optional[Dict[str, Any]] = None,
) -> None:
    """Create a __subprotocol__ sentinel and submit a single parallel method-group task.

    Mirrors _submit_expanded_steps_via_sentinel for top-level parallel subprotocols.
    step_id is used as the AutocontrolItem.method_id for completion tracking.
    """
    from ..liquid_handler.state import samples
    from ..liquid_handler.samplelist import MethodList
    from ..liquid_handler.methods import RawMethod, MethodType
    from ..autocontrol.autocontrol import _build_method_group_task, _register_and_submit_tasks

    _, sample = samples.getSampleById(sample_id)
    if sample is None:
        raise RuntimeError(f"Sample {sample_id!r} not found in lh_manager")

    if "methods" not in sample.stages:
        sample.stages["methods"] = MethodList()

    sentinel = RawMethod(
        id=sentinel_id,
        method_name="__subprotocol__",
        display_name=subprotocol_name,
        method_type=MethodType.NONE,
        method_data={
            "method_name": "__subprotocol__",
            "display_name": subprotocol_name,
            "subprotocol_name": subprotocol_name,
            **(input_params or {}),
        },
    )
    method_index = len(sample.stages["methods"].methods)
    sample.stages["methods"].methods.append(sentinel)

    try:
        mtype = MethodType(method_type_str)
    except ValueError:
        mtype = MethodType.NONE
    task = _build_method_group_task(sample, group, mtype)
    if task is None:
        raise RuntimeError(f"Failed to build parallel task for subprotocol {subprotocol_name!r}")
    _register_and_submit_tasks(sample, "methods", method_index, sentinel, [(step_id, task)])


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
