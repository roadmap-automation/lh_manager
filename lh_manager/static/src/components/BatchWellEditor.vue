<script setup lang="ts">
import { ref, defineProps, onMounted, watch, toRaw, computed, nextTick } from 'vue'
import { Modal } from 'bootstrap/dist/js/bootstrap.esm';
import { batch_editor_active, rack_to_edit, device_defs, device_layouts, update_rack, remove_well_definition, update_well_contents } from '../store';
import type { Rack, DeviceLayout } from '../store';

//const props = defineProps<{
//  wells: Well[]
//}>();

const dialog = ref<HTMLDivElement>();
const current_rack = ref<Rack>();
const current_rack_id = ref<string>();
const first_well = ref<number>();
const last_well = ref<number>();
const update_address = ref<string>();

let modal: Modal;

onMounted(() => {
  modal = new Modal(dialog.value, { backdrop: 'static', keyboard: false, focus: true });
});

watch(batch_editor_active, async (newval, oldval) => {
  (newval) ? modal?.show() : modal?.hide();
});

watch(rack_to_edit, async(newval, oldval) => {
  // populate a local copy of a well, for editing.
  if (newval === undefined) { return }
  const { device, rack_id, rack } = toRaw(newval);
  if (device in device_layouts.value) {
    update_address.value = device_defs.value[device].address;
  }
  else {
    update_address.value = "/Waste";
  }
  current_rack.value = structuredClone(toRaw(rack));
  current_rack_id.value = rack_id;
  first_well.value = 1;
  last_well.value = rack.rows * rack.columns;
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

async function empty_wells() {
    for (let i = first_well?.value ?? 1; i < ((last_well?.value) ?? (rack_to_edit.rack.rows * rack_to_edit.rack.columns - 1)) + 1; i++) {
        const new_well = empty_well;
        new_well.rack_id = current_rack_id.value;
        new_well.well_number = i;
        await update_well_contents(update_address.value, new_well)
    }
    batch_editor_active.value = false;
}

async function remove_wells() {
    for (let i = first_well?.value ?? 1; i < ((last_well?.value) ?? (rack_to_edit.rack.rows * rack_to_edit.rack.columns - 1)) + 1; i++) {
        const new_well = empty_well;
        new_well.rack_id = current_rack_id.value;
        new_well.well_number = i;
        await remove_well_definition(update_address.value, new_well)
    }
    batch_editor_active.value = false;
}

</script>

<template>
  <div class="modal" tabindex="-1" ref="dialog">
    <div class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Batch edit wells in rack {{ rack_to_edit?.rack_id }} on {{ rack_to_edit?.device }}</h5>
          <button type="button" class="btn-close" aria-label="Close" @click="batch_editor_active=false"></button>
        </div>
        <div class="modal-body">
          <div v-if="current_rack_id && current_rack" class="col">
            <div class="row-auto">
                <label>First well: <input type="number" v-model="first_well" min="1" :max="last_well" /></label>
            </div>
            <div class="row-auto">
                <label>Last well: <input type="number" v-model="last_well" :min="first_well" :max="rack_to_edit?.rack.rows * rack_to_edit?.rack.columns"/></label>
            </div>
          </div>
        </div>
        <div class="modal-footer justify-content-between">
          <div class="d-inline-flex">
            <button type="button" class="btn btn-secondary me-2" @click="batch_editor_active=false">Cancel</button>
            <button type="button" class="btn btn-dark me-2" @click="remove_wells">Remove well definitions</button>
            <button type="button" class="btn btn-primary me-2" @click="empty_wells">Replace vials with empties</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>

</style>