<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { method_defs, source_components, source_well, target_well, layout, emitter } from '../store';
import type { SampleStatus, WellLocation, MethodType } from '../store';

const props = defineProps<{
  methods: MethodType[],
  components: any,
  status: SampleStatus,
  collapsed: boolean,
  active_item: number | null
}>();

const emit = defineEmits(['add_method', 'set_location', 'set_active', 'update_method']);
const active_well_field = ref<string | null>(null);

function toggleItem(index) {
  emit('set_active', index);
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
  return (props.status?.status === 'inactive');
});

function add_method(event) {
  const method_name = event.target.value;
  const method_def = method_defs.value[method_name];
  emit('add_method', {method_name})
  event.target.value = "null";

}

function pick_handler({rack_id, well_number}) {
  const method_index = props.active_item;
  if (method_index == null) {
    console.warn(`tried to handle pick on collapsed? ${method_index}, ${JSON.stringify(props)}`);
    return
  }
  const name = active_well_field.value;
  if (name != null) {
    emit('set_location', method_index, name, {rack_id, well_number});
  }
}


function activateSelector({name, type}) {
  if (type === '#/definitions/WellLocation') {
    active_well_field.value = name;
  }
}

function send_changes(index, param) {
  console.log('send changes', param.name, param.value);
  emit('update_method', index, param.name, param.value);
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

watch(() => props.active_item, (active_item) => {

  if (!props.collapsed && active_item !== null) {
    const method = props.methods[active_item];
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
})

watch(() => props.collapsed, (collapsed: boolean) => {
  if (collapsed) {
    source_well.value = null; // can be undefined
    target_well.value = null; // can be undefined
    emitter.off('well_picked', pick_handler);
  }
  else {
    emitter.on('well_picked', pick_handler);
    if (props.active_item != null) {
      const method_index = props.active_item;
      const method = props.methods[method_index];
      source_well.value = method['Source'] ?? null; // can be undefined
      target_well.value = method['Target'] ?? null; // can be undefined
    }
  }
})

</script>

<template>
  <div class="accordion accordion-flush">
    <div class="accordion-item" v-for="(method, index) of methods" :key="index">
      <h2 class="accordion-header">
        <button class="accordion-button p-1" :class="{ collapsed: index !== active_item }" type="button"
          @click="toggleItem(index)" :aria-expanded="index === active_item">
          <span class="d-inline align-middle text-light bg-dark" > {{ method.display_name }}:</span>
          <span class="d-inline align-middle px-2 method-string" :class="{ 'text-danger': status?.methods_complete?.[index] }">
            {{ method_string(method) }}
          </span>
        </button>
      </h2>
      <div class="accordion-collapse collapse" :class="{ show: index === active_item }">
        <div class="accordion-body p-2 border bg-light">
          <table class="table m-0 table-borderless" v-if="index === active_item">
            <fieldset :disabled="!editable">
              <tr v-for="param of parameters[index]" @click="activateSelector(param)">
                <td :class="{'selector-active': active_well_field === param.name}">
                  <div class="form-check">
                  <label>
                    <!-- <input class="form-check-input" v-if="ptype === '#/definitions/Well'" type="radio" :name="`param_${name}`" /> -->
                    {{ param.name }}:
                  </label>
                  </div>
                </td>
                <td v-if="param.type === 'number' || param.type === 'integer'">
                  <input class="number px-1 py-0"
                    v-model.number="param.value" :name="`param_${param.name}`"
                    @keydown.enter="send_changes(index, param)"
                    @blur="send_changes(index, param)" />
                </td>
                <td v-if="param.type === 'boolean'">
                  <input type="checkbox"
                    v-model="param.value" :name="`param_${param.name}`"
                    @change="send_changes(index, param)" />
                </td>
                <td v-if="param.type === '#/definitions/WellLocation'">
                  <select v-if="layout != null && param.value && 'rack_id' in param.value" v-model="param.value.rack_id" @change="send_changes(index, param)">
                    <option :value="null" disabled></option>
                    <option v-for="(rack_def, rack_name) of layout.racks">{{rack_name}}</option>
                  </select>
                  <input v-if="param.value && 'well_number' in param.value" class="number px-1 py-0" v-model="param.value.well_number"
                    :name="`param_${param.name}_well`" 
                    @keydown.enter="send_changes(index, param)"
                    @blur="send_changes(index, param)" />
                </td>
                <td v-if="param.type === 'array' && param.properties?.items?.$ref === '#/definitions/Zone'">
                  <select v-model="param.value" multiple @change="send_changes(index, param)">
                    <option v-for="zone in param.schema.definitions?.Zone?.enum" :value="zone">{{ zone }}</option>
                  </select>
                </td>
                <td v-if="param.type === '#/definitions/Composition'">
                  <div>
                    <div>Solutes: 
                      <button class="btn btn-sm btn-outline-primary" @click="add_component(index, param, 'solutes')">add</button>
                    </div>
                    <div class="ps-3" v-for="(solute, sindex) of (param?.value?.solutes ?? [])">
                      <select v-model="solute.name" @change="send_changes(index, param)">
                        <option v-for="source_solute of filter_components(index, 'solutes')" :value="source_solute">{{ source_solute }}</option>
                      </select>
                      <label>concentration ({{ solute.units }}):
                        <input 
                          class="number px-1 py-0"  
                          v-model="solute.concentration"
                          @keydown.enter="send_changes(index, param)"
                          @blur="send_changes(index, param)" />
                      </label>
                      <button type="button" class="btn-close btn-sm align-middle" aria-label="Close"
                         @click="param.value.solutes.splice(sindex, 1); send_changes(index, param)"></button>
                    </div>
                  </div>
                  <div>
                    <div>Solvents: 
                      <button class="btn btn-sm btn-outline-primary" @click="add_component(index, param, 'solvents')">add</button>
                    </div>
                    <div class="ps-3" v-for="(solvent, sindex) of (param?.value?.solvents ?? [])">
                      <select v-model="solvent.name">
                        <option v-for="source_solvent of filter_components(index, 'solvents')" :value="source_solvent">{{ source_solvent }}</option>
                      </select>
                      <label>fraction:
                        <input 
                          class="number px-1 py-0"  
                          v-model="solvent.fraction"
                          @keydown.enter="send_changes(index, param)"
                          @blur="send_changes(index, param)" />
                      </label>
                      <button type="button" class="btn-close btn-sm align-middle" aria-label="Close"
                         @click="param.value.solvents.splice(sindex, 1); send_changes(index, param)"></button>
                    </div>
                  </div>
                </td>
              </tr>
            </fieldset>
          </table>
        </div>
      </div>
    </div>
    <select v-if="editable" class="form-select form-select-sm text-primary outline-primary"
      @change="add_method" value="null">
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