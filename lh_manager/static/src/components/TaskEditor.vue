<script setup lang="ts">
import { ref, computed, watch, defineProps, defineEmits, onMounted } from 'vue';
import { update_at_pointer, task_modal_data, task_modal, task_to_edit } from '../store';
import Modal from 'bootstrap/js/src/modal';
import type { MethodType, ModalData } from '../store';

const modal_node = ref<HTMLElement>();
const modal = task_modal;
const modal_error = ref<string>();
const task_input = ref<HTMLInputElement>();

function validate_modal() {
    try {
        JSON.parse(task_to_edit.value);
        modal_error.value = ""
    } catch (e) {
        modal_error.value = "Invalid JSON";
    };
}

onMounted(() => {
  modal.value = new Modal(modal_node.value);
  modal_node.value?.addEventListener('shown.bs.modal', function () {
    task_input.value?.focus();
  })
});

function close_modal() {
  modal.value?.hide();
}

function send_changes(param) {
  const method_pointer = task_modal_data.value.pointer;
  update_at_pointer(task_modal_data.value.sample_id, method_pointer, param);
}

function update_task() {
  send_changes(JSON.parse(task_to_edit.value));
  close_modal();
}

</script>

<template>
  <div ref="modal_node" class="modal fade" id="task_editor" tabindex="-1">
      <div class="modal-dialog">
      <div class="modal-content">
          <div class="modal-header">
            <div class="col">
              <div class="row">
                <h5 class="modal-title">{{ task_modal_data.title }}</h5>
              </div>
              <div class="row mx-2 uuid">{{ task_modal_data.task_id }}</div>
            </div>
            <div class="col-auto">
              <button type="button" class="btn-close" @click="close_modal" aria-label="Close"></button>
            </div>
          </div>
          <div class="modal-body">
          <div class="col-md-12">
              <div class="row m-2">{{ task_modal_data.device }} </div>
              <div class="row m-2">
              <textarea ref="task_input" rows="10" :disabled="!task_modal_data.editable" class="string width:100% h-50" v-model="task_to_edit"
                  @blur="validate_modal"></textarea>
              <div v-if="modal_error" class="text-danger error-text"> {{ modal_error }}</div>
              </div>
          </div>
          </div>
          <div class="modal-footer">
          <button type="button" class="btn btn-secondary" @click="close_modal">Close</button>
          <button v-if="task_modal_data.editable" type="button" class="btn btn-primary" @click="update_task">Save changes</button>
          </div>
      </div>
      </div>
  </div>
</template>

<style scoped>
.uuid {
  font-size: 0.8rem;
}
</style>