<script setup>
import { onMounted, ref, computed } from 'vue';
import { Modal } from 'bootstrap';
import { v4 as uuidv4 } from 'uuid';
import MethodList from './MethodList.vue';
// import { socket_emit } from '../store.ts';
import { update_sample, active_item, active_stage, active_method } from '../store';

const props = defineProps({
  samples: Array,
  sample_status: Object,
});

const emit = defineEmits(['update_sample']);

const editing_item = ref(null);
const modal_node = ref(null);
const modal = ref(null);
const name_input = ref(null);
const modal_title = ref("Edit Sample Name and Description")
const sample_to_edit = ref({ name: '', description: '', id: '' });

function toggleItem(index) {
  active_item.value = (index === active_item.value) ? null : index;
  active_method.value = null;
  active_stage.value = null;
}

function add_sample() {
  const id = uuidv4();
  const name = "";
  const description = "";
  modal_title.value = "Create New Sample";
  sample_to_edit.value = { id, name, description };
  modal.value?.show();
}

async function edit_sample_name(index) {
  const s = props.samples[index];
  const { id, name, description } = s;
  modal_title.value = "Edit Sample Name and Description";
  sample_to_edit.value = { id, name, description };
  modal.value?.show();
}

function update_sample_name() {
  update_sample(sample_to_edit.value);
  close_modal();
}

function close_modal() {
  modal.value?.hide();
}

function add_method(method, sample, stage_name) {
  const { id, stages } = sample;
  // work with a copy
  const stage = { ...stages[stage_name] };
  const new_methods = [...stage.methods, method];
  stage.methods = new_methods
  const new_sample = { ...sample };
  sample.stages[stage_name] = stage;
  console.log('adding method', method, sample, stage, new_sample);
  update_sample(new_sample);
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

function set_location(index, name, {rack_id, well_number}, sample, stage_name) {
  const { id, stages } = sample;
  // work with a copy
  const stage = { ...stages[stage_name] };
  const method = stage.methods[index];
  method[name] = {rack_id, well_number};
  const new_sample = { ...sample };
  sample.stages[stage_name] = stage;
  update_sample(new_sample);
}

function set_active_method(stage_name, method_index) {
  if (active_stage.value === stage_name && active_method.value === method_index) {
    active_method.value = null;
    active_stage.value = null;
  }
  else {
    active_stage.value = stage_name;
    active_method.value = method_index;
  }
}

onMounted(() => {
  modal.value = new Modal(modal_node.value);
  modal_node.value.addEventListener('shown.bs.modal', function () {
    name_input.value?.focus();
  })
});

function get_sample_status_class(sample_id) {
  const status = props.sample_status[sample_id] ?? {};
  const stage_status = Object.values(status).map((stage) => stage?.status);
  if (stage_status.every(s => s === 'pending')) {
    return '';
  }
  else if (stage_status.some((s) => s === 'active')) {
    return 'text-success';
  }
  else if (stage_status.every((s) => s === 'completed')) {
    return 'text-danger';
  }
  else if (stage_status.some((s) => s === 'completed')) {
    return 'text-warning';
  }
  else {
    console.warn(`unexpected status: ${status}`);
    return null;
  }

}

const status_by_id = computed(() => {
  return Object.fromEntries(props.samples.map((s) => {
    return [s.id, get_sample_status_class(s.id)];
  }));
})

const status_class_map = {
  'pending': '',
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
          :class="{ collapsed: sindex !== active_item, [status_by_id[sample.id]]: true }" type="button"
          @click="toggleItem(sindex)" :aria-expanded="sindex === active_item">
          <span class="fw-bold align-middle px-2"> {{ sample.name }} </span>
          <span class="align-middle px-2"> {{ sample.description }}</span>
          <button type="button" class="btn-close btn-sm align-middle edit" aria-label="Edit Name or Description"
            @click.stop="edit_sample_name(sindex)"></button>
        </button>
      </div>
      <div class="accordion-collapse collapse" :class="{ show: sindex === active_item }">
        <div class="accordion-body py-0">
          <div v-for="(stage, stage_name) of sample.stages">
            <h6 :class="status_class_map[sample_status?.[sample.id]?.[stage_name]?.status ?? 'pending']">{{ stage_name }}:
            </h6>
            <MethodList :methods="stage.methods" :status="sample_status?.[sample.id]?.prep" :collapsed="!(sindex === active_item && stage_name == active_stage)"
              :active_item="(stage_name === active_stage) ? active_method : null"
              @add_method="(m) => add_method(m, sample, stage_name)"
              @set_location="(i, n, l) => set_location(i, n, l, sample, stage_name)"
              @set_active="(index) => set_active_method(stage_name, index)"
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
</style>