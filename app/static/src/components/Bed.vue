<script setup lang="ts">
import { computed, onMounted } from 'vue';

const props = defineProps<{
  height: number,
  width: number,
  title: string,
  columns: number,
  rows: number,
  wells: object,
  style: 'grid' | 'staggered',
}>();

const text_size = 30;
const padding = 6;

const row_array = computed(() => Array.from({length: props.rows}).map((_,i) => i))
const col_array = computed(() => Array.from({length: props.columns}).map((_,i) => i));
const cell_size = computed(() => {
  const max_col_width = (props.width - text_size - 2*padding) / props.columns;
  const max_row_height = (props.height - text_size - 2*padding) / props.rows;
  return Math.min(max_row_height, max_col_width);
})
const r = computed(() => (cell_size.value / 2.0 - padding/2.0));

function y_offset(col) {
  return 2 * padding + (cell_size.value * (col + 0.5));
}

function x_offset(col, row) {
  let start: number;
  if (props.style === 'staggered') {
    start = (row % 2) * 0.5 + 0.25;
  }
  else {
    start = 0.5;
  }

  return 2 * padding + (cell_size.value * (col + start));
}

function clicked(vial) {
  alert(`pressed: ${JSON.stringify(vial)}`)
}

const emit = defineEmits(['clicked']);

onMounted(() => {
})

</script>

<template>
  <rect :width="width" :height="height"></rect>
    <g v-for="row of row_array" :index="row">
      <g v-for="col of col_array" :index="col" :n="row * props.columns + col">
        <title>{{row * props.columns + col + 1}}</title>
        <circle class="vial-button" :cx="x_offset(col, row)" :cy="y_offset(row)" :r="r" @click="emit('clicked', props.title, (row * props.columns + col + 1))"></circle>
        <text class="vial-label" :x="x_offset(col,row)" :y="y_offset(row)" text-anchor="middle">{{row * props.columns + col + 1}}</text>
      </g>
    </g>
    <text class="title" :y="height - padding" :x="width/2">{{props.title}}</text>
</template>

<style scoped>
rect {
  stroke-width: 1px;
  stroke: black;
  clip-path: rect();
  fill: #a0a0a0;
}
.title {
  fill: white;
  font: normal 30px sans-serif;
  text-anchor: middle;
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

</style>