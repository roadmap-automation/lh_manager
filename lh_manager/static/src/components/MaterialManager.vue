<script setup lang="ts">
import { ref, computed } from 'vue';
import BedLayout from './BedLayout.vue';

import { materials, materialType, soluteMassUnits, soluteVolumeUnits, add_material, delete_material, material_from_sequence, set_hidden } from '../store';
import type { Material, MaterialType } from '../store';

type sortOrder = "name" | "full_name" | "iupac_name" | "molecular_weight" | "type";
const sortby = ref<sortOrder>("name");
const step = ref(1);
const chosenMaterial = ref<string | null>(null);
const soluteUnits = [...soluteMassUnits, ...soluteVolumeUnits];

const generate_new_material = () => ({
  name: "", full_name: "", iupac_name: "", molecular_weight: null,
  concentration_units: null, density: null, type: null,
  hidden: 0, formula: null, sld: null,
});
const new_material = ref<Partial<Material>>(generate_new_material());

const UP_ARROW = "▲";
const DOWN_ARROW = "▼";

const active_sequence = ref<string>("");
const sequence_error = ref<string | null>(null);
const active_search_pattern = ref<string | null>(null);
const active_search_regexp = ref<RegExp | null>(null);

const active_type_filter = ref<string>("All");
const show_hidden = ref(false);
const selected_names = ref<Set<string>>(new Set());

function NameSearch(m: Material) {
  const re = active_search_regexp.value;
  if (re) {
    for (const name of [m.name, m.full_name, m.iupac_name]) {
      if (name && re.test(name)) return true;
    }
    return false;
  }
  return true;
}

function MaterialSorter(a: Material, b: Material) {
  let av = a[sortby.value];
  let bv = b[sortby.value];
  if (typeof av === 'string') av = av.toLowerCase();
  if (typeof bv === 'string') bv = bv.toLowerCase();
  const s = step.value;
  if (av === null && bv === null) return 0;
  else if (av === null) return s;
  else if (bv === null) return -s;
  else if (av > bv) return s;
  else if (av < bv) return -s;
  else return 0;
}

const filtered_materials = computed(() => {
  return materials.value
    .filter(m => show_hidden.value || !m.hidden)
    .filter(m => active_type_filter.value === "All" || m.type === active_type_filter.value)
    .filter(NameSearch)
    .sort(MaterialSorter);
});

function toggleSorting(column: sortOrder) {
  if (sortby.value === column) {
    step.value = -step.value;
  } else {
    sortby.value = column;
    step.value = 1;
  }
}

function calculateIcon(column: sortOrder) {
  if (sortby.value === column) return (step.value > 0) ? UP_ARROW : DOWN_ARROW;
  return "";
}

function toggleSelect(name: string) {
  const s = new Set(selected_names.value);
  if (s.has(name)) s.delete(name);
  else s.add(name);
  selected_names.value = s;
}

async function batchSetHidden(hidden: boolean) {
  await set_hidden(Array.from(selected_names.value), hidden);
  selected_names.value = new Set();
}

async function pubchem_search() {
  const pubchem_cid = new_material.value.pubchem_cid;
  const response = await fetch(`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/${pubchem_cid}/property/MolecularWeight,IUPACName,MolecularFormula/JSON`)
  const data = await response.json();
  const props = data.PropertyTable.Properties[0];
  new_material.value.iupac_name = props.IUPACName;
  new_material.value.molecular_weight = props.MolecularWeight;
  new_material.value.formula = props.MolecularFormula ?? null;
  if (new_material.value.name === "") {
    const name_response = await fetch(`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/${pubchem_cid}/synonyms/TXT`);
    const name_data = await name_response.text();
    new_material.value.name = name_data.split("\n")[0];
    new_material.value.full_name = name_data.split("\n")[0];
  }
}

