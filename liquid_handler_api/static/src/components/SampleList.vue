<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import Modal from 'bootstrap/js/src/modal';
import { v4 as uuidv4 } from 'uuid';
import MethodList from './MethodList.vue';
// import { socket_emit } from '../store.ts';
import { samples, sample_status, update_sample, run_sample, active_sample_index, active_stage, active_method_index, archive_and_remove_sample } from '../store';
import type { SampleStatus, SampleStatusMap, StatusType, Sample, StageName } from '../store';

const emit = defineEmits(['update_sample']);

const editing_item = ref(null);
const modal_node = ref<HTMLElement>();
const modal = ref<Modal>();
const name_input = ref<HTMLInputElement>();
const modal_title = ref("Edit Sample Name and Description")
const sample_to_edit = ref<Partial<Sample>>({ name: '', description: '', id: '' });

function toggleItem(index) {
  active_sample_index.value = (index === active_sample_index.value) ? null : index;
  active_method_index.value = null;
  active_stage.value = null;
}

function add_sample() {
  // when "update_sample" is called with a new id, 
  // it creates a new sample on the server
  const id = uuidv4();
  const name = "";
  const description = "";
  modal_title.value = "Create New Sample";
  sample_to_edit.value = { id, name, description };
  modal.value?.show();
}

async function edit_sample_name(index) {
  const s = samples[index];
  const { id, name, description } = s;
  modal_title.value = "Edit Sample Name and Description";
  sample_to_edit.value = { id, name, description };
  modal.value?.show();
}

async function archive_sample(index) {
  const s = samples[index];
  const result = await archive_and_remove_sample(s);
  return result;
}

function update_sample_name() {
  update_sample(sample_to_edit.value);
  close_modal();
}

async function run_stage(sample: Sample, stage: StageName[]) {
  const result = await run_sample(sample, stage);
  console.log("result of run_stage: ", result);
}

function close_modal() {
  modal.value?.hide();
}

function update_method(sample, stage_name, index, field_name, field_value) {
  const { id, stages } = sample;
  // work with a copy
  const stage = { ...stages[stage_name] };
  const methods = stage.methods.slice();
  const method = methods[index];
  method[field_name] = field_value;
  stage.methods = methods;
  const new_sample = { ...sample };
  sample.stages[stage_name] = stage;
  console.log('updating method', method, sample, stage, new_sample);
  update_sample(new_sample);
}

onMounted(() => {
  modal.value = new Modal(modal_node.value);
  modal_node.value?.addEventListener('shown.bs.modal', function () {
    name_input.value?.focus();
  })
});

const status_class_map: {[status in StatusType]: string} = {
  'inactive': '',
  'partially complete': 'text-warning',
  'pending': 'text-secondary',
  'active': 'text-success',
  'completed': 'text-danger',
}

</script>

