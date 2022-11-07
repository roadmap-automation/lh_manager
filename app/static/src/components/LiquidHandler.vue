<script setup>
import { ref } from 'vue'
// import { Modal } from 'bootstrap';
import { Modal } from 'bootstrap';
import { onMounted } from 'vue';
import Mixture from './Mixture.vue';
import Bed from './Bed.vue';

defineProps({
  msg: String
})

const chemical_components = [
  "D2O",
  "H2O",
  "Polymer goo"
]

const mixture_parts = [];

onMounted(() => {

});

const layout = {
  "racks": {
    "MTPlateBottom": {
      "columns": 8,
      "max_volume": 0.28,
      "rows": 12,
      "style": "grid",
      "wells": []
    },
    "MTPlateTop": {
      "columns": 8,
      "max_volume": 0.28,
      "rows": 12,
      "style": "grid",
      "wells": []
    },
    "Mix": {
      "columns": 4,
      "max_volume": 9.0,
      "rows": 20,
      "style": "staggered",
      "wells": [
        {
          "composition": {
            "solutes": [],
            "solvents": []
          },
          "rack_id": "Mix",
          "volume": 0.0,
          "well_number": 1
        }
      ]
    },
    "Samples": {
      "columns": 4,
      "max_volume": 2.0,
      "rows": 15,
      "style": "grid",
      "wells": []
    },
    "Solvent": {
      "columns": 3,
      "max_volume": 700.0,
      "rows": 1,
      "style": "grid",
      "wells": []
    },
    "Stock": {
      "columns": 2,
      "max_volume": 20.0,
      "rows": 7,
      "style": "grid",
      "wells": [
        {
          "composition": {
            "solutes": [
              {
                "concentration": 0.1,
                "name": "KCl",
                "units": "M"
              }
            ],
            "solvents": [
              {
                "fraction": 1.0,
                "name": "D2O"
              }
            ]
          },
          "rack_id": "Stock",
          "volume": 8.0,
          "well_number": 1
        },
        {
          "composition": {
            "solutes": [
              {
                "concentration": 1.0,
                "name": "KCl",
                "units": "M"
              }
            ],
            "solvents": [
              {
                "fraction": 1.0,
                "name": "H2O"
              }
            ]
          },
          "rack_id": "Stock",
          "volume": 8.0,
          "well_number": 2
        }
      ]
    }
  }
}



function clicked(bed, vial) {
  console.log(bed, vial);
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
    <div class="tab-pane show active d-flex flex-column flex-grow-1" id="Layout" role="tabpanel"
      aria-labelledby="layout-tab">
      <!-- <div style="height:calc(100%);width:auto;background-color:blue;">
        <svg viewBox="0 0 150 100" width="150" height="100" preserveAspectRatio="xMinyMin" x="0" y="0" style="height:calc(100% - 1em);width:calc(100% - 1em);">
        <rect width="150" height="100" fill="green"></rect>
        <g v-for="vial in vials" :key="vial.target">
          <circle class="vial-button" :cx="vial.x" :cy="vial.y" r="4" @click="clicked(vial)" />
          <text class="vial-label" :x="vial.x" :y="vial.y" text-anchor="middle" dy=".3em">{{vial.label}}</text>
        </g>
      </svg>
      </div> -->
      <svg viewBox="0 0 1500 1000" x="0" y="0" preserveAspectRatio="xMinyMin meet" style="width:100%;height:100%;">
        <!-- <rect width="150" height="80" fill="green" x="0" y="20"></rect> -->
        <g transform="translate(0,0)">
          <rect class="solvents" width="900" height="200"></rect>
          <g v-for="s in 3" :index="s">
            <!-- <ellipse class="solvent" v-for="s in 3" rx="125" ry="70" :cx="s * 300 - 150" :cy="80"></ellipse> -->
            <rect class="vial-button" width="250" height="140" :x="(s - 1) * 300 + 25" :y="25"></rect>
            <text class="vial-label" :x="(s - 1) * 300 + 150" :y="95" text-anchor="middle">{{ s }}</text>
          </g>
          <text class="title" :y="192" :x="450">Solvents</text>
        </g>
        <g transform="translate(0,200)">
          <Bed width="300" height="800" title="Samples" :rows="layout.racks.Samples.rows"
            :columns="layout.racks.Samples.columns" :style="layout.racks.Samples.style"
            :wells="layout.racks.Samples.wells" @clicked="clicked" />
        </g>
        <g transform="translate(300,200)">
          <Bed width="300" height="800" title="Stock" :rows="layout.racks.Stock.rows"
            :columns="layout.racks.Stock.columns" :style="layout.racks.Stock.style" :wells="layout.racks.Stock.wells"
            @clicked="clicked" />
        </g>
        <g transform="translate(600,200)">
          <Bed width="300" height="800" title="Mix" :rows="layout.racks.Mix.rows" :columns="layout.racks.Mix.columns"
            :style="layout.racks.Mix.style" :wells="layout.racks.Mix.wells" @clicked="clicked" />

        </g>
        <!-- <g v-for="vial in vials" :key="vial.target">
          <circle class="vial-button" :cx="vial.x" :cy="vial.y" r="4" @click="clicked(vial)" />
          <text class="vial-label" :x="vial.x" :y="vial.y" text-anchor="middle" dy=".3em">{{vial.label}}</text>
        </g> -->
      </svg>
    </div>

  </div>




</template>

<style scoped>
.flex-column {
  min-height: 0;
}

.vial-button {
  cursor: pointer;
  fill: orange;
  stroke: black;
  stroke-width: 1px;
}

.vial-label {
  font: normal 20px sans-serif;
  pointer-events: none;
  dominant-baseline: central;
  fill: darkgreen;
}

svg rect {
  stroke-width: 0.2px;
  stroke: black;
  clip-path: rect();
  fill: #a0a0a0;
}

.title {
  fill: white;
  font: normal 30px sans-serif;
  text-anchor: middle;
}

.tab-pane:not(.active) {
  display: none !important;
}
</style>
