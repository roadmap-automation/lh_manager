<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import Modal from 'bootstrap/js/src/modal';
import { v4 as uuidv4 } from 'uuid';
import MethodList from './MethodList.vue';
import TaskEditor from './TaskEditor.vue';
// import { socket_emit } from '../store.ts';
import { samples, sample_status, update_sample, run_sample, active_sample_index, active_stage, active_method_index, archive_and_remove_sample, remove_sample, duplicate_sample, explode_stage } from '../store';
import type { StatusType, Sample } from '../store';

const props = defineProps<{
  channel: number,
}>();

const emit = defineEmits(['update_sample']);

const editing_item = ref(null);
const modal_node = ref<HTMLElement>();
const modal = ref<Modal>();
const name_input = ref<HTMLInputElement>();
const modal_title = ref("Edit Sample Name and Description")
const sample_to_edit = ref<Partial<Sample>>({ name: '', description: '', id: '' });
const channel_samples = computed(() => {
  const filtered_samples = samples.value.filter(s => s.channel === props.channel);
  console.log('filtered_samples', filtered_samples, samples.value, props.channel);
  return filtered_samples;
});

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
  sample_to_edit.value = { id, name, description, channel: props.channel };
  modal.value?.show();
}

async function edit_sample_name(index) {
  const s = channel_samples.value[index];
  const { id, name, description } = s;
  modal_title.value = "Edit Sample Name and Description";
  sample_to_edit.value = { id, name, description };
  modal.value?.show();
}

function update_sample_name() {
  update_sample(sample_to_edit.value);
  close_modal();
}

