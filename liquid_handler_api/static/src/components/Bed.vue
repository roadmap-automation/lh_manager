<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { layout, pick_handler, source_well, target_well } from '../store';
import type { Well } from '../store';

const props = defineProps<{
  height: number,
  width: number,
  rack_id: string,
  shape: 'circle' | 'rect',
  wells: Well[]
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
  if (well_number in filled_cells.value) {
    classList.push("partially-filled");
  }
  return classList.join(" ")
}

const filled_cells = computed(() => {
  const local_wells = props.wells.filter((w) => (w.rack_id === props.rack_id));
  const local_wells_lookup = Object.fromEntries(local_wells.map((w) => [w.well_number, w]));
  console.log(props.rack_id, local_wells_lookup);
  return local_wells_lookup;
});

function fill_path(col, row) {
  const well_number = (row * rack.columns + col + 1).toFixed();
  if (well_number in filled_cells.value) {
    const well_volume = filled_cells.value[well_number].volume;
    const max_volume = layout.value?.racks[props.rack_id].max_volume ?? well_volume;
    const fill_fraction = well_volume / max_volume;
    const cx = x_offset(col, row);
    const cy = y_offset(row);
    if (props.shape === 'circle') {  
      const rr = r.value;
      const y = cy + rr * (2 * fill_fraction - 1);
      // const sweep_flag = (fill_fraction > 0.5) ? "0" : "1";
      const large_arc = (fill_fraction > 0.5) ? "0" : "1";
      const dx = 2 * rr * Math.sqrt(fill_fraction - fill_fraction**2);
      return `M${cx - dx} ${y} A ${rr} ${rr} 0 ${large_arc} 0 ${cx + dx} ${y} Z`;
    }
    else if (props.shape === 'rect') {
      const dx = 0.5 * (col_width.value ?? 0) - padding;
      const dy = 0.5 * (row_height.value ?? 0) - padding;
      const x = cx - padding;
      const y = cy - padding;
      return `M${x - dx} ${y - dy} L ${x + dx} ${y - dy} L ${x + dx} ${y + dy} L ${x - dx} ${y + dy} Z`;
    }
  }
  else {
    return '';
  }
}
onMounted(() => {
})

</script>

<template>
  <rect :width="width" :height="height"></rect>
  <g v-for="row of row_array" :index="row">
    <g v-for="col of col_array" :index="col" :class="highlight_class(col, row)" :n="row * rack.columns + col">
      <title>{{ row * rack.columns + col + 1 }}</title>
      <circle v-if="props.shape === 'circle'" class="vial-button" :cx="x_offset(col, row)" :cy="y_offset(row)" :r="r"
        @click="clicked(row, col)">
        <title>{{ filled_cells[row*rack.columns + col + 1] }}</title>
      </circle>
      <rect :class="highlight_class(col, row)" v-if="props.shape === 'rect'" class="vial-button" :width="col_width - 2*padding" :height="row_height - 2*padding"
        :x="x_offset(col, row, false)" :y="y_offset(row, false)" @click="clicked(row, col)">
        <title>{{ filled_cells[row*rack.columns + col + 1] }}</title>
      </rect>
      <path class="fill-fraction" :d="fill_path(col, row)"></path>
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
  fill: white;
  fill-opacity: 0.3;
  stroke: black;
  stroke-width: 1px;
}

.vial-label {
  font: normal 20px sans-serif;
  pointer-events: none;
  dominant-baseline: central;
  fill: darkgreen;
}

.Source circle, .Source rect {
  /* fill: url(#source); */
  stroke: magenta;
  stroke-width: 8px;
}
.Target circle, .Target rect {
  /* fill: url(#target); */
  stroke: darkorange;
  stroke-width: 8px;
}

g.partially-filled circle, g.partially-filled rect {
  fill: white;
  fill-opacity: 1;
}

.fill-fraction {
  fill: lightgreen;
  fill-opacity: 0.6;
  pointer-events: none;
}

</style>