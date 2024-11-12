<script setup lang="ts">
import { ref, computed } from 'vue';
import BedLayout from './BedLayout.vue';

import { materials, materialType, soluteMassUnits, soluteVolumeUnits, add_material, delete_material, wells } from '../store';
import type { Material, MaterialType } from '../store';

type sortOrder = "name" | "full_name" | "iupac_name" | "molecular_weight" | "type";
const sortby = ref<sortOrder>("name");
const step = ref(1);
const chosenMaterial = ref<string | null>(null);
const soluteUnits = [...soluteMassUnits, ...soluteVolumeUnits];

const generate_new_material = () => ({ name: "", full_name: "", iupac_name: "", molecular_weight: null, type: null });
const new_material = ref<Partial<Material>>(generate_new_material());

const UP_ARROW = "▲";
const DOWN_ARROW = "▼";

const active_search_pattern = ref<string | null>(null);
const active_search_regexp = ref<RegExp | null>(null);

function NameSearch(m: Material) {
  let result = false
  if (!!active_search_regexp.value) {
    result = result || active_search_regexp.value.test(m.name)
    if (!!m.full_name) {
      result = result || active_search_regexp.value.test(m.full_name)
    }
    if (!!m.iupac_name) {
      result = result || active_search_regexp.value.test(m.iupac_name)
    }
  }
  else {
    result = true
  }
  return result
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

async function pubchem_search() {
  const pubchem_cid = new_material.value.pubchem_cid;
  const response = await fetch(`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/${pubchem_cid}/property/MolecularWeight,IUPACName/JSON`)
  // const response = await fetch(`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/${pubchem_cid}/json`);
  const data = await response.json();
  console.log(data);
  new_material.value.iupac_name = data.PropertyTable.Properties[0].IUPACName;
  new_material.value.molecular_weight = data.PropertyTable.Properties[0].MolecularWeight;
  if (new_material.value.name === "") {
    const name_response = await fetch(`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/${pubchem_cid}/synonyms/TXT`);
    const name_data = await name_response.text();
    new_material.value.name = name_data.split("\n")[0];
    new_material.value.full_name = name_data.split("\n")[0];
  }
}

async function submit_add() {
  await add_material(new_material.value);
  new_material.value = generate_new_material();
}

function clear() {
  new_material.value = generate_new_material();
}

function check_delete(material: Material) {
  if (confirm(`Are you sure you want to delete ${material.name}?`)) {
    delete_material(material);
  }
}

function edit_material(material: Material) {
  new_material.value = {...material};
}

</script>

<template>
  <div class="row flex-grow-1">
      <div class="col">
        <h5>Materials:</h5>
        <div class="input-group mb-3">
          <div class="form-floating">
            <input type="text" class="form-control" v-model="new_material.name" id="floatingInputName">
            <label for="floatingInputName">Material name</label>
          </div>
          <div class="form-floating">
            <input type="text" class="form-control" @keydown.enter="pubchem_search" @blur="pubchem_search" v-model="new_material.pubchem_cid" id="floatingInputCID">
            <label for="floatingInputCID">PubChem CID</label>
          </div>
          <div class="form-floating">
            <input type="text" class="form-control" v-model="new_material.full_name" id="floatingInputFullName">
            <label for="floatingInputFullName">Full name</label>
          </div>          
          <div class="form-floating">
            <input type="text" class="form-control" v-model="new_material.iupac_name" id="floatingInputIUPAC">
            <label for="floatingInputIUPAC">IUPAC name</label>
          </div>
          <div class="form-floating">
            <input type="number" class="form-control" v-model="new_material.molecular_weight" id="floatingInputMW">
            <label for="floatingInputMW">Molec. Weight</label>
          </div>
          <div class="form-floating">
            <select class="form-select" v-model="new_material.type" title="choose type">
              <option value="null"></option>
              <option v-for="type in materialType" :key="type" :value="type">{{ type }}</option>
            </select>
            <label for="floatingInputType">Type</label>
          </div>
          <button class="btn btn-outline-secondary" type="button" @click="submit_add">{{ materials.some((m) => m.name === new_material.name) ? 'Save' : 'Add' }}</button>
          <button class="btn btn-outline-secondary" type="button" @click="clear">Clear</button>
        </div>
        <div class="input-group mb-3">
          <input type="text" class="form-control" placeholder="Search for material" v-model="active_search_pattern"
            @input="active_search_regexp = new RegExp(active_search_pattern ?? '.', 'i')">
        </div>
        <table class="table table-sm">
          <thead>
            <tr class="sticky-top text-body bg-white">
              <th scope="col" @click="toggleSorting('name')">Name{{ calculateIcon('name') }}</th>
              <th scope="col">PubChem CID</th>
              <th scope="col" @click="toggleSorting('full_name')">Full name{{ calculateIcon('full_name') }}</th>
              <th scope="col" @click="toggleSorting('iupac_name')">IUPAC name{{ calculateIcon('iupac_name') }}</th>
              <th scope="col" @click="toggleSorting('molecular_weight')">Molecular Weight{{ calculateIcon('molecular_weight') }}</th>
              <th scope="col" @click="toggleSorting('type')">Type{{ calculateIcon('type') }}</th>
              <th scope="col" title="delete"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="material in filtered_materials"
              :key="material.name"
              :class="{'table-warning': material.name == chosenMaterial}"
              @click="chosenMaterial=material.name"
              @dblclick="edit_material(material)"
              >
              <td>{{ material.name }}</td>
              <td>{{ material.pubchem_cid }}</td>
              <td>{{ material.full_name }}</td>
              <td>{{ material.iupac_name }}</td>
              <td>{{ material.molecular_weight }}</td>
              <td>{{ material.type }}</td>
              <td><button class="btn btn-outline-danger" @click="check_delete(material)">Delete</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="col">
        <BedLayout :wells="wells" />
      </div>
  </div>
</template>

<style scoped>
  select:has(option[value="null"]:checked) {
    color: gray;
  }
  option[value="null"] {
    color: gray;
  }
  .form-floating>label {
    padding-left: 0.1rem;
  }
</style>