async function run_stage(sample: Sample, stage: string[]) {
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
  //modal_node.value?.addEventListener('shown.bs.modal', function () {
  //  name_input.value?.focus();
  //})
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
  <button class="btn btn-outline-primary btn-sm" @click="add_sample">+ Add sample in channel {{ props.channel }}</button>
  <div class="accordion">
    <div class="accordion-item" v-for="(sample, sindex) of channel_samples" :key="sample.id">
      <div class="accordion-header">
        <button class="accordion-button p-1"
          :class="{ collapsed: sindex !== active_sample_index, [status_class_map[sample_status[sample.id]?.status ?? 'inactive']]: true }" type="button"
          @click="toggleItem(sindex)" :aria-expanded="sindex === active_sample_index">
          <span class="fw-bold align-middle px-2"> {{ sample.name }} </span>
          <span class="align-middle px-2"> {{ sample.description }}</span>
          <button type="button" class="btn-close btn-sm align-middle edit"
            aria-label="Edit Name or Description"
            title="Edit Name or Description"
            @click.stop="edit_sample_name(sindex)">
          </button>
          <button 
            v-if="(sample_status?.[sample.id]?.status ?? 'inactive') === 'inactive'"
            type="button"
            class="btn-close btn-sm align-middle start"
            aria-label="Run all stages"
            title="Run all stages"
            @click.stop="run_stage(sample, ['prep', 'inject'])">
          </button>
          <button
            v-if="true || (['active', 'completed', 'partially_completed'].includes(sample_status[sample.id]?.status))"
            type="button"
            class="btn-close btn-sm align-middle archive"
            aria-label="Archive sample"
            title="Archive sample"
            @click.stop="archive_and_remove_sample(sample.id)">
          </button>
          <button
            type="button"
            class="btn-close btn-sm align-middle trash"
            aria-label="Remove sample (not archived)"
            title="Remove (trash) sample"
            @click.stop="remove_sample(sample.id)">
          </button>
          <button
            type="button"
            class="btn-close btn-sm align-middle copy"
            aria-label="Duplicate sample"
            title="Duplicate sample"
            @click.stop="duplicate_sample(sample.id, sample.channel)">
          </button>
          <button
            type="button"
            class="btn-close btn-sm align-middle box_arrow_right"
            aria-label="Copy sample to next channel"
            title="Copy sample to next channel"
            @click.stop="duplicate_sample(sample.id, sample.channel + 1)">
          </button>          
        </button>
      </div>
      <div class="accordion-collapse collapse" :class="{ show: sindex === active_sample_index }">
        <div v-if="sindex === active_sample_index" class="samplelist accordion-body py-0">
          <div class="methodlist" v-for="(stage, stage_name) of sample.stages">
            <h6 :class="status_class_map[sample_status?.[sample.id]?.[stage_name]?.status ?? 'inactive']">{{ stage_name }}:
              <button
                type="button"
                class="btn-close btn-sm align-middle expand-up-down"
                aria-label="explode"
                title="explode"
                @click.stop="explode_stage(sample, stage_name)">
              </button>
              <button 
                type="button"
                class="btn-close btn-sm align-middle start"
                aria-label="Run stage"
                title="Run stage"
                @click.stop="run_stage(sample, [stage_name])">
              </button>
            </h6>
            <div class="pm-2">
              <div class="stage-label">Draft</div>
              <MethodList
                :sample_id="sample.id"
                :stage_name="stage_name"
                :methods="stage.methods"
                :editable="true"
                :stage_label="'methods'"
                @update_method="(index, field_name, field_value) => update_method(sample, stage_name, index, field_name, field_value)" />
            </div>
            <div class="pm-2" v-if="!!stage.active.length">
              <div class="stage-label">Submitted</div>
              <MethodList
              :sample_id="sample.id"
              :stage_name="stage_name"
              :methods="stage.active"
              :editable="false"
              :stage_label="'active'"
              @update_method="(index, field_name, field_value) => update_method(sample, stage_name, index, field_name, field_value)" />              
            </div>
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
  <TaskEditor></TaskEditor>
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

.btn-close.copy {
  background-image: url('data:image/svg+xml,<svg version="1.1" id="Layer_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" x="0px" y="0px" viewBox="0 0 512 512" style="enable-background:new 0 0 512 512;" xml:space="preserve"><g><path d="M232.7,186.2v23.3h209.5c12.8,0,23.2,10.4,23.3,23.3v209.5c0,12.8-10.4,23.2-23.3,23.3H232.7c-12.8,0-23.2-10.4-23.3-23.3V232.7c0-12.8,10.4-23.3,23.3-23.3V186.2v-23.3c-38.6,0-69.8,31.2-69.8,69.8v209.5c0,38.6,31.2,69.8,69.8,69.8h209.5c38.6,0,69.8-31.2,69.8-69.8V232.7c0-38.6-31.2-69.8-69.8-69.8H232.7V186.2z"/><path d="M93.1,302.5H69.8c-12.8,0-23.2-10.4-23.3-23.3V69.8C46.6,57,57,46.6,69.8,46.5h209.5c12.8,0,23.2,10.4,23.3,23.3v23.3c0,12.9,10.4,23.3,23.3,23.3c12.9,0,23.3-10.4,23.3-23.3V69.8c0-38.6-31.2-69.8-69.8-69.8H69.8C31.2,0,0,31.2,0,69.8v209.5c0,38.6,31.2,69.8,69.8,69.8l23.3,0c12.9,0,23.3-10.4,23.3-23.3C116.4,313,105.9,302.5,93.1,302.5z"/></g></svg>')
}

.btn-close.trash {
  background-image: url('data:image/svg+xml,<svg version="1.1" id="Capa_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="800px" height="800px" viewBox="0 0 482 482" xml:space="preserve"><g><g><path d="M381.163,57.799h-75.094C302.323,25.316,274.686,0,241.214,0c-33.471,0-61.104,25.315-64.85,57.799h-75.098c-30.39,0-55.111,24.728-55.111,55.117v2.828c0,23.223,14.46,43.1,34.83,51.199v260.369c0,30.39,24.724,55.117,55.112,55.117h210.236c30.389,0,55.111-24.729,55.111-55.117V166.944c20.369-8.1,34.83-27.977,34.83-51.199v-2.828C436.274,82.527,411.551,57.799,381.163,57.799z M241.214,26.139c19.037,0,34.927,13.645,38.443,31.66h-76.879C206.293,39.783,222.184,26.139,241.214,26.139z M375.305,427.312c0,15.978-13,28.979-28.973,28.979H136.096c-15.973,0-28.973-13.002-28.973-28.979V170.861h268.182V427.312z M410.135,115.744c0,15.978-13,28.979-28.973,28.979H101.266c-15.973,0-28.973-13.001-28.973-28.979v-2.828c0-15.978,13-28.979,28.973-28.979h279.897c15.973,0,28.973,13.001,28.973,28.979V115.744z"/><path d="M171.144,422.863c7.218,0,13.069-5.853,13.069-13.068V262.641c0-7.216-5.852-13.07-13.069-13.07c-7.217,0-13.069,5.854-13.069,13.07v147.154C158.074,417.012,163.926,422.863,171.144,422.863z"/><path d="M241.214,422.863c7.218,0,13.07-5.853,13.07-13.068V262.641c0-7.216-5.854-13.07-13.07-13.07c-7.217,0-13.069,5.854-13.069,13.07v147.154C228.145,417.012,233.996,422.863,241.214,422.863z"/><path d="M311.284,422.863c7.217,0,13.068-5.853,13.068-13.068V262.641c0-7.216-5.852-13.07-13.068-13.07c-7.219,0-13.07,5.854-13.07,13.07v147.154C298.213,417.012,304.067,422.863,311.284,422.863z"/></g></g></svg>')
}

.btn-close.expand-up-down {
  background-image: url('data:image/svg+xml,<svg height="800px" width="800px" version="1.1" id="Layer_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 512 512" xml:space="preserve"><g><g><g><path d="M199.541,365.792c-4.237-4.093-10.99-3.976-15.083,0.262c-3.993,4.134-3.993,10.687,0,14.821l64,64c4.157,4.174,10.911,4.187,15.085,0.03c0.01-0.01,0.02-0.02,0.03-0.03l64-64c4.093-4.237,3.976-10.99-0.261-15.083c-4.134-3.993-10.688-3.993-14.821,0l-45.824,45.792V100.416l45.792,45.792c4.237,4.093,10.99,3.976,15.083-0.262c3.993-4.134,3.993-10.687,0-14.821l-64-64c-4.157-4.174-10.911-4.187-15.085-0.03c-0.01,0.01-0.02,0.02-0.03,0.03l-64,64c-4.093,4.237-3.975,10.99,0.262,15.083c4.134,3.992,10.687,3.992,14.82,0l45.824-45.792v311.168L199.541,365.792z"/><path d="M394.667,490.667H117.333c-5.891,0-10.667,4.776-10.667,10.667S111.442,512,117.333,512h277.333c5.891,0,10.667-4.776,10.667-10.667S400.558,490.667,394.667,490.667z"/><path d="M117.333,21.333h277.333c5.891,0,10.667-4.776,10.667-10.667C405.333,4.776,400.558,0,394.667,0H117.333c-5.891,0-10.667,4.776-10.667,10.667C106.667,16.558,111.442,21.333,117.333,21.333z"/></g></g></g></svg>')
}

.btn-close.box_arrow_right {
  background-image: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-box-arrow-right" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M10 12.5a.5.5 0 0 1-.5.5h-8a.5.5 0 0 1-.5-.5v-9a.5.5 0 0 1 .5-.5h8a.5.5 0 0 1 .5.5v2a.5.5 0 0 0 1 0v-2A1.5 1.5 0 0 0 9.5 2h-8A1.5 1.5 0 0 0 0 3.5v9A1.5 1.5 0 0 0 1.5 14h8a1.5 1.5 0 0 0 1.5-1.5v-2a.5.5 0 0 0-1 0z"/><path fill-rule="evenodd" d="M15.854 8.354a.5.5 0 0 0 0-.708l-3-3a.5.5 0 0 0-.708.708L14.293 7.5H5.5a.5.5 0 0 0 0 1h8.793l-2.147 2.146a.5.5 0 0 0 .708.708z"/></svg>')
 
}

.stage-label {
  font-style:italic;
}

.samplelist {
  background-image: linear-gradient(to bottom, #BBBBBB, #FFFFFF);
}

.methodlist {
  opacity: 90%;
}

</style>