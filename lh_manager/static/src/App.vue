<script setup lang="ts">
// This starter template is using Vue 3 <script setup> SFCs
// Check out https://vuejs.org/api/sfc-script-setup.html#script-setup
import LiquidHandler from './components/LiquidHandler.vue';
import { ref, onMounted } from 'vue';
import { io } from 'socket.io-client';
import { samples, refreshSamples, refreshSampleStatus, refreshMethodDefs, refreshWaste, refreshWells, refreshMaterials, refreshDeviceDefs, refreshDeviceLayouts, device_defs } from './store';
import type { MethodDef } from './store';

const connected = ref(false);

const socket = io('', {
});

socket.on('connect', () => {
  console.log("connected: ", socket.id);
  connected.value = true;
  refreshSamples();
  refreshSampleStatus();
  refreshMethodDefs();
  refreshMaterials();
  refreshDeviceLayouts();
  establish_socket_connections();
  refreshWaste();
});

socket.on('disconnect', (payload) => {
  console.log("disconnected!", payload);
  connected.value = false;
})

socket.on('update_samples', () => {
  // go fetch from the endpoint...
  refreshSamples();
})

socket.on('update_sample_status', () => {
  // go fetch from the endpoint...
  refreshSampleStatus();
})

socket.on('update_waste', () => {
//  console.log('Got base refresh')
//  refreshDeviceLayouts()
  refreshWaste();
})

socket.on('update_materials', () => {
  refreshMaterials();
});

socket.on('update_devices', () => {
  refreshDeviceDefs();
});

async function establish_socket_connections() {
  await refreshDeviceLayouts();
  console.log(device_defs.value)
  for (const device of Object.values(device_defs.value)) {
    console.log('Creating new socket for ' + device.device_name)
    const new_socket = io(device.address)

    new_socket.on('connect', () => {
      console.log('Connected to ' + device.device_name);
      refreshWells(device.device_name);
    })

    new_socket.on('update_layout', () => {
      console.log('Got update layout from ' + device.device_name)
      refreshWells(device.device_name);
    })
  }
}

</script>

<template>
  <div class="h-100 d-flex flex-column overflow-hidden">
    <nav class="navbar navbar-light bg-light py-0">
      <div class="container-fluid">
        <div class="navbar-brand">
          <img src="./assets/f_nist-logo-centerforneutronresearch-black_nist-logo-centerforneutronresearch-black.png"
            alt="" height="50" class="d-inline-block align-text-middle">
          Reflectometry Liquid Handling
        </div>
      </div>
    </nav>
    <LiquidHandler />
  </div>
</template>

<style scoped>
.logo {
  height: 6em;
  padding: 1.5em;
  will-change: filter;
}

.logo:hover {
  filter: drop-shadow(0 0 2em #646cffaa);
}

.logo.vue:hover {
  filter: drop-shadow(0 0 2em #42b883aa);
}
</style>
