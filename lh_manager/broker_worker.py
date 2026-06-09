"""Broker integration for lh_manager.

Runs an asyncio event loop in a dedicated daemon thread alongside the
synchronous Flask/SocketIO server.  Provides:

  Inbound (broker → lh_manager):
    scheduler.task_dispatched              — task is now active on a device
    scheduler.task_completed               — task has finished successfully
    scheduler.task_failed                  — task has finished with an error
    layout.updated                         — a device's bed layout has changed
    command.lh.submit_task                 — autocontrol dispatching an LH job
    command.lh_manager.run_subprotocol     — run a named subprotocol
    command.lh_manager.cancel_subprotocol  — cancel a running subprotocol by run_id

  Outbound (lh_manager → broker):
    command.autocontrol.submit_task    — replaces POST /put
    command.autocontrol.resubmit_task  — replaces POST /resubmit
    command.autocontrol.cancel_task    — replaces POST /cancel
    task.accepted              — LH job accepted
    task.completed             — LH job completed successfully
    task.failed                — LH job failed

Thread model
------------
The broker event loop runs in a daemon thread.  Sync Flask threads call
the public submit_task / resubmit_task / cancel_task methods, which use
asyncio.run_coroutine_threadsafe to hand work to that loop.  A _ready
threading.Event gates all outbound calls until the exchange is connected.
"""

import asyncio
import json
import logging
import queue
import threading
import uuid
from typing import Dict, Optional

import aio_pika

from roadmap_broker_client.connection import get_connection
from roadmap_broker_client.consumer import consume
from roadmap_broker_client.envelope import Envelope, build
from roadmap_broker_client.publisher import publish
from roadmap_broker_client.topology import declare_node_queue, declare_topology
from roadmap_broker_client.topics import (
    CMD_CANCEL_SUBPROTOCOL,
    CMD_RUN_SUBPROTOCOL,
    DEVICE_ANNOUNCE_REQUEST,
    DEVICE_REGISTERED,
    INSTRUMENT_EXCHANGE,
    LAYOUT_UPDATED,
    PROTOCOL_EXCHANGE,
    SAMPLE_METHOD_COMPLETED,
    SCHEDULER_TASK_COMPLETED,
    SCHEDULER_TASK_DISPATCHED,
    SCHEDULER_TASK_FAILED,
    SUBPROTOCOL_COMPLETED,
    SUBPROTOCOL_FAILED,
    TASK_ACCEPTED,
    TASK_COMPLETED,
    TASK_FAILED,
    WASTE_GENERATED,
    command_key,
    command_subscription_pattern,
)

logger = logging.getLogger(__name__)

_READY_TIMEOUT = 30.0  # seconds to wait for broker connection before giving up


