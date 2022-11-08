<script setup>
import { ref } from 'vue'
import Bed from './Bed.vue';

defineProps({
  layout: Object
})

const example_layout = {
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

</script>

<template>
  <svg class="wrapper" v-if="layout != null" xmlns="http://www.w3.org/2000/svg" >
      <svg class="inner" viewBox="0 0 900 1000" x="0" y="0"
        preserveAspectRatio="xMinYMin meet">
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
      </svg>
  </svg>
</template>

<style scoped>
svg.inner {
  height: auto;
  width: auto;
}

svg.wrapper {
  height: 100%;
  width: 100%;
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
</style>