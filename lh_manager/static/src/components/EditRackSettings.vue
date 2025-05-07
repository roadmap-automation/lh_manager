<script setup lang="ts">
import { ref, defineProps, onMounted, watch, toRaw, computed, nextTick } from 'vue'
import { Modal } from 'bootstrap/dist/js/bootstrap.esm';
import { rack_editor_active, rack_to_edit, device_defs, device_layouts, update_rack } from '../store';
import type { Rack, DeviceLayout } from '../store';

//const props = defineProps<{
//  wells: Well[]
//}>();

const dialog = ref<HTMLDivElement>();
const current_rack = ref<Rack>();
const current_rack_id = ref<string>();
const update_address = ref<string>();

let modal: Modal;

onMounted(() => {
  modal = new Modal(dialog.value, { backdrop: 'static', keyboard: false, focus: true });
});

watch(rack_editor_active, async (newval, oldval) => {
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
  current_rack_id.value = rack_id
});

function send_changes() {
  if (current_rack.value) {
    update_rack(update_address.value, current_rack_id.value, current_rack.value);
  }
  rack_editor_active.value = false;
};

</script>

<template>
  <div class="modal" tabindex="-1" ref="dialog">
    <div class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Edit Rack {{ rack_to_edit?.rack_id }} on {{ rack_to_edit?.device }}</h5>
          <button type="button" class="btn-close" aria-label="Close" @click="rack_editor_active=false"></button>
        </div>
        <div class="modal-body">
          <div v-if="current_rack_id && current_rack" class="col">
            <div class="row-auto">
                <label>Min Volume (mL): <input type="number" v-model="current_rack.min_volume" /></label>
            </div>
            <div class="row-auto">
                <label>Max Volume (mL): <input type="number" v-model="current_rack.max_volume" /></label>
            </div>
          </div>
        </div>
        <div class="modal-footer justify-content-between">
          <div class="d-inline-flex">
            <button type="button" class="btn btn-secondary me-2" @click="rack_editor_active=false">Cancel</button>
            <button type="button" class="btn btn-primary" @click="send_changes">Save changes</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>

</style>