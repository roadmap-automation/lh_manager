"""Unit tests for lh_manager.subprotocol.executor.

No RabbitMQ, autocontrol, or lh_manager process required.
expand_subprotocol is a pure synchronous function; DB calls for nested
subprotocol / method_group steps are mocked via unittest.mock.patch.
"""

import json
import uuid
from unittest.mock import patch

import pytest

from lh_manager.subprotocol.executor import (
    _MAX_DEPTH,
    _build_method_group,
    _resolve_value,
    expand_subprotocol,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_defn(
    name="TestProto",
    execution="sequential",
    steps=None,
    outputs=None,
    allocations=None,
    method_type=None,
):
    d = {
        "name": name,
        "execution": execution,
        "steps": json.dumps(steps or []),
        "outputs": json.dumps(outputs or {}),
        "allocations": json.dumps(allocations or []),
    }
    if method_type is not None:
        d["method_type"] = method_type
    return d


# ---------------------------------------------------------------------------
# _resolve_value
# ---------------------------------------------------------------------------

class TestResolveValue:
    def test_literal_string(self):
        assert _resolve_value("hello", {}, "s") == "hello"

    def test_literal_number(self):
        assert _resolve_value(42.0, {}, "s") == 42.0

    def test_literal_none(self):
        assert _resolve_value(None, {}, "s") is None

    def test_ref_resolved(self):
        ctx = {"input.volume": 100.0}
        assert _resolve_value({"$ref": "input.volume"}, ctx, "s") == 100.0

    def test_ref_missing_raises(self):
        with pytest.raises(ValueError, match="ref"):
            _resolve_value({"$ref": "input.missing"}, {}, "s")

    def test_alloc_resolved(self):
        ctx = {"alloc.well_id": "some-uuid"}
        assert _resolve_value({"$alloc": "well_id"}, ctx, "s") == "some-uuid"

    def test_alloc_missing_raises(self):
        with pytest.raises(ValueError, match="alloc"):
            _resolve_value({"$alloc": "missing"}, {}, "s")

    def test_nested_dict_resolved(self):
        ctx = {"input.x": 1.0}
        result = _resolve_value({"Target": {"$ref": "input.x"}}, ctx, "s")
        assert result == {"Target": 1.0}

    def test_deeply_nested_alloc(self):
        ctx = {"alloc.well_id": "uuid-abc"}
        result = _resolve_value({"Target": {"id": {"$alloc": "well_id"}}}, ctx, "s")
        assert result == {"Target": {"id": "uuid-abc"}}

    def test_list_resolved(self):
        ctx = {"input.a": 10}
        result = _resolve_value([{"$ref": "input.a"}, 20], ctx, "s")
        assert result == [10, 20]

    def test_plain_dict_without_ref_resolved_recursively(self):
        ctx = {"input.v": 5.0}
        result = _resolve_value({"k": {"$ref": "input.v"}, "m": 3}, ctx, "s")
        assert result == {"k": 5.0, "m": 3}


# ---------------------------------------------------------------------------
# _build_method_group
# ---------------------------------------------------------------------------

class TestBuildMethodGroup:
    def test_empty_steps(self):
        assert _build_method_group([], {}) == []

    def test_single_step_no_params(self):
        steps = [{"id": "s1", "method_name": "Rinse", "parameters": {}}]
        assert _build_method_group(steps, {}) == [{"method_name": "Rinse"}]

    def test_single_step_literal_params(self):
        steps = [{"id": "s1", "method_name": "Inject", "parameters": {"volume": 10.0}}]
        assert _build_method_group(steps, {}) == [{"method_name": "Inject", "volume": 10.0}]

    def test_multiple_steps_with_refs(self):
        ctx = {"input.vol": 5.0, "input.flow": 1.0}
        steps = [
            {"id": "s1", "method_name": "Load", "parameters": {"volume": {"$ref": "input.vol"}}},
            {"id": "s2", "method_name": "Inject", "parameters": {"flow_rate": {"$ref": "input.flow"}}},
        ]
        result = _build_method_group(steps, ctx)
        assert result == [
            {"method_name": "Load", "volume": 5.0},
            {"method_name": "Inject", "flow_rate": 1.0},
        ]


# ---------------------------------------------------------------------------
# expand_subprotocol — basic sequential expansion
# ---------------------------------------------------------------------------

class TestExpandSubprotocol:
    def test_empty_steps_returns_empty(self):
        steps, leaf_map = expand_subprotocol(_make_defn(), {})
        assert steps == []
        assert leaf_map == {}

    def test_single_method_step(self):
        defn_steps = [{"id": "s1", "type": "method", "method_name": "Rinse", "parameters": {}}]
        steps, leaf_map = expand_subprotocol(_make_defn(steps=defn_steps), {})
        assert steps == [{"type": "method", "step_id": "s1", "method_name": "Rinse", "params": {}}]

    def test_single_method_step_with_output(self):
        defn_steps = [{"id": "s1", "type": "method", "method_name": "Measure", "parameters": {}}]
        steps, leaf_map = expand_subprotocol(
            _make_defn(steps=defn_steps, outputs={"my_data": {"step_id": "s1", "type": "QCMDData"}}), {}
        )
        assert leaf_map == {"my_data": "s1"}

    def test_resolves_ref_in_params(self):
        ctx = {"input.volume": 50.0}
        defn_steps = [{"id": "s1", "type": "method", "method_name": "Inject",
                  "parameters": {"volume": {"$ref": "input.volume"}}}]
        steps, _ = expand_subprotocol(_make_defn(steps=defn_steps), ctx)
        assert steps[0]["params"] == {"volume": 50.0}

    def test_resolves_alloc_in_params(self):
        ctx = {"alloc.well_id": "test-uuid"}
        defn_steps = [{"id": "s1", "type": "method", "method_name": "Formulate",
                  "parameters": {"well": {"$alloc": "well_id"}}}]
        steps, _ = expand_subprotocol(_make_defn(steps=defn_steps), ctx)
        assert steps[0]["params"] == {"well": "test-uuid"}

    def test_multiple_steps_preserved_in_order(self):
        defn_steps = [
            {"id": "s1", "type": "method", "method_name": "A", "parameters": {}},
            {"id": "s2", "type": "method", "method_name": "B", "parameters": {}},
        ]
        steps, _ = expand_subprotocol(_make_defn(steps=defn_steps), {})
        assert [r["step_id"] for r in steps] == ["s1", "s2"]
        assert [r["method_name"] for r in steps] == ["A", "B"]

    def test_unknown_step_type_is_skipped(self):
        defn_steps = [{"id": "s1", "type": "unknown_type", "method_name": "Foo", "parameters": {}}]
        steps, _ = expand_subprotocol(_make_defn(steps=defn_steps), {})
        assert steps == []

    def test_method_group_step_expanded(self):
        mg_defn = {
            "steps": json.dumps([
                {"id": "m1", "method_name": "Load", "parameters": {"volume": 10.0}},
                {"id": "m2", "method_name": "Inject", "parameters": {}},
            ]),
            "method_type": "prepare",
        }
        defn_steps = [{"id": "g1", "type": "method_group", "method_group_name": "LoadAndInject",
                  "parameters": {}}]
        defn = _make_defn(steps=defn_steps)

        with patch("lh_manager.method_group.db.get_method_group_by_name", return_value=mg_defn):
            steps, _ = expand_subprotocol(defn, {})

        assert len(steps) == 1
        assert steps[0]["type"] == "method_group"
        assert steps[0]["step_id"] == "g1"
        assert steps[0]["method_type"] == "prepare"
        assert steps[0]["group"] == [
            {"method_name": "Load", "volume": 10.0},
            {"method_name": "Inject"},
        ]

    def test_method_group_not_found_raises(self):
        defn_steps = [{"id": "g1", "type": "method_group", "method_group_name": "Missing",
                  "parameters": {}}]
        with patch("lh_manager.method_group.db.get_method_group_by_name", return_value=None):
            with pytest.raises(ValueError, match="not found"):
                expand_subprotocol(_make_defn(steps=defn_steps), {})


# ---------------------------------------------------------------------------
# expand_subprotocol — nested subprotocol steps
# ---------------------------------------------------------------------------

class TestExpandNestedSubprotocol:
    def test_sequential_child_is_flattened(self):
        child_defn = _make_defn(
            name="child",
            steps=[{"id": "c1", "type": "method", "method_name": "Rinse", "parameters": {}}],
        )
        parent_steps = [{"id": "sp1", "type": "subprotocol",
                         "subprotocol_name": "child", "parameters": {}, "output_alias": {}}]
        defn = _make_defn(steps=parent_steps)

        with patch("lh_manager.subprotocol.db.get_subprotocol_by_name", return_value=child_defn):
            steps, _ = expand_subprotocol(defn, {})

        assert len(steps) == 1
        assert steps[0]["step_id"] == "sp1.c1"
        assert steps[0]["method_name"] == "Rinse"

    def test_sequential_child_steps_ordered_correctly(self):
        child_defn = _make_defn(
            name="child",
            steps=[
                {"id": "c1", "type": "method", "method_name": "A", "parameters": {}},
                {"id": "c2", "type": "method", "method_name": "B", "parameters": {}},
            ],
        )
        parent_steps = [{"id": "sp1", "type": "subprotocol",
                         "subprotocol_name": "child", "parameters": {}, "output_alias": {}}]

        with patch("lh_manager.subprotocol.db.get_subprotocol_by_name", return_value=child_defn):
            steps, _ = expand_subprotocol(_make_defn(steps=parent_steps), {})

        assert [r["step_id"] for r in steps] == ["sp1.c1", "sp1.c2"]

    def test_parallel_child_becomes_method_group(self):
        child_defn = _make_defn(
            name="child",
            execution="parallel",
            steps=[
                {"id": "c1", "method_name": "Load", "parameters": {}},
                {"id": "c2", "method_name": "Inject", "parameters": {}},
            ],
            method_type="prepare",
        )
        parent_steps = [{"id": "sp1", "type": "subprotocol",
                         "subprotocol_name": "child", "parameters": {}, "output_alias": {}}]

        with patch("lh_manager.subprotocol.db.get_subprotocol_by_name", return_value=child_defn):
            steps, _ = expand_subprotocol(_make_defn(steps=parent_steps), {})

        assert len(steps) == 1
        assert steps[0]["type"] == "method_group"
        assert steps[0]["step_id"] == "sp1"
        assert steps[0]["method_type"] == "prepare"
        assert len(steps[0]["group"]) == 2

    def test_child_input_params_resolved_from_parent(self):
        child_defn = _make_defn(
            name="child",
            steps=[{"id": "c1", "type": "method", "method_name": "Inject",
                    "parameters": {"volume": {"$ref": "input.volume"}}}],
        )
        parent_steps = [{"id": "sp1", "type": "subprotocol", "subprotocol_name": "child",
                         "parameters": {"volume": {"$ref": "input.vol"}}, "output_alias": {}}]
        parent_ctx = {"input.vol": 75.0}

        with patch("lh_manager.subprotocol.db.get_subprotocol_by_name", return_value=child_defn):
            steps, _ = expand_subprotocol(_make_defn(steps=parent_steps), parent_ctx)

        assert steps[0]["params"]["volume"] == 75.0

    def test_child_allocations_minted(self):
        child_defn = _make_defn(
            name="child",
            allocations=["well_id"],
            steps=[{"id": "c1", "type": "method", "method_name": "Formulate",
                    "parameters": {"well": {"$alloc": "well_id"}}}],
        )
        parent_steps = [{"id": "sp1", "type": "subprotocol",
                         "subprotocol_name": "child", "parameters": {}, "output_alias": {}}]

        with patch("lh_manager.subprotocol.db.get_subprotocol_by_name", return_value=child_defn):
            steps, _ = expand_subprotocol(_make_defn(steps=parent_steps), {})

        well_val = steps[0]["params"]["well"]
        uuid.UUID(well_val)  # must be a valid UUID

    def test_child_not_found_raises(self):
        parent_steps = [{"id": "sp1", "type": "subprotocol",
                         "subprotocol_name": "nonexistent", "parameters": {}, "output_alias": {}}]
        with patch("lh_manager.subprotocol.db.get_subprotocol_by_name", return_value=None):
            with pytest.raises(ValueError, match="not found"):
                expand_subprotocol(_make_defn(steps=parent_steps), {})

    def test_max_depth_exceeded_raises(self):
        recursive_defn = _make_defn(
            name="recursive",
            steps=[{"id": "r1", "type": "subprotocol",
                    "subprotocol_name": "recursive", "parameters": {}, "output_alias": {}}],
        )
        with patch("lh_manager.subprotocol.db.get_subprotocol_by_name", return_value=recursive_defn):
            with pytest.raises(RuntimeError, match=str(_MAX_DEPTH)):
                expand_subprotocol(recursive_defn, {})

    def test_mixed_parent_and_child_steps_ordered(self):
        """Parent has a method step, then a child with two steps — all flattened in order."""
        child_defn = _make_defn(
            name="child",
            steps=[
                {"id": "c1", "type": "method", "method_name": "ChildA", "parameters": {}},
                {"id": "c2", "type": "method", "method_name": "ChildB", "parameters": {}},
            ],
        )
        parent_steps = [
            {"id": "p1", "type": "method", "method_name": "ParentFirst", "parameters": {}},
            {"id": "sp1", "type": "subprotocol",
             "subprotocol_name": "child", "parameters": {}, "output_alias": {}},
            {"id": "p2", "type": "method", "method_name": "ParentLast", "parameters": {}},
        ]

        with patch("lh_manager.subprotocol.db.get_subprotocol_by_name", return_value=child_defn):
            steps, _ = expand_subprotocol(_make_defn(steps=parent_steps), {})

        assert [r["step_id"] for r in steps] == ["p1", "sp1.c1", "sp1.c2", "p2"]

    def test_output_alias_propagated_to_leaf_map(self):
        """output_alias renames child output names in the parent's output_leaf_map."""
        child_defn = _make_defn(
            name="child",
            steps=[{"id": "step_record", "type": "method", "method_name": "Measure", "parameters": {}}],
            outputs={"qcmd_data": {"step_id": "step_record", "type": "QCMDData"}},
        )
        parent_steps = [{"id": "solvent_phase", "type": "subprotocol",
                         "subprotocol_name": "child", "parameters": {},
                         "output_alias": {"qcmd_data": "qcmd_solvent"}}]

        with patch("lh_manager.subprotocol.db.get_subprotocol_by_name", return_value=child_defn):
            steps, leaf_map = expand_subprotocol(_make_defn(steps=parent_steps), {})

        assert leaf_map == {"qcmd_solvent": "solvent_phase.step_record"}

    def test_repeated_child_step_ids_are_disambiguated(self):
        """Using the same child subprotocol twice must produce distinct prefixed step_ids."""
        child_defn = _make_defn(
            name="child",
            steps=[{"id": "step_record", "type": "method", "method_name": "Measure", "parameters": {}}],
            outputs={"qcmd_data": {"step_id": "step_record", "type": "QCMDData"}},
        )
        parent_steps = [
            {"id": "phase_a", "type": "subprotocol", "subprotocol_name": "child",
             "parameters": {}, "output_alias": {"qcmd_data": "qcmd_a"}},
            {"id": "phase_b", "type": "subprotocol", "subprotocol_name": "child",
             "parameters": {}, "output_alias": {"qcmd_data": "qcmd_b"}},
        ]

        with patch("lh_manager.subprotocol.db.get_subprotocol_by_name", return_value=child_defn):
            steps, leaf_map = expand_subprotocol(_make_defn(steps=parent_steps), {})

        assert [s["step_id"] for s in steps] == ["phase_a.step_record", "phase_b.step_record"]
        assert leaf_map == {
            "qcmd_a": "phase_a.step_record",
            "qcmd_b": "phase_b.step_record",
        }
