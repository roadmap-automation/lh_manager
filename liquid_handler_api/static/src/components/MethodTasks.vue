<script setup lang="ts">
import { ref, computed, watch, defineProps, defineEmits, onMounted } from 'vue';
import { update_at_pointer, resubmit_task, edit_task, cancel_task } from '../store';
import type { MethodType } from '../store';

const props = defineProps<{
  sample_id: string,
  pointer: string,
  method: MethodType,
  editable: boolean,
  hide_fields: string[],
}>();

function send_changes(param, pointer) {
  const method_pointer = `${props.pointer}/${pointer}`;
  console.log(method_pointer, param)
  update_at_pointer(props.sample_id, method_pointer, param);
}

function parse_tasks(method: MethodType) {
  const tasks = method.tasks.map((taskcontainer) => {
    const { task, status } = taskcontainer
    const subtasks = task.tasks.map((subtask) => {
      const methods = subtask.method_data?.method_list.map((method) => {
        return {name: method.method_name, method_data: method.method_data, value: JSON.stringify(method, null, 2)}
      })
      return {id: subtask.id, device: subtask.device, methods: methods, value: subtask.method_data?.method_list}
    })
    return {id: task.id, status: status, methods: subtasks, task: task};
  });
  return tasks
}

const tasks = computed(() => {
  return parse_tasks(props.method);
});

function clone(obj) {
  return (obj === undefined) ? undefined : JSON.parse(JSON.stringify(obj));
}

</script>

<template>
  <table>
    <tr class="mx-0 py-0">
      <td class="mx-0 py-0">
        <div class="stage-label mx-0 py-0 row">
          Tasks
        </div>
      </td>
    </tr>
    <tr class="mx-2" v-for="(task, task_index) of tasks">
      <td class="mx-2">
        <div class="mx-2 row">
          <h6>{{ task.id }}
            <div v-if="!(task.status === 'completed')">
              <button
                type="button"
                class="btn-close btn-sm arrow-repeat"
                aria-label="Resubmit task"
                title="Resubmit task"
                @click.stop="resubmit_task(task.task)">
              </button>
              <button
                type="button"
                class="btn-close btn-sm cancel"
                aria-label="Cancel task"
                title="Cancel task"
                @click.stop="cancel_task(task.task, false, false)">
              </button>
              <button
                type="button"
                class="btn-close btn-sm cancel-fill"
                aria-label="Super cancel task"
                title="Super cancel task"
                @click.stop="cancel_task(task.task, true, true)">
              </button>
            </div>
          </h6>
        </div>
        <div class="mx-2 row" v-for="(imethod, imethod_index) of task.methods">
          <div class="mx-2 row">
            <div class="col-sm-auto">
              <button
                  type="button"
                  class="btn-close btn-sm align-middle gear"
                  aria-label="View/edit task data"
                  title="View/edit task data"
                  @click.stop="edit_task({'sample_id': props.sample_id, 'title': (!(task.status === 'completed') ? 'Edit' : 'View') + ' task data', 'device': imethod.device, 'editable': !(task.status === 'completed'), 'pointer': `${props.pointer}/tasks/${task_index}/task/tasks/${imethod_index}/method_data/method_list`, 'task_id': task.id, 'task': imethod.value ?? null})">
              </button>                
            </div>
            <div class="col">
              <div class="row">{{ imethod.device }} </div>
              <div class="row uuid">{{ imethod.id }}</div>
              <div class="row method-data" v-for="(iimethod, iimethod_index) of imethod.methods">
                {{ iimethod.name }} : {{ iimethod.method_data }}
                <!-- <textarea ref="task_input" :disabled="!modal_data.editable" class="string" v-model="task_to_edit"
                @blur="validate_modal"></textarea>
                <div v-if="modal_error" class="text-danger error-text"> {{ modal_error }}</div> -->
              </div>
            </div>
          </div>
        </div>
      </td>
    </tr>
  </table>
  </template>

<style scoped>
.btn-close.edit {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-pencil-square' viewBox='0 0 16 16'><path d='M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z'/><path fill-rule='evenodd' d='M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5v11z'/></svg>")
}

