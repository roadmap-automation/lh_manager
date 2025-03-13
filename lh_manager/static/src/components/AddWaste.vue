<script setup lang="ts">
import { ref, defineProps, onMounted, watch, toRaw, computed, nextTick } from 'vue'
import { Modal } from 'bootstrap/dist/js/bootstrap.esm';
import { add_waste_active, current_composition, add_waste } from '../store';
import NewComposition from './NewComposition.vue';

//const props = defineProps<{
//  wells: Well[]
//}>();

const dialog = ref<HTMLDivElement>();
const update_address = ref<string>();
const waste_volume = ref<number>(0);

let modal: Modal;

onMounted(() => {
  modal = new Modal(dialog.value, { backdrop: 'static', keyboard: false, focus: true });
});

watch(add_waste_active, async (newval, oldval) => {
  current_composition.value = { solvents: [], solutes: [] };
  (newval) ? modal?.show() : modal?.hide();
});

function send_changes() {
  if (waste_volume.value > 0) {
    add_waste(waste_volume.value, current_composition.value);
  }
  add_waste_active.value = false;
};

</script>

<template>
  <div class="modal" tabindex="-1" ref="dialog">
    <div class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Manual Waste Addition</h5>
          <button type="button" class="btn-close" aria-label="Close" @click="add_waste_active=false"></button>
        </div>
        <div class="modal-body">
            <label>Volume: <input type="number" v-model="waste_volume" min="0"/></label>
            <NewComposition/>    
        </div>
        <div class="modal-footer justify-content-between">
          <div class="d-inline-flex">
            <button type="button" class="btn btn-secondary me-2" @click="add_waste_active=false">Cancel</button>
            <button type="button" class="btn btn-primary" @click="send_changes">Add Waste</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>

</style>