<template>
  <button class="btn btn-outline-primary btn-sm" @click="add_sample">+ Add sample</button>
  <div class="accordion">
    <div class="accordion-item" v-for="(sample, sindex) of samples" :key="sample.id">
      <div class="accordion-header">
        <button class="accordion-button p-1"
          :class="{ collapsed: sindex !== active_sample_index, [status_class_map[sample_status[sample.id]?.status ?? 'inactive']]: true }" type="button"
          @click="toggleItem(sindex)" :aria-expanded="sindex === active_sample_index">
          <span class="fw-bold align-middle px-2"> {{ sample.name }} </span>
          <span class="align-middle px-2"> {{ sample.description }}</span>
          <button type="button" class="btn-close btn-sm align-middle edit" aria-label="Edit Name or Description"
            @click.stop="edit_sample_name(sindex)"></button>
            <button 
              v-if="(sample_status?.[sample.id]?.status ?? 'inactive') === 'inactive'"
              type="button"
              class="btn-close btn-sm align-middle start"
              aria-label="Run stages"
              @click.stop="run_stage(sample, ['prep', 'inject'])">
            </button>
            <button
              v-if="(sample_status[sample.id]?.status ?? 'inactive') === 'inactive'"
              type="button"
              class="btn-close btn-sm align-middle archive"
              aria-label="Archive sample"
              @click.stop="archive_and_remove_sample(sample.id)">
            </button>
        </button>
      </div>
      <div class="accordion-collapse collapse" :class="{ show: sindex === active_sample_index }">
        <div v-if="sindex === active_sample_index" class="accordion-body py-0">
          <div v-for="(stage, stage_name) of sample.stages">
            <h6 :class="status_class_map[sample_status?.[sample.id]?.[stage_name]?.status ?? 'inactive']">{{ stage_name }}:
              <button 
                v-if="sample_status?.[sample.id]?.stages?.[stage_name]?.status === 'inactive'"
                type="button"
                class="btn-close btn-sm align-middle start"
                aria-label="Run stage"
                @click.stop="run_stage(sample, [stage_name])">
              </button>
            </h6>
            <MethodList
              :sample_id="sample.id"
              :stage_name="stage_name"
              :methods="stage.methods"
              @update_method="(index, field_name, field_value) => update_method(sample, stage_name, index, field_name, field_value)" />
          </div>
        </div>
      </div>
    </div>
  </div>
  <div ref="modal_node" class="modal fade" id="edit_sample" tabindex="-1">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">{{ modal_title }}</h5>
          <button type="button" class="btn-close" @click="close_modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <table class="table">
            <tr>
              <td><label for="sample_name">name:</label></td>
              <td><input ref="name_input" type="text" @keydown.enter="update_sample_name" v-model="sample_to_edit.name"
                  name="sample_name" /></td>
            </tr>
            <tr>
              <td><label for="sample_description">description:</label></td>
              <td><input type="text" @keydown.enter="update_sample_name" v-model="sample_to_edit.description"
                  name="sample_description" /></td>
            </tr>
          </table>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" @click="close_modal">Close</button>
          <button type="button" class="btn btn-primary" @click="update_sample_name">Save changes</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
.btn-close.edit {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-pencil-square' viewBox='0 0 16 16'><path d='M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z'/><path fill-rule='evenodd' d='M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5v11z'/></svg>")
}

.btn-close.start {
  background-image: url('data:image/svg+xml,<svg class="svg-icon" style="width: 1em; height: 1em;vertical-align: middle;fill: currentColor;overflow: hidden;" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg"><path d="M212.992 526.336 212.992 526.336 212.992 526.336 215.04 526.336 212.992 526.336Z"  /><path d="M817.152 202.752 817.152 202.752C737.28 122.88 628.736 75.776 509.952 75.776c-118.784 0-229.376 49.152-307.2 126.976l0 0c-77.824 77.824-126.976 186.368-126.976 307.2 0 118.784 49.152 229.376 126.976 307.2 77.824 79.872 188.416 126.976 307.2 126.976 120.832 0 229.376-49.152 307.2-126.976 79.872-77.824 126.976-186.368 126.976-307.2C946.176 389.12 897.024 280.576 817.152 202.752zM770.048 770.048c-65.536 65.536-157.696 108.544-260.096 108.544-102.4 0-194.56-40.96-260.096-108.544C184.32 704.512 141.312 612.352 141.312 509.952s40.96-194.56 108.544-260.096C317.44 184.32 409.6 141.312 509.952 141.312c100.352 0 192.512 40.96 258.048 106.496l2.048 2.048c65.536 65.536 108.544 157.696 108.544 260.096S837.632 704.512 770.048 770.048z"  /><path d="M385.024 249.856l202.752 116.736 202.752 116.736c14.336 8.192 18.432 26.624 10.24 40.96-4.096 4.096-8.192 8.192-12.288 12.288l-202.752 116.736 0 0-202.752 116.736c-14.336 8.192-32.768 4.096-40.96-10.24-2.048-6.144-4.096-10.24-4.096-16.384L337.92 509.952l0 0L337.92 274.432c0-16.384 12.288-28.672 28.672-28.672C374.784 245.76 380.928 247.808 385.024 249.856L385.024 249.856z"  /></svg>');
}

.btn-close.archive {
  background-image: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-box-arrow-in-down" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M3.5 6a.5.5 0 0 0-.5.5v8a.5.5 0 0 0 .5.5h9a.5.5 0 0 0 .5-.5v-8a.5.5 0 0 0-.5-.5h-2a.5.5 0 0 1 0-1h2A1.5 1.5 0 0 1 14 6.5v8a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 14.5v-8A1.5 1.5 0 0 1 3.5 5h2a.5.5 0 0 1 0 1h-2z"/><path fill-rule="evenodd" d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"/></svg>')
}
</style>