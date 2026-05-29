<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import {
  subprotocols, refreshSubprotocols,
  fetchSubprotocol, createSubprotocol, updateSubprotocol, deleteSubprotocol,
  method_defs, grouped_method_defs, method_groups, refreshMethodGroups,
  fetchMethodGroup,
} from '../store';
import type { Subprotocol, SubprotocolStep, ExposedField } from '../store';

const METHOD_TYPES = ['prepare', 'measure', 'transfer', 'init', 'shutdown', 'none'] as const;
const PARAM_TYPES = ['number', 'boolean', 'Composition'] as const;
const STEP_TYPES = ['method', 'method_group', 'subprotocol'] as const;

// ── Types ────────────────────────────────────────────────────────────────────

interface InputParam {
  name: string;
  type: string;
  display_name: string;
  is_static: boolean;
  static_value: string;
  default_value: string;
}

interface StepField {
  name: string;
  display: string;
  type: string;   // 'number' | 'string' | 'WellLocation' | etc.
}

type FieldMode = 'literal' | 'ref' | 'alloc';

// ── State ─────────────────────────────────────────────────────────────────────

const selected_id = ref<string | null>(null);
const is_new = ref(false);
const saving = ref(false);
const error_msg = ref<string | null>(null);

const editing = ref<Subprotocol>(blank_subprotocol());

// Parameters (inputs) stored as array for the UI; synced to/from the dict on load/save
const input_params_list = ref<InputParam[]>([]);
const new_input = ref<InputParam>({ name: '', type: 'number', display_name: '', is_static: false, static_value: '', default_value: '' });

// Allocations
const new_alloc = ref('');

// On-demand caches for foreign schemas
const mg_exposed_fields = ref<Record<string, ExposedField[]>>({});      // keyed by mg name
const sp_inputs_cache = ref<Record<string, InputParam[]>>({});           // keyed by sp name

// ── Helpers ───────────────────────────────────────────────────────────────────

function blank_subprotocol(): Subprotocol {
  return { id: '', name: '', steps: [], execution: 'sequential', allocations: [], inputs: {}, outputs: {}, method_type: null };
}

function sync_inputs_from_editing() {
  const inputs = editing.value.inputs ?? {};
  input_params_list.value = Object.entries(inputs).map(([name, v]: [string, any]) => ({
    name,
    type: typeof v === 'object' ? (v.type ?? '') : '',
    display_name: typeof v === 'object' ? (v.display_name ?? '') : '',
    is_static: typeof v === 'object' ? (v.is_static ?? false) : false,
    static_value: typeof v === 'object' ? String(v.static_value ?? '') : '',
    default_value: typeof v === 'object' ? String(v.default_value ?? '') : '',
  }));
}

function inputs_to_dict(): Record<string, any> {
  return Object.fromEntries(
    input_params_list.value.map(p => {
      const v: any = { type: p.type, display_name: p.display_name };
      if (p.is_static) {
        v.is_static = true; v.static_value = p.static_value;
      } else if (p.default_value !== '') {
        v.default_value = p.default_value;
      }
      return [p.name, v];
    })
  );
}

// Fetch exposed fields for a method_group (idempotent)
async function ensure_mg_fields(name: string) {
  if (!name || name in mg_exposed_fields.value) return;
  const mg = method_groups.value.find(m => m.name === name);
  if (mg) {
    const full = await fetchMethodGroup(mg.id);
    mg_exposed_fields.value = { ...mg_exposed_fields.value, [name]: full.exposed_fields };
  }
}

// Fetch inputs for a nested subprotocol (idempotent, skip self)
async function ensure_sp_inputs(name: string) {
  if (!name || name in sp_inputs_cache.value) return;
  const found = subprotocols.value.find(s => s.name === name);
  if (found && found.id !== selected_id.value) {
    const full = await fetchSubprotocol(found.id);
    const inputs = full.inputs ?? {};
    sp_inputs_cache.value = {
      ...sp_inputs_cache.value,
      [name]: Object.entries(inputs).map(([k, v]: [string, any]) => ({
        name: k, type: v?.type ?? '', display_name: v?.display_name ?? '',
        is_static: v?.is_static ?? false, static_value: String(v?.static_value ?? ''),
      })),
    };
  }
}

