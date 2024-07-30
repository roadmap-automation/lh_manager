<script setup lang="ts">
import { ref, computed } from 'vue';

import { materials, add_material, delete_material } from '../store';
import type { Material } from '../store';

type sortOrder = "name" | "iupac_name" | "molecular_weight" | "type";
const sortby = ref<sortOrder>("name");
const step = ref(1);
const new_material = ref<Partial<Material>>({name: "", iupac_name: "", molecular_weight: null, type: "", display_units: ""});

const UP_ARROW = "▲";
const DOWN_ARROW = "▼";

const active_search_pattern = ref<string | null>(null);
const active_search_regexp = ref<RegExp | null>(null);

function NameSearch(m: Material) {
  if (active_search_regexp.value === null) {
    return true;
  }
  else {
    return active_search_regexp.value.test(m.name);
  }
}

function MaterialSorter(a: Material, b: Material) {
  const av = a[sortby.value];
  const bv = b[sortby.value];
  const s = step.value;
  if (av === null && bv === null) {
    return 0;
  }
  else if (av === null) {
    return s;
  }
  else if (bv === null) {
    return -s;
  }
  else if (av > bv) {
    return s;
  }
  else if (av < bv) {
    return -s;
  }
  else {
    return 0;
  }
}

function doSorting() {
  filtered_materials.value = materials.value.filter(NameSearch).sort(MaterialSorter);
}


const filtered_materials = computed(() => {
  return materials.value.filter(NameSearch).sort(MaterialSorter);
});

function toggleSorting(column: sortOrder) {
  if (sortby.value === column) {
    // toggling direction of already-selected column
    step.value = -step.value;
  }
  else {
    sortby.value = column;
    step.value = 1;
  }
}


function calculateIcon(column: sortOrder) {
  if (sortby.value === column) {
    return (step.value > 0) ? UP_ARROW : DOWN_ARROW;
  }
  else {
    return "";
  }
}


</script>

<template>
  <div class="container">
    <h5>Materials:</h5>
    <div class="input-group mb-3">
      <input type="text" class="form-control" placeholder="Material name" v-model="new_material.name">
      <input type="text" class="form-control" placeholder="PubChem CID" v-model="new_material.pubchem_cid">
      <input type="text" class="form-control" placeholder="IUPAC name" v-model="new_material.iupac_name">
      <input type="number" class="form-control" placeholder="Molecular Weight" v-model="new_material.molecular_weight">
      <input type="text" class="form-control" placeholder="Type" v-model="new_material.type">
      <input type="text" class="form-control" placeholder="Display Units" v-model="new_material.display_units">
      <button class="btn btn-outline-secondary" type="button" @click="add_material(new_material)">Add</button>
    </div>
    <div class="input-group mb-3">
      <input type="text" class="form-control" placeholder="Search for material" v-model="active_search_pattern"
        @input="active_search_regexp = new RegExp(active_search_pattern, 'i')">
      <button class="btn btn-outline-secondary" type="button" @click="doSorting">Search</button>
    </div>
    <table class="table table-sm">
      <thead>
        <tr class="sticky-top text-body bg-white">
          <th scope="col" @click="toggleSorting('name')">Name{{ calculateIcon('name') }}</th>
          <th scope="col">PubChem CID</th>
          <th scope="col" @click="toggleSorting('iupac_name')">IUPAC name{{ calculateIcon('iupac_name') }}</th>
          <th scope="col" @click="toggleSorting('molecular_weight')">Molecular Weight{{ calculateIcon('molecular_weight') }}</th>
          <th scope="col" @click="toggleSorting('type')">Type{{ calculateIcon('type') }}</th>
          <th scope="col" title="concentration display units">conc. default units</th>
          <th scope="col" title="delete"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="material in filtered_materials"
          :key="material.name"
          :class="{'table-warning': material.name == chosenMaterial}"
          @click="chosenMaterial=material.name"
          @dblclick="chosenMaterial=material.name;chooseMaterial()"
          >
          <td>{{ material.name }}</td>
          <td>{{ material.pubchem_cid }}</td>
          <td>{{ material.iupac_name }}</td>
          <td>{{ material.molecular_weight }}</td>
          <td>{{ material.type }}</td>
          <td>{{ material.display_units }}</td>
          <td><button class="btn btn-outline-danger" @click="delete_material(material)">Delete</button></td>
        </tr>
      </tbody>
    </table>
  </div>  
</template>