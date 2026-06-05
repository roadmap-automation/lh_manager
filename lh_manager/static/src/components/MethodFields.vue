<script setup lang="ts">
import { ref, computed, watch, defineProps, defineEmits } from 'vue';
import { active_well_field, method_defs, soluteMassUnits, soluteVolumeUnits, materials, source_well, target_well, device_layouts, update_at_pointer, subprotocol_schemas } from '../store';
import json_pointer from 'json-pointer';
import type { MethodType, Solvent, Solute } from '../store';

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

const source_components = computed(() => {
  // compile all components
  const solvents = {} as {[name: string]: (Solvent & { zone: string })[]};
  const solutes = {} as {[name: string]: (Solute & { zone: string })[]};
  for (const device_name in device_layouts.value) {
    const sc = device_layouts.value[device_name].source_components
    for (const s in sc.solvents) {
      if (!(s in solvents)) {
        solvents[s] = [];
      }
      solvents[s].push(...sc.solvents[s]);
    }
    for (const s in sc.solutes) {
      if (!(s in solutes)) {
        solutes[s] = [];
      }
      solutes[s].push(...sc.solutes[s]);
    }
  };
  return { solvents, solutes };
});

function get_parameters(method: MethodType) {
  if (!method) return [];
  const { method_name } = method;

  if (method_name === '__method_group__') {
    const exposed_fields: any[] = (method as any).exposed_fields ?? [];
    return exposed_fields.map((ef: any) => {
      const type = ef.type ?? 'string';
      let value = clone((method as any)[ef.field_name]) ?? null;
      if (isWellLocationType(type) && value == null) {
        value = { rack_id: null, well_number: 0 };
      }
      return {
        name: ef.field_name,
        value,
        original_value: clone((method as any)[ef.field_name]),
        type,
        schema: { properties: { [ef.field_name]: { type } } },
        properties: { type },
      };
    });
  }

  if (method_name === '__subprotocol__') {
    const sp_name = (method as any).subprotocol_name;
    const sp_schema = subprotocol_schemas.value[sp_name] ?? {};
    const excluded = new Set(['method_name', 'display_name', 'subprotocol_name', 'id', 'status', 'tasks']);
    return Object.entries(sp_schema)
      .filter(([field_name]) => !excluded.has(field_name))
      .map(([field_name, input_def]: [string, any]) => {
        let type = input_def.type ?? 'string';
        if (type === 'object') type = '#/$defs/Composition';
        const value = clone((method as any)[field_name]) ?? null;
        return {
          name: field_name,
          value,
          original_value: clone((method as any)[field_name]),
          type,
          schema: { properties: { [field_name]: { type } } },
          properties: { type },
        };
      });
  }

  const method_def = method_defs.value[method_name];
  if (method_def == null) {
    return [];
  }
  const { fields, schema } = method_def;
  const params = fields.map((field_name) => {
    const properties = schema.properties[field_name];
    const type = ('$ref' in properties) ? properties['$ref'] : properties.type;
    let value = clone(method[field_name]);
    // Ensure structured fields always have a base object so their controls render.
    if (isWellLocationType(type) && value == null) {
      value = { rack_id: null, well_number: 0 };
    }
    if ((type === '#/$defs/TransferMethod' || type === '#/$defs/MixMethod' || type === '#/$defs/InjectMethod') && value == null) {
      value = { method_name: null };
    }
    const original_value = clone(method[field_name]);
    return {name: field_name, value, original_value, type, schema, properties };
  });
  return params
}

const parameters = computed(() => {
  return get_parameters(props.method);
});

function getMethodDefaults(method_name: string): Record<string, any> {
  const mdef = method_defs.value[method_name];
  if (!mdef) return { method_name };
  const defaults: Record<string, any> = { method_name };
  const props = (mdef.schema?.properties ?? {}) as Record<string, any>;
  for (const [field, prop] of Object.entries(props)) {
    if (prop != null && 'default' in prop) {
      defaults[field] = prop.default;
    }
  }
  return defaults;
}