class LHManagerBrokerWorker:
    """Subscribes to autocontrol scheduler events and device layout events.
    Also publishes commands to autocontrol (submit/resubmit/cancel task).

    Wire in app.py:
        broker_worker = LHManagerBrokerWorker(socketio)
        broker_worker.start()
        set_broker_worker(broker_worker)   # in autocontrol module
        launch_autocontrol_interface()
    """

    def __init__(self, socketio) -> None:
        self._socketio = socketio
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._exchange: Optional[aio_pika.abc.AbstractExchange] = None
        self._protocol_exchange: Optional[aio_pika.abc.AbstractExchange] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._emit_queue: queue.Queue = queue.Queue()
        # Subprotocol execution: step_id → asyncio.Event (set by _on_scheduler_event)
        self._pending_step_completions: Dict[str, asyncio.Event] = {}
        # Subprotocol execution: step_id → retrieval_uri from completed measurement tasks
        self._step_retrieval_uris: Dict[str, str] = {}
        # Tracks step_ids cancelled by operator; checked after event fires in _on_run_subprotocol.
        self._cancelled_steps: set = set()
        # run_id → {"final_step_id": str, "all_step_ids": list[str]}
        self._active_subprotocols: Dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Thread-safe public API  (called from sync Flask threads)
    # ------------------------------------------------------------------

    def submit_task(self, task) -> None:
        """Publish command.autocontrol.submit_task (replaces POST /put)."""
        self._schedule(self._emit_command(
            "submit_task",
            task.model_dump(mode="json"),
            task_id=task.id,
            sample_id=task.sample_id,
        ))

    def resubmit_task(self, task) -> None:
        """Publish command.autocontrol.resubmit_task (replaces POST /resubmit)."""
        self._schedule(self._emit_command(
            "resubmit_task",
            {"task_id": str(task.id), "task": task.model_dump(mode="json")},
            task_id=task.id,
            sample_id=task.sample_id,
        ))

    def cancel_task(self, task_id: str, include_active_queue: bool = False,
                    drop_material: bool = True) -> None:
        """Publish command.autocontrol.cancel_task (replaces POST /cancel)."""
        self._schedule(self._emit_command(
            "cancel_task",
            {"task_id": task_id,
             "include_active_queue": include_active_queue,
             "drop_material": drop_material},
        ))

    # ------------------------------------------------------------------
    # Internal: schedule a coroutine on the broker event loop
    # ------------------------------------------------------------------

    def _schedule(self, coro) -> None:
        if not self._ready.wait(timeout=_READY_TIMEOUT):
            logger.error("Broker not ready after %.0fs — dropping command.", _READY_TIMEOUT)
            return
        if self._loop is None or self._loop.is_closed():
            logger.warning("Broker loop not running — dropping command.")
            return
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    def signal_step_cancelled(self, step_id: str) -> None:
        """Called from mark_cancelled() (Flask thread) to unblock a waiting subprotocol executor."""
        self._schedule(self._fire_step_cancelled(step_id))

    async def _fire_step_cancelled(self, step_id: str) -> None:
        self._cancelled_steps.add(step_id)
        event = self._pending_step_completions.pop(step_id, None)
        if event is not None:
            event.set()

    async def _on_cancel_subprotocol(self, run_id: str) -> None:
        """Cancel all queued autocontrol tasks for a running subprotocol.

        Finds every pending/active autocontrol task whose method_id matches one
        of the subprotocol's step_ids, cancels them via the broker, then fires
        the final-step cancel signal so the executor coroutine wakes and exits.
        """
        from .autocontrol.autocontrol import active_tasks, mark_status
        from .liquid_handler.samplecontainer import SampleStatus

        info = self._active_subprotocols.get(run_id)
        if info is None:
            logger.warning("cancel_subprotocol: run_id %r not active — ignoring.", run_id)
            return

        all_step_ids: set = set(info["all_step_ids"])
        final_step_id: str = info["final_step_id"]

        # Collect autocontrol task IDs whose method_id matches a step in this run.
        task_ids_to_cancel: list = []
        with active_tasks.lock:
            for task_id, item in list(active_tasks.pending.items()):
                if item.method_id in all_step_ids:
                    task_ids_to_cancel.append(task_id)
            for task_id, item in list(active_tasks.active.items()):
                if item.method_id in all_step_ids:
                    task_ids_to_cancel.append(task_id)

        for task_id in task_ids_to_cancel:
            self.cancel_task(task_id, include_active_queue=True, drop_material=False)
            logger.info("cancel_subprotocol %r: cancelled autocontrol task %s", run_id, task_id)

        # Unblock the waiting executor so it raises the cancelled RuntimeError.
        await self._fire_step_cancelled(final_step_id)
        logger.info("cancel_subprotocol %r: signalled final step %s as cancelled.", run_id, final_step_id)

        # Clean up lh_manager's task tracking so cancelled tasks don't linger in
        # active_tasks as orphans.  If an orphaned task were later cancelled via
        # the GUI, mark_cancelled would fire signal_step_cancelled(final_step_id)
        # with no executor waiting, leaving a stale _cancelled_steps entry that
        # would poison the next run of the same subprotocol.
        # Use mark_status(CANCELLED) rather than mark_cancelled to avoid re-firing
        # signal_step_cancelled (which we already did above via _fire_step_cancelled).
        def _cleanup_orphaned_tasks() -> None:
            with active_tasks.lock:
                for task_id in task_ids_to_cancel:
                    if task_id in active_tasks.active:
                        mark_status(task_id, SampleStatus.CANCELLED)
                    elif task_id in active_tasks.pending:
                        active_tasks.pending.pop(task_id, None)

        await asyncio.to_thread(_cleanup_orphaned_tasks)

    # ------------------------------------------------------------------
    # Async publish helpers
    # ------------------------------------------------------------------

    async def _emit_command(self, verb: str, payload: dict,
                             task_id=None, sample_id=None) -> None:
        if self._exchange is None:
            return
        rk = command_key("autocontrol", verb)
        envelope = build(
            device_id="lh_manager",
            routing_key=rk,
            task_id=task_id,
            sample_id=sample_id,
            payload=payload,
        )
        await publish(self._exchange, rk, envelope)

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    def _sio_emit(self, event: str, data: dict) -> None:
        """Enqueue a SocketIO emit for delivery on a plain threading.Thread.

        Flask-SocketIO (threading mode) doesn't reliably emit when called
        from within an asyncio coroutine.  This method decouples the emit
        from the asyncio execution context by handing it off to a dedicated
        emitter thread that has no asyncio loop running.
        """
        self._emit_queue.put((event, data))

    def start(self) -> None:
        """Start the broker worker in a background daemon thread."""

        def _emitter_loop() -> None:
            while True:
                event, data = self._emit_queue.get()
                try:
                    self._socketio.emit(event, data)
                except Exception:
                    logger.exception("SocketIO emit failed for event '%s'.", event)

        emitter = threading.Thread(
            target=_emitter_loop, name="lh-manager-sio-emitter", daemon=True
        )
        emitter.start()

        def _thread_main() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._run())
            except Exception:
                logger.exception("LHManager broker worker exited with error.")
            finally:
                self._loop.close()

        self._thread = threading.Thread(
            target=_thread_main, name="lh-manager-broker", daemon=True
        )
        self._thread.start()
        logger.info("LHManager broker worker thread started.")

    # ------------------------------------------------------------------
    # Async main loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        connection = await get_connection()
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)
            await declare_topology(channel)

            self._exchange = await channel.get_exchange(INSTRUMENT_EXCHANGE)
            self._protocol_exchange = await channel.get_exchange(PROTOCOL_EXCHANGE)
            self._ready.set()

            # Subscribe to autocontrol scheduler task events.
            task_queue = await channel.declare_queue(
                "lh_manager.scheduler_events",
                durable=True,
                arguments={"x-dead-letter-exchange": "exchange.dead_letter"},
            )
            await task_queue.bind(self._exchange, routing_key=SCHEDULER_TASK_DISPATCHED)
            await task_queue.bind(self._exchange, routing_key=SCHEDULER_TASK_COMPLETED)
            await task_queue.bind(self._exchange, routing_key=SCHEDULER_TASK_FAILED)

            # Transient queue for layout notifications — non-durable, auto-deletes
            # on disconnect so stale messages never pile up across restarts.
            layout_queue = await channel.declare_queue(
                "lh_manager.layout_events",
                durable=False,
                auto_delete=True,
            )
            await layout_queue.bind(self._exchange, routing_key=LAYOUT_UPDATED)

            # Transient queue for waste events from devices.
            waste_queue = await channel.declare_queue(
                "lh_manager.waste_events",
                durable=False,
                auto_delete=True,
            )
            await waste_queue.bind(self._exchange, routing_key=WASTE_GENERATED)

            # Transient queue for device registration — auto-deletes on disconnect
            # so stale announcements never pile up across restarts.
            reg_queue = await channel.declare_queue(
                "lh_manager.device_registrations",
                durable=False,
                auto_delete=True,
            )
            await reg_queue.bind(self._exchange, routing_key=DEVICE_REGISTERED)

            # Durable command queue on exchange.protocol for subprotocol execution
            # commands from Protocol Studio.
            subprotocol_cmd_queue = await channel.declare_queue(
                "lh_manager.subprotocol_commands",
                durable=True,
                arguments={"x-dead-letter-exchange": "exchange.dead_letter"},
            )
            await subprotocol_cmd_queue.bind(
                self._protocol_exchange,
                routing_key=command_subscription_pattern("lh_manager"),
            )

            # Request all running devices to re-announce themselves with their current
            # method schemas. This handles the case where lh_manager starts after devices.
            announce_msg = build(
                device_id="lh_manager",
                routing_key=DEVICE_ANNOUNCE_REQUEST,
                payload={},
            )
            await publish(self._exchange, DEVICE_ANNOUNCE_REQUEST, announce_msg)
            logger.info("LHManager published device.announce_request to trigger re-registration.")

            logger.info("LHManager broker worker running.")
            await asyncio.gather(
                consume(task_queue, self._on_scheduler_event),
                consume(layout_queue, self._on_layout_updated),
                consume(waste_queue, self._on_waste_generated),
                consume(reg_queue, self._on_device_registered),
                consume(subprotocol_cmd_queue, self._on_lhmanager_command),
            )

    # ------------------------------------------------------------------
    # Inbound: scheduler.task_* events from autocontrol
    # ------------------------------------------------------------------

    async def _on_scheduler_event(
        self, envelope: Envelope, message: aio_pika.abc.AbstractIncomingMessage
    ) -> None:
        from .autocontrol.autocontrol import active_tasks, mark_status
        from .liquid_handler.samplecontainer import SampleStatus

        rk = message.routing_key or ""
        task_id = str(envelope.task_id)

        if rk == SCHEDULER_TASK_COMPLETED:
            new_status = SampleStatus.COMPLETED
        elif rk == SCHEDULER_TASK_DISPATCHED:
            new_status = SampleStatus.ACTIVE
        elif rk == SCHEDULER_TASK_FAILED:
            new_status = SampleStatus.FAILED
        else:
            return

        # Capture sample_id and step_id before mark_status() pops the item for
        # completed/failed tasks — after that call the dict entry is gone.
        captured: dict = {}

        def _sync_update() -> None:
            with active_tasks.lock:
                if task_id not in active_tasks.active:
                    logger.debug("Scheduler event for untracked task %s — ignoring.", task_id)
                    return
                item = active_tasks.active[task_id]
                captured["sample_id"] = item.id
                captured["step_id"] = item.method_id
                mark_status(task_id, new_status)

        await asyncio.to_thread(_sync_update)

        if rk in (SCHEDULER_TASK_COMPLETED, SCHEDULER_TASK_FAILED):
            sample_id = captured.get("sample_id")
            step_id = captured.get("step_id")
            device_payload = envelope.payload or {}
            retrieval_uri = device_payload.get("retrieval_uri")
            if sample_id and step_id and self._protocol_exchange is not None:
                method_payload: dict = {"step_id": step_id, "status": new_status.value}
                resolved_composition = device_payload.get("resolved_composition")
                if resolved_composition is not None:
                    method_payload["resolved_composition"] = resolved_composition
                if retrieval_uri is not None:
                    method_payload["retrieval_uri"] = retrieval_uri
                envelope_out = build(
                    device_id="lh_manager",
                    routing_key=SAMPLE_METHOD_COMPLETED,
                    task_id=task_id,
                    sample_id=sample_id,
                    payload=method_payload,
                )
                await publish(self._protocol_exchange, SAMPLE_METHOD_COMPLETED, envelope_out)

            # Unblock any subprotocol executor step awaiting this task's completion.
            # Only fire on COMPLETED — FAILED leaves the waiter blocked until the
            # operator either resubmits (success) or cancels (signal_step_cancelled).
            if step_id and rk == SCHEDULER_TASK_COMPLETED:
                if retrieval_uri is not None:
                    self._step_retrieval_uris[step_id] = retrieval_uri
                event = self._pending_step_completions.pop(step_id, None)
                if event is not None:
                    event.set()

    # ------------------------------------------------------------------
    # Inbound: command.lh_manager.# from Protocol Studio (exchange.protocol)
    # ------------------------------------------------------------------

    async def _on_lhmanager_command(
        self, envelope: Envelope, message: aio_pika.abc.AbstractIncomingMessage
    ) -> None:
        rk = message.routing_key or ""
        if rk == command_key("lh_manager", CMD_RUN_SUBPROTOCOL):
            asyncio.create_task(self._on_run_subprotocol(envelope))
        elif rk == command_key("lh_manager", CMD_CANCEL_SUBPROTOCOL):
            run_id = (envelope.payload or {}).get("subprotocol_run_id", "")
            asyncio.create_task(self._on_cancel_subprotocol(run_id))
        else:
            logger.debug("Ignoring unknown lh_manager command: %s", rk)

    async def _on_run_subprotocol(self, envelope: Envelope) -> None:
        """Execute a named subprotocol and publish SUBPROTOCOL_COMPLETED/FAILED.

        All steps are expanded synchronously (resolving $ref/$alloc, flattening
        nested subprotocols) and then submitted to autocontrol in one shot.
        autocontrol's per-channel FIFO queue handles sequential ordering.
        Only the final step's completion is awaited before publishing the result.
        """
        from .subprotocol.db import get_subprotocol_by_name
        from .subprotocol.executor import (
            expand_subprotocol,
            _build_method_group,
            _create_sample_sync,
            _submit_expanded_steps_via_sentinel,
            _submit_parallel_subprotocol_via_sentinel,
        )

        payload = envelope.payload or {}
        name: str = payload.get("subprotocol_name", "")
        run_id: str = payload.get("subprotocol_run_id") or str(uuid.uuid4())
        sample_id: Optional[str] = payload.get("sample_id") or None
        channel: int = int(payload.get("channel", 0))
        params: dict = payload.get("parameters", {})
        sample_name: str = payload.get("sample_name") or f"subprotocol {run_id[:8]}"

        defn = await asyncio.to_thread(get_subprotocol_by_name, name)
        if defn is None:
            logger.error("Subprotocol %r not found — cannot execute run %s.", name, run_id)
            await self._publish_protocol(SUBPROTOCOL_FAILED, run_id, sample_id, {
                "subprotocol_run_id": run_id,
                "channel": channel,
                "error": f"Subprotocol {name!r} not found in lh_manager DB",
            })
            return

        try:
            # Build context: allocations minted once, inputs available as $ref.
            context: dict = {f"input.{k}": v for k, v in params.items()}
            for alloc_name in json.loads(defn.get("allocations") or "[]"):
                context[f"alloc.{alloc_name}"] = str(uuid.uuid4())
            # Seed static/default inputs not supplied by the caller.
            for inp_name, inp_def in json.loads(defn.get("inputs") or "{}").items():
                key = f"input.{inp_name}"
                if key not in context:
                    if inp_def.get("is_static") and "static_value" in inp_def:
                        context[key] = inp_def["static_value"]
                    elif "default_value" in inp_def:
                        context[key] = inp_def["default_value"]

            actual_sample_id = sample_id or await asyncio.to_thread(
                _create_sample_sync, sample_name, channel
            )

            # Extract all resolved input values so the GUI sentinel shows them.
            full_params = {k[6:]: v for k, v in context.items() if k.startswith("input.")}

            outputs_defn: dict = json.loads(defn.get("outputs") or "{}")
            execution: str = defn.get("execution") or "sequential"

            sentinel_id = str(uuid.uuid4())
            all_step_ids: list
            if execution == "parallel":
                # All top-level steps dispatched as one method group under a sentinel.
                # Parallel subprotocols never produce retrieval_uris, so outputs are empty.
                steps = json.loads(defn["steps"])
                group = _build_method_group(steps, context)
                final_step_id = run_id
                step_to_output: dict = {}
                all_step_ids = [run_id]
                await asyncio.to_thread(
                    _submit_parallel_subprotocol_via_sentinel,
                    actual_sample_id, name, sentinel_id, run_id, group,
                    defn.get("method_type") or "prepare",
                    full_params,
                )
            else:
                # Pre-expand ALL steps at submission time; autocontrol's FIFO
                # queue enforces ordering — no need to await each step before
                # submitting the next.
                expanded, output_leaf_map = await asyncio.to_thread(expand_subprotocol, defn, context)
                step_to_output = {leaf_id: name for name, leaf_id in output_leaf_map.items()}
                if not expanded:
                    await self._publish_protocol(SUBPROTOCOL_COMPLETED, run_id, actual_sample_id, {
                        "subprotocol_run_id": run_id,
                        "channel": channel,
                        "sample_id": actual_sample_id,
                        "outputs": {},
                    })
                    return
                all_step_ids = [s["step_id"] for s in expanded]
                await asyncio.to_thread(
                    _submit_expanded_steps_via_sentinel, actual_sample_id, name, sentinel_id, expanded,
                    full_params,
                )
                final_step_id = expanded[-1]["step_id"]

            # Register so cancel_subprotocol can find this run's steps.
            self._active_subprotocols[run_id] = {
                "final_step_id": final_step_id,
                "all_step_ids": all_step_ids,
            }

            # Wait for the final step to complete (set by _on_scheduler_event).
            # Discard any stale entry left from a prior cancelled run of this same
            # subprotocol (same deterministic step IDs) before registering the new
            # event, so an old cancellation signal can never poison a new run.
            self._cancelled_steps.discard(final_step_id)
            event = asyncio.Event()
            self._pending_step_completions[final_step_id] = event
            await event.wait()
            self._active_subprotocols.pop(run_id, None)
            self._pending_step_completions.pop(final_step_id, None)

            if final_step_id in self._cancelled_steps:
                self._cancelled_steps.discard(final_step_id)
                raise RuntimeError(f"Subprotocol {name!r} was cancelled by operator")

            # Collect outputs from any steps that produced a retrieval_uri.
            outputs: dict = {}
            for step_id, output_name in step_to_output.items():
                uri = self._step_retrieval_uris.pop(step_id, None)
                if uri is not None:
                    outputs[output_name] = {
                        "uri": uri,
                        "type": outputs_defn.get(output_name, {}).get("type", "unknown"),
                    }

            await self._publish_protocol(SUBPROTOCOL_COMPLETED, run_id, actual_sample_id, {
                "subprotocol_run_id": run_id,
                "channel": channel,
                "sample_id": actual_sample_id,
                "outputs": outputs,
            })
            logger.info("Subprotocol %r run %s completed.", name, run_id)

        except Exception as exc:
            self._active_subprotocols.pop(run_id, None)
            logger.exception("Subprotocol %r run %s failed.", name, run_id)
            await self._publish_protocol(SUBPROTOCOL_FAILED, run_id, sample_id, {
                "subprotocol_run_id": run_id,
                "channel": channel,
                "sample_id": sample_id,
                "error": str(exc),
            })

    async def _publish_protocol(
        self,
        routing_key: str,
        task_id: Optional[str] = None,
        sample_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> None:
        if self._protocol_exchange is None:
            return
        env = build(
            device_id="lh_manager",
            routing_key=routing_key,
            task_id=task_id,
            sample_id=sample_id,
            payload=payload or {},
        )
        await publish(self._protocol_exchange, routing_key, env)

    # ------------------------------------------------------------------
    # Inbound: waste.generated events from devices
    # ------------------------------------------------------------------

    async def _on_waste_generated(
        self, envelope: Envelope, message: aio_pika.abc.AbstractIncomingMessage
    ) -> None:
        from .waste_manager.wastedata import WasteItem
        from .waste_manager.waste_api.waste import waste_layout

        try:
            waste_item = WasteItem(**envelope.payload)
        except Exception as exc:
            logger.error("waste.generated: cannot deserialize payload: %s", exc)
            raise

        await asyncio.to_thread(waste_layout.add_waste, waste_item)
        await asyncio.to_thread(waste_layout.save_waste)
        self._sio_emit('update_waste', {'msg': 'update_waste'})
        logger.debug("Waste added: %s", waste_item)

    # ------------------------------------------------------------------
    # Inbound: device.registered — dynamic device registration
    # ------------------------------------------------------------------

    async def _on_device_registered(
        self, envelope: Envelope, message: aio_pika.abc.AbstractIncomingMessage
    ) -> None:
        from .liquid_handler.devices import DeviceBase, device_manager
        from .liquid_handler.methods import method_manager

        payload = envelope.payload
        device_id = payload.get("device_id", "")
        num_channels = int(payload.get("num_channels", 1))

        # model_construct bypasses Literal validation on device_name / device_type
        # so we can create a generic DeviceBase for any dynamically discovered device.
        device = DeviceBase.model_construct(
            device_name=device_id,
            display_name=payload.get("display_name", device_id),
            device_type=payload.get("device_type", device_id),
            multichannel=(num_channels > 1),
            allow_sample_mixing=bool(payload.get("allow_sample_mixing", True)),
            address=payload.get("address", ""),
        )
        await asyncio.to_thread(device_manager.register, device)

        # Register method schemas provided by the device.
        methods: dict = payload.get("methods", {})
        if methods:
            def _register() -> None:
                for name, schema in methods.items():
                    method_manager.register_schema(name, {**schema, 'device_id': device_id, 'origin': device_id})
            await asyncio.to_thread(_register)
            logger.info(
                "device.registered: lh_manager registered '%s' at %s with %d methods",
                device_id, device.address, len(methods),
            )
        else:
            logger.info(
                "device.registered: lh_manager registered '%s' at %s",
                device_id, device.address,
            )

        # Tell the frontend a new device is available; refreshWells() will call
        # refreshDeviceLayouts() if device_id is not yet in device_layouts.
        self._sio_emit("update_layout", {
            "device_name": device_id,
            "retrieval_uri": payload.get("address", ""),
        })
        # Tell the frontend to refresh its method dropdown — new schemas may have arrived.
        if methods:
            self._sio_emit("update_methods", {})

    # ------------------------------------------------------------------
    # Inbound: layout.updated events from devices
    # ------------------------------------------------------------------

    async def _on_layout_updated(
        self, envelope: Envelope, message: aio_pika.abc.AbstractIncomingMessage
    ) -> None:
        device_name = envelope.payload.get("device_name") or envelope.device_id
        retrieval_uri = envelope.payload.get("retrieval_uri")
        if not device_name:
            return
        self._sio_emit("update_layout", {
            "device_name": device_name,
            "retrieval_uri": retrieval_uri,
        })
        logger.debug("Forwarded layout.updated for device '%s' to frontend.", device_name)
