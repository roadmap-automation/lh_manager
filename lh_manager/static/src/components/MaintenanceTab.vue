<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import {
  maintenance_samples,
  method_defs,
  grouped_method_defs,
  num_channels,
  sample_status,
  submit_maintenance_run,
  dismiss_maintenance,
  resubmit_all_tasks,
} from '../store';

const selected_method = ref<string>('');
const selected_channel = ref<number | null>(null);
const params = reactive<Record<string, unknown>>({});
const submit_error = ref<string | null>(null);
const submitting = ref(false);

// Build default params whenever the selected method changes.
watch(selected_method, (name) => {
  Object.keys(params).forEach(k => delete params[k]);
  submit_error.value = null;
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
});

function field_type(field: string): string {
  const mdef = method_defs.value[selected_method.value];
  if (!mdef) return 'string';
  const prop = (mdef.schema.properties as Record<string, any>)[field] ?? {};
  if ('$ref' in prop) return 'WellLocation';
  return prop.type ?? 'string';
}

async function on_submit() {
  if (!selected_method.value) return;
  submitting.value = true;
  submit_error.value = null;
  try {
    const result = await submit_maintenance_run(selected_method.value, { ...params }, selected_channel.value);
    if (result.error) {
      submit_error.value = result.error;
    }
  } finally {
    submitting.value = false;
  }
}

async function on_retry(sample_id: string, stage: string) {
  await resubmit_all_tasks(sample_id, stage, 0);
}

async function on_dismiss() {
  await dismiss_maintenance();
}

function status_badge_class(status: string | undefined): string {
  switch (status) {
    case 'active': return 'text-bg-success';
    case 'pending': return 'text-bg-secondary';
    case 'completed': return 'text-bg-primary';
    case 'error':
    case 'failed': return 'text-bg-danger';
    case 'cancelled': return 'text-bg-warning';
    default: return 'text-bg-light';
  }
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
              <option v-for="[name] in methods" :key="name" :value="name">{{ name }}</option>
            </optgroup>
          </select>
        </div>

        <div class="mb-2">
          <label class="form-label">Channel</label>
          <select class="form-select form-select-sm" :value="selected_channel" @change="e => selected_channel = (e.target as HTMLSelectElement).value === 'null' ? null : parseInt((e.target as HTMLSelectElement).value)">
            <option value="null">None (exclusive LH access)</option>
            <option v-for="ch in channels" :key="ch" :value="ch">Channel {{ ch }}</option>
          </select>
        </div>

        <template v-if="selected_method">
          <div class="mb-2" v-for="field in method_defs[selected_method]?.fields ?? []" :key="field">
            <label class="form-label small">{{ field }}</label>
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
        <button class="btn btn-primary btn-sm" :disabled="!selected_method || submitting" @click="on_submit">
          {{ submitting ? 'Submitting…' : 'Submit' }}
        </button>
      </div>
    </div>

    <!-- Current maintenance job -->
    <div class="card" v-if="maintenance_samples.length > 0">
      <div class="card-header fw-semibold">Current Maintenance Job</div>
      <ul class="list-group list-group-flush">
        <li class="list-group-item d-flex align-items-center gap-2" v-for="sample in maintenance_samples" :key="sample.id">
          <span class="fw-bold">{{ sample.name }}</span>
          <span class="text-muted small">{{ sample.description }}</span>
          <span class="badge rounded-pill ms-1"
            :class="status_badge_class(sample_status[sample.id]?.status)">
            {{ sample_status[sample.id]?.status ?? 'inactive' }}
          </span>
          <span class="ms-auto d-flex gap-1">
            <button
              v-if="['error', 'failed'].includes(sample_status[sample.id]?.status ?? '')"
              class="btn btn-warning btn-sm"
              @click="on_retry(sample.id, Object.keys(sample.stages)[0])">
              Retry
            </button>
            <button
              v-if="['completed', 'cancelled', 'error', 'failed'].includes(sample_status[sample.id]?.status ?? '')"
              class="btn btn-outline-secondary btn-sm"
              @click="on_dismiss">
              Dismiss
            </button>
          </span>
        </li>
      </ul>
    </div>

  </div>
</template>