function wellCount(rack_id: string): number {
  const rack = available_racks.value[rack_id] as any;
  return rack ? (rack.rows ?? 1) * (rack.columns ?? 1) : 0;
}

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
    const [name, values] = first_available;
    const new_component: {name: string, fraction?: number, concentration?: number, molecular_weight?: number, units?: string} = { name };
    if (component_type === 'solvents') {
      new_component.fraction = values[0].fraction ?? 0;
    }
    else {
      new_component.concentration = values[0].concentration ?? 0;
      new_component.molecular_weight = values[0].molecular_weight ?? null;
      new_component.units = values[0].units ?? 'M';
    }
    console.log({param});
    param.value[component_type].push(new_component);
    send_changes(param);
  }
}

function filter_components(component_key: 'solutes' | 'solvents') {
  const components = source_components.value?.[component_key] ?? {};
  console.log({component_key, components});
  const include_zones_param = parameters.value.find((p) => p.name === 'include_zones');
  const include_zones = include_zones_param?.value ?? null;
  const component_entries = Object.entries(components);
  if (include_zones === null) {
    return component_entries;
  }
  const filtered_components = component_entries.map(([name, values]) => {
    return [name, values.filter((v) => include_zones.includes(v.zone))];
  });
  return filtered_components.filter(([name, values]) => values.length > 0);
}

function change_solute(solute, param) {
  const { units, concentration, molecular_weight } = source_components.value.solutes[solute.name][0];
  solute.units = units;
  solute.concentration = concentration;
  solute.molecular_weight = molecular_weight;
  send_changes(param);
}

function available_solute_units(solute_name: string) {
  // if the molecular weight is defined, then we can use any units.
  const material = materials.value.find((m) => m.name === solute_name);
  if (material && material.molecular_weight !== undefined) {
    return [...soluteMassUnits, ...soluteVolumeUnits];
  }
  const solute_instances = source_components.value.solutes[solute_name];
  const massUnitsToAdd = solute_instances.some((s) => soluteMassUnits.includes(s.units)) ? soluteMassUnits : [];
  const volumeUnitsToAdd = solute_instances.some((s) => soluteVolumeUnits.includes(s.units)) ? soluteVolumeUnits : [];
  return [...massUnitsToAdd, ...volumeUnitsToAdd];
}

const method_origin = computed(() =>
  method_defs.value[props.method?.method_name]?.origin ?? null
);
const method_device_layout = computed(() =>
  method_origin.value ? device_layouts.value[method_origin.value] : null
);

// Racks to show in WellLocation and include_zones selectors.
// Prefers the method's own device layout; falls back to all known device racks
// so that locally-registered methods (origin=null) still show something.
const available_racks = computed(() => {
  const specific = method_device_layout.value?.layout?.racks;
  if (specific) return specific;
  const racks: Record<string, unknown> = {};
  for (const dl of Object.values(device_layouts.value)) {
    Object.assign(racks, dl.layout?.racks ?? {});
  }
  return racks;
});

function isWellLocationType(t: string) {
  return t === '#/$defs/WellLocation' || t === 'WellLocation';
}

function isCompositionType(t: string) {
  return t === '#/$defs/Composition' || t === 'Composition';
}

function activateSelector({name, type}) {
  if (isWellLocationType(type)) {
    active_well_field.value = name;
  }
}
</script>

