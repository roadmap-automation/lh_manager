<script setup>
import { ref, computed, onMounted } from 'vue'
import Mixture from './Mixture.vue';
import BedLayout from './BedLayout.vue';
import SampleChannels from './SampleChannels.vue';
import { device_defs, device_layouts } from '../store';
import EditWellContents from './EditWellContents.vue';
import MaterialManager from './MaterialManager.vue';
import AddWaste from './AddWaste.vue';
import WasteManager from './WasteManager.vue';
import EditRackSettings from './EditRackSettings.vue';
import BatchWellEditor from './BatchWellEditor.vue';
import SubProtocols from './SubProtocols.vue';
import MethodGroups from './MethodGroups.vue';

const props = defineProps({
  msg: String,
})

const emit = defineEmits(['remove_sample', 'add_sample']);

const all_devices = computed(() => {
  const keys = new Set([...Object.keys(device_defs.value), ...Object.keys(device_layouts.value)]);
  return Array.from(keys).map((device_name) => {
    const def = device_defs.value[device_name] ?? {};
    const dl = device_layouts.value[device_name];
    return {
      device_name,
      display_name: def.display_name || device_name,
      address: def.address ?? null,
      device_type: def.device_type ?? null,
      num_channels: def.num_channels ?? null,
      allow_sample_mixing: def.allow_sample_mixing ?? null,
      layout: (dl?.layout != null) ? dl : null,
    };
  });
});

</script>

<template>
  <ul class="nav nav-tabs" id="myTab" role="tablist">
    <li class="nav-item" role="presentation">
      <button class="nav-link active" id="layout-tab" data-bs-toggle="tab" data-bs-target="#Layout" type="button"
        role="tab" aria-controls="Layout" aria-selected="true">Main</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="materials-tab" data-bs-toggle="tab" data-bs-target="#Materials" type="button" role="tab"
        aria-controls="Materials" aria-selected="false">Materials</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="waste-tab" data-bs-toggle="tab" data-bs-target="#Waste" type="button" role="tab"
        aria-controls="Waste" aria-selected="false">Waste</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="subprotocols-tab" data-bs-toggle="tab" data-bs-target="#SubProtocols" type="button" role="tab"
        aria-controls="SubProtocols" aria-selected="false">SubProtocols</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="method-groups-tab" data-bs-toggle="tab" data-bs-target="#MethodGroups" type="button" role="tab"
        aria-controls="MethodGroups" aria-selected="false">Method groups</button>
    </li>
  </ul>
  <div class="tab-content d-flex flex-column flex-grow-1" id="myTabContent">
    <div class="tab-pane show active d-flex flex-row flex-grow-1 align-items-stretch overflow-auto" id="Layout"
      role="tabpanel" aria-labelledby="layout-tab">
      <div class="overflow-auto">
        <div class="card m-3">
          <div class="card-body">
            <h5 class="card-title">Samples</h5>
          </div>
          <SampleChannels />
        </div>
      </div>

      <div class="flex-grow-1">
        <ul class="nav nav-tabs" id="layout-tabs" role="tablist">
          <li v-for="(device, index) in all_devices" :key="device.device_name" class="nav-item" role="presentation">
            <button class="nav-link" :id="device.device_name + '-tab'" data-bs-toggle="tab" :data-bs-target="'#' + device.device_name + '-div'" type="button" role="tab"
              :aria-controls="device.device_name" :class="{ active: (index==0) }" :aria-selected="(index == 0) ? true : false">{{ device.display_name }}</button>
          </li>
        </ul>
        <div class="tab-content d-flex flex-fill" style="height:90%; width:90%" id="layoutTabContent">
          <div v-for="(device, index) in all_devices" :key="device.device_name" class="tab-pane bedlayout" :class="{ active: (index==0), show: (index==0) }" :id="device.device_name + '-div'">
            <div class="device-info d-flex align-items-center gap-2 px-3 py-2">
              <a v-if="device.address" :href="device.address" target="_blank" class="fw-semibold text-decoration-none">{{ device.display_name }}</a>
              <span v-else class="fw-semibold">{{ device.display_name }}</span>
              <span v-if="device.device_type" class="badge bg-light text-dark border">{{ device.device_type }}</span>
              <span v-if="device.num_channels != null" class="badge bg-light text-dark border">{{ device.num_channels }} ch</span>
              <span v-if="device.allow_sample_mixing != null" class="badge border"
                :class="device.allow_sample_mixing ? 'bg-success-subtle text-success-emphasis border-success-subtle' : 'bg-secondary-subtle text-secondary-emphasis border-secondary-subtle'">
                {{ device.allow_sample_mixing ? 'mixing ok' : 'no mixing' }}
              </span>
              <a v-if="device.address" :href="device.address" target="_blank" class="ms-auto text-muted small font-monospace text-decoration-none">{{ device.address }}</a>
            </div>
            <BedLayout v-if="device.layout !== null" :device_name="device.device_name" :layout="device.layout"/>
            <p v-else class="text-muted p-3 small">No layout available.</p>
          </div>
        </div>
      </div>


    </div>
    <div class="tab-pane d-flex flex-grow-1 h-100 overflow-auto" id="Materials" role="tabpanel" aria-labelledby="materials-tab">
      <MaterialManager />
    </div>
    <div class="tab-pane d-flex flex-grow-1 h-100" id="Waste" role="tabpanel" aria-labelledby="waste-tab">
      <WasteManager />
    </div>
    <div class="tab-pane d-flex flex-grow-1 h-100 overflow-hidden" id="SubProtocols" role="tabpanel" aria-labelledby="subprotocols-tab">
      <SubProtocols />
    </div>
    <div class="tab-pane d-flex flex-grow-1 h-100 overflow-hidden" id="MethodGroups" role="tabpanel" aria-labelledby="method-groups-tab">
      <MethodGroups />
    </div>
    </div>

  <EditWellContents/>
  <EditRackSettings/>
  <BatchWellEditor/>
  <AddWaste/>

</template>

<style scoped>
.flex-column {
  min-height: 0;
}

.bedlayout {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
}

.device-info {
  flex-shrink: 0;
  border-bottom: 1px solid #dee2e6;
}

.list-move,
.list-enter-active,
.list-leave-active {
  transition: all 0.5s;
}

.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.list-leave-active {
  position: absolute;
}

.list-group-item-action {
  cursor: pointer;
}

.tab-pane:not(.active) {
  display: none !important;
}

.btn-close.edit {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-pencil-square' viewBox='0 0 16 16'><path d='M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z'/><path fill-rule='evenodd' d='M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5v11z'/></svg>")
}
</style>
