<script setup lang="ts">
import { ref, computed, defineProps } from 'vue';
import { active_well_field, active_method_index, active_stage, add_method, remove_method, move_method, get_number_of_methods, method_defs, source_components, source_well, target_well, layout, sample_status, update_method, active_sample_index, reuse_method, copy_method, run_method } from '../store';
import type { MethodType, StageName } from '../store';
import MethodFields from './MethodFields.vue';

const props = defineProps<{
  sample_id: string,
  stage_name: StageName,
  methods: MethodType[],
  editable: boolean
}>();

// const active_well_field = ref<string | null>(null);
const pointer_base = `/${props.stage_name}/methods`;

function toggleItem(method_index) {
  const pointer = `${pointer_base}/${method_index}`;
  if (active_stage.value === props.stage_name && active_method_index.value === method_index) {
    active_method_index.value = null;
    active_stage.value = null;
    source_well.value = null; // can be undefined
    target_well.value = null; // can be undefined
  }
  else {
    active_stage.value = props.stage_name;
    active_method_index.value = method_index;
    const method = props.methods[method_index];
    source_well.value = method['Source'] ?? null; // can be undefined
    target_well.value = method['Target'] ?? null; // can be undefined

    if ((method?.Source?.rack_id == null || method?.Source?.well_number == null)) {
      active_well_field.value = 'Source';
    }
    else if ((method?.Target?.rack_id == null || method?.Target?.well_number == null)) {
      active_well_field.value = 'Target';
    }
    else {
      active_well_field.value = null;
    }
  }
}

function method_string(method: MethodType) {
  const param_strings = get_parameters(method)
    .map(({name, value}) => {
      if (value &&  typeof(value) === 'object') {
        value = Object.values(value).join(":")
      }
      return `${name}=${value}`
    });

  const output = `${param_strings.join(', ')}`;
  return output;
}

function get_parameters(method: MethodType) {
  const { method_name } = method;
  const method_def = method_defs.value[method_name];
  if (method_def == null) {
    return [];
  }
  const { fields, schema } = method_def;
  const params = fields.map((field_name) => {
    const properties = schema.properties[field_name];
    const type = ('$ref' in properties) ? properties['$ref'] : properties.type;
    const value = clone(method[field_name]);
    const original_value = clone(method[field_name]);
    return {name: field_name, value, original_value, type, schema, properties };
  });
  return params
}

function clone(obj) {
  return (obj === undefined) ? undefined : JSON.parse(JSON.stringify(obj));
}

const status = computed(() => {
  return sample_status.value[props.sample_id]?.stages?.[props.stage_name];
})

</script>

<template>
  <div class="accordion accordion-flush">
    <div class="accordion-item" v-for="(method, index) of methods" :key="index">
      <h2 class="accordion-header">
        <button class="accordion-button p-1" :class="{ collapsed: stage_name === active_stage || index !== active_method_index }" type="button"
          @click="toggleItem(index)" :aria-expanded="index === active_method_index">
          <span class="d-inline align-middle text-light bg-dark" > {{ method.display_name }}:</span>
          <span class="d-inline align-middle px-2 method-string" :class="{ 'text-danger': method.status === 'completed' }">
            {{ method_string(method) }}
          </span>
          <button
            v-if="props.editable"
            type="button"
            class="btn-close btn-sm align-middle start"
            aria-label="Duplicate method"
            title="Duplicate method"
            @click.stop="run_method(sample_id, stage_name, index)">
          </button>
          <button
            v-if="props.editable"
            type="button"
            class="btn-close btn-sm align-middle copy"
            aria-label="Duplicate method"
            title="Duplicate method"
            @click.stop="copy_method(sample_id, stage_name, index)">
          </button>
          <button
            v-if="!props.editable"
            type="button"
            class="btn-close btn-sm align-middle arrow-90deg-up"
            aria-label="Reuse method"
            title="Reuse method"
            @click.stop="reuse_method(sample_id, stage_name, index)">
          </button>      
          <button
            v-if="!props.editable && !(method.status === 'completed')"
            type="button"
            class="btn-close btn-sm align-middle arrow-repeat"
            aria-label="Resubmit tasks"
            title="Resubmit tasks"
            @click.stop="reuse_method(sample_id, stage_name, index)">
          </button>                  
          <button
            v-if="props.editable"
            class="btn-close btn-sm btn-danger trash"
            aria-label="Remove method"
            title="Remove method"
            @click="remove_method(sample_id, stage_name, index)"></button>
          </button>
        </h2>
      <div class="accordion-collapse collapse" :class="{ show: stage_name === active_stage && index === active_method_index }">
        <div class="accordion-body p-2 border bg-light">
          <table class="table m-0 table-borderless" v-if="stage_name === active_stage && index === active_method_index">
            <MethodFields
              :sample_id="sample_id"
              :pointer="`/stages/${stage_name}/methods/${index}`"
              :editable="props.editable"
              :method="method"
              :hide_fields="[]"
            />

          </table>
          <div v-if="props.editable" class="d-flex justify-content-end">
            <button class="btn-close btn-sm btn-secondary arrow-up-square" :class=" { disabled: index < 1} " aria-label="Move up" title="Move up" @click="move_method(sample_id, stage_name, index, index - 1)"></button>
            <button class="btn-close btn-sm btn-secondary arrow-down-square" :class=" { disabled: index == get_number_of_methods(sample_id, stage_name) - 1} " aria-label="Move down" title="Move down" @click="move_method(sample_id, stage_name, index, index + 1)"></button>
          </div>
        </div>
      </div>
    </div>
    <select v-if="props.editable" class="form-select form-select-sm text-primary outline-primary"
      @change="add_method(sample_id, stage_name, $event)" value="">
      <option class="disabled" disabled selected value="">+ Add method</option>
      <option v-for="(mdef, mname) of method_defs" :value="mname">{{ mdef.display_name }}</option>
    </select>
  </div>
