<script setup>
import { ref } from 'vue'
import { Modal } from 'bootstrap';
import { onMounted } from 'vue';
import Mixture from './Mixture.vue';
import BedLayout from './BedLayout.vue';
import { Emitter } from '@socket.io/component-emitter';

defineProps({
  msg: String,
  layout: Object,
  samples: Object
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

});

function clicked(bed, vial) {
  console.log(bed, vial);
}

function sample_clicked(id) {
  active_sample.value = id;
}

function remove_sample(id) {
  emit('remove_sample', id);
}

function add_sample(id) {
  emit('add_sample');
}

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
            <h5 class="card-title">Samples
              <button class="btn btn-outline-primary" @click="add_sample">Add</button>
            </h5>
          </div>
          <!-- <ol class="list-group list-group-flush list-group-numbered overflow-auto"> -->
            <transition-group  class="list-group list-group-flush list-group-numbered overflow-auto" name="list" tag="ol">
              <li class="list-group-item d-flex justify-content-between list-group-item-action list-complete-item"
                :class="{ active: sample.id === active_sample }" v-for="sample of samples" :key="sample.id"
                @click="sample_clicked(sample.id)">
                <span class="fw-bold align-middle px-2"> {{ sample.name }} </span>
                <span class="align-middle px-2"> {{ sample.description }}</span>
                <button type="button" class="btn-close btn-sm align-middle text-align-right side-btn" aria-label="Close"
                  @click="remove_sample(sample.id)"></button>
              </li>
            </transition-group>
            <!-- <button class="btn btn-outline-primary" @click="add_sample">Add</button> -->
          <!-- </ol> -->
        </div>
      </div>
      <div class="flex-grow-1">
        <BedLayout :layout="layout" />
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
</style>
