<script setup lang="ts">
import { ref, computed, defineProps } from 'vue'
import Bed from './Bed.vue';
import { device_layouts } from '../store';
import type { Well } from '../store';

const props = defineProps<{
  device_name: string
}>();

const max_x = computed(() => Math.max(...Object.values(device_layouts.value[props.device_name].layout.racks).map((rack) => rack.x_translate + rack.width)));
const max_y = computed(() => Math.max(...Object.values(device_layouts.value[props.device_name].layout.racks).map((rack) => rack.y_translate + rack.height)));

</script>

<template>
  <svg class="wrapper" v-if="device_layouts[props.device_name] !== undefined" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <pattern id="pattern"
              width="8" height="10"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45 50 50)">
        <line stroke="#a6a6a6" stroke-width="7px" y2="10"/>
      </pattern>
      <pattern id="source"
              width="12" height="12"
              viewBox="0,0,6,6"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(-45 0 0)">
        <line stroke="#E1FAE1" stroke-width="6px" x1="6" x2="6" y1="0" y2="12" />
        <line stroke="lightgreen" stroke-width="6px" x1="0" x2="0" y1="0" y2="10"/>
      </pattern>
      <pattern id="target"
              width="12" height="12"
              viewBox="0,0,6,6"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45 0 0)">
        <line stroke="white" stroke-width="6px" x1="6" x2="6" y1="0" y2="12" />
        <line stroke="pink" stroke-width="6px" x1="0" x2="0" y1="0" y2="10"/>
      </pattern>
    </defs>
    <svg class="inner" :viewBox="'0 0 ' + max_x.toString() + ' ' + max_y.toString()" x="0" y="0" preserveAspectRatio="xMinYMin meet">
      <!-- <rect width="150" height="80" fill="green" x="0" y="20"></rect> -->
      <g v-for="(rack, rack_id) in device_layouts[props.device_name].layout.racks" :transform="'translate(' + rack.x_translate + ',' + rack.y_translate + ')'">
        <Bed :rack_id="rack_id" :rack="rack" :device_name="props.device_name"/>
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