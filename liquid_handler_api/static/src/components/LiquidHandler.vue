<script setup>
import { ref } from 'vue'
import { onMounted } from 'vue';
import Mixture from './Mixture.vue';
import BedLayout from './BedLayout.vue';
import SampleList from './SampleList.vue';
import { samples, sample_status, wells } from '../store';

const props = defineProps({
  msg: String,
  // samples: Array,
  // sample_status: Object,
})

const emit = defineEmits(['remove_sample', 'add_sample']);

const active_sample = ref(0);

const chemical_components = [
  "D2O",
  "H2O",
  "Polymer goo"
]

const mixture_parts = [];

onMounted(() => {
  console.log(props.sample_status);
});

const mixtureIsOpen = ref(false);

function openMixture() {
  mixtureIsOpen.value = true;
}


</script>

<template>
  <ul class="nav nav-tabs" id="myTab" role="tablist">
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="home-tab" data-bs-toggle="tab" data-bs-target="#NICE" type="button" role="tab"
        aria-controls="NICE" aria-selected="false">NICE</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="profile-tab" data-bs-toggle="tab" data-bs-target="#GilsonLH" type="button" role="tab"
        aria-controls="GilsonLH" aria-selected="false">Gilson LH</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link active" id="layout-tab" data-bs-toggle="tab" data-bs-target="#Layout" type="button"
        role="tab" aria-controls="Layout" aria-selected="true">Layout</button>
    </li>
  </ul>
  <div class="tab-content d-flex flex-column flex-grow-1" id="myTabContent">
    <div class="tab-pane" id="NICE" role="tabpanel" aria-labelledby="home-tab">NICE things</div>
    <div class="tab-pane" id="GilsonLH" role="tabpanel" aria-labelledby="profile-tab">
      <h1>Liquid Handler things</h1>
      <!-- Button trigger modal -->
      <button type="button" class="btn btn-primary" @click="openMixture">
        Launch demo modal
      </button>
      <Mixture @close="mixtureIsOpen = false" :show="mixtureIsOpen" :chemical_components="chemical_components" />

    </div>
    <div class="tab-pane show active d-flex flex-row flex-grow-1 align-items-stretch overflow-auto" id="Layout"
      role="tabpanel" aria-labelledby="layout-tab">
      <div class="overflow-auto">
        <div class="card m-3">
          <div class="card-body">
            <h5 class="card-title">Samples</h5>
          </div>
          <SampleList />
        </div>
      </div>

      <div class="flex-grow-1">
        <BedLayout :wells="wells" />
      </div>
    </div>

  </div>




</template>

<style scoped>
.flex-column {
  min-height: 0;
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
