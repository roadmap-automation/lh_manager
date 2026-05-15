"""
Broker integration test for lh_manager.

Requires:
  1. RabbitMQ running:   docker-compose up -d rabbitmq
  2. lh_manager running: python -m lh_manager.app
     (autocontrol does NOT need to be running for these tests)

Tests:
  - layout.updated broker event → update_layout SocketIO event forwarded to frontend
  - scheduler.task_* events for untracked tasks are silently ignored (no crash)

Usage:
  cd lh_manager
  python tests/broker_test.py
"""

import asyncio
import logging
import sys
import threading
import time
import uuid
from pathlib import Path

import aio_pika
import socketio

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'roadmap-broker-client'))

from roadmap_broker_client.connection import get_connection
from roadmap_broker_client.envelope import build
from roadmap_broker_client.publisher import publish
from roadmap_broker_client.topology import declare_topology
from roadmap_broker_client.topics import (
    INSTRUMENT_EXCHANGE,
    LAYOUT_UPDATED,
    SCHEDULER_TASK_COMPLETED,
    SCHEDULER_TASK_DISPATCHED,
)

LH_MANAGER_URL = 'http://localhost:5001'
EVENT_TIMEOUT = 10.0

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
_results: list[tuple[str, bool]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = PASS if condition else FAIL
    suffix = f"  ({detail})" if detail and not condition else ""
    print(f"  [{status}] {name}{suffix}")
    _results.append((name, condition))


# ---------------------------------------------------------------------------
# SocketIO test client (sync)
# ---------------------------------------------------------------------------

class SIOTestClient:
    def __init__(self) -> None:
        self.sio = socketio.Client()
        self._received: list[tuple[str, dict]] = []
        self._lock = threading.Lock()
        self._event = threading.Event()

        @self.sio.on('connect')
        def on_connect():
            pass

        @self.sio.on('update_layout')
        def on_update_layout(payload):
            with self._lock:
                self._received.append(('update_layout', payload))
            self._event.set()

    def connect(self) -> None:
        self.sio.connect(LH_MANAGER_URL)

    def disconnect(self) -> None:
        self.sio.disconnect()

    def wait_for(self, event: str, timeout: float = EVENT_TIMEOUT) -> dict | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                for ev, payload in self._received:
                    if ev == event:
                        return payload
            remaining = deadline - time.monotonic()
            self._event.wait(timeout=min(remaining, 0.5))
            self._event.clear()
        return None

    def clear(self) -> None:
        with self._lock:
            self._received.clear()
        self._event.clear()


# ---------------------------------------------------------------------------
# Async broker publisher helpers
# ---------------------------------------------------------------------------

async def run_tests(sio_client: SIOTestClient) -> None:
    connection = await get_connection()
    async with connection:
        ch = await connection.channel()
        await declare_topology(ch)
        exchange = await ch.get_exchange(INSTRUMENT_EXCHANGE)

        await test_layout_forwarding(sio_client, exchange)
        await test_layout_unknown_device(sio_client, exchange)
        await test_scheduler_untracked_ignored(sio_client, exchange)


async def test_layout_forwarding(sio_client: SIOTestClient, exchange) -> None:
    print("\n[test_layout_forwarding] layout.updated → update_layout SocketIO event")
    sio_client.clear()

    device_name = "injection"
    base_url = "http://localhost:5003"

    env = build(
        device_id=device_name,
        routing_key=LAYOUT_UPDATED,
        payload={"device_name": device_name, "retrieval_uri": base_url},
    )
    await publish(exchange, LAYOUT_UPDATED, env)

    payload = sio_client.wait_for('update_layout')
    check("update_layout received", payload is not None)
    check("device_name correct", payload is not None and payload.get("device_name") == device_name)
    check("retrieval_uri forwarded", payload is not None and payload.get("retrieval_uri") == base_url)


async def test_layout_unknown_device(sio_client: SIOTestClient, exchange) -> None:
    print("\n[test_layout_unknown_device] layout.updated for unknown device is forwarded (not dropped)")
    sio_client.clear()

    device_name = "nonexistent_device"
    base_url = "http://localhost:9999"

    env = build(
        device_id=device_name,
        routing_key=LAYOUT_UPDATED,
        payload={"device_name": device_name, "retrieval_uri": base_url},
    )
    await publish(exchange, LAYOUT_UPDATED, env)

    payload = sio_client.wait_for('update_layout')
    check("update_layout forwarded for unknown device", payload is not None)
    check("device_name preserved", payload is not None and payload.get("device_name") == device_name)


async def test_scheduler_untracked_ignored(sio_client: SIOTestClient, exchange) -> None:
    print("\n[test_scheduler_untracked_ignored] scheduler.task_completed for unknown task_id → no crash")
    sio_client.clear()

    # Publish a scheduler event for a task_id that lh_manager has never seen.
    # The worker should log a debug message and return cleanly.
    env = build(
        device_id="autocontrol",
        routing_key=SCHEDULER_TASK_COMPLETED,
        task_id=uuid.uuid4(),
        payload={"device": "injection", "channel": 0},
    )
    await publish(exchange, SCHEDULER_TASK_COMPLETED, env)

    # Give broker worker time to process; if lh_manager crashes this test will hang.
    await asyncio.sleep(2.0)
    check("lh_manager still connected after untracked task event",
          sio_client.sio.connected)


# ---------------------------------------------------------------------------
# Main harness
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s  %(name)-20s  %(levelname)s  %(message)s",
    )

    print("\n" + "=" * 60)
    print("Running lh_manager broker tests")
    print("=" * 60)

    sio_client = SIOTestClient()
    try:
        sio_client.connect()
    except Exception as exc:
        print(f"\n[FATAL] Could not connect to lh_manager at {LH_MANAGER_URL}: {exc}")
        print("  Is lh_manager running?  python -m lh_manager.app")
        sys.exit(1)

    try:
        asyncio.run(run_tests(sio_client))
    finally:
        sio_client.disconnect()

    passed = sum(1 for _, ok in _results if ok)
    total = len(_results)
    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed")
    if passed < total:
        print("Failed:")
        for name, ok in _results:
            if not ok:
                print(f"  - {name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
