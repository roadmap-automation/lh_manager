<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { method_defs, source_well, target_well, layout, emitter } from '../store';

type Method = {
  display_name: string,
  method_name: string,
}

const props = defineProps<{
  methods: Method[],
  status: object,
  collapsed: boolean,
  active_item: number | null
}>();

const emit = defineEmits(['add_method', 'set_location', 'set_active']);
const active_well_field = ref<string | null>(null);

function toggleItem(index) {
  emit('set_active', index);
}

function method_string(method: Method) {
  const param_strings = get_parameters(method)
    .map(([key, value]) => {
      if (value &&  typeof(value) === 'object') {
        value = Object.values(value).join(":")
      }
      return `${key}=${value}`
    });

  const output = `${method.display_name}: ${param_strings.join(',')}`;
  return output;
}

function get_parameters(method: Method) {
  const { method_name } = method;
  const method_def = method_defs.value[method_name];
  if (method_def == null) {
    return [];
  }
  const { fields, schema: { properties } } = method_def;
  const params = fields.map((field_name) => {
    const p = properties[field_name];
    const t = ('$ref' in p) ? p['$ref'] : p.type;
    return [field_name, method[field_name], t, p];
  });
  return params
}

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


function activateSelector(method_index, name, field_type) {
  if (field_type === '#/definitions/WellLocation') {
    active_well_field.value = name;
  }
}

watch(() => props.collapsed, (collapsed: boolean) => {
  console.log({collapsed, props});
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
      source_well.value = method['Source']; // can be undefined
      target_well.value = method['Target']; // can be undefined
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
          <span class="align-middle px-2" :class="{ 'text-danger': status?.methods_complete?.[index] }"> {{
              method_string(method)
          }}</span>
        </button>
      </h2>
      <div class="accordion-collapse collapse" :class="{ show: index === active_item }">
        <div class="accordion-body p-2 border bg-light">
          <table class="table m-0 table-borderless" v-if="index === active_item">
            <fieldset :disabled="status.status != 'pending'">
              <tr v-for="[name, value, ptype] of get_parameters(method)" @click="activateSelector(index, name, ptype)">
                <td :class="{'selector-active': active_well_field === name}">
                  <div class="form-check">
                  <label>
                    <!-- <input class="form-check-input" v-if="ptype === '#/definitions/Well'" type="radio" :name="`param_${name}`" /> -->
                    {{ name }}:
                  </label>
                  </div>
                </td>
                <td v-if="ptype === 'number' || ptype === 'integer'"><input class="number px-1 py-0" :value="value ?? 0" :name="`param_${name}`" /></td>
                <td v-if="ptype === '#/definitions/WellLocation'">
                  <select v-if="layout != null" :value="value?.rack_id">
                    <option :value="null" disabled></option>
                    <option v-for="(rack_def, rack_name) of layout.racks">{{rack_name}}</option>
                  </select>
                  <input class="number px-1 py-0" :value="value?.well_number" :name="`param_${name}_well`" />
                </td>
              </tr>
            </fieldset>
          </table>
        </div>
      </div>
    </div>
    <select v-if="status?.status === 'pending'" class="form-select form-select-sm text-primary outline-primary"
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
</style>