</template>

<style scoped>
.btn-close.edit {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-pencil-square' viewBox='0 0 16 16'><path d='M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z'/><path fill-rule='evenodd' d='M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5v11z'/></svg>")
}

.btn-close.recycle {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-recycle' viewBox='0 0 16 16'><path d='M9.302 1.256a1.5 1.5 0 0 0-2.604 0l-1.704 2.98a.5.5 0 0 0 .869.497l1.703-2.981a.5.5 0 0 1 .868 0l2.54 4.444-1.256-.337a.5.5 0 1 0-.26.966l2.415.647a.5.5 0 0 0 .613-.353l.647-2.415a.5.5 0 1 0-.966-.259l-.333 1.242zM2.973 7.773l-1.255.337a.5.5 0 1 1-.26-.966l2.416-.647a.5.5 0 0 1 .612.353l.647 2.415a.5.5 0 0 1-.966.259l-.333-1.242-2.545 4.454a.5.5 0 0 0 .434.748H5a.5.5 0 0 1 0 1H1.723A1.5 1.5 0 0 1 .421 12.24zm10.89 1.463a.5.5 0 1 0-.868.496l1.716 3.004a.5.5 0 0 1-.434.748h-5.57l.647-.646a.5.5 0 1 0-.708-.707l-1.5 1.5a.5.5 0 0 0 0 .707l1.5 1.5a.5.5 0 1 0 .708-.707l-.647-.647h5.57a1.5 1.5 0 0 0 1.302-2.244z'/></svg>")
}

.btn-close.arrow-90deg-up {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-arrow-90deg-up' viewBox='0 0 16 16'><path fill-rule='evenodd' d='M4.854 1.146a.5.5 0 0 0-.708 0l-4 4a.5.5 0 1 0 .708.708L4 2.707V12.5A2.5 2.5 0 0 0 6.5 15h8a.5.5 0 0 0 0-1h-8A1.5 1.5 0 0 1 5 12.5V2.707l3.146 3.147a.5.5 0 1 0 .708-.708z'/></svg>");
}

.btn-close.arrow-down-square {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-arrow-down-square' viewBox='0 0 16 16'><path fill-rule='evenodd' d='M15 2a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1zM0 2a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2zm8.5 2.5a.5.5 0 0 0-1 0v5.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293z'/></svg>");
}

.btn-close.arrow-up-square {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-arrow-up-square' viewBox='0 0 16 16'><path fill-rule='evenodd' d='M15 2a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1zM0 2a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2zm8.5 9.5a.5.5 0 0 1-1 0V5.707L5.354 7.854a.5.5 0 1 1-.708-.708l3-3a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1-.708.708L8.5 5.707z'/></svg>");
}

.btn-close.arrow-up-square {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-arrow-up-square' viewBox='0 0 16 16'><path fill-rule='evenodd' d='M15 2a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1zM0 2a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2zm8.5 9.5a.5.5 0 0 1-1 0V5.707L5.354 7.854a.5.5 0 1 1-.708-.708l3-3a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1-.708.708L8.5 5.707z'/></svg>");
}

.btn-close.arrow-repeat {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-arrow-repeat' viewBox='0 0 16 16'><path d='M11.534 7h3.932a.25.25 0 0 1 .192.41l-1.966 2.36a.25.25 0 0 1-.384 0l-1.966-2.36a.25.25 0 0 1 .192-.41m-11 2h3.932a.25.25 0 0 0 .192-.41L2.692 6.23a.25.25 0 0 0-.384 0L.342 8.59A.25.25 0 0 0 .534 9'/><path fill-rule='evenodd' d='M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 1 1-.771-.636A6.002 6.002 0 0 1 13.917 7H12.9A5 5 0 0 0 8 3M3.1 9a5.002 5.002 0 0 0 8.757 2.182.5.5 0 1 1 .771.636A6.002 6.002 0 0 1 2.083 9z'/></svg>");
}

.btn-method {
    margin-left: 4px;
}

input.number {
  width: 10em;
}

.form-select {
  color: #0d6efd;
  border-color: #0d6efd;
}

.selector-active {
  background-color: orange;
}

input.dirty {
  color: red;
}
span.method-string {
  max-width: 800px;
}
</style>