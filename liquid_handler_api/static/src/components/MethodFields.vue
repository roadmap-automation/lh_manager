<script setup lang="ts">
import { ref, computed, watch, defineProps, defineEmits } from 'vue';
import { active_well_field, method_defs, source_components, source_well, target_well, layout, update_at_pointer } from '../store';
import json_pointer from 'json-pointer';
import type { MethodType, StageName } from '../store';

const props = defineProps<{
  sample_id: string,
  pointer: string,
  method: MethodType,
  editable: boolean,
  hide_fields: string[],
}>();

function send_changes(param) {
  const method_pointer = `${props.pointer}/${param.name}`;
  update_at_pointer(props.sample_id, method_pointer, param.value);
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

const parameters = computed(() => {
  return get_parameters(props.method);
});

function get_template_names(field_type: string, schema: any) {
  const schema_def = json_pointer.get(schema, field_type.replace(/^#/, ''));
  const method_type = schema_def?.properties?.method_type?.default;
  const template_names = Object.entries(method_defs.value).filter(([mname, mdef]) => (
    mdef.schema.properties?.method_type?.default === method_type
  )).map(([mname, mdef]) => mname);
  return template_names;
}

function get_fields_to_hide(field_type: string, schema: any) {
  const schema_def = json_pointer.get(schema, field_type.replace(/^#/, ''));
  return Object.keys(schema_def?.properties ?? {});
}

function clone(obj) {
  return (obj === undefined) ? undefined : JSON.parse(JSON.stringify(obj));
}

function add_component(param, component_type: 'solvents' | 'solutes') {
  if (param.value == null) {
    param.value = {
      solutes: [],
      solvents: []
    }
  }
  const first_available = filter_components(component_type)[0];
  console.log(component_type, first_available);
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
    send_changes(param);
  }
}

function filter_components(component_key: 'solutes' | 'solvents') {
  const components = source_components.value?.[component_key] ?? [];
  const include_zones_param = parameters.value.find((p) => p.name === 'include_zones');
  const include_zones = include_zones_param?.value ?? null;
  const filtered_components = (include_zones === null) ? [...components] : components.filter((c) => (include_zones.includes(c[1])));
  const unique_components = new Set(filtered_components.map((c) => c[0]));
  // console.log(source_components.value, component_key);
  // console.log({components, filtered_components, include_zones, unique_components});
  return [...unique_components];
}

function activateSelector({name, type}) {
  if (type === '#/definitions/WellLocation') {
    active_well_field.value = name;
  }
}
</script>

<template>
  <fieldset :disabled="!editable">
    <tr v-for="param of parameters.filter((p) => (!hide_fields.includes(p.name)))" @click="activateSelector(param)">
      <td :class="{ 'selector-active': active_well_field === param.name, [param.name]: param.type === '#/definitions/WellLocation' }">
        <div class="form-check">
          <label>
            {{ param.name }}:
          </label>
        </div>
      </td>
      <td v-if="param.type === 'number' || param.type === 'integer'">
        <input class="number px-1 py-0" v-model.number="param.value" :name="`param_${param.name}`"
          @keydown.enter="send_changes(param)" @blur="send_changes(param)" />
      </td>
      <td v-if="param.type === 'boolean'">
        <input type="checkbox" v-model="param.value" :name="`param_${param.name}`" @change="send_changes(param)" />
      </td>
      <td v-if="param.type === '#/definitions/WellLocation'">
        <select v-if="layout != null && param.value && 'rack_id' in param.value" v-model="param.value.rack_id"
          @change="send_changes(param)">
          <option :value="null" disabled></option>
          <option v-for="(rack_def, rack_name) of layout.racks">{{ rack_name }}</option>
        </select>
        <input v-if="param.value && 'well_number' in param.value" class="number px-1 py-0"
          v-model="param.value.well_number" :name="`param_${param.name}_well`" @keydown.enter="send_changes(param)"
          @blur="send_changes(param)" />
      </td>
      <td v-if="param.type === 'array' && param.properties?.items?.$ref === '#/definitions/Zone'">
        <select v-model="param.value" multiple @change="send_changes(param)">
          <option v-for="zone in param.schema.definitions?.Zone?.enum" :value="zone">{{ zone }}</option>
        </select>
      </td>
      <td v-if="param.type === '#/definitions/Composition'">
        <div>
          <div>Solutes:
            <button class="btn btn-sm btn-outline-primary" @click="add_component(param, 'solutes')">add</button>
          </div>
          <div class="ps-3" v-for="(solute, sindex) of (param?.value?.solutes ?? [])">
            <select v-model="solute.name" @change="send_changes(param)">
              <option v-for="source_solute of filter_components('solutes')" :value="source_solute">{{
                source_solute }}</option>
            </select>
            <label>concentration ({{ solute.units }}):
              <input class="number px-1 py-0" v-model="solute.concentration" @keydown.enter="send_changes(param)"
                @blur="send_changes(param)" />
            </label>
            <button type="button" class="btn-close btn-sm align-middle" aria-label="Close"
              @click="param.value.solutes.splice(sindex, 1); send_changes(param)"></button>
          </div>
        </div>
        <div>
          <div>Solvents:
            <button class="btn btn-sm btn-outline-primary" @click="add_component(param, 'solvents')">add</button>
          </div>
          <div class="ps-3" v-for="(solvent, sindex) of (param?.value?.solvents ?? [])">
            <select v-model="solvent.name">
              <option v-for="source_solvent of filter_components('solvents')" :value="source_solvent">
                {{ source_solvent }}</option>
            </select>
            <label>fraction:
              <input class="number px-1 py-0" v-model="solvent.fraction" @keydown.enter="send_changes(param)"
                @blur="send_changes(param)" />
            </label>
            <button type="button" class="btn-close btn-sm align-middle" aria-label="Close"
              @click="param.value.solvents.splice(sindex, 1); send_changes(param)"></button>
          </div>
        </div>
      </td>
      <td v-if="param.type === '#/definitions/TransferMethod' || param.type === '#/definitions/MixMethod'">
        <select v-model="param.value.method_name">
            <option v-for="mname of get_template_names(param.type, param.schema)" >
              {{ mname }}</option>
        </select>
        <MethodFields
          :sample_id="sample_id"
          :pointer="`${pointer}/${param.name}`"
          :editable="editable"
          :method="param.value"
          :hide_fields="get_fields_to_hide(param.type, param.schema)"
        />
      </td>
    </tr>
  </fieldset>
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
  border-color: #0d6efd;
  border-style: solid;
  border-width: 3px;
  border-radius: 10;

}

td.Source {
  background: repeating-linear-gradient(
    45deg,
    lightgreen 0px,
    lightgreen 5px,
    #E1FAE1 5px,
    #E1FAE1 10px
  );
}

td.Target {
  background: repeating-linear-gradient(
    -45deg,
    pink 0px,
    pink 5px,
    white 5px,
    white 10px
  );
}
input.dirty {
  color: red;
}
span.method-string {
  max-width: 800px;
}
</style>