<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { pick_handler, rack_editor_active, rack_to_edit, source_well, target_well, well_editor_active, well_to_edit, batch_editor_active } from '../store';
import type { Rack, Well } from '../store';

const props = defineProps<{
  rack_id: string,
  rack: Rack,
  wells: Well[],
  device_name: string,
}>();

const text_size = 30;
const padding = 6;

const row_array = computed(() => Array.from({ length: props.rack.rows }).map((_, i) => i))
const col_array = computed(() => Array.from({ length: props.rack.columns }).map((_, i) => i));
const max_col_width = computed(() => (props.rack.width - text_size - 2 * padding) / props.rack.columns);
const row_height = computed(() => (props.rack.height - text_size - 2 * padding) / props.rack.rows);
// For square cells (circle shape vials):
const cell_size = computed(() => {
  return Math.min(row_height.value, max_col_width.value);
})
const r = computed(() => (cell_size.value / 2.0 - padding / 2.0));

const col_width = computed(() => {
  if (props.rack.shape === 'rect') {
    return props.rack.width / props.rack.columns;
  }
  else if (props.rack.shape === 'circle') {
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
  if (props.rack.style === 'staggered') {
    start = (row % 2) * 0.5 + centering_offset;
  }
  else {
    start = centering_offset;
  }  
  return padding + ((col_width.value ?? 0) * (col + start));
}

function clicked(row: number, col: number) {
  const well_number = row * props.rack.columns + col + 1;
  const rack_id = props.rack_id;
  pick_handler({ rack_id, well_number });
}

function edit_well(row: number, col: number) {
  const well_number = row * props.rack.columns + col + 1;
  const rack_id = props.rack_id;
  well_to_edit.value = {device: props.device_name, well: {well_number, rack_id}};

  // only trigger editing modal if rack is editable
  if (props.rack.editable) {
    well_editor_active.value = true;
  }
}

function edit_rack() {
  rack_to_edit.value = {device: props.device_name, rack_id: props.rack_id, rack: props.rack};
  rack_editor_active.value = true;
}

function batch_edit() {
  rack_to_edit.value = {device: props.device_name, rack_id: props.rack_id, rack: props.rack};
  batch_editor_active.value = true;
}

function highlight_class(col, row) {
  const well_number = row * props.rack.columns + col + 1;
  const classList: string[] = [];
  const target = target_well.value;
  const source = source_well.value;
  if (props.rack_id === target?.rack_id && well_number === target?.well_number) {
    classList.push("Target");
  }
  if (props.rack_id === source?.rack_id && well_number === source?.well_number) {
    classList.push("Source");
  }
  //if (well_number in reserved_cells.value) {
  //  classList.push("vial-reserved")
  //}  
  if (well_number in filled_cells.value) {
    classList.push("partially-filled");
  }
  //if (!props.rack.editable) {
  //  classList.push("not-editable")
  //}
  return classList.join(" ")
}

const filled_cells = computed(() => {
  const local_wells = props.wells.filter((w) => (w.rack_id === props.rack_id));
  const local_wells_lookup = Object.fromEntries(local_wells.map((w) => [w.well_number, w]));
  return local_wells_lookup;
});

const reserved_cells = computed(() => {
  const local_wells = props.wells.filter((w) => (w.id !== null) && (w.rack_id === props.rack_id));
  const local_wells_lookup = Object.fromEntries(local_wells.map((w) => [w.well_number, w]));
  return local_wells_lookup;
});

function fill_path(col, row) {
  const well_number = (row * props.rack.columns + col + 1).toFixed();
  if (well_number in filled_cells.value) {
    const well_volume = filled_cells.value[well_number].volume;
    const max_volume = props.rack.max_volume ?? well_volume;
    const epsilon = 1e-8;
    // keep fill fraction just below one so there's still an arc to draw...
    const fill_fraction = Math.min(well_volume / max_volume, 1-epsilon);
    const cx = x_offset(col, row);
    const cy = y_offset(row);
    if (props.rack.shape === 'circle') {  
      const rr = r.value;
      const y = cy - rr * (2 * fill_fraction - 1);
      // const sweep_flag = (fill_fraction > 0.5) ? "0" : "1";
      const large_arc = (fill_fraction > 0.5) ? "1" : "0";
      const dx = 2 * rr * Math.sqrt(fill_fraction - fill_fraction**2);
      return `M${cx - dx} ${y} A ${rr} ${rr} 0 ${large_arc} 0 ${cx + dx} ${y} Z`;
    }
    else if (props.rack.shape === 'rect') {
      const dx = 0.5 * (col_width.value ?? 0) - padding;
      const dy = 0.5 * (row_height.value ?? 0) - padding;
      const x = cx - padding;
      const y = cy - padding;
      const y_top = y - dy * (2 * fill_fraction - 1);
      return `M${x - dx} ${y_top} L ${x + dx} ${y_top} L ${x + dx} ${y + dy} L ${x - dx} ${y + dy} Z`;
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
  <rect :width="props.rack.width" :height="props.rack.height" :class="{'not-editable': (!props.rack.editable)}"></rect>
  <g v-for="row of row_array" :index="row">
    <g v-for="col of col_array" :index="col" :class="highlight_class(col, row)" :n="row * props.rack.columns + col">
      <title>{{ row * props.rack.columns + col + 1 }}</title>
      <circle v-if="props.rack.shape === 'circle'" class="vial-button" :cx="x_offset(col, row)" :cy="y_offset(row)" :r="r"
        @click="clicked(row, col)"
        @contextmenu.prevent="edit_well(row, col)">
        <title>{{ filled_cells[row*props.rack.columns + col + 1] }}</title>
      </circle>
      <rect :class="highlight_class(col, row)" v-if="props.rack.shape === 'rect'" class="vial-button" :width="col_width - 2*padding" :height="row_height - 2*padding"
        :x="x_offset(col, row, false)" :y="y_offset(row, false)" @click="clicked(row, col)" @contextmenu.prevent="edit_well(row, col)">
        <title>{{ filled_cells[row*props.rack.columns + col + 1] }}</title>
      </rect>
      <path class="fill-fraction" :d="fill_path(col, row)"></path>
      <text v-if="(props.rack.columns * props.rack.rows > 1)" class="vial-label" :class="(row * props.rack.columns + col + 1) in reserved_cells ? 'vial-reserved' : 'vial-notreserved'" :x="x_offset(col, row)" :y="y_offset(row)" text-anchor="middle">
        {{ row * props.rack.columns + col + 1 }}</text>
    </g>
  </g>
  <text class="title" :y="props.rack.height - padding" :x="props.rack.width / 2">{{ props.rack_id }}</text>
  <image @click="batch_edit" v-if="props.rack.editable" class="vial-button" :x="props.rack.width - text_size * 2" :y="props.rack.height - text_size" :width="text_size - padding" :height="text_size - padding" href='data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-grid-3x3-gap" viewBox="0 0 16 16"><path d="M4 2v2H2V2zm1 12v-2a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1m0-5V7a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1m0-5V2a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1m5 10v-2a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1m0-5V7a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1m0-5V2a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1M9 2v2H7V2zm5 0v2h-2V2zM4 7v2H2V7zm5 0v2H7V7zm5 0h-2v2h2zM4 12v2H2v-2zm5 0v2H7v-2zm5 0v2h-2v-2zM12 1a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1zm-1 6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1zm1 4a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1z"/></svg>'>
    <title>Batch edit wells</title>
  </image>  
  <image @click="edit_rack" class="vial-button" :x="props.rack.width - text_size" :y="props.rack.height - text_size" :width="text_size - padding" :height="text_size - padding" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-gear' viewBox='0 0 16 16'><path d='M8 4.754a3.246 3.246 0 1 0 0 6.492 3.246 3.246 0 0 0 0-6.492M5.754 8a2.246 2.246 0 1 1 4.492 0 2.246 2.246 0 0 1-4.492 0'/><path d='M9.796 1.343c-.527-1.79-3.065-1.79-3.592 0l-.094.319a.873.873 0 0 1-1.255.52l-.292-.16c-1.64-.892-3.433.902-2.54 2.541l.159.292a.873.873 0 0 1-.52 1.255l-.319.094c-1.79.527-1.79 3.065 0 3.592l.319.094a.873.873 0 0 1 .52 1.255l-.16.292c-.892 1.64.901 3.434 2.541 2.54l.292-.159a.873.873 0 0 1 1.255.52l.094.319c.527 1.79 3.065 1.79 3.592 0l.094-.319a.873.873 0 0 1 1.255-.52l.292.16c1.64.893 3.434-.902 2.54-2.541l-.159-.292a.873.873 0 0 1 .52-1.255l.319-.094c1.79-.527 1.79-3.065 0-3.592l-.319-.094a.873.873 0 0 1-.52-1.255l.16-.292c.893-1.64-.902-3.433-2.541-2.54l-.292.159a.873.873 0 0 1-1.255-.52zm-2.633.283c.246-.835 1.428-.835 1.674 0l.094.319a1.873 1.873 0 0 0 2.693 1.115l.291-.16c.764-.415 1.6.42 1.184 1.185l-.159.292a1.873 1.873 0 0 0 1.116 2.692l.318.094c.835.246.835 1.428 0 1.674l-.319.094a1.873 1.873 0 0 0-1.115 2.693l.16.291c.415.764-.42 1.6-1.185 1.184l-.291-.159a1.873 1.873 0 0 0-2.693 1.116l-.094.318c-.246.835-1.428.835-1.674 0l-.094-.319a1.873 1.873 0 0 0-2.692-1.115l-.292.16c-.764.415-1.6-.42-1.184-1.185l.159-.291A1.873 1.873 0 0 0 1.945 8.93l-.319-.094c-.835-.246-.835-1.428 0-1.674l.319-.094A1.873 1.873 0 0 0 3.06 4.377l-.16-.292c-.415-.764.42-1.6 1.185-1.184l.292.159a1.873 1.873 0 0 0 2.692-1.115z'/></svg>">
    <title>Rack settings</title>
  </image>
</template>

<style scoped>
rect {
  stroke-width: 3px;
  stroke: black;
  clip-path: rect();
  fill: #a0a0a0;
}

.not-editable {
  stroke-dasharray: 10, 10;
}

.title {
  fill: white;
  font: normal 2vmin sans-serif;
  text-anchor: middle;
}

.vial-reserved {
  fill: lightcoral;
}

.vial-notreserved {
  fill: darkgreen;
}

.vial-button {
  cursor: pointer;
  fill: white;
  fill-opacity: 0.3;
  stroke: black;
  stroke-width: 2px;
}

.vial-label {
  font: normal 2vmin sans-serif;
  pointer-events: none;
  dominant-baseline: central;
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