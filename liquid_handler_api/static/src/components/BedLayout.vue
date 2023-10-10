<script setup>
import { ref } from 'vue'
import Bed from './Bed.vue';
import { layout, emitter } from '../store';

</script>

<template>
  <svg class="wrapper" v-if="layout !== undefined" xmlns="http://www.w3.org/2000/svg">
    <svg class="inner" viewBox="0 0 900 1000" x="0" y="0" preserveAspectRatio="xMinYMin meet">
      <!-- <rect width="150" height="80" fill="green" x="0" y="20"></rect> -->
      <g transform="translate(0,0)">
        <Bed width="900" height="200" rack_id="Solvent" shape="rect" />
      </g>
      <g transform="translate(0,200)">
        <Bed width="300" height="800" rack_id="Samples" shape="circle" />
      </g>
      <g transform="translate(300,200)">
        <Bed width="300" height="800" rack_id="Stock" shape="circle"/>
      </g>
      <g transform="translate(600,200)">
        <Bed width="300" height="800" rack_id="Mix" shape="circle"/>
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