<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { layout, pick_handler, source_well, target_well } from '../store';

const props = defineProps<{
  height: number,
  width: number,
  rack_id: string,
  shape: 'circle' | 'rect'
}>();

const text_size = 30;
const padding = 6;

const rack = layout.value?.racks[props.rack_id] ?? {rows: 0, columns:0, style: 'grid'};

const row_array = computed(() => Array.from({ length: rack.rows }).map((_, i) => i))
const col_array = computed(() => Array.from({ length: rack.columns }).map((_, i) => i));
const max_col_width = computed(() => (props.width - text_size - 2 * padding) / rack.columns);
const row_height = computed(() => (props.height - text_size - 2 * padding) / rack.rows);
// For square cells (circle shape vials):
const cell_size = computed(() => {
  return Math.min(row_height.value, max_col_width.value);
})
const r = computed(() => (cell_size.value / 2.0 - padding / 2.0));

const col_width = computed(() => {
  if (props.shape === 'rect') {
    return props.width / rack.columns;
  }
  else if (props.shape === 'circle') {
    return cell_size.value;
  }
});

function y_offset(col: number, centered: boolean = true) {
  const centering_offset = (centered) ? 0.5 : 0;
  return 2 * padding + (cell_size.value * (col + centering_offset));
}

function x_offset(col: number, row: number, centered: boolean = true) {
  let start: number;
  const centering_offset = (centered) ? 0.5 : 0;
  if (rack.style === 'staggered') {
    start = (row % 2) * 0.5 + centering_offset;
  }
  else {
    start = centering_offset;
  }  
  return padding + ((col_width.value ?? 0) * (col + start));
}

function clicked(row: number, col: number) {
  const well_number = row * rack.columns + col + 1;
  const rack_id = props.rack_id;
  pick_handler({ rack_id, well_number });
}

function highlight_class(col, row) {
  const well_number = row * rack.columns + col + 1;
  const classList: string[] = [];
  const target = target_well.value;
  const source = source_well.value;
  if (props.rack_id === target?.rack_id && well_number === target?.well_number) {
    classList.push("Target");
  }
  if (props.rack_id === source?.rack_id && well_number === source?.well_number) {
    classList.push("Source");
  }
  return classList.join(" ")
}

onMounted(() => {
})

</script>

<template>
  <rect :width="width" :height="height"></rect>
  <g v-for="row of row_array" :index="row">
    <g v-for="col of col_array" :index="col" :n="row * rack.columns + col">
      <title>{{ row * rack.columns + col + 1 }}</title>
      <circle :class="highlight_class(col, row)" v-if="props.shape === 'circle'" class="vial-button" :cx="x_offset(col, row)" :cy="y_offset(row)" :r="r"
        @click="clicked(row, col)"></circle>
      <rect :class="highlight_class(col, row)" v-if="props.shape === 'rect'" class="vial-button" :width="col_width - 2*padding" :height="row_height - 2*padding"
        :x="x_offset(col, row, false)" :y="y_offset(row, false)" @click="clicked(row, col)"></rect>
      <text class="vial-label" :x="x_offset(col, row)" :y="y_offset(row)" text-anchor="middle">
        {{ row * rack.columns + col + 1 }}</text>
    </g>
  </g>
  <text class="title" :y="height - padding" :x="width / 2">{{ props.rack_id }}</text>
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

.Source {
  fill: url(#source);
}
.Target {
  fill: url(#target);
}
</style>