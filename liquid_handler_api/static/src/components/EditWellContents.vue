<script setup lang="ts">
import { ref, defineProps, onMounted, watch, toRaw } from 'vue'
import { Modal } from 'bootstrap/dist/js/bootstrap.esm';
import { well_editor_active, well_to_edit, layout, update_well_contents, remove_well_definition } from '../store';
import type { Well, Solute, Solvent } from '../store';

const props = defineProps<{
  wells: Well[]
}>();

const dialog = ref<HTMLDivElement>();
const current_well = ref<Well>();

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
  const { rack_id, well_number } = toRaw(newval);
  const existing_well = props.wells.find((well) => (well.rack_id === rack_id && well.well_number === well_number));
  current_well.value = structuredClone(toRaw(existing_well)) ?? {...structuredClone(empty_well), rack_id, well_number};
});

const solute_template: Solute = { name: "", concentration: 0, units: "M" };
const solvent_template: Solvent = { name: "", fraction: 0 };
const component_templates = {
  'solutes': solute_template,
  'solvents': solvent_template,
}

const empty_well = {
  rack_id: null,
  well_number: null,
  composition: {
    solvents: [],
    solutes: [],
  },
  volume: 0,
}

function add_component(target: 'solutes' | 'solvents') {
  current_well.value?.composition[target].push(structuredClone(component_templates[target]));
}

function send_changes() {
  if (current_well.value) {
    update_well_contents(current_well.value);
  }
  well_editor_active.value = false;
};

function remove_definition() {
  if (current_well.value) {
    remove_well_definition(current_well.value);
  }
  well_editor_active.value = false;
}

</script>

<template>
  <div class="modal" tabindex="-1" ref="dialog">
    <div class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Edit Well {{  well_to_edit?.rack_id }}::{{ well_to_edit?.well_number }}</h5>
          <button type="button" class="btn-close" aria-label="Close" @click="well_editor_active=false"></button>
        </div>
        <div class="modal-body">
          <details>
            <summary>json</summary>
            <pre>{{ JSON.stringify(toRaw(current_well), null, 2) }}</pre>
          </details>
          <div v-if="current_well && layout">
            <label>Volume: <input type="number" v-model="current_well.volume" :max="layout.racks[current_well.rack_id].max_volume" /></label>
            <emph>(Max Volume: {{ layout.racks[current_well.rack_id].max_volume }})</emph>
            <div>
              <input type="range" class="form-range" v-model="current_well.volume" min="0" :max="layout.racks[current_well.rack_id].max_volume">
            </div>
          </div>
          <div>
            <div>Solutes:
              <button class="btn btn-sm btn-outline-primary" @click="add_component('solutes')">add</button>
            </div>
            <div class="ps-3" v-for="(solute, sindex) of (current_well?.composition?.solutes ?? [])">
              <input type="text" v-model="solute.name" />
              <label>concentration ({{ solute.units }}):
                <input class="number px-1 py-0" v-model="solute.concentration" />
              </label>
              <button type="button" class="btn-close btn-sm align-middle" aria-label="Close"
                @click="current_well?.composition.solutes.splice(sindex, 1)"></button>
            </div>
          </div>
          <div>
            <div>Solvents:
              <button class="btn btn-sm btn-outline-primary" @click="add_component('solvents')">add</button>
            </div>
            <div class="ps-3" v-for="(solvent, sindex) of (current_well?.composition?.solvents ?? [])">
              <input type="text" v-model="solvent.name" />
              <label>fraction:
                <input class="number px-1 py-0" v-model="solvent.fraction" />
              </label>
              <button type="button" class="btn-close btn-sm align-middle" aria-label="Close"
                @click="current_well?.composition.solvents.splice(sindex, 1)"></button>
            </div>
          </div>
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