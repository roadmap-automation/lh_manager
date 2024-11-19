<script setup lang="ts">
import { ref, defineProps, onMounted, watch, toRaw, computed, nextTick } from 'vue'
import { Modal } from 'bootstrap/dist/js/bootstrap.esm';
import { soluteMassUnits, soluteVolumeUnits, materials, well_editor_active, well_to_edit, layout, update_well_contents, remove_well_definition } from '../store';
import type { Material, Well, Solute, Solvent } from '../store';

const props = defineProps<{
  wells: Well[]
}>();

const dialog = ref<HTMLDivElement>();
const current_well = ref<Well>();
const solute_search_regexp = ref<RegExp | null>(null);
const solute_search_pattern = ref<string | null>(null);
const solvent_search_regexp = ref<RegExp | null>(null);
const solvent_search_pattern = ref<string | null>(null);

const soluteUnits = [...soluteMassUnits, ...soluteVolumeUnits];

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

const filtered_solute_materials = computed(() => {
  return materials.value.filter((m) => {
    return (m.type !== 'solvent' && (solute_search_regexp.value?.test(m.name) ?? true))
  });
});

const filtered_solvent_materials = computed(() => {
  return materials.value.filter((m) => {
    console.log(m.name, m);
    return ( (m.type === 'solvent' || m.type === null) && (solvent_search_regexp.value?.test(m.name) ?? true))
  });
});

const generate_solute = () => ({ name: filtered_solute_materials.value[0]?.name ?? "", concentration: 0, units: "M" }) as Solute;
const new_solute = ref(generate_solute());
const generate_solvent = () => ({ name: filtered_solvent_materials.value[0]?.name ?? "", fraction: 0 }) as Solvent;
const new_solvent = ref(generate_solvent());
const component_templates = {
  'solutes': generate_solute(),
  'solvents': generate_solvent(),
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

function add_solute() {
  current_well.value?.composition.solutes.push(structuredClone(toRaw(new_solute.value)));
  new_solute.value = generate_solute();
  solute_search_pattern.value = null;
}

async function do_solute_search() {
  solute_search_regexp.value = new RegExp(solute_search_pattern.value ?? '.', 'i');
  await nextTick();
  if (filtered_solute_materials.value.length > 0) {
    new_solute.value.name = filtered_solute_materials.value[0].name;
  }
}

function add_solvent() {
  current_well.value?.composition.solvents.push(structuredClone(toRaw(new_solvent.value)));
  new_solvent.value = generate_solvent();
  solvent_search_pattern.value = null;
}

async function do_solvent_search() {
  solvent_search_regexp.value = new RegExp(solvent_search_pattern.value ?? '.', 'i');
  await nextTick();
  if (filtered_solvent_materials.value.length > 0) {
    new_solvent.value.name = filtered_solvent_materials.value[0].name;
  }
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
            <div>
              <div class="input-group">
                <span class="input-group-text">Solutes: </span>
                <select class="form-select" v-model="new_solute.name">
                  <option v-for="material in filtered_solute_materials" :key="material.name" :value="material.name">{{ material.name }}</option>
                </select>
                <input class="form-input" v-model="solute_search_pattern" @input="do_solute_search" placeholder="search" />
                <button class="btn btn-sm btn-outline-primary" @click="add_solute">add</button>
              </div>
            </div>
            <div class="ps-3" v-for="(solute, sindex) of (current_well?.composition?.solutes ?? [])">
              <input class="mx-2" type="text" :value="solute.name" disabled />
              <label>concentration
                <input class="number px-1 py-0" v-model="solute.concentration" />
              </label>
              <select v-model="solute.units">
                  <option v-for="unit in soluteUnits" :key="unit" :value="unit">{{ unit }}</option>
              </select>
              <button type="button" class="btn-close btn-sm align-middle" aria-label="Close"
                @click="current_well?.composition.solutes.splice(sindex, 1)"></button>
            </div>
          </div>
          <div class="mt-2">
            <div>
              <div class="input-group">
                <span class="input-group-text">Solvents: </span>
                <select class="form-select" v-model="new_solvent.name">
                  <option v-for="material in filtered_solvent_materials" :key="material.name" :value="material.name">{{ material.name }}</option>
                </select>
                <input class="form-input" v-model="solvent_search_pattern" @input="do_solvent_search" placeholder="search" />
                <button class="btn btn-sm btn-outline-primary" @click="add_solvent">add</button>
              </div>
            </div>
            <div class="ps-3" v-for="(solvent, sindex) of (current_well?.composition?.solvents ?? [])">
              <input class="mx-2" type="text" :value="solvent.name" disabled />
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