<script setup lang="ts">
import { ref, computed, watch, defineProps, defineEmits } from 'vue';
import { active_well_field, method_defs, source_components, soluteMassUnits, soluteVolumeUnits, materials, source_well, target_well, layout, update_at_pointer } from '../store';
import json_pointer from 'json-pointer';
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
        return {value: JSON.stringify(method, null, 2)}
      })
      return {id: subtask.id, device: subtask.device, methods: methods}
    })
    return {id: task.id, status: status, methods: subtasks};
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
  <tr v-for="(task, task_index) of tasks">
    <td>
      <div>
        {{ task.id }}
      </div>
      <div v-for="(imethod, imethod_index) of task.methods">
        <div>{{ imethod.device }} : {{ imethod.id }}</div>
          <div v-for="(iimethod, iimethod_index) of imethod.methods">
            <textarea :disabled="task.status === 'completed'" class="string" v-model="iimethod.value"
              @keydown.enter="send_changes(JSON.parse(iimethod.value), `tasks/${task_index}/task/tasks/${imethod_index}/method_data/method_list/${iimethod_index}`)"
              @blur="send_changes(JSON.parse(iimethod.value), `tasks/${task_index}/task/tasks/${imethod_index}/method_data/method_list/${iimethod_index}`)">
            </textarea>
          </div>
      </div>
    </td>
  </tr>
</template>

<style scoped>
.btn-close.edit {
  background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-pencil-square' viewBox='0 0 16 16'><path d='M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z'/><path fill-rule='evenodd' d='M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5v11z'/></svg>")
}
input.number {
  width: 10em;
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