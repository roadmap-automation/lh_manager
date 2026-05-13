# lh_manager — Refactor Context for AI Assistant

## 1. Core Responsibility
`lh_manager` is the orchestration server for the Gilson 271 multi-channel liquid handler: it manages a sample queue, tracks bed layout state, dispatches prep/injection jobs to the physical LH (via the Autocontrol scheduler), and relays status back to the operator GUI and upstream instruments (NICE).

---

## 2. Physical Constraints

- **Multi-channel with sticky channel affinity.** The LH supports N parallel channels (configurable, default 2). `Sample.channel` is assigned at creation and must be preserved across all operations on all downstream devices. Never reassign a channel mid-workflow.
- **Two error domains depending on operation type:**
  - **PREPARE / MIX** (reagent mixing into a target well) → **Irreversible error domain.** A failure during prep partially combines reagents; the sample is ruined. Abort that sample, release downstream locks, advance queue.
  - **TRANSFER / INJECT** (moving sample from well to instrument) → **Uncertain error domain.** A robotic failure leaves the sample's physical location unknown. Do NOT auto-retry or continue. Freeze that sample's workflow and require operator intervention.
- **Well reservation is server-side and stateful.** Methods reference wells by a UUID (`WellLocation.id` / `InferredWellLocation`). Before dispatch, `LHBedLayout.infer_location()` resolves a UUID to the next available physical well and tags it, preventing double-assignment. This reservation state lives in lh_manager (`liquid_handler/state.py:layout`) and must be resolved before a task message is published to the broker — the device must receive concrete `(rack_id, well_number)` coordinates, not unresolved UUIDs.
- **Single job at a time on the LH interface.** `LHInterface` enforces a one-job-at-a-time gate (`InterfaceStatus.BUSY`). The broker consumer for this device must respect this constraint; new tasks must queue behind the active job.
- **Bed layout is the source of truth for available reagents.** `LHBedLayout` tracks well volumes and compositions. Dry-run (layout simulation) executes `method.execute(layout)` on a copy to validate a proposed queue before committing. This simulation must remain available after the refactor.

---

## 3. Deprecated REST Endpoints

These endpoints represent command/event flows that will be replaced by broker messages.

### GUI operator commands (→ broker or internal event)
- `POST /GUI/RunSample/` — run a sample by stage
- `POST /GUI/RunMethod/` — run a single method within a stage
- `POST /GUI/ResubmitTasks/` — resubmit previously dispatched tasks
- `POST /GUI/CancelTasks/` — cancel active/pending tasks
- `POST /GUI/InitializeDevices/` — send INIT tasks to Autocontrol

### LH device callbacks (Gilson → lh_manager; will become device→broker events)
- `POST /LH/SubmitJob/` — device acknowledges job receipt
- `POST /LH/PutSampleListValidation/<id>` — device reports validation result
- `POST /LH/PutSampleData/` — device reports per-method result (success or failure)
- `POST /LH/ReportError/` — device reports an error condition

### Status polling (will become broker telemetry / pub-sub)
- `GET /GUI/GetSampleStatus/` — full status of all samples
- `GET /autocontrol/GetStatus` — Autocontrol scheduler status
- `GET /autocontrol/GetTaskStatus` — individual task status (currently polls Autocontrol via redirect)

### Sample CRUD (may become broker events or remain REST for GUI)
- `POST /GUI/AddSample/`, `/UpdateSample/`, `/DuplicateSample/`, `/RemoveSample/`, `/ArchiveandRemoveSample/`

---

## 4. Future Telemetry Needs

### State change events to broadcast (lightweight, publish on change)
- `sample.status` changed — per-sample status transitions (INACTIVE → PENDING → ACTIVE → COMPLETED / FAILED / CANCELLED)
- `stage.status` changed — per-stage status within a sample
- `task.status` changed — per-task status (maps to Autocontrol task lifecycle)
- `lh_interface.status` changed — LH interface UP / BUSY / ERROR / DOWN
- `layout` changed — bed layout updated (well volume/composition changes after job completion or operator edit)
- `device_list` changed — device registered or configuration updated

### Large data payloads (Claim Check pattern — do not carry in broker message body)
- **Job results from Gilson LH** — `PutSampleData` payloads contain full `sampleData` run records from Trilution. Save to `LHJobHistory` (SQLite, `persistent_state/lh_jobs.sqlite`); publish only `{job_id, retrieval_uri}`.
- **Completed sample history** — archived `Sample` objects (full method lists, stage history) stored in `persistent_state/completed_samples.sqlite`; reference by sample UUID.
- **Waste accumulation log** — per-job waste composition and volume (currently tracked in `waste_manager`); publish summary, not raw data.

### Reference / query endpoints (likely stay REST — not time-sensitive)
- `GET /GUI/GetLayout/` — bed layout (large JSON, operator-driven)
- `GET /GUI/GetAllMethods/` — method schema registry
- `GET /GUI/GetAllDevices/` — device registry
- `GET /LH/GetJob/<id>` — job history lookup
- `POST /LH/CheckFormulation/` — formulation feasibility solver
- All `/Materials/...` endpoints — material database CRUD
