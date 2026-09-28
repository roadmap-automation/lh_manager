<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import {
  maintenance_samples,
  method_defs,
  grouped_method_defs,
  num_channels,
  sample_status,
  submit_maintenance_run,
  dismiss_maintenance,
  subprotocols,
  subprotocol_schemas,
  refreshSubprotocols,
  method_groups,
  refreshMethodGroups,
  fetchMethodGroup,
} from '../store';
import type { ExposedField, MethodGroup } from '../store';
import MethodList from './MethodList.vue';

// ---------------------------------------------------------------------------
// Selection state
// ---------------------------------------------------------------------------

const selected_method = ref<string>('');

const selected_kind = computed(() => {
  const idx = selected_method.value.indexOf(':');
  return idx > 0
    ? (selected_method.value.slice(0, idx) as 'method' | 'method_group' | 'subprotocol')
    : 'method';
});

const selected_name = computed(() => {
  const idx = selected_method.value.indexOf(':');
  return idx > 0 ? selected_method.value.slice(idx + 1) : selected_method.value;
});

const selected_channel = ref<number | null>(null);
const params = reactive<Record<string, unknown>>({});
const submit_error = ref<string | null>(null);
const submitting = ref(false);

// Full method group definition, fetched lazily when a method group is selected.
const selected_mg = ref<MethodGroup | null>(null);

const mg_exposed_fields = computed<ExposedField[]>(() =>
  selected_mg.value?.exposed_fields ?? []
);

// ---------------------------------------------------------------------------
// Load lists on mount
// ---------------------------------------------------------------------------

onMounted(() => {
  if (subprotocols.value.length === 0) refreshSubprotocols();
  if (method_groups.value.length === 0) refreshMethodGroups();
});

// ---------------------------------------------------------------------------
// Build default params when selection changes
// ---------------------------------------------------------------------------

watch(selected_method, async () => {
  Object.keys(params).forEach(k => delete params[k]);
  submit_error.value = null;
  selected_mg.value = null;

  const kind = selected_kind.value;
  const name = selected_name.value;
  if (!name) return;

  if (kind === 'method') {
    const mdef = method_defs.value[name];
    if (!mdef) return;
    for (const field of mdef.fields) {
      const prop = (mdef.schema.properties as Record<string, any>)[field] ?? {};
      if ('$ref' in prop) {
        params[field] = { rack_id: '', well_number: 0, id: null };
      } else if (prop.type === 'boolean') {
        params[field] = false;
      } else if (prop.type === 'number' || prop.type === 'integer') {
        params[field] = 0;
      } else {
        params[field] = '';
      }
    }
  } else if (kind === 'method_group') {
    const summary = method_groups.value.find(m => m.name === name);
    if (summary) {
      selected_mg.value = await fetchMethodGroup(summary.id);
      for (const ef of mg_exposed_fields.value) {
        if (ef.is_static) continue;
        params[ef.field_name] = null;
      }
    }
  } else if (kind === 'subprotocol') {
    const schema = subprotocol_schemas.value[name] ?? {};
    for (const [field, def] of Object.entries(schema)) {
      if (def.is_static) continue;
      params[field] = def.default_value ?? null;
    }
  }
});

// ---------------------------------------------------------------------------
// Active param fields + type resolution
// ---------------------------------------------------------------------------

const active_fields = computed<string[]>(() => {
  const kind = selected_kind.value;
  const name = selected_name.value;
  if (!name) return [];
  if (kind === 'method') return method_defs.value[name]?.fields ?? [];
  if (kind === 'method_group') return mg_exposed_fields.value.filter(ef => !ef.is_static).map(ef => ef.field_name);
  if (kind === 'subprotocol') {
    const schema = subprotocol_schemas.value[name] ?? {};
    return Object.entries(schema).filter(([, def]) => !def.is_static).map(([f]) => f);
  }
  return [];
});

function field_label(field: string): string {
  const kind = selected_kind.value;
  const name = selected_name.value;
  if (kind === 'method_group') {
    return mg_exposed_fields.value.find(ef => ef.field_name === field)?.display_name ?? field;
  }
  if (kind === 'subprotocol') {
    return subprotocol_schemas.value[name]?.[field]?.display_name ?? field;
  }
  return field;
}

function field_type(field: string): string {
  const kind = selected_kind.value;
  const name = selected_name.value;
  if (kind === 'method') {
    const mdef = method_defs.value[name];
    if (!mdef) return 'string';
    const prop = (mdef.schema.properties as Record<string, any>)[field] ?? {};
    if ('$ref' in prop) return 'WellLocation';
    return prop.type ?? 'string';
  }
  if (kind === 'method_group') {
    return mg_exposed_fields.value.find(ef => ef.field_name === field)?.type ?? 'string';
  }
  if (kind === 'subprotocol') {
    return subprotocol_schemas.value[name]?.[field]?.type ?? 'string';
  }
  return 'string';
}

