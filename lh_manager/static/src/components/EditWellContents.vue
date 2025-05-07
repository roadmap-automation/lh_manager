<script setup lang="ts">
import { ref, defineProps, onMounted, watch, toRaw, computed, nextTick } from 'vue'
import { Modal } from 'bootstrap/dist/js/bootstrap.esm';
import { well_editor_active, well_to_edit, update_well_contents, remove_well_definition, device_defs, device_layouts, waste_layout, current_composition } from '../store';
import type { Well, DeviceLayout } from '../store';
import NewComposition from './NewComposition.vue';

//const props = defineProps<{
//  wells: Well[]
//}>();

const dialog = ref<HTMLDivElement>();
const current_well = ref<Well>();
const current_layout = ref<DeviceLayout>();
const update_address = ref<string>();

let modal: Modal;

onMounted(() => {
  modal = new Modal(dialog.value, { backdrop: 'static', keyboard: false, focus: true });
});

watch(well_editor_active, async (newval, oldval) => {
  (newval) ? modal?.show() : modal?.hide();
});

watch(well_to_edit, async(newval, oldval) => {
  // populate a local copy of a well, for editing.
  if (newval === undefined) { return }
  const { device, well } = toRaw(newval);
  const { rack_id, well_number } = well;
  if (device in device_layouts.value) {
    current_layout.value = device_layouts.value[device];
    update_address.value = device_defs.value[device].address;
  }
  else {
    current_layout.value = waste_layout.value;
    update_address.value = "/Waste"
  }
  const existing_well = current_layout.value.wells.find((well) => (well.rack_id === rack_id && well.well_number === well_number));
  current_well.value = structuredClone(toRaw(existing_well)) ?? {...structuredClone(empty_well), rack_id, well_number};
  current_composition.value = current_well.value?.composition;
});

const empty_well = {
  rack_id: null,
  well_number: null,
  composition: {
    solvents: [],
    solutes: [],
  },
  volume: 0,
}

function send_changes() {
  if (current_well.value) {
    current_well.value.composition = current_composition.value;
    update_well_contents(update_address.value, current_well.value);
  }
  well_editor_active.value = false;
};

function remove_definition() {
  if (current_well.value) {
    remove_well_definition(update_address.value, current_well.value);
  }
  well_editor_active.value = false;
}

</script>

<template>
  <div class="modal" tabindex="-1" ref="dialog">
    <div class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Edit Well {{  well_to_edit?.well.rack_id }}::{{ well_to_edit?.well.well_number }}</h5>
          <button type="button" class="btn-close" aria-label="Close" @click="well_editor_active=false"></button>
        </div>
        <div class="modal-body">
          <details>
            <summary>json</summary>
            <pre>{{ JSON.stringify(toRaw(current_well), null, 2) }}</pre>
          </details>
          <div v-if="current_well && current_layout.layout">
            <label>Volume: <input type="number" v-model="current_well.volume" :max="current_layout.layout.racks[current_well.rack_id].max_volume" /></label>
            <emph>(Max Volume: {{ current_layout.layout.racks[current_well.rack_id].max_volume }})</emph>
            <div>
              <input type="range" class="form-range" v-model="current_well.volume" min="0" :max="current_layout.layout.racks[current_well.rack_id].max_volume">
            </div>
          </div>
          <NewComposition/>    
        </div>
        <div class="modal-footer justify-content-between">
          <button type="button" class="btn btn-danger" @click="remove_definition">Remove Definition</button>
          <div class="d-inline-flex">
            <button type="button" class="btn btn-secondary me-2" @click="well_editor_active=false">Cancel</button>
            <button type="button" class="btn btn-primary" @click="send_changes">Save changes</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>

</style>