// Resolve all foreign schemas referenced in loaded steps
async function prefetch_step_schemas(steps: SubprotocolStep[]) {
  for (const step of steps) {
    if (step.type === 'method_group' && step.method_group_name) await ensure_mg_fields(step.method_group_name);
    if (step.type === 'subprotocol' && step.subprotocol_name) await ensure_sp_inputs(step.subprotocol_name);
  }
}

// Return the renderable fields for a step based on its type and selected name
function get_step_fields(step: SubprotocolStep): StepField[] {
  if (step.type === 'method' && step.method_name) {
    const mdef = method_defs.value[step.method_name];
    if (!mdef) return [];
    return mdef.fields.map(f => {
      const prop = mdef.schema?.properties?.[f] as any;
      let type = '';
      if (prop) {
        if ('$ref' in prop) type = prop['$ref'].replace('#/$defs/', '');
        else type = prop.type ?? '';
      }
      return { name: f, display: f, type };
    });
  }
  if (step.type === 'method_group' && step.method_group_name) {
    return (mg_exposed_fields.value[step.method_group_name] ?? []).map(ef => ({
      name: ef.field_name, display: ef.display_name || ef.field_name, type: ef.type,
    }));
  }
  if (step.type === 'subprotocol' && step.subprotocol_name) {
    return (sp_inputs_cache.value[step.subprotocol_name] ?? []).map(p => ({
      name: p.name, display: p.display_name || p.name, type: p.type,
    }));
  }
  return [];
}

// Field value mode detection
function get_field_mode(value: any): FieldMode {
  if (value && typeof value === 'object') {
    if ('$ref' in value) return 'ref';
    if ('$alloc' in value) return 'alloc';
  }
  return 'literal';
}

function get_ref_param(value: any): string {
  const ref: string = value?.$ref ?? '';
  return ref.startsWith('input.') ? ref.slice(6) : ref;
}

function get_alloc_name(value: any): string {
  return value?.$alloc ?? '';
}

function set_field_mode(step: SubprotocolStep, field: string, mode: FieldMode) {
  if (!step.parameters) step.parameters = {};
  if (mode === 'literal') {
    step.parameters[field] = '';
  } else if (mode === 'ref') {
    const first = input_params_list.value[0]?.name ?? '';
    step.parameters[field] = { '$ref': `input.${first}` };
  } else {
    const first = editing.value.allocations[0] ?? '';
    step.parameters[field] = { '$alloc': first };
  }
  step.parameters = { ...step.parameters };
}

function set_literal_value(step: SubprotocolStep, field: string, raw: string, field_type: string) {
  if (!step.parameters) step.parameters = {};
  const numTypes = ['number', 'integer', 'float'];
  if (numTypes.includes(field_type)) {
    step.parameters[field] = parseFloat(raw) || raw;
  } else if (field_type === 'array') {
    try { step.parameters[field] = JSON.parse(raw); } catch { step.parameters[field] = raw; }
  } else {
    step.parameters[field] = raw;
  }
  step.parameters = { ...step.parameters };
}

function set_ref_value(step: SubprotocolStep, field: string, param_name: string) {
  if (!step.parameters) step.parameters = {};
  step.parameters[field] = { '$ref': `input.${param_name}` };
  step.parameters = { ...step.parameters };
}

function set_alloc_value(step: SubprotocolStep, field: string, alloc_name: string) {
  if (!step.parameters) step.parameters = {};
  step.parameters[field] = { '$alloc': alloc_name };
  step.parameters = { ...step.parameters };
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await Promise.all([refreshSubprotocols(), refreshMethodGroups()]);
});

// ── CRUD ──────────────────────────────────────────────────────────────────────

async function select_subprotocol(id: string) {
  error_msg.value = null;
  is_new.value = false;
  selected_id.value = id;
  const sp = await fetchSubprotocol(id);
  editing.value = sp;
  sync_inputs_from_editing();
  await prefetch_step_schemas(sp.steps);
}

function new_subprotocol() {
  error_msg.value = null;
  selected_id.value = null;
  is_new.value = true;
  editing.value = blank_subprotocol();
  input_params_list.value = [];
  new_alloc.value = '';
}