<template>
  <fieldset :disabled="!editable">
    <tr v-for="param of parameters.filter((p) => (!hide_fields.includes(p.name)))" @click="activateSelector(param)">
      <td :class="{ 'selector-active': active_well_field === param.name, [param.name]: isWellLocationType(param.type) }">
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
      <td v-if="param.type === 'string'">
        <input class="string" v-model="param.value" :name="`param_${param.name}`"
          @keydown.enter="send_changes(param)" @blur="send_changes(param)" />
      </td>
      <td v-if="param.type === 'boolean'">
        <input type="checkbox" v-model="param.value" :name="`param_${param.name}`" @change="send_changes(param)" />
      </td>
      <td v-if="isWellLocationType(param.type)">
        <select v-if="Object.keys(available_racks).length > 0"
          v-model="param.value.rack_id"
          @change="param.value.well_number = 1; send_changes(param)">
          <option :value="null" disabled></option>
          <option v-for="(rack_def, rack_name) of available_racks">{{ rack_name }}</option>
        </select>
        <input type="number" class="number px-1 py-0"
          v-model.number="param.value.well_number"
          :min="1" :max="wellCount(param.value.rack_id)"
          :name="`param_${param.name}_well`"
          @keydown.enter="send_changes(param)" @blur="send_changes(param)" />
      </td>
      <td v-if="param.type === 'array' && (param.properties?.items?.$ref === '#/$defs/Zone' || param.name === 'include_zones')">
        <select v-model="param.value" multiple @change="send_changes(param)">
          <option v-for="zone in Object.keys(available_racks)" :value="zone">{{ zone }}</option>
        </select>
      </td>
      <td v-if="isCompositionType(param.type)">
        <div>
          <div>Solutes:
            <button class="btn btn-sm btn-outline-primary" @click="add_component(param, 'solutes')">add</button>
          </div>
          <div class="ps-3" v-for="(solute, sindex) of (param?.value?.solutes ?? [])">
            <select v-model="solute.name" @change="change_solute(solute, param)">
              <option v-for="source_solute of filter_components('solutes')" :value="source_solute[0]">{{
                source_solute[0] }}</option>
            </select>
            <label>concentration:
              <input class="number px-1 py-0" v-model="solute.concentration" @keydown.enter="send_changes(param)"
                @blur="send_changes(param)" />
            </label>
            <select v-model="solute.units" @change="send_changes(param)">
              <option v-for="unit of available_solute_units(solute.name)" :value="unit">{{ unit }}</option>
            </select>
            <button type="button" class="btn-close btn-sm align-middle" aria-label="Close"
              @click="param.value.solutes.splice(sindex, 1); send_changes(param)"></button>
          </div>
        </div>
        <div>
          <div>Solvents:
            <button class="btn btn-sm btn-outline-primary" @click="add_component(param, 'solvents')">add</button>
          </div>
          <div class="ps-3" v-for="(solvent, sindex) of (param?.value?.solvents ?? [])">
            <select v-model="solvent.name" @change="send_changes(param)">
              <option v-for="source_solvent of filter_components('solvents')" :value="source_solvent[0]">
                {{ source_solvent[0] }}</option>
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
      <td v-if="param.type === '#/$defs/TransferMethod' || param.type === '#/$defs/MixMethod' || param.type === '#/$defs/InjectMethod'">
        <select v-model="param.value.method_name" @change="param.value = getMethodDefaults(param.value.method_name); send_changes(param)">
            <option :value="null" disabled>-- select --</option>
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
  /* border-color: #0d6efd;
  border-style: solid;
  border-width: 3px;
  border-radius: 10; */
  background-color: yellow;

}

td.Source-old {
  background: repeating-linear-gradient(
    45deg,
    lightgreen 0px,
    lightgreen 5px,
    #E1FAE1 5px,
    #E1FAE1 10px
  );
}

td.Source .form-check {
  border-color: magenta;
  border-style: solid;
  border-width: 8px;
  border-radius: 10;
}

td.Target-old {
  background: repeating-linear-gradient(
    -45deg,
    pink 0px,
    pink 5px,
    white 5px,
    white 10px
  );
}

td.Target .form-check {
  border-color: darkorange;
  border-style: solid;
  border-width: 8px;
  border-radius: 10;
}

input.dirty {
  color: red;
}
span.method-string {
  max-width: 800px;
}
</style>