<script setup lang="ts">
// This starter template is using Vue 3 <script setup> SFCs
// Check out https://vuejs.org/api/sfc-script-setup.html#script-setup
import LiquidHandler from './components/LiquidHandler.vue';
import { ref, onMounted } from 'vue';
import { io } from 'socket.io-client';
import { samples, refreshSamples, refreshSampleStatus, refreshMethodDefs, refreshLayout, refreshComponents, refreshWells } from './store';
import type { MethodDef } from './store';

const connected = ref(false);

const socket = io('', {
});

socket.on('connect', () => {
  console.log("connected: ", socket.id);
  connected.value = true;
  refreshLayout();
  refreshWells();
  refreshSamples();
  refreshSampleStatus();
  refreshMethodDefs();
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

socket.on('update_layout', () => {
  refreshLayout();
})


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
