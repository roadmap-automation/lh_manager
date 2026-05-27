"""Unit tests for lh_manager.method_group.db and executor method_group step.

No RabbitMQ, autocontrol, or lh_manager process required.
"""

import asyncio
import json
import os
import tempfile
import uuid
from unittest.mock import MagicMock, patch

import pytest

from lh_manager.method_group.db import (
    create_method_group,
    delete_method_group,
    get_method_group,
    get_method_group_by_name,
    list_method_groups,
    update_method_group,
)
from lh_manager.subprotocol.executor import SubprotocolExecutor, _build_method_group


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    """Redirect DB to a temporary directory so tests don't share state."""
    monkeypatch.setattr(
        "lh_manager.method_group.db.DB_FOLDER", str(tmp_path)
    )
    from lh_manager.method_group import db
    db.init_db()
    yield


# ---------------------------------------------------------------------------
# MethodGroup CRUD
# ---------------------------------------------------------------------------

class TestMethodGroupCRUD:
    def test_create_and_get_by_id(self):
        steps = [{"method_name": "GilsonFormulation", "parameters": {}, "composition_source": True}]
        mg_id = create_method_group(name="TestGroup", steps=steps, method_type="prepare")
        assert mg_id

        mg = get_method_group(mg_id)
        assert mg is not None
        assert mg["name"] == "TestGroup"
        assert mg["method_type"] == "prepare"
        assert json.loads(mg["steps"]) == steps

    def test_get_by_name(self):
        create_method_group(name="MyGroup", steps=[], description="desc")
        mg = get_method_group_by_name("MyGroup")
        assert mg is not None
        assert mg["description"] == "desc"

    def test_get_missing_returns_none(self):
        assert get_method_group(str(uuid.uuid4())) is None
        assert get_method_group_by_name("nonexistent") is None

    def test_list_method_groups(self):
        create_method_group(name="GroupA", steps=[])
        create_method_group(name="GroupB", steps=[])
        groups = list_method_groups()
        names = [g["name"] for g in groups]
        assert "GroupA" in names
        assert "GroupB" in names

    def test_update(self):
        mg_id = create_method_group(name="OldName", steps=[{"method_name": "Rinse", "parameters": {}}])
        new_steps = [{"method_name": "Inject", "parameters": {"volume": 10.0}}]
        update_method_group(mg_id=mg_id, name="NewName", steps=new_steps, method_type="inject")
        mg = get_method_group(mg_id)
        assert mg["name"] == "NewName"
        assert json.loads(mg["steps"]) == new_steps
        assert mg["method_type"] == "inject"

    def test_delete(self):
        mg_id = create_method_group(name="ToDelete", steps=[])
        delete_method_group(mg_id)
        assert get_method_group(mg_id) is None

    def test_exposed_fields_roundtrip(self):
        fields = [{"field_name": "volume", "type": "number", "display_name": "Volume (mL)", "step_index": 1}]
        mg_id = create_method_group(name="WithFields", steps=[], exposed_fields=fields)
        mg = get_method_group(mg_id)
        assert json.loads(mg["exposed_fields"]) == fields


# ---------------------------------------------------------------------------
# Executor: method_group step type
# ---------------------------------------------------------------------------

def _make_worker():
    worker = MagicMock()
    worker._pending_step_completions = {}
    worker._step_retrieval_uris = {}
    return worker


def _make_subprotocol_defn(steps, execution="sequential", allocations=None):
    return {
        "name": "TestProto",
        "execution": execution,
        "steps": json.dumps(steps),
        "outputs": json.dumps({}),
        "allocations": json.dumps(allocations or []),
    }


def _make_mg_defn(name, mg_steps, method_type="prepare"):
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "steps": json.dumps(mg_steps),
        "exposed_fields": "[]",
        "method_type": method_type,
    }


class TestExecutorMethodGroupStep:
    def test_method_group_step_dispatches_as_group(self):
        """method_group step should call _submit_method_group_sync with the group steps."""
        worker = _make_worker()
        executor = SubprotocolExecutor(worker)

        captured = []

        mg_defn = _make_mg_defn("LoadInject", [
            {"method_name": "GilsonFormulation", "parameters": {"volume": 5.0}, "composition_source": True},
            {"method_name": "InjectLoop", "parameters": {"await_composition_transfer": True}},
        ])

        parent_steps = [{"id": "step-mg", "type": "method_group", "method_group_name": "LoadInject", "parameters": {}}]
        sp_defn = _make_subprotocol_defn(parent_steps)

        async def fake(func, *args, **kwargs):
            name = getattr(func, "__name__", "")
            if name == "_create_sample_sync":
                return "sample-1"
            if name == "get_method_group_by_name":
                return mg_defn
            if name == "_submit_method_group_sync":
                _, run_id, _, group = args
                captured.extend(group)
                ev = worker._pending_step_completions.get(run_id)
                if ev:
                    ev.set()
            return None

        async def _run():
            with patch("asyncio.to_thread", side_effect=fake):
                return await executor.execute(sp_defn, "run-1", "sample-1", 0, {})

        asyncio.run(_run())
        assert len(captured) == 2
        assert captured[0]["method_name"] == "GilsonFormulation"
        assert captured[1]["method_name"] == "InjectLoop"
        assert captured[1].get("await_composition_transfer") is True

    def test_method_group_step_not_found_raises(self):
        worker = _make_worker()
        executor = SubprotocolExecutor(worker)

        parent_steps = [{"id": "s1", "type": "method_group", "method_group_name": "Missing", "parameters": {}}]
        sp_defn = _make_subprotocol_defn(parent_steps)

        async def fake(func, *args, **kwargs):
            name = getattr(func, "__name__", "")
            if name == "_create_sample_sync":
                return "sample-1"
            if name == "get_method_group_by_name":
                return None
            return None

        async def _run():
            with patch("asyncio.to_thread", side_effect=fake):
                await executor.execute(sp_defn, "run-1", "sample-1", 0, {})

        with pytest.raises(ValueError, match="Missing"):
            asyncio.run(_run())

    def test_method_group_params_resolved_with_context(self):
        """Parameters in MethodGroup steps are resolved via $ref from subprotocol context."""
        worker = _make_worker()
        executor = SubprotocolExecutor(worker)

        captured = []

        mg_defn = _make_mg_defn("VolumeGroup", [
            {"method_name": "Inject", "parameters": {"volume": {"$ref": "input.vol"}}},
        ])

        parent_steps = [{
            "id": "mg1", "type": "method_group",
            "method_group_name": "VolumeGroup",
            "parameters": {},
        }]
        sp_defn = _make_subprotocol_defn(parent_steps)

        async def fake(func, *args, **kwargs):
            name = getattr(func, "__name__", "")
            if name == "_create_sample_sync":
                return "sample-1"
            if name == "get_method_group_by_name":
                return mg_defn
            if name == "_submit_method_group_sync":
                _, run_id, _, group = args
                captured.extend(group)
                ev = worker._pending_step_completions.get(run_id)
                if ev:
                    ev.set()
            return None

        async def _run():
            with patch("asyncio.to_thread", side_effect=fake):
                await executor.execute(sp_defn, "run-1", "sample-1", 0, {"vol": 42.0})

        asyncio.run(_run())
        assert len(captured) == 1
        assert captured[0]["volume"] == 42.0
