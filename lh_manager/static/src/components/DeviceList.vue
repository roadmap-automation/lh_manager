<script setup lang="ts">
import { ref, computed, defineProps } from 'vue';
import { device_defs, initialize_devices, update_device } from '../store';
import type { DeviceType } from '../store';

const excluded_fields = ['device_name', 'device_type'];

const props = defineProps<{
  devices: Record<string, DeviceType>,
}>();

function get_parameters(device: DeviceType) {
  const { device_name, device_type } = device;
  const device_def = device_defs.value[device_name];
  if (device_def == null) {
    return [];
  }
  const fields = Object.keys(device)
  const params = fields.filter((field_name) => !excluded_fields.includes(field_name))
    .map((field_name) => {
    const type = typeof(device[field_name])
    const value = clone(device[field_name]);
    const original_value = clone(device[field_name]);
    return { name: field_name, value, original_value, type };
  });
  return params
}

function clone(obj) {
  return (obj === undefined) ? undefined : JSON.parse(JSON.stringify(obj));
}

</script>

<template>
  <div class="row-sm-auto">
    <button type="button" class="btn btn-primary m-8" @click="initialize_devices">Initialize devices</button>
  </div>
  <div class="row-sm-auto">
    <div class="col d-flex flex-wrap">
      <div class="card" v-for="(device, device_name) of props.devices" :key="device_name">
        <div class="card-body p-2 border bg-light">
          <h5 class="card-title">{{ device_name }}</h5>
          <!-- <h6 class="card-title">{{ device.device_type }}</h6> -->
          <table class="table m-2">
            <tr v-for="field of get_parameters(device)" :key="field.name">
              <td>
                <div>
                  <label>
                    {{ field.name }}:
                  </label>
                </div>
              </td>
              <td v-if="field.type === 'number'">
                <input class="number px-1 py-0" v-model.number="field.value" :name="`param_${field.name}`"
                  @keydown.enter="update_device(device_name, field.name, field.value)" @blur="update_device(device_name, field.name, field.value)" />
              </td>
              <td v-if="field.type === 'string'">
                <input class="string py-1" v-model="field.value" :name="`param_${field.name}`"
                  @keydown.enter="update_device(device_name, field.name, field.value)" @blur="update_device(device_name, field.name, field.value)" />
              </td>
              <td v-if="field.type === 'boolean'">
                <input type="checkbox" v-model="field.value" :name="`param_${field.name}`" @change="update_device(device_name, field.name, field.value)" />
              </td>
            </tr>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
.btn-close.arrow-repeat {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-arrow-repeat' viewBox='0 0 16 16'><path d='M11.534 7h3.932a.25.25 0 0 1 .192.41l-1.966 2.36a.25.25 0 0 1-.384 0l-1.966-2.36a.25.25 0 0 1 .192-.41m-11 2h3.932a.25.25 0 0 0 .192-.41L2.692 6.23a.25.25 0 0 0-.384 0L.342 8.59A.25.25 0 0 0 .534 9'/><path fill-rule='evenodd' d='M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 1 1-.771-.636A6.002 6.002 0 0 1 13.917 7H12.9A5 5 0 0 0 8 3M3.1 9a5.002 5.002 0 0 0 8.757 2.182.5.5 0 1 1 .771.636A6.002 6.002 0 0 1 2.083 9z'/></svg>");
}

</style>

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

table {
  width:auto;
  table-layout: auto;
}

</style>