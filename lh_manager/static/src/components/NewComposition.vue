<script setup lang="ts">
import { ref, defineProps, onMounted, watch, toRaw, computed, nextTick } from 'vue'
import { soluteMassUnits, soluteVolumeUnits, materials, current_composition } from '../store';
import type { Solute, Solvent } from '../store';

//const props = defineProps<{
//  wells: Well[]
//}>();

const solute_search_regexp = ref<RegExp | null>(null);
const solute_search_pattern = ref<string | null>(null);
const solvent_search_regexp = ref<RegExp | null>(null);
const solvent_search_pattern = ref<string | null>(null);
const soluteUnits = [...soluteMassUnits, ...soluteVolumeUnits];

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

function add_solute() {
  current_composition.value.solutes.push(structuredClone(toRaw(new_solute.value)));
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
  current_composition.value.solvents.push(structuredClone(toRaw(new_solvent.value)));
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

</script>

<template>
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
        <div class="ps-3" v-for="(solute, sindex) of (current_composition?.solutes ?? [])">
        <input class="mx-2" type="text" :value="solute.name" disabled />
        <label>concentration
            <input class="number px-1 py-0" v-model="solute.concentration" />
        </label>
        <select v-model="solute.units">
            <option v-for="unit in soluteUnits" :key="unit" :value="unit">{{ unit }}</option>
        </select>
        <button type="button" class="btn-close btn-sm align-middle" aria-label="Close"
            @click="current_composition.solutes.splice(sindex, 1)"></button>
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
        <div class="ps-3" v-for="(solvent, sindex) of (current_composition?.solvents ?? [])">
        <input class="mx-2" type="text" :value="solvent.name" disabled />
        <label>fraction:
            <input class="number px-1 py-0" v-model="solvent.fraction" />
        </label>
        <button type="button" class="btn-close btn-sm align-middle" aria-label="Close"
            @click="current_composition.solvents.splice(sindex, 1)"></button>
        </div>
    </div>
</template>
  