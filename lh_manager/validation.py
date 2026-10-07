"""Availability validation for subprotocols and method groups.

Walks the subprotocol/method-group step tree and checks that every referenced
device method is present in the currently-registered method set.  A subprotocol
is unavailable if any leaf method it (recursively) depends on is missing.
"""

from __future__ import annotations

from typing import Any

_MAX_DEPTH = 5


def _mg_available(mg_steps: list, available: set[str]) -> bool:
    for step in mg_steps:
        if step.get("method_name", "") not in available:
            return False
    return True


def _sp_available(
    sp_steps: list,
    available: set[str],
    sp_by_name: dict[str, list],
    mg_by_name: dict[str, list],
    visited: set[str],
    depth: int,
) -> bool:
    if depth > _MAX_DEPTH:
        return True
    for step in sp_steps:
        step_type = step.get("type", "method")
        if step_type == "method":
            if step.get("method_name", "") not in available:
                return False
        elif step_type == "method_group":
            mg_name = step.get("method_group_name", "")
            if mg_name in mg_by_name:
                if not _mg_available(mg_by_name[mg_name], available):
                    return False
        elif step_type == "subprotocol":
            sp_name = step.get("subprotocol_name", "")
            if sp_name and sp_name not in visited and sp_name in sp_by_name:
                if not _sp_available(
                    sp_by_name[sp_name], available, sp_by_name, mg_by_name,
                    visited | {sp_name}, depth + 1,
                ):
                    return False
    return True


def compute_availability(
    subprotocols: list[dict[str, Any]],
    method_groups: list[dict[str, Any]],
    available_methods: set[str],
) -> tuple[dict[str, bool], dict[str, bool]]:
    """Return (sp_availability, mg_availability) keyed by name.

    Each item must have 'name' and 'steps' as a parsed list (not a JSON string).
    """
    sp_by_name: dict[str, list] = {sp["name"]: sp["steps"] for sp in subprotocols}
    mg_by_name: dict[str, list] = {mg["name"]: mg["steps"] for mg in method_groups}

    mg_availability = {
        mg["name"]: _mg_available(mg["steps"], available_methods)
        for mg in method_groups
    }

    sp_availability = {
        sp["name"]: _sp_available(
            sp["steps"], available_methods, sp_by_name, mg_by_name,
            visited={sp["name"]}, depth=0,
        )
        for sp in subprotocols
    }

    return sp_availability, mg_availability
