<script setup>
// This starter template is using Vue 3 <script setup> SFCs
// Check out https://vuejs.org/api/sfc-script-setup.html#script-setup
import LiquidHandler from './components/LiquidHandler.vue';
import { ref, onMounted } from 'vue';
import { io } from 'socket.io-client';
import { method_defs } from './store';

const connected = ref(false);
const layout = ref(null);
const samples = ref([]);
const sample_status = ref({});

const socket = io('', {
  // this is mostly here to test what happens on server fail:
});

socket.on('connect', () => {
  console.log("connected: ", socket.id);
  connected.value = true;
  refreshLayout();
  refreshSamples();
  refreshSampleStatus();
  refreshMethodDefs();
});

socket.on('disconnect', (payload) => {
  console.log("disconnected!", payload);
  connected.value = false;
})

socket.on('update_samples', () => {
  console.log("it's time to update samples...");
  // go fetch from the endpoint...
})

socket.on('update_layout', () => {
  console.log("it's time to update the layout...");
})

async function refreshLayout() {
  const new_layout = await (await fetch("/GUI/GetLayout")).json();
  layout.value = new_layout;
}

async function refreshSamples() {
  const { samples: { samples: new_samples_in } } = await (await fetch('/GUI/GetSamples/')).json();
  // filter samples to extract only what the GUI will edit:
  const new_samples = new_samples_in.map((s) => {
    const { description, stages: unfiltered_stages, name, id } = s;
    const stages = Object.fromEntries(Object.entries(unfiltered_stages).map(([stage, { methods }]) => [stage, { methods }]));
    return { description, name, id, stages };
  });
  samples.value = new_samples;
}

async function refreshSampleStatus() {
  const { samples: { samples: new_samples_in } } = await (await fetch('/GUI/GetSamples/')).json();
  const new_sample_status = Object.fromEntries(new_samples_in.map((s) => {
    const { stages: unfiltered_stages, id } = s;
    const stages = Object.fromEntries(Object.entries(unfiltered_stages).map(([stage, { methods_complete, status }]) => [stage, { methods_complete, status }]));

    return [id, stages];
  }));
  sample_status.value = new_sample_status;
  console.log(new_sample_status, new_samples_in);
}

async function refreshMethodDefs() {
  const { methods } = await (await fetch("/GUI/GetAllMethods/")).json();
  method_defs.value = methods;
}

function remove_sample(id) {
  const idx_to_remove = samples.value.findIndex((s) => s.id == id);
  if (idx_to_remove != null) {
    samples.value.splice(idx_to_remove, 1);
  }
}

function add_sample() {
  const ids = samples.value.map((s) => s.id);
  samples.value.push({ name: 'new', description: '', id: Math.max(...ids) + 1 })
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
    <LiquidHandler :layout="layout" :samples="samples" :sample_status="sample_status" @remove_sample="remove_sample"
      @add_sample="add_sample" />
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
