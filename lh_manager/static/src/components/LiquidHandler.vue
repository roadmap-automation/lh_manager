<script setup>
import { ref, computed, onMounted } from 'vue'
import Mixture from './Mixture.vue';
import DeviceList from './DeviceList.vue';
import BedLayout from './BedLayout.vue';
import SampleChannels from './SampleChannels.vue';
import { device_defs, device_layouts } from '../store';
import EditWellContents from './EditWellContents.vue';
import MaterialManager from './MaterialManager.vue';
import AddWaste from './AddWaste.vue';
import WasteManager from './WasteManager.vue';
import LHInterface from './LHInterface.vue';
import EditRackSettings from './EditRackSettings.vue';

const props = defineProps({
  msg: String,
  // samples: Array,
  // sample_status: Object,
})

const emit = defineEmits(['remove_sample', 'add_sample']);

onMounted(() => {
  console.log(props.sample_status);
});

const filtered_layouts = computed(()=> {
  const layouts = Object.entries(device_layouts.value).filter(([device_name, layout]) => (layout.layout !== null));
  return layouts.map(([device_name, layout]) => {return { device_name, layout }});
    });

</script>

<template>
  <ul class="nav nav-tabs" id="myTab" role="tablist">
    <li class="nav-item" role="presentation">
      <button class="nav-link active" id="layout-tab" data-bs-toggle="tab" data-bs-target="#Layout" type="button"
        role="tab" aria-controls="Layout" aria-selected="true">Main</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="devices-tab" data-bs-toggle="tab" data-bs-target="#Devices" type="button" role="tab"
        aria-controls="Devices" aria-selected="false">Devices</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="lh-tab" data-bs-toggle="tab" data-bs-target="#LHInterface" type="button" role="tab"
        aria-controls="LHInterface" aria-selected="false">LH Controls</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="materials-tab" data-bs-toggle="tab" data-bs-target="#Materials" type="button" role="tab"
        aria-controls="Materials" aria-selected="false">Materials</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="waste-tab" data-bs-toggle="tab" data-bs-target="#Waste" type="button" role="tab"
        aria-controls="Waste" aria-selected="false">Waste</button>
    </li>
  </ul>
  <div class="tab-content d-flex flex-column flex-grow-1" id="myTabContent">
    <div class="tab-pane d-flex flex-column align-items-stretch overflow-auto" id="Devices" role="tabpanel" aria-labelledby="home-tab">
      <DeviceList :devices="device_defs"></DeviceList>
    </div>
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
          <li v-for="(layout, index) in filtered_layouts" :key="layout.device_name" class="nav-item" role="presentation">
            <button class="nav-link" :id="layout.device_name.replaceAll(' ', '') + '-tab'" data-bs-toggle="tab" :data-bs-target="'#' + layout.device_name.replaceAll(' ', '') + '-div'" type="button" role="tab"
        :aria-controls="layout.device_name" :class="{ active: (index==0) }" :aria-selected="(index == 0) ? true : false">{{ layout.device_name }}</button>
          </li>
        </ul>
        <div class="tab-content d-flex flex-fill" style="height:90%; width:90%" id="layoutTabContent">
          <div v-for="(layout, index) in filtered_layouts" :key="layout.device_name" class="tab-pane bedlayout" :class="{ active: (index==0), show: (index==0) }" :id="layout.device_name.replaceAll(' ', '') + '-div'">
            <BedLayout :device_name="layout.device_name" :layout="layout.layout"/>
          </div>        
        </div>
      </div>


    </div>
    <div class="tab-pane d-flex flex-grow-1 h-100 overflow-auto" id="LHInterface" role="tabpanel" aria-labelledby="lh-tab">
      <LHInterface />
    </div>    
    <div class="tab-pane d-flex flex-grow-1 h-100 overflow-auto" id="Materials" role="tabpanel" aria-labelledby="materials-tab">
      <MaterialManager />
    </div>
    <div class="tab-pane d-flex flex-grow-1 h-100" id="Waste" role="tabpanel" aria-labelledby="waste-tab">
      <WasteManager />
    </div>
    </div>

  <EditWellContents/>
  <EditRackSettings/>
  <AddWaste/>

</template>

<style scoped>
.flex-column {
  min-height: 0;
}

.bedlayout {
  height: 100%;
  width: 100%;
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