async function fetch_material_from_sequence() {
  if (!active_sequence.value.trim()) return;
  sequence_error.value = null;
  try {
    const material = await material_from_sequence(new_material.value.name ?? "", active_sequence.value.trim());
    if (material) {
      new_material.value = material;
    } else {
      sequence_error.value = 'Server returned no material — check the sequence is valid single-letter amino acid codes.';
    }
  } catch {
    sequence_error.value = 'Request failed — is periodictable installed on the server?';
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
      <div class="row">
        <h5>Materials:</h5>
      </div>
      <div class="row">
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
            <input type="text" class="form-control" v-model="new_material.formula" id="floatingInputFormula">
            <label for="floatingInputFormula">Formula</label>
          </div>
          <div class="form-floating" v-if="new_material.type === 'sample' || new_material.type === 'protein'">
            <input type="number" class="form-control" v-model="new_material.sld" id="floatingInputSLD">
            <label for="floatingInputSLD">SLD (10⁻⁶ Å⁻²)</label>
          </div>
          <div class="form-floating">
            <select class="form-select" v-model="new_material.concentration_units" title="choose type" :disabled="new_material.type == 'solvent'">
              <option value="null"></option>
              <option v-for="units in soluteUnits" :key="units" :value="units">{{ units }}</option>
            </select>
            <label for="floatingInputUnits">Conc. units</label>
          </div>
          <div class="form-floating">
            <input type="number" class="form-control" v-model="new_material.density" id="floatingInputDensity"
              :disabled="new_material.type !== 'solvent' && new_material.type !== 'sample' && new_material.type !== 'protein'">
            <label for="floatingInputDensity">Density (g/cm<sup>3</sup>)</label>
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
        <div v-if="new_material.type == 'protein'" class="mb-3">
          <div class="input-group">
            <input type="text" class="form-control" placeholder="Amino acid sequence (single-letter codes)" v-model="active_sequence" @keydown.enter.prevent="fetch_material_from_sequence">
            <button class="btn btn-outline-secondary" type="button" @click="fetch_material_from_sequence" :disabled="!active_sequence.trim()">Calculate MW &amp; density</button>
          </div>
          <div v-if="sequence_error" class="text-danger small mt-1">{{ sequence_error }}</div>
        </div>
        <div class="row input-group mb-3">
          <input type="text" class="form-control" placeholder="Search for material" v-model="active_search_pattern"
            @input="active_search_regexp = new RegExp(active_search_pattern ?? '.', 'i')">
        </div>
      </div>

      <!-- Type filter pills -->
      <div class="d-flex flex-wrap gap-1 mb-2 align-items-center">
        <button v-for="pill in ['All', ...materialType]" :key="pill"
          class="btn btn-sm"
          :class="active_type_filter === pill ? 'btn-primary' : 'btn-outline-secondary'"
          @click="active_type_filter = pill">{{ pill }}</button>
        <div class="ms-auto form-check form-switch d-inline-flex align-items-center gap-1">
          <input class="form-check-input" type="checkbox" id="showHiddenToggle" v-model="show_hidden">
          <label class="form-check-label small" for="showHiddenToggle">Show hidden</label>
        </div>
      </div>

      <!-- Batch hide/unhide buttons -->
      <div v-if="selected_names.size > 0" class="mb-2 d-flex gap-2">
        <button class="btn btn-sm btn-warning" @click="batchSetHidden(true)">Hide selected ({{ selected_names.size }})</button>
        <button class="btn btn-sm btn-secondary" @click="batchSetHidden(false)">Unhide selected ({{ selected_names.size }})</button>
      </div>

      <div class="row-auto">
        <div>
          <table class="table table-sm">
            <thead>
              <tr class="sticky-top text-body bg-white">
                <th scope="col"></th>
                <th scope="col" @click="toggleSorting('name')">Name{{ calculateIcon('name') }}</th>
                <th scope="col">PubChem CID</th>
                <th scope="col" @click="toggleSorting('full_name')">Full name{{ calculateIcon('full_name') }}</th>
                <th scope="col" @click="toggleSorting('iupac_name')">IUPAC name{{ calculateIcon('iupac_name') }}</th>
                <th scope="col" @click="toggleSorting('molecular_weight')">Mol. Weight{{ calculateIcon('molecular_weight') }}</th>
                <th scope="col">Formula</th>
                <th scope="col">SLD</th>
                <th scope="col">Conc. units</th>
                <th scope="col">Density (g/cm<sup>3</sup>)</th>
                <th scope="col" @click="toggleSorting('type')">Type{{ calculateIcon('type') }}</th>
                <th scope="col" title="delete"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="material in filtered_materials"
                :key="material.name"
                :class="{'table-warning': material.name == chosenMaterial}"
                :style="material.hidden ? 'opacity: 0.5' : ''"
                @click="chosenMaterial=material.name"
                @dblclick="edit_material(material)"
              >
                <td><input type="checkbox" :checked="selected_names.has(material.name)" @change="toggleSelect(material.name)" @click.stop></td>
                <td :style="material.hidden ? 'text-decoration: line-through' : ''">{{ material.name }}</td>
                <td>{{ material.pubchem_cid }}</td>
                <td>{{ material.full_name }}</td>
                <td>{{ material.iupac_name }}</td>
                <td>{{ material.molecular_weight }}</td>
                <td>{{ material.formula }}</td>
                <td>{{ material.sld }}</td>
                <td>{{ material.concentration_units }}</td>
                <td>{{ material.density }}</td>
                <td>{{ material.type }}</td>
                <td><button class="btn btn-outline-danger" @click="check_delete(material)">Delete</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
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