async function save() {
  error_msg.value = null;
  if (!editing.value.name.trim()) { error_msg.value = 'Name is required.'; return; }
  saving.value = true;
  try {
    const payload: Partial<Subprotocol> = {
      name: editing.value.name.trim(),
      steps: editing.value.steps,
      execution: editing.value.execution,
      allocations: editing.value.allocations,
      inputs: inputs_to_dict(),
      outputs: editing.value.outputs,
      method_type: editing.value.method_type || null,
    };
    if (is_new.value) {
      const new_id = await createSubprotocol(payload);
      await refreshSubprotocols();
      is_new.value = false;
      selected_id.value = new_id;
      editing.value = await fetchSubprotocol(new_id);
      sync_inputs_from_editing();
    } else {
      await updateSubprotocol(selected_id.value!, payload);
      await refreshSubprotocols();
    }
  } catch (e: any) {
    error_msg.value = String(e);
  } finally {
    saving.value = false;
  }
}

async function remove_subprotocol() {
  if (!selected_id.value) return;
  if (!confirm(`Delete subprotocol "${editing.value.name}"?`)) return;
  await deleteSubprotocol(selected_id.value);
  await refreshSubprotocols();
  selected_id.value = null;
  is_new.value = false;
  editing.value = blank_subprotocol();
  input_params_list.value = [];
}

async function duplicate_subprotocol() {
  const new_name = prompt('Name for duplicate:', `Copy of ${editing.value.name}`);
  if (!new_name || !new_name.trim()) return;
  saving.value = true;
  error_msg.value = null;
  try {
    const payload: Partial<Subprotocol> = {
      name: new_name.trim(),
      steps: JSON.parse(JSON.stringify(editing.value.steps)),
      execution: editing.value.execution,
      allocations: [...editing.value.allocations],
      inputs: inputs_to_dict(),
      outputs: editing.value.outputs,
      method_type: editing.value.method_type || null,
    };
    const new_id = await createSubprotocol(payload);
    await refreshSubprotocols();
    is_new.value = false;
    selected_id.value = new_id;
    editing.value = await fetchSubprotocol(new_id);
    sync_inputs_from_editing();
  } catch (e: any) {
    error_msg.value = String(e);
  } finally {
    saving.value = false;
  }
}

// ── Parameters (inputs) ───────────────────────────────────────────────────────

function add_input() {
  const name = new_input.value.name.trim();
  if (!name || input_params_list.value.some(p => p.name === name)) return;
  input_params_list.value.push({ ...new_input.value, name });
  new_input.value = { name: '', type: 'number', display_name: '', is_static: false, static_value: '', default_value: '' };
}

function remove_input(i: number) {
  input_params_list.value.splice(i, 1);
}

// ── Allocations ───────────────────────────────────────────────────────────────

function add_alloc() {
  const name = new_alloc.value.trim();
  if (name && !editing.value.allocations.includes(name)) editing.value.allocations.push(name);
  new_alloc.value = '';
}

function remove_alloc(i: number) {
  editing.value.allocations.splice(i, 1);
}

// ── Outputs ───────────────────────────────────────────────────────────────────

const OUTPUT_TYPES = ['QCMDData', 'ReflData', 'ReflAnalysisData', 'FloatWithUncertainty'] as const;
const new_output = ref({ name: '', step_id: '', type: 'QCMDData' as string });

function add_output() {
  const name = new_output.value.name.trim();
  if (!name || !new_output.value.step_id) return;
  if (!editing.value.outputs) editing.value.outputs = {};
  editing.value.outputs = { ...editing.value.outputs, [name]: { step_id: new_output.value.step_id, type: new_output.value.type } };
  new_output.value = { name: '', step_id: '', type: 'QCMDData' };
}

function remove_output(name: string) {
  if (!editing.value.outputs) return;
  const updated = { ...editing.value.outputs };
  delete updated[name];
  editing.value.outputs = updated;
}

// ── Steps ─────────────────────────────────────────────────────────────────────

function blank_step(): SubprotocolStep {
  return { id: crypto.randomUUID().slice(0, 8), type: 'method', method_name: '', parameters: {} };
}

function add_step() { editing.value.steps.push(blank_step()); }