// ---------------------------------------------------------------------------
// Submit
// ---------------------------------------------------------------------------

async function on_submit() {
  if (!selected_name.value) return;
  submitting.value = true;
  submit_error.value = null;
  try {
    const result = await submit_maintenance_run(
      selected_name.value,
      { ...params },
      selected_channel.value,
    );
    if (result.error) submit_error.value = result.error;
  } finally {
    submitting.value = false;
  }
}

// ---------------------------------------------------------------------------
// Status display helpers
// ---------------------------------------------------------------------------

function is_dismissable(sample: any): boolean {
  const st = sample_status.value[sample.id]?.status;
  return ['completed', 'cancelled', 'error', 'failed'].includes(st ?? '');
}

const channels = computed(() => Array.from({ length: num_channels.value }, (_, i) => i));
</script>

<template>
  <div class="p-3">

    <!-- Submission form -->
    <div class="card mb-3">
      <div class="card-header fw-semibold">Submit Maintenance Job</div>
      <div class="card-body">

        <div class="mb-2">
          <label class="form-label">Method</label>
          <select class="form-select form-select-sm" v-model="selected_method">
            <option value="">— select method —</option>
            <optgroup v-for="(methods, origin) in grouped_method_defs" :label="String(origin)">
              <option v-for="[name] in methods" :key="name" :value="`method:${name}`">{{ name }}</option>
            </optgroup>
            <optgroup v-if="method_groups.length" label="Method Groups">
              <option v-for="mg in method_groups" :key="mg.id" :value="`method_group:${mg.name}`">
                {{ mg.name }}
              </option>
            </optgroup>
            <optgroup v-if="subprotocols.length" label="Subprotocols">
              <option v-for="sp in subprotocols" :key="sp.id" :value="`subprotocol:${sp.name}`">
                {{ sp.name }}
              </option>
            </optgroup>
          </select>
        </div>

        <div class="mb-2">
          <label class="form-label">Channel</label>
          <select class="form-select form-select-sm"
                  :value="selected_channel"
                  @change="e => selected_channel = (e.target as HTMLSelectElement).value === 'null' ? null : parseInt((e.target as HTMLSelectElement).value)">
            <option value="null">None (exclusive LH access)</option>
            <option v-for="ch in channels" :key="ch" :value="ch">Channel {{ ch }}</option>
          </select>
        </div>

        <template v-if="selected_name && active_fields.length > 0">
          <div class="mb-2" v-for="field in active_fields" :key="field">
            <label class="form-label small">{{ field_label(field) }}</label>
            <template v-if="field_type(field) === 'boolean'">
              <div class="form-check">
                <input class="form-check-input" type="checkbox" v-model="(params as any)[field]">
              </div>
            </template>
            <template v-else-if="field_type(field) === 'WellLocation'">
              <div class="input-group input-group-sm">
                <span class="input-group-text">Rack</span>
                <input class="form-control" type="text" v-model="(params as any)[field].rack_id" placeholder="rack_id">
                <span class="input-group-text">Well</span>
                <input class="form-control" type="number" v-model.number="(params as any)[field].well_number" placeholder="0">
                <span class="input-group-text">ID</span>
                <input class="form-control" type="text" v-model="(params as any)[field].id" placeholder="optional">
              </div>
            </template>
            <template v-else-if="field_type(field) === 'number' || field_type(field) === 'integer'">
              <input class="form-control form-control-sm" type="number" v-model.number="(params as any)[field]">
            </template>
            <template v-else>
              <input class="form-control form-control-sm" type="text" v-model="(params as any)[field]">
            </template>
          </div>
        </template>

        <div v-if="submit_error" class="alert alert-danger py-1 small">{{ submit_error }}</div>
        <button class="btn btn-primary btn-sm" :disabled="!selected_name || submitting" @click="on_submit">
          {{ submitting ? 'Submitting…' : 'Submit' }}
        </button>
      </div>
    </div>

    <!-- Active maintenance jobs (reuses MethodList for full task controls) -->
    <div v-for="sample in maintenance_samples" :key="sample.id" class="card mb-2">
      <div class="card-header d-flex align-items-center gap-2">
        <span class="fw-semibold">{{ sample.name }}</span>
        <span class="text-muted small">{{ sample.description }}</span>
        <span class="ms-auto">
          <button
            v-if="is_dismissable(sample)"
            class="btn btn-outline-secondary btn-sm"
            @click="dismiss_maintenance">
            Dismiss
          </button>
        </span>
      </div>
      <div class="card-body p-0">
        <MethodList
          :sample_id="sample.id"
          :stage_name="Object.keys(sample.stages)[0]"
          :methods="(sample.stages as any)[Object.keys(sample.stages)[0]].active"
          stage_label="active"
          :editable="false"
          display_label="Active"
        />
      </div>
    </div>

  </div>
</template>
