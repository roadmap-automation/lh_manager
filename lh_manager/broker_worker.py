"""Broker integration for lh_manager.

Runs an asyncio event loop in a dedicated daemon thread alongside the
synchronous Flask/SocketIO server.  Provides:

  Inbound (broker → lh_manager):
    scheduler.task_dispatched  — task is now active on a device
    scheduler.task_completed   — task has finished successfully
    scheduler.task_failed      — task has finished with an error
    layout.updated             — a device's bed layout has changed
    command.lh.submit_task     — autocontrol dispatching an LH job

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
import logging
import queue
import threading
from typing import Optional

import aio_pika

from roadmap_broker_client.connection import get_connection
from roadmap_broker_client.consumer import consume
from roadmap_broker_client.envelope import Envelope, build
from roadmap_broker_client.publisher import publish
from roadmap_broker_client.topology import declare_node_queue, declare_topology
from roadmap_broker_client.topics import (
    DEVICE_ANNOUNCE_REQUEST,
    DEVICE_REGISTERED,
    INSTRUMENT_EXCHANGE,
    LAYOUT_UPDATED,
    PROTOCOL_EXCHANGE,
    SAMPLE_METHOD_COMPLETED,
    SCHEDULER_TASK_COMPLETED,
    SCHEDULER_TASK_DISPATCHED,
    SCHEDULER_TASK_FAILED,
    TASK_ACCEPTED,
    TASK_COMPLETED,
    TASK_FAILED,
    WASTE_GENERATED,
    command_key,
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

            # Durable command queue for LH jobs dispatched by autocontrol.
            lh_cmd_queue = await declare_node_queue(channel, "lh", INSTRUMENT_EXCHANGE)

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
                consume(lh_cmd_queue, self._on_lh_command),
                consume(waste_queue, self._on_waste_generated),
                consume(reg_queue, self._on_device_registered),
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
            if sample_id and step_id and self._protocol_exchange is not None:
                method_payload: dict = {"step_id": step_id, "status": new_status.value}
                device_payload = envelope.payload or {}
                resolved_composition = device_payload.get("resolved_composition")
                if resolved_composition is not None:
                    method_payload["resolved_composition"] = resolved_composition
                retrieval_uri = device_payload.get("retrieval_uri")
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

    # ------------------------------------------------------------------
    # Inbound: command.lh.submit_task from autocontrol
    # ------------------------------------------------------------------

    async def _on_lh_command(
        self, envelope: Envelope, message: aio_pika.abc.AbstractIncomingMessage
    ) -> None:
        from .liquid_handler.lhinterface import LHJob, lh_interface, InterfaceStatus
        from .liquid_handler.job import ResultStatus
        from .liquid_handler.state import layout

        rk = message.routing_key or ""
        if rk.split(".")[-1] != "submit_task":
            logger.warning("LH: unknown command verb on key '%s'", rk)
            return

        try:
            # envelope.task_id is authoritative; autocontrol puts it in the
            # envelope header only, not in the payload body.
            job = LHJob(**{**envelope.payload, "id": str(envelope.task_id)})
        except Exception as exc:
            logger.error("LH: cannot deserialize job: %s", exc)
            raise

        if lh_interface.get_status() != InterfaceStatus.UP:
            logger.error("LH: interface busy, rejecting task %s", envelope.task_id)
            await self._emit_lh(TASK_FAILED, envelope, {"error": "LH interface busy"})
            return

        await self._emit_lh(TASK_ACCEPTED, envelope, {})

        # One-shot callback: fires on each result update; publishes completed/failed
        # once the job reaches a terminal state. Uses a flag to prevent double-firing.
        fired = [False]

        def _on_result(result_job: LHJob, *args, **kwargs) -> None:
            if fired[0]:
                return
            status = result_job.get_result_status()
            if status == ResultStatus.SUCCESS:
                fired[0] = True
                asyncio.run_coroutine_threadsafe(
                    self._emit_lh(TASK_COMPLETED, envelope, {}), self._loop
                )
            elif status == ResultStatus.FAIL:
                fired[0] = True
                asyncio.run_coroutine_threadsafe(
                    self._emit_lh(TASK_FAILED, envelope, {"error": "LH job failed"}), self._loop
                )

        lh_interface.results_callbacks.append(_on_result)

        try:
            lh_interface.activate_job(job, layout)
        except Exception as exc:
            lh_interface.results_callbacks.remove(_on_result)
            logger.error("LH: activate_job failed: %s", exc)
            await self._emit_lh(TASK_FAILED, envelope, {"error": str(exc)})
            return

        self._sio_emit('job_activation', {'job_id': job.id})
        self._sio_emit('update_lh_job', {'msg': 'update_lh_job'})

    async def _emit_lh(self, routing_key: str, envelope: Envelope, extra: dict) -> None:
        if self._exchange is None:
            return
        msg = build(
            device_id="lh_manager",
            routing_key=routing_key,
            task_id=envelope.task_id,
            sample_id=envelope.sample_id,
            assigned_channel=envelope.assigned_channel,
            execution_policy=envelope.execution_policy or "infrastructure",
            payload=extra,
        )
        await publish(self._exchange, routing_key, msg)

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