function remove_step(i: number) { editing.value.steps.splice(i, 1); }

function move_step(i: number, dir: -1 | 1) {
  const j = i + dir;
  if (j < 0 || j >= editing.value.steps.length) return;
  const s = editing.value.steps;
  [s[i], s[j]] = [s[j], s[i]];
}

function reset_step_name(step: SubprotocolStep) {
  step.method_name = '';
  step.method_group_name = undefined;
  step.subprotocol_name = undefined;
  step.parameters = {};
}

async function on_mg_change(step: SubprotocolStep, name: string) {
  step.method_group_name = name;
  step.parameters = {};
  await ensure_mg_fields(name);
}

async function on_sp_change(step: SubprotocolStep, name: string) {
  step.subprotocol_name = name;
  step.parameters = {};
  await ensure_sp_inputs(name);
}

function on_method_change(step: SubprotocolStep) {
  const props = method_defs.value[step.method_name ?? '']?.schema?.properties as Record<string, any> ?? {};
  const defaults: Record<string, any> = {};
  for (const [f, prop] of Object.entries(props)) {
    if (prop != null && 'default' in prop) defaults[f] = prop.default;
  }
  step.parameters = defaults;
}

const method_group_names = computed(() => method_groups.value.map(mg => mg.name));
const subprotocol_names = computed(() => subprotocols.value.map(sp => sp.name));
</script>

