# lh_manager — Interface Layer / ROADMAP Business Logic Boundary

lh_manager is the single boundary where ROADMAP business logic is concentrated. It
translates high-level experiment commands from Protocol Studio into hardware tasks for
autocontrol, manages the SubProtocol and MethodGroup libraries, assigns channels from an
internal pool, and aggregates hardware completion events into unified results that Protocol
Studio can act on.

No other component knows both the experiment domain (SubProtocols, sample compositions)
and the hardware domain (device methods, channel counts). This separation is intentional
and must be preserved.

---

## Role in the System

lh_manager is the **Interface Layer** — the only component that bridges
`exchange.protocol` (Tier 1) and `exchange.instrument` (Tier 2). It is the facade through
which Protocol Studio addresses the physical world.

```
exchange.protocol                    exchange.instrument
─────────────────                    ───────────────────
Protocol Studio                      autocontrol
    │ command.lh_manager             │ command.<device>.submit_task
    │   .run_subprotocol             │
    ▼                                ▼
lh_manager ──────────────────────► autocontrol
    │  command.autocontrol           │
    │    .submit_task                └──► devices
    │
    ◄── scheduler.task_completed / failed
    │
    └──► lh_manager.sample.method_completed  (exchange.protocol)
         subprotocol.completed / failed
```

---

## Method Abstraction Hierarchy

lh_manager owns three abstraction levels, each hiding the level below from Protocol Studio:

```
SubProtocol      User-facing procedure. Exposes compositions, volumes, flow rates.
    │            Contains allocations ($alloc) for well reservation.
    │ expands into
MethodGroup      Set of device methods dispatched as one autocontrol Task.
    │            Devices coordinate during execution via broker
    │            (composition.transfer, gsioc.trigger).
    │ contains
Device Method    Single-device atomic operation (e.g., LoadLoopBubbleSensor, QCMDRecord).
                 Defined in the device package; dispatched by autocontrol.
```

**SubProtocol library** and **MethodGroup library** are stored in lh_manager's SQLite
database and editable through the web GUI. The seed script is at
`lh_manager/scripts/seed_subprotocols.py`.

---

## Channel Pool

lh_manager assigns channels from an internal pool whose size is derived from device
registration (`num_channels` in the `device.registered` payload). Once assigned, a
channel number travels in every envelope for that sample's lifetime. autocontrol enforces
affinity; lh_manager must not change `assigned_channel` after initial assignment.

---

## Broker Interface

### Subscribes to — `exchange.instrument`
| Routing key | Queue | Publisher | Action |
|---|---|---|---|
| `command.lh_manager.run_subprotocol` | `lh_manager.commands` (durable) | Protocol Studio | Expand SubProtocol → MethodGroups → submit to autocontrol |
| `command.lh_manager.run_sample` | `lh_manager.commands` | Protocol Studio | Legacy direct-run path |
| `command.lh_manager.cancel_tasks` | `lh_manager.commands` | Protocol Studio | Cancel all tasks for a sample |
| `command.lh_manager.resubmit_tasks` | `lh_manager.commands` | Protocol Studio | Resubmit last failed task (Clear Fault) |
| `command.lh_manager.initialize_devices` | `lh_manager.commands` | Protocol Studio | Dispatch INIT tasks to all registered devices |
| `scheduler.task_dispatched` | `lh_manager.scheduler_events` (durable) | autocontrol | Update task status to RUNNING |
| `scheduler.task_completed` | `lh_manager.scheduler_events` | autocontrol | `mark_status(COMPLETED)`; publish `sample.method_completed` |
| `scheduler.task_failed` | `lh_manager.scheduler_events` | autocontrol | `mark_status(FAILED)`; publish `sample.method_completed` |
| `layout.updated` | transient (non-durable) | any device | Forward to GUI via SocketIO `update_layout` event |
| `device.registered` | transient | any device | Register device; merge method schemas; emit `update_layout` |
| `device.announce_request` | — | self (sent on startup) | Prompt all running devices to re-announce |
| `waste.generated` | transient | lh_devices injection | Record waste volume and composition |

### Publishes — `exchange.instrument`
| Routing key | When |
|---|---|
| `command.autocontrol.submit_task` | After SubProtocol expansion |
| `command.autocontrol.cancel_task` | On task cancellation request |
| `command.autocontrol.resubmit_task` | On Clear Fault request |
| `device.announce_request` | Once, immediately after broker connection is ready |
| `lh_manager.sample.status_changed` | On sample status transitions |
| `lh_manager.task.status_changed` | On task status transitions |
| `lh_manager.device_list.updated` | After device registration |

### Publishes — `exchange.protocol`
| Routing key | When |
|---|---|
| `lh_manager.sample.method_completed` | After each scheduler task completes/fails; triggers Protocol Studio step unblock |
| `protocol_studio.subprotocol.completed` | After all tasks in a subprotocol run finish successfully |
| `protocol_studio.subprotocol.failed` | After a subprotocol task fails |

---

## REST Endpoints (remain after broker refactor)

The lh_manager web GUI and its proxy endpoints remain REST. Broker events supplement
(not replace) these for real-time state changes.

| Endpoint | Purpose |
|---|---|
| `GET /GUI/GetAllMethods/` | All device method schemas (local + remote via device registration) |
| `GET /GUI/GetMaterials/` | Materials / formulation library |
| `GET /subprotocols/` | SubProtocol CRUD |
| `GET /method_groups/` | MethodGroup CRUD |
| Autocontrol proxy (`/get_task_status/`, etc.) | Read-only query forwarding to autocontrol |

---

## Getting Started

```bash
# Via process-compose (recommended):
process-compose up

# Or directly (builds frontend first):
npm --prefix lh_manager/static/src run build && python -m lh_manager.app
```

Devices should be running before lh_manager so service discovery completes before the
first subprotocol is dispatched. lh_manager publishes `device.announce_request` on
startup to prompt already-running devices to re-register.

### Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `AMQP_URL` | `amqp://roadbot:roadbot_dev@localhost/` | RabbitMQ connection |
| `AUTOCONTROL_URL` | `http://localhost:5000` | autocontrol REST base URL (read-only query proxying only) |
| `LH_MANAGER_PORT` | `5001` | Port for this service |
