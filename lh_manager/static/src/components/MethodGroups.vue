<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import {
  method_groups, refreshMethodGroups,
  fetchMethodGroup, createMethodGroup, updateMethodGroup, deleteMethodGroup,
  method_defs, grouped_method_defs,
} from '../store';
import type { MethodGroup, MethodGroupStep, ExposedField } from '../store';

const METHOD_TYPES = ['prepare', 'measure', 'transfer', 'init', 'shutdown', 'none'] as const;

interface StepField { name: string; display: string; type: string; }

// ── State ──────────────────────────────────────────────────────────────────

const selected_id = ref<string | null>(null);
const is_new = ref(false);
const saving = ref(false);
const error_msg = ref<string | null>(null);

function blank_group(): MethodGroup {
  return { id: '', name: '', description: null, steps: [], exposed_fields: [], method_type: null };
}
const editing = ref<MethodGroup>(blank_group());

// ── Schema helpers ──────────────────────────────────────────────────────────

function fields_for_step(step_index: number): StepField[] {
  const step = editing.value.steps[step_index];
  if (!step?.method_name) return [];
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

function infer_field_type(step_index: number, field_name: string): string {
  const step = editing.value.steps[step_index];
  if (!step?.method_name || !field_name) return '';
  const prop = method_defs.value[step.method_name]?.schema?.properties?.[field_name] as any;
  if (!prop) return '';
  if ('$ref' in prop) return prop['$ref'].replace('#/$defs/', '');
  return prop.type ?? '';
}

// ── Field binding helpers ───────────────────────────────────────────────────

function is_exposed(step: MethodGroupStep, field_name: string): boolean {
  const v = step.parameters?.[field_name];
  return v !== undefined && v !== null && typeof v === 'object' && '$ref' in (v as object);
}

// Returns the part of $ref after "input." — this is the SubProtocol input name
function get_ref_key(step: MethodGroupStep, field_name: string): string {
  const ref: string = (step.parameters?.[field_name] as any)?.$ref ?? '';
  return ref.startsWith('input.') ? ref.slice(6) : ref;
}

// Toggle a field between static literal and exposed ($ref) binding
function toggle_expose(step_index: number, step: MethodGroupStep, field_name: string) {
  if (!step.parameters) step.parameters = {};
  if (is_exposed(step, field_name)) {
    // Expose → Static: replace $ref with empty literal, remove from exposed_fields
    step.parameters[field_name] = '';
    editing.value.exposed_fields = editing.value.exposed_fields.filter(
      ef => !(ef.step_index === step_index && ef.field_name === field_name)
    );
  } else {
    // Static → Expose: store $ref, auto-add exposed_fields entry
    step.parameters[field_name] = { '$ref': `input.${field_name}` };
    if (!editing.value.exposed_fields.some(ef => ef.step_index === step_index && ef.field_name === field_name)) {
      editing.value.exposed_fields.push({
        field_name,
        display_name: field_name,
        type: infer_field_type(step_index, field_name),
        step_index,
        is_static: false,
        static_value: '',
      });
    }
  }
  step.parameters = { ...step.parameters };
}

function set_static_value(step: MethodGroupStep, field_name: string, raw: string, field_type: string) {
  if (!step.parameters) step.parameters = {};
  const numTypes = ['number', 'integer', 'float'];
  if (numTypes.includes(field_type)) {
    step.parameters[field_name] = parseFloat(raw) || raw;
  } else if (field_type === 'array') {
    try { step.parameters[field_name] = JSON.parse(raw); } catch { step.parameters[field_name] = raw; }
  } else {
    step.parameters[field_name] = raw;
  }
  step.parameters = { ...step.parameters };
}

// When user edits the input key in the exposed fields summary, sync $ref in step parameters
function on_ref_key_change(ef: ExposedField, new_key: string) {
  const step = editing.value.steps[ef.step_index];
  if (step?.parameters) {
    step.parameters[ef.field_name] = { '$ref': `input.${new_key}` };
    step.parameters = { ...step.parameters };
  }
}

// ── Lifecycle & CRUD ────────────────────────────────────────────────────────

onMounted(async () => { await refreshMethodGroups(); });

async function select_group(id: string) {
  error_msg.value = null;
  is_new.value = false;
  selected_id.value = id;
  editing.value = await fetchMethodGroup(id);
}

function new_group() {
  error_msg.value = null;
  selected_id.value = null;
  is_new.value = true;
  editing.value = blank_group();
}

async function save() {
  error_msg.value = null;
  if (!editing.value.name.trim()) { error_msg.value = 'Name is required.'; return; }
  saving.value = true;
  try {
    const payload: Partial<MethodGroup> = {
      name: editing.value.name.trim(),
      description: editing.value.description || null,
      method_type: editing.value.method_type || null,
      steps: editing.value.steps,
      exposed_fields: editing.value.exposed_fields,
    };
    if (is_new.value) {
      const new_id = await createMethodGroup(payload);
      await refreshMethodGroups();
      is_new.value = false;
      selected_id.value = new_id;
      editing.value = await fetchMethodGroup(new_id);
    } else {
      await updateMethodGroup(selected_id.value!, payload);
      await refreshMethodGroups();
    }
  } catch (e: any) {
    error_msg.value = String(e);
  } finally {
    saving.value = false;
  }
}

async function remove_group() {
  if (!selected_id.value) return;
  if (!confirm(`Delete method group "${editing.value.name}"?`)) return;
  await deleteMethodGroup(selected_id.value);
  await refreshMethodGroups();
  selected_id.value = null;
  is_new.value = false;
  editing.value = blank_group();
}

async function duplicate_group() {
  const new_name = prompt('Name for duplicate:', `Copy of ${editing.value.name}`);
  if (!new_name || !new_name.trim()) return;
  saving.value = true;
  error_msg.value = null;
  try {
    const payload: Partial<MethodGroup> = {
      name: new_name.trim(),
      description: editing.value.description || null,
      method_type: editing.value.method_type || null,
      steps: JSON.parse(JSON.stringify(editing.value.steps)),
      exposed_fields: JSON.parse(JSON.stringify(editing.value.exposed_fields)),
    };
    const new_id = await createMethodGroup(payload);
    await refreshMethodGroups();
    is_new.value = false;
    selected_id.value = new_id;
    editing.value = await fetchMethodGroup(new_id);
  } catch (e: any) {
    error_msg.value = String(e);
  } finally {
    saving.value = false;
  }
}

// ── Steps ───────────────────────────────────────────────────────────────────

function add_step() {
  editing.value.steps.push({ method_name: '', parameters: {}, composition_source: false });
}

function remove_step(i: number) {
  editing.value.steps.splice(i, 1);
  editing.value.exposed_fields = editing.value.exposed_fields
    .filter(ef => ef.step_index !== i)
    .map(ef => ({ ...ef, step_index: ef.step_index > i ? ef.step_index - 1 : ef.step_index }));
}

function move_step(i: number, dir: -1 | 1) {
  const j = i + dir;
  if (j < 0 || j >= editing.value.steps.length) return;
  const s = editing.value.steps;
  [s[i], s[j]] = [s[j], s[i]];
  editing.value.exposed_fields = editing.value.exposed_fields.map(ef => {
    if (ef.step_index === i) return { ...ef, step_index: j };
    if (ef.step_index === j) return { ...ef, step_index: i };
    return ef;
  });
}

// When the device method is changed, seed parameters from schema defaults and clear exposed fields
function on_method_change(step_index: number, step: MethodGroupStep) {
  const props = method_defs.value[step.method_name ?? '']?.schema?.properties as Record<string, any> ?? {};
  const defaults: Record<string, any> = {};
  for (const [f, prop] of Object.entries(props)) {
    if (prop != null && 'default' in prop) defaults[f] = prop.default;
  }
  step.parameters = defaults;
  editing.value.exposed_fields = editing.value.exposed_fields.filter(ef => ef.step_index !== step_index);
}
</script>

<template>
  <div class="d-flex flex-row flex-grow-1 overflow-hidden h-100">

    <!-- Left: list -->
    <div class="border-end overflow-auto" style="min-width: 220px; max-width: 280px;">
      <div class="p-2 border-bottom d-flex justify-content-between align-items-center">
        <span class="fw-semibold small">Method Groups</span>
        <button class="btn btn-sm btn-outline-primary" @click="new_group">+ New</button>
      </div>
      <ul class="list-group list-group-flush">
        <li v-for="mg in method_groups" :key="mg.id"
          class="list-group-item list-group-item-action py-1 px-2 small"
          :class="{ active: mg.id === selected_id }"
          @click="select_group(mg.id)" style="cursor: pointer;">
          <div class="fw-semibold text-truncate">{{ mg.name }}</div>
          <div class="text-muted" style="font-size:0.75rem;">{{ mg.method_type ?? '—' }}</div>
        </li>
        <li v-if="method_groups.length === 0" class="list-group-item text-muted small fst-italic py-2 px-2">
          No method groups yet.
        </li>
      </ul>
    </div>

    <!-- Right: editor -->
    <div class="flex-grow-1 overflow-auto p-3">
      <div v-if="!selected_id && !is_new" class="text-muted fst-italic mt-4 text-center">
        Select a method group or click <strong>+ New</strong>.
      </div>

      <div v-else>
        <div class="d-flex align-items-center mb-3 gap-2">
          <h5 class="mb-0">{{ is_new ? 'New Method Group' : editing.name }}</h5>
          <div class="ms-auto d-flex gap-2">
            <button class="btn btn-sm btn-primary" :disabled="saving" @click="save">
              {{ saving ? 'Saving…' : 'Save' }}
            </button>
            <button v-if="!is_new" class="btn btn-sm btn-outline-secondary" :disabled="saving" @click="duplicate_group">Duplicate</button>
            <button v-if="!is_new" class="btn btn-sm btn-outline-danger" @click="remove_group">Delete</button>
          </div>
        </div>
        <div v-if="error_msg" class="alert alert-danger py-1 small">{{ error_msg }}</div>

        <!-- Identity -->
        <div class="row g-2 mb-3">
          <div class="col-md-4">
            <label class="form-label small mb-1">Name</label>
            <input class="form-control form-control-sm" v-model="editing.name" placeholder="e.g. FormulateAndLoad" />
          </div>
          <div class="col-md-4">
            <label class="form-label small mb-1">Description</label>
            <input class="form-control form-control-sm" v-model="editing.description" placeholder="Optional" />
          </div>
          <div class="col-md-3">
            <label class="form-label small mb-1">Method type</label>
            <select class="form-select form-select-sm" v-model="editing.method_type">
              <option :value="null">— unset —</option>
              <option v-for="t in METHOD_TYPES" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
        </div>

        <!-- ── Steps ──────────────────────────────────────────────────── -->
        <div class="mb-4">
          <div class="d-flex align-items-center mb-2">
            <span class="fw-semibold small">Steps</span>
            <button class="btn btn-sm btn-outline-secondary ms-2" @click="add_step">+ Add step</button>
          </div>
          <div v-if="editing.steps.length === 0" class="text-muted small fst-italic">No steps yet.</div>

          <div v-for="(step, i) in editing.steps" :key="i" class="border rounded mb-2">

            <!-- Step header -->
            <div class="d-flex align-items-center gap-2 p-2 bg-light border-bottom flex-wrap">
              <select class="form-select form-select-sm" style="min-width:220px; flex:1"
                v-model="step.method_name" @change="on_method_change(i, step)">
                <option value="">— select device method —</option>
                <optgroup v-for="(methods, origin) in grouped_method_defs" :label="String(origin)">
                  <option v-for="[mname] of methods" :key="mname" :value="mname">{{ mname }}</option>
                </optgroup>
              </select>

              <div class="form-check form-check-inline mb-0">
                <input class="form-check-input" type="checkbox" :id="`cs-${i}`" v-model="step.composition_source" />
                <label class="form-check-label small" :for="`cs-${i}`">Composition source</label>
              </div>

              <div class="ms-auto d-flex gap-1">
                <button class="btn btn-sm btn-outline-secondary p-1" :disabled="i === 0" @click="move_step(i, -1)">▲</button>
                <button class="btn btn-sm btn-outline-secondary p-1" :disabled="i === editing.steps.length - 1" @click="move_step(i, 1)">▼</button>
                <button class="btn btn-sm btn-outline-danger p-1" @click="remove_step(i)">✕</button>
              </div>
            </div>

            <!-- Per-field binding table -->
            <div class="p-2">
              <div v-if="!step.method_name" class="text-muted small fst-italic py-1">
                Select a device method above.
              </div>
              <div v-else-if="fields_for_step(i).length === 0" class="text-muted small fst-italic py-1">
                No schema available for this method.
              </div>
              <table v-else class="table table-sm table-borderless mb-0 align-middle" style="font-size:0.82rem;">
                <thead>
                  <tr class="border-bottom">
                    <th class="text-muted fw-normal" style="width:170px">Field</th>
                    <th class="text-muted fw-normal" style="width:100px">Binding</th>
                    <th class="text-muted fw-normal">Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="field in fields_for_step(i)" :key="field.name">
                    <!-- Field label -->
                    <td class="pe-2" style="white-space:nowrap">
                      {{ field.display }}
                      <span v-if="field.type" class="text-muted ms-1" style="font-size:0.7rem; opacity:0.6;">({{ field.type }})</span>
                    </td>

                    <!-- Static / Expose toggle -->
                    <td>
                      <div class="form-check form-switch mb-0">
                        <input class="form-check-input" type="checkbox"
                          :id="`exp-${i}-${field.name}`"
                          :checked="is_exposed(step, field.name)"
                          @change="toggle_expose(i, step, field.name)"
                        />
                        <label class="form-check-label small"
                          :for="`exp-${i}-${field.name}`"
                          :class="is_exposed(step, field.name) ? 'text-success fw-semibold' : 'text-muted'">
                          {{ is_exposed(step, field.name) ? 'expose' : 'static' }}
                        </label>
                      </div>
                    </td>

                    <!-- Value: editable literal (static) or $ref badge (exposed) -->
                    <td>
                      <input v-if="!is_exposed(step, field.name)"
                        class="form-control form-control-sm"
                        :type="field.type === 'number' || field.type === 'integer' ? 'number' : 'text'"
                        :value="Array.isArray(step.parameters?.[field.name]) ? JSON.stringify(step.parameters?.[field.name]) : (step.parameters?.[field.name] ?? '')"
                        @input="set_static_value(step, field.name, ($event.target as HTMLInputElement).value, field.type)"
                      />
                      <code v-else class="small text-success">
                        input.{{ get_ref_key(step, field.name) }}
                      </code>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

          </div><!-- end step -->
        </div>

        <!-- ── Parameters (auto-derived from Expose toggles above) ──────── -->
        <div class="mb-3">
          <div class="fw-semibold small mb-1">
            Parameters
            <span class="text-muted fw-normal">(auto-derived from ▲ — exposed = caller provides; static = baked-in value)</span>
          </div>
          <div v-if="editing.exposed_fields.length === 0" class="text-muted small fst-italic">
            No parameters — use Expose toggles above.
          </div>
          <table v-else class="table table-sm table-bordered mb-0 align-middle" style="font-size:0.82rem;">
            <thead class="table-light">
              <tr>
                <th>Step / device field</th>
                <th>Type</th>
                <th>Mode</th>
                <th>Value / Input key</th>
                <th>Display name</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(ef, i) in editing.exposed_fields" :key="i">
                <td class="text-muted small">
                  <span class="font-monospace">{{ ef.field_name }}</span>
                  <span class="ms-1" style="opacity:0.6;">step {{ ef.step_index }}</span>
                </td>
                <td class="text-muted small font-monospace">{{ ef.type }}</td>
                <td style="width:105px">
                  <div class="form-check form-switch mb-0">
                    <input class="form-check-input" type="checkbox" :id="`mg-static-${i}`" v-model="ef.is_static" />
                    <label class="form-check-label small" :for="`mg-static-${i}`"
                      :class="ef.is_static ? 'text-muted' : 'text-success fw-semibold'">
                      {{ ef.is_static ? 'static' : 'exposed' }}
                    </label>
                  </div>
                </td>
                <td style="width:160px">
                  <input v-if="ef.is_static"
                    class="form-control form-control-sm"
                    :type="ef.type === 'number' || ef.type === 'integer' ? 'number' : 'text'"
                    v-model="ef.static_value" placeholder="value"
                  />
                  <input v-else
                    class="form-control form-control-sm font-monospace" style="font-size:0.8rem"
                    :value="get_ref_key(editing.steps[ef.step_index], ef.field_name)"
                    @change="on_ref_key_change(ef, ($event.target as HTMLInputElement).value)"
                  />
                </td>
                <td>
                  <input class="form-control form-control-sm" v-model="ef.display_name" />
                </td>
              </tr>
            </tbody>
          </table>
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