<template>
  <div class="d-flex flex-row flex-grow-1 overflow-hidden h-100">

    <!-- Left: list -->
    <div class="border-end overflow-auto" style="min-width: 220px; max-width: 280px;">
      <div class="p-2 border-bottom d-flex justify-content-between align-items-center">
        <span class="fw-semibold small">SubProtocols</span>
        <button class="btn btn-sm btn-outline-primary" @click="new_subprotocol">+ New</button>
      </div>
      <ul class="list-group list-group-flush">
        <li v-for="sp in subprotocols" :key="sp.id"
          class="list-group-item list-group-item-action py-1 px-2 small"
          :class="{ active: sp.id === selected_id }"
          @click="select_subprotocol(sp.id)" style="cursor: pointer;">
          <div class="fw-semibold text-truncate">{{ sp.name }}</div>
        </li>
        <li v-if="subprotocols.length === 0" class="list-group-item text-muted small fst-italic py-2 px-2">
          No subprotocols yet.
        </li>
      </ul>
    </div>

    <!-- Right: editor -->
    <div class="flex-grow-1 overflow-auto p-3">
      <div v-if="!selected_id && !is_new" class="text-muted fst-italic mt-4 text-center">
        Select a subprotocol or click <strong>+ New</strong>.
      </div>

      <div v-else>
        <!-- Header row -->
        <div class="d-flex align-items-center mb-3 gap-2">
          <h5 class="mb-0">{{ is_new ? 'New SubProtocol' : editing.name }}</h5>
          <div class="ms-auto d-flex gap-2">
            <button class="btn btn-sm btn-primary" :disabled="saving" @click="save">
              {{ saving ? 'Saving…' : 'Save' }}
            </button>
            <button v-if="!is_new" class="btn btn-sm btn-outline-secondary" :disabled="saving" @click="duplicate_subprotocol">Duplicate</button>
            <button v-if="!is_new" class="btn btn-sm btn-outline-danger" @click="remove_subprotocol">Delete</button>
          </div>
        </div>
        <div v-if="error_msg" class="alert alert-danger py-1 small">{{ error_msg }}</div>

        <!-- Identity fields -->
        <div class="row g-2 mb-3">
          <div class="col-md-4">
            <label class="form-label small mb-1">Name</label>
            <input class="form-control form-control-sm" v-model="editing.name" placeholder="e.g. BaseMeasurement" />
          </div>
          <div class="col-md-3">
            <label class="form-label small mb-1">Method type</label>
            <select class="form-select form-select-sm" v-model="editing.method_type">
              <option :value="null">— unset —</option>
              <option v-for="t in METHOD_TYPES" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
          <div class="col-md-3">
            <label class="form-label small mb-1">Execution</label>
            <select class="form-select form-select-sm" v-model="editing.execution">
              <option value="sequential">sequential</option>
              <option value="parallel">parallel</option>
            </select>
          </div>
        </div>

        <!-- ── Parameters (inputs) ─────────────────────────────────────────── -->
        <div class="mb-4">
          <div class="fw-semibold small mb-2">Parameters <span class="text-muted fw-normal">(exposed = caller provides; static = baked-in value)</span></div>
          <div class="d-flex gap-1 mb-2 align-items-end flex-wrap">
            <div>
              <label class="form-label small mb-1">Name</label>
              <input class="form-control form-control-sm" style="width:130px" v-model="new_input.name"
                placeholder="e.g. volume" @keydown.enter="add_input" />
            </div>
            <div>
              <label class="form-label small mb-1">Type</label>
              <select class="form-select form-select-sm" style="width:130px" v-model="new_input.type">
                <option v-for="t in PARAM_TYPES" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>
            <div>
              <label class="form-label small mb-1">Display name</label>
              <input class="form-control form-control-sm" style="width:170px" v-model="new_input.display_name"
                placeholder="Volume (mL)" />
            </div>
            <button class="btn btn-sm btn-outline-secondary" style="height:31px" @click="add_input">Add</button>
          </div>
          <div v-if="input_params_list.length === 0" class="text-muted small fst-italic">No parameters defined.</div>
          <table v-else class="table table-sm table-bordered mb-0" style="font-size:0.82rem;">
            <thead class="table-light">
              <tr><th>Name</th><th>Type</th><th>Display name</th><th>Mode</th><th>Value / Default</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="(p, i) in input_params_list" :key="i">
                <td class="font-monospace">{{ p.name }}</td>
                <td>{{ p.type }}</td>
                <td style="min-width:120px">
                  <input class="form-control form-control-sm border-0 p-0" v-model="p.display_name" />
                </td>
                <td style="width:105px">
                  <div class="form-check form-switch mb-0">
                    <input class="form-check-input" type="checkbox" :id="`sp-static-${i}`" v-model="p.is_static" />
                    <label class="form-check-label small" :for="`sp-static-${i}`"
                      :class="p.is_static ? 'text-muted' : 'text-success fw-semibold'">
                      {{ p.is_static ? 'static' : 'exposed' }}
                    </label>
                  </div>
                </td>
                <td style="width:140px">
                  <input v-if="p.is_static"
                    class="form-control form-control-sm"
                    :type="p.type === 'number' || p.type === 'integer' ? 'number' : 'text'"
                    placeholder="value"
                    title="Static value — baked in, caller cannot override"
                    v-model="p.static_value"
                  />
                  <input v-else
                    class="form-control form-control-sm border-secondary-subtle text-muted"
                    :type="p.type === 'number' || p.type === 'integer' ? 'number' : 'text'"
                    placeholder="default (optional)"
                    title="Default — pre-filled for the caller, can be changed"
                    v-model="p.default_value"
                  />
                </td>
                <td><button class="btn btn-sm btn-outline-danger p-0 px-1" @click="remove_input(i)">✕</button></td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- ── Allocations ─────────────────────────────────────────────────── -->
        <div class="mb-4">
          <div class="fw-semibold small mb-2">Allocations <span class="text-muted fw-normal">(UUIDs minted per run, referenced as ⊕alloc)</span></div>
          <div class="d-flex gap-2 align-items-center mb-2">
            <input class="form-control form-control-sm" style="max-width:200px"
              v-model="new_alloc" placeholder="e.g. well_id" @keydown.enter="add_alloc" />
            <button class="btn btn-sm btn-outline-secondary" @click="add_alloc">Add</button>
          </div>
          <div v-if="editing.allocations.length === 0" class="text-muted small fst-italic">No allocations.</div>
          <div class="d-flex flex-wrap gap-1">
            <span v-for="(alloc, i) in editing.allocations" :key="i"
              class="badge bg-warning text-dark d-inline-flex align-items-center gap-1" style="font-size:0.8rem;">
              ⊕ {{ alloc }}
              <button type="button" class="btn-close" style="font-size:0.55rem" @click="remove_alloc(i)"></button>
            </span>
          </div>
        </div>

        <!-- ── Outputs ────────────────────────────────────────────────────── -->
        <div class="mb-4">
          <div class="fw-semibold small mb-2">Outputs <span class="text-muted fw-normal">(declare which step produces each retrievable result)</span></div>
          <div class="d-flex gap-1 mb-2 align-items-end flex-wrap">
            <div>
              <label class="form-label small mb-1">Name</label>
              <input class="form-control form-control-sm" style="width:140px" v-model="new_output.name"
                placeholder="e.g. measurement" @keydown.enter="add_output" />
            </div>
            <div>
              <label class="form-label small mb-1">Step ID</label>
              <select class="form-select form-select-sm" style="width:220px" v-model="new_output.step_id">
                <option value="">— select step —</option>
                <option v-for="step in editing.steps" :key="step.id" :value="step.id">
                  {{ step.id }} ({{ step.method_name || step.method_group_name || step.subprotocol_name || '?' }})
                </option>
              </select>
            </div>
            <div>
              <label class="form-label small mb-1">Type</label>
              <select class="form-select form-select-sm" style="width:190px" v-model="new_output.type">
                <option v-for="t in OUTPUT_TYPES" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>
            <button class="btn btn-sm btn-outline-secondary" style="height:31px" @click="add_output">Add</button>
          </div>
          <div v-if="Object.keys(editing.outputs ?? {}).length === 0" class="text-muted small fst-italic">No outputs defined.</div>
          <table v-else class="table table-sm table-bordered mb-0" style="font-size:0.82rem;">
            <thead class="table-light">
              <tr><th>Name</th><th>Step ID</th><th>Type</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="(def, name) in (editing.outputs ?? {})" :key="name">
                <td class="font-monospace">{{ name }}</td>
                <td class="font-monospace text-muted">{{ def.step_id }}</td>
                <td>{{ def.type }}</td>
                <td><button class="btn btn-sm btn-outline-danger p-0 px-1" @click="remove_output(String(name))">✕</button></td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- ── Steps ──────────────────────────────────────────────────────── -->
        <div class="mb-3">
          <div class="d-flex align-items-center mb-2">
            <span class="fw-semibold small">Steps</span>
            <button class="btn btn-sm btn-outline-secondary ms-2" @click="add_step">+ Add step</button>
          </div>
          <div v-if="editing.steps.length === 0" class="text-muted small fst-italic">No steps yet.</div>

          <div v-for="(step, i) in editing.steps" :key="i" class="border rounded mb-2">

            <!-- Step header bar -->
            <div class="d-flex align-items-center gap-2 p-2 border-bottom bg-light flex-wrap">
              <!-- Step ID -->
              <input class="form-control form-control-sm font-monospace"
                style="width:90px; font-size:0.75rem" v-model="step.id" title="Step ID" />

              <!-- Type -->
              <select class="form-select form-select-sm" style="width:130px" v-model="step.type"
                @change="reset_step_name(step)">
                <option v-for="t in STEP_TYPES" :key="t" :value="t">{{ t }}</option>
              </select>

              <!-- Name selector (context-sensitive) -->
              <select v-if="step.type === 'method'" class="form-select form-select-sm" style="min-width:200px; flex:1"
                v-model="step.method_name" @change="on_method_change(step)">
                <option value="">— select method —</option>
                <optgroup v-for="(methods, origin) in grouped_method_defs" :label="String(origin)">
                  <option v-for="[mname] of methods" :key="mname" :value="mname">{{ mname }}</option>
                </optgroup>
              </select>

              <select v-else-if="step.type === 'method_group'" class="form-select form-select-sm" style="min-width:200px; flex:1"
                :value="step.method_group_name ?? ''"
                @change="on_mg_change(step, ($event.target as HTMLSelectElement).value)">
                <option value="">— select group —</option>
                <option v-for="name in method_group_names" :key="name" :value="name">{{ name }}</option>
              </select>

              <select v-else class="form-select form-select-sm" style="min-width:200px; flex:1"
                :value="step.subprotocol_name ?? ''"
                @change="on_sp_change(step, ($event.target as HTMLSelectElement).value)">
                <option value="">— select subprotocol —</option>
                <option v-for="name in subprotocol_names" :key="name" :value="name">{{ name }}</option>
              </select>

              <!-- Move / delete -->
              <div class="ms-auto d-flex gap-1">
                <button class="btn btn-sm btn-outline-secondary p-1" :disabled="i === 0" @click="move_step(i, -1)">▲</button>
                <button class="btn btn-sm btn-outline-secondary p-1" :disabled="i === editing.steps.length - 1" @click="move_step(i, 1)">▼</button>
                <button class="btn btn-sm btn-outline-danger p-1" @click="remove_step(i)">✕</button>
              </div>
            </div>

            <!-- Step fields -->
            <div class="p-2">
              <div v-if="get_step_fields(step).length === 0" class="text-muted small fst-italic py-1">
                {{
                  (step.type === 'method' && !step.method_name) ||
                  (step.type === 'method_group' && !step.method_group_name) ||
                  (step.type === 'subprotocol' && !step.subprotocol_name)
                    ? 'Select a name above to see parameters.'
                    : 'No schema available for this step.'
                }}
              </div>

              <table v-else class="table table-sm table-borderless mb-0 align-middle" style="font-size:0.82rem;">
                <tbody>
                  <tr v-for="field in get_step_fields(step)" :key="field.name">
                    <!-- Field label -->
                    <td class="text-muted pe-2" style="white-space:nowrap; width:150px;">
                      {{ field.display }}
                      <span v-if="field.type" class="text-muted ms-1" style="font-size:0.7rem; opacity:0.6;">({{ field.type }})</span>
                    </td>

                    <!-- Mode toggle -->
                    <td style="width:145px;">
                      <div class="btn-group btn-group-sm">
                        <button class="btn" style="font-size:0.7rem; padding:1px 6px;"
                          :class="get_field_mode(step.parameters?.[field.name]) === 'literal' ? 'btn-dark' : 'btn-outline-secondary'"
                          @click="set_field_mode(step, field.name, 'literal')" title="Literal value">val</button>
                        <button class="btn" style="font-size:0.7rem; padding:1px 6px;"
                          :class="get_field_mode(step.parameters?.[field.name]) === 'ref' ? 'btn-success' : 'btn-outline-success'"
                          @click="set_field_mode(step, field.name, 'ref')" title="Reference a parameter">→ param</button>
                        <button class="btn" style="font-size:0.7rem; padding:1px 6px;"
                          :class="get_field_mode(step.parameters?.[field.name]) === 'alloc' ? 'btn-warning' : 'btn-outline-warning'"
                          @click="set_field_mode(step, field.name, 'alloc')" title="Reference an allocation">⊕ alloc</button>
                      </div>
                    </td>

                    <!-- Value input -->
                    <td>
                      <!-- literal -->
                      <input v-if="get_field_mode(step.parameters?.[field.name]) === 'literal'"
                        class="form-control form-control-sm"
                        :type="field.type === 'number' || field.type === 'integer' ? 'number' : 'text'"
                        :value="Array.isArray(step.parameters?.[field.name]) ? JSON.stringify(step.parameters?.[field.name]) : (step.parameters?.[field.name] ?? '')"
                        @input="set_literal_value(step, field.name, ($event.target as HTMLInputElement).value, field.type)"
                      />
                      <!-- param ref -->
                      <select v-else-if="get_field_mode(step.parameters?.[field.name]) === 'ref'"
                        class="form-select form-select-sm"
                        :value="get_ref_param(step.parameters?.[field.name])"
                        @change="set_ref_value(step, field.name, ($event.target as HTMLSelectElement).value)">
                        <option value="">— param —</option>
                        <option v-for="p in input_params_list" :key="p.name" :value="p.name">
                          {{ p.display_name || p.name }}
                        </option>
                      </select>
                      <!-- alloc ref -->
                      <select v-else
                        class="form-select form-select-sm"
                        :value="get_alloc_name(step.parameters?.[field.name])"
                        @change="set_alloc_value(step, field.name, ($event.target as HTMLSelectElement).value)">
                        <option value="">— allocation —</option>
                        <option v-for="a in editing.allocations" :key="a" :value="a">{{ a }}</option>
                      </select>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

          </div><!-- end step -->
        </div>

      </div>
    </div>
  </div>
</template>

<style scoped>
.list-group-item.active {
  background-color: #0d6efd;
  border-color: #0d6efd;
}
</style>
