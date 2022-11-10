<script setup>
import { onMounted, ref } from 'vue';
import { Modal } from 'bootstrap';
import MethodList from './MethodList.vue';

const props = defineProps({
  samples: Array,
  sample_status: Object,
  method_defs: Object,
});

const active_item = ref(null);
const editing_item = ref(null);
const modal_node = ref(null);
const modal = ref(null);
const sample_to_edit = ref({});

function toggleItem(index) {
  active_item.value = (index === active_item.value) ? null : index;
}

function edit_sample_name(index) {
  sample_to_edit.value = props.samples[index];
  modal.value?.show();
}

function close_modal() {
  modal.value?.hide();
}

onMounted(() => {
  modal.value = new Modal(modal_node.value);
});


</script>

<template>
  <div class="accordion">
    <div class="accordion-item" v-for="(sample, sindex) of samples" :key="sample.id">
      <div class="accordion-header">
        <button class="accordion-button p-1" :class="{ collapsed: sindex !== active_item, [`status_${sample_status[sample.id]?.status ?? 'pending'}`]: true }" type="button"
          @click="toggleItem(sindex)" :aria-expanded="sindex === active_item">
          <span class="fw-bold align-middle px-2"> {{ sample.name }} </span>
          <span class="align-middle px-2"> {{ sample.description }}</span>
          <button type="button" class="btn-close btn-sm align-middle edit" aria-label="Edit Name or Description"
            @click.stop="edit_sample_name(sindex)"></button>
        </button>
      </div>
      <div class="accordion-collapse collapse" :class="{ show: sindex === active_item }">
        <div class="accordion-body py-0">
          <MethodList :methods="sample.methods" :method_defs="method_defs" :status="sample_status[sample.id]" />
        </div>
      </div>
    </div>
  </div>
  <div ref="modal_node" class="modal fade" id="edit_sample" tabindex="-1">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Edit Sample Name and Description</h5>
          <button type="button" class="btn-close" @click="close_modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <table class="table">
          <tr>
            <td><label for="sample_name">name:</label></td>
            <td><input type="text" :value="sample_to_edit.name" name="sample_name" /></td>
          </tr>
          <tr>
            <td><label for="sample_description">description:</label></td>
            <td><input type="text" :value="sample_to_edit.description" name="sample_description" /></td>
          </tr>
        </table>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" @click="close_modal">Close</button>
          <button type="button" class="btn btn-primary" @click="">Save changes</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
.btn-close.edit {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-pencil-square' viewBox='0 0 16 16'><path d='M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z'/><path fill-rule='evenodd' d='M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5v11z'/></svg>")
}

.status_pending span {
  color: grey;
}
.status_completed span {
  color: orange;
}
.status_active span {
  color: green;
}
</style>