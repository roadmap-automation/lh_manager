<script setup lang="ts">
import { ref, computed, defineProps } from 'vue';
import { active_well_field, active_method_index, active_stage, add_method, remove_method, method_defs, source_components, source_well, target_well, layout, sample_status, update_method } from '../store';
import type { MethodType, StageName } from '../store';
import MethodFields from './MethodFields.vue';

const props = defineProps<{
  sample_id: string,
  stage_name: StageName,
  methods: MethodType[],
}>();

// const active_well_field = ref<string | null>(null);

function toggleItem(method_index) {
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
    console.log(source_well.value, target_well.value);

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

const parameters = computed(() => {
  return props.methods.map(get_parameters);
});

const status = computed(() => {
  return sample_status.value[props.sample_id]?.stages?.[props.stage_name];
})

function filter_components(index, component_key: 'solutes' | 'solvents') {
  const components = source_components.value?.[component_key] ?? [];
  const include_zones_param = parameters.value[index].find((p) => p.name === 'include_zones');
  const include_zones = include_zones_param?.value ?? null;
  const filtered_components = (include_zones === null) ? [...components] : components.filter((c) => (include_zones.includes(c[1])));
  const unique_components = new Set(filtered_components.map((c) => c[0]));
  // console.log(source_components.value, component_key);
  // console.log({components, filtered_components, include_zones, unique_components});
  return [...unique_components];
}

const editable = computed(() => {
  return (status.value?.status === 'inactive');
});


function activateSelector({name, type}) {
  if (type === '#/definitions/WellLocation') {
    active_well_field.value = name;
  }
}

function send_changes(index, param) {
  update_method(props.sample_id, props.stage_name, index, param.name, param.value);
}


function add_component(index, param, component_type: 'solvents' | 'solutes') {
  if (param.value == null) {
    param.value = {
      solutes: [],
      solvents: []
    }
  }
  const first_available = filter_components(index, component_type)[0];
  console.log(index, component_type, first_available);
  if (first_available !== undefined) {
    const new_component: {name: string, fraction?: number, concentration?: number} = {name: first_available};
    if (component_type === 'solvents') {
      new_component.fraction = 0;
    }
    else {
      new_component.concentration = 0;
    }
    console.log({param});
    param.value[component_type].push(new_component);
    send_changes(index, param);
  }
}


</script>

<template>
  <div class="accordion accordion-flush">
    <div class="accordion-item" v-for="(method, index) of methods" :key="index">
      <h2 class="accordion-header">
        <button class="accordion-button p-1" :class="{ collapsed: stage_name === active_stage && index !== active_method_index }" type="button"
          @click="toggleItem(index)" :aria-expanded="index === active_method_index">
          <span class="d-inline align-middle text-light bg-dark" > {{ method.display_name }}:</span>
          <span class="d-inline align-middle px-2 method-string" :class="{ 'text-danger': status?.methods_complete?.[index] }">
            {{ method_string(method) }}
          </span>
        </button>
      </h2>
      <div class="accordion-collapse collapse" :class="{ show: stage_name === active_stage && index === active_method_index }">
        <div class="accordion-body p-2 border bg-light">
          <table class="table m-0 table-borderless" v-if="stage_name === active_stage && index === active_method_index">
            <MethodFields
              :sample_id="sample_id"
              :stage_name="stage_name"
              :editable="editable"
              :method_index="index"
              :method="method"
            />

          </table>
          <div class="d-flex justify-content-end">
            <button class="btn btn-sm btn-danger" @click="remove_method(sample_id, stage_name, index)">remove</button>
          </div>
        </div>
      </div>
    </div>
    <select v-if="editable" class="form-select form-select-sm text-primary outline-primary"
      @change="add_method(sample_id, stage_name, $event.target?.value)" value="null">
      <option class="disabled" disabled selected value="null">+ Add method</option>
      <option v-for="(mdef, mname) of method_defs" :value="mname">{{ mdef.display_name }}</option>
    </select>
  </div>
</template>

<style scoped>
.btn-close.edit {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-pencil-square' viewBox='0 0 16 16'><path d='M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z'/><path fill-rule='evenodd' d='M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5v11z'/></svg>")
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