.btn-close.gear {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-gear' viewBox='0 0 16 16'><path d='M8 4.754a3.246 3.246 0 1 0 0 6.492 3.246 3.246 0 0 0 0-6.492M5.754 8a2.246 2.246 0 1 1 4.492 0 2.246 2.246 0 0 1-4.492 0'/><path d='M9.796 1.343c-.527-1.79-3.065-1.79-3.592 0l-.094.319a.873.873 0 0 1-1.255.52l-.292-.16c-1.64-.892-3.433.902-2.54 2.541l.159.292a.873.873 0 0 1-.52 1.255l-.319.094c-1.79.527-1.79 3.065 0 3.592l.319.094a.873.873 0 0 1 .52 1.255l-.16.292c-.892 1.64.901 3.434 2.541 2.54l.292-.159a.873.873 0 0 1 1.255.52l.094.319c.527 1.79 3.065 1.79 3.592 0l.094-.319a.873.873 0 0 1 1.255-.52l.292.16c1.64.893 3.434-.902 2.54-2.541l-.159-.292a.873.873 0 0 1 .52-1.255l.319-.094c1.79-.527 1.79-3.065 0-3.592l-.319-.094a.873.873 0 0 1-.52-1.255l.16-.292c.893-1.64-.902-3.433-2.541-2.54l-.292.159a.873.873 0 0 1-1.255-.52zm-2.633.283c.246-.835 1.428-.835 1.674 0l.094.319a1.873 1.873 0 0 0 2.693 1.115l.291-.16c.764-.415 1.6.42 1.184 1.185l-.159.292a1.873 1.873 0 0 0 1.116 2.692l.318.094c.835.246.835 1.428 0 1.674l-.319.094a1.873 1.873 0 0 0-1.115 2.693l.16.291c.415.764-.42 1.6-1.185 1.184l-.291-.159a1.873 1.873 0 0 0-2.693 1.116l-.094.318c-.246.835-1.428.835-1.674 0l-.094-.319a1.873 1.873 0 0 0-2.692-1.115l-.292.16c-.764.415-1.6-.42-1.184-1.185l.159-.291A1.873 1.873 0 0 0 1.945 8.93l-.319-.094c-.835-.246-.835-1.428 0-1.674l.319-.094A1.873 1.873 0 0 0 3.06 4.377l-.16-.292c-.415-.764.42-1.6 1.185-1.184l.292.159a1.873 1.873 0 0 0 2.692-1.115z'/></svg>")
}

.btn-close.cancel {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-x-circle' viewBox='0 0 16 16'><path d='M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14m0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16'/><path d='M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708'/></svg>")
}

.btn-close.cancel-fill {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-x-circle-fill' viewBox='0 0 16 16'><path d='M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0M5.354 4.646a.5.5 0 1 0-.708.708L7.293 8l-2.647 2.646a.5.5 0 0 0 .708.708L8 8.707l2.646 2.647a.5.5 0 0 0 .708-.708L8.707 8l2.647-2.646a.5.5 0 0 0-.708-.708L8 7.293z'/></svg>")
}

input.number {
  width: 10em;
}

.method-data {
  font-size: 0.8rem;
}

.error-text {
  font-size: 0.8rem;
}

.uuid {
  font-size: 0.8rem;
}
.form-select {
  color: #0d6efd;
  border-color: #0d6efd;
}
.selector-active {
  /* border-color: #0d6efd;
  border-style: solid;
  border-width: 3px;
  border-radius: 10; */
  background-color: yellow;

}

td.Source-old {
  background: repeating-linear-gradient(
    45deg,
    lightgreen 0px,
    lightgreen 5px,
    #E1FAE1 5px,
    #E1FAE1 10px
  );
}

td.Source .form-check {
  border-color: magenta;
  border-style: solid;
  border-width: 8px;
  border-radius: 10;
}

td.Target-old {
  background: repeating-linear-gradient(
    -45deg,
    pink 0px,
    pink 5px,
    white 5px,
    white 10px
  );
}

td.Target .form-check {
  border-color: darkorange;
  border-style: solid;
  border-width: 8px;
  border-radius: 10;
}

input.dirty {
  color: red;
}
span.method-string {
  max-width: 800px;
}
</style>