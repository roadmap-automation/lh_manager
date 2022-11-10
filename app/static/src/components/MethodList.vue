<script setup>
import { ref } from 'vue';

const props = defineProps({
  methods: Object,
  method_defs: Object,
  status: Object
});

const active_item = ref(null);

function toggleItem(index) {
  active_item.value = (index === active_item.value) ? null : index;
}

function method_string(method) {
  const param_strings = get_parameters(method)
    .map(([key, value]) => `${key}=${value}`);

  const output = `${method.display_name}: ${param_strings.join(',')}`;
  return output;
}

function get_parameters(method) {
  const params = Object.entries(method)
    .filter(([key, value]) => (key !== 'display_name' && key !== 'method_name'))
  return params
}

function add_method(event) {
  const method_name = event.target.value;
  const method_def = props.method_defs[method_name];
  const parameters = get_parameters(method_def.schema.properties);
  console.log(method_def, parameters);
  event.target.value = "null";

}

</script>

<template>
  <div class="accordion accordion-flush">
    <div class="accordion-item" v-for="(method, index) of methods" :key="index">
      <h2 class="accordion-header">
        <button class="accordion-button p-1" :class="{ collapsed: index !== active_item }" type="button"
          @click="toggleItem(index)" :aria-expanded="index === active_item">
          <span class="align-middle px-2" :class="{status_completed: status?.methods_complete?.[index]}"> {{ method_string(method) }}</span>
        </button>
      </h2>
      <div class="accordion-collapse collapse" :class="{ show: index === active_item }">
        <div class="accordion-body p-2 border bg-light">
          <table class="table m-0 table-borderless" v-if="index === active_item">
            <fieldset :disabled="status.status != 'pending'">
              <tr v-for="[name, value] of get_parameters(method)">
                <td><label :for="`param_${name}`">{{ name }}:</label></td>
                <td><input class="px-1 py-0" :value="value" :name="`param_${name}`" /></td>
              </tr>
            </fieldset>
          </table>
        </div>
      </div>
    </div>
    <select v-if="status?.status === 'pending'" class="form-select btn-outline-primary btn-sm" @change="add_method" value="null">
      <option class="disabled" disabled selected value="null">+ Add method</option>
      <option v-for="(mdef, mname) of method_defs" :value="mname">{{ mdef.display_name }}</option>
    </select>
  </div>
</template>

<style scoped>
.btn-close.edit {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-pencil-square' viewBox='0 0 16 16'><path d='M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z'/><path fill-rule='evenodd' d='M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5v11z'/></svg>")
}

input {
  width: 10em;
}

.form-select {
  color: #0d6efd ;
  border-color: #0d6efd ;
}

.status_completed {
  color: orange;
}
</style>