import { computed, nextTick, reactive, ref, shallowRef, toRaw } from 'vue';
import json_pointer from 'json-pointer';
import Modal from 'bootstrap/js/src/modal';
import mitt from 'mitt';

export interface MethodDef {
  display_name: string,
  fields: string[],
  schema: {
    properties: {[key: string]: object},
    definitions: {[key: string]: object},
  }
}

export interface WellLocation {
  rack_id: string,
  well_number: number,
  id?: string | null,
}

export type DeviceMethodType = {
  method_name: string,
  method_data: object
}

export type TaskDataType = {
  id: string,
  device: string,
  channel?: number,
  method_data?: {'method_list': DeviceMethodType[]},
  md: object,

  device_type?: string,
  device_address?: string,
  channel_mode?: number,
  number_of_channels?: number,
  simulated: boolean,
  sample_mixing: boolean,

  acquisition_time?: number
  non_channel_storage?: string,
  wait_for_queue_to_empty: boolean,
}

export type TaskType = {
  id: string,
  md: object,
  priority?: number | null,
  sample_id?: string,
  sample_number?: number,
  tasks: TaskDataType[],
  task_history: string[],
  task_type: string
  dependency_id?: string,
  dependency_sample_number?: number
}

export type TaskContainerType = {
  id: string,
  task: TaskType,
  subtasks: TaskDataType[],
  status: StatusType
}

export type MethodType = {
  id: string | null,
  display_name: string,
  method_name: string,
  Source?: WellLocation,
  Target?: WellLocation,
  [fieldname: string]: string | number | WellLocation | null | undefined,
  tasks: TaskContainerType[],
  status: StatusType
}

export type DeviceType = {
  device_name: string,
  device_type: string,
  multichannel: boolean,
  allow_sample_mixing: boolean,
  address: string
}

// Class representing a list of methods representing one LH job. Allows dividing
// prep and inject operations for a single sample.
export interface MethodList {
    createdDate: string | null,
    methods: MethodType[],
    active: MethodType[],
}

export type WellFieldName = 'Source' | 'Target';

export interface Sample {
  channel: number,
  id: string,
  name: string,
  description: string,
  stages: {string: MethodList},
  NICE_uuid: string,
  NICE_slotID: number | null,
  current_contents: string,
}

export type StatusType = 'pending' | 'active' | 'completed' | 'inactive' | 'partially complete' | 'cancelled' | 'error' | 'unknown';

export interface SampleStatus {
  status?: StatusType,
  methods_complete?: boolean[]
}

export interface SampleStatusMap {
  [sample_id: string]: {
    status: StatusType,
    stages: {
      string: SampleStatus
    }
  }
}

export type Solute = {name: string, concentration: number, units: SoluteMassUnits | SoluteVolumeUnits};
export type Solvent = {name: string, fraction: number};


export interface Well {
  composition: {solvents: Solvent[], solutes: Solute[]},
  rack_id: string,
  volume: number,
  well_number: number,
  id: string | null,
}

interface WellWithZone extends Well {
  zone: string,
}

interface SourceComponents {
  solutes: { [name: string]: (Solute & { zone: string })[] },
  solvents: { [name: string]: (Solvent & { zone: string })[] },
}

export const materialType = ["solvent", "solute", "lipid", "protein"] as const;
export type MaterialType = typeof materialType[number];
export const soluteMassUnits = ["mg/mL", "mg/L"] as const;
export const soluteVolumeUnits = ["M", "mM", "nM"] as const;
export type SoluteMassUnits = typeof soluteMassUnits[number];
export type SoluteVolumeUnits = typeof soluteVolumeUnits[number];

// @dataclass
// class Material:
//     uuid: str
//     name: str
//     pubchem_cid: Optional[int] = None
//     iupac_name: Optional[str] = None
//     molecular_weight: Optional[float] = None
//     metadata: Optional[dict] = None
//     type: Optional[str] = None
//     density: Optional[float] = None
//     solute_concentration_units: Optional[str] = None

export interface Material {
  name: string,
  pubchem_cid: number | null,
  full_name: string | null,
  iupac_name: string | null,
  molecular_weight: number | null,
  metadata: object | null,
  type: MaterialType | null,
  density: number | null,
  solute_concentration_units: SoluteMassUnits | SoluteVolumeUnits | null,
}

export interface Rack {
  rows: number,
  columns: number,
  style: 'grid' | 'staggered',
  max_volume: number,
  height: number,
  width: number,
  x_translate: number,
  y_translate: number,
  shape: string,
  editable: boolean
}

export interface DeviceLayout {
  layout: {racks: {[rack_id: string]: Rack} },
  wells: Well[],
  source_components: SourceComponents
}

export const method_defs = shallowRef<Record<string, MethodDef>>({});
export const device_defs = shallowRef<Record<string, DeviceType>>({});
export const device_layouts = ref<Record<string, DeviceLayout>>({});
export const waste_layout = ref<DeviceLayout>();
//export const layout = ref<{racks: {[rack_id: string]: {rows: number, columns: number, style: 'grid' | 'staggered', max_volume: number}} }>();
export const samples = ref<Sample[]>([]);
export const sample_status = ref<SampleStatusMap>({});
//export const source_components = shallowRef<SourceComponents>({solvents: {}, solutes: {}});
//export const wells = ref<Well[]>([]);
export const well_editor_active = ref(false);
export const add_waste_active = ref(false);
export const well_to_edit = ref<{device: string, well: WellLocation}>();
export const num_channels = ref<number>(1);
export const materials = ref<Material[]>([]);
export const current_composition = ref<{ solvents: Solvent[], solutes: Solute []}>({solvents: [], solutes: []});

export type ModalData = {
  title: string,
  sample_id: string,
  task_id: string,
  device: string,
  pointer: string,
  editable: boolean,
  task: object | null
}

export const task_modal = ref<Modal>();
export const show_task_modal = ref<boolean>(false)
export const task_modal_data = ref<ModalData>({sample_id: '', title: '', task_id: '', device: '', pointer: '', editable: false, task: {}});
export const task_to_edit = ref<string>("")

export async function edit_task(data: ModalData) {
  task_modal_data.value = data;
  task_to_edit.value = JSON.stringify(task_modal_data.value.task, null, 2);
  task_modal.value.show();
}


// export const layout_with_contents = computed(() => {
//   const layout_copy = structuredClone(toRaw(layout.value));
//   wells.value.forEach((w) => {
//     layout_copy[w.rack_id] = 
//   })
// });

type Events = {
  well_picked: WellLocation
  [event_name: string]: object,
}

export const emitter = mitt<Events>();

export async function update_sample(sample_obj: Partial<Sample>): Promise<object> {
  const update_result = await fetch("/GUI/UpdateSample/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sample_obj)
  });
  const response_body = await update_result.json();
  return response_body;
}

function get_sample_by_id(sample_id: string) {
  return samples.value.find((s) => (s.id === sample_id));
}

export async function archive_and_remove_sample(sample_id: string) {
  const update_result = await fetch("/GUI/ArchiveandRemoveSample/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({id: sample_id})
  });
  const response_body = await update_result.json();
  return response_body;
}

export function add_method(sample_id: string, stage_name: string, event: Event) {
  const sample = get_sample_by_id(sample_id);
  // event comes from a select element:
  const event_target = event.target as HTMLOptionElement;
  const method_name = event_target.value;
  console.log(method_name)
  if (sample !== undefined) {
    const s: Sample = structuredClone(toRaw(sample));
    const { stages } = s;
    const stage = stages[stage_name];
    const num_methods = stage.methods.push({ method_name });
    update_sample(s);
    active_stage.value = stage_name;
    active_method_index.value = num_methods - 1;
  }
  event_target.value = "";
}

export async function update_at_pointer(sample_id: string, pointer: string | string[], value: any) {
  const sample = get_sample_by_id(sample_id);
  // console.log({pointer});
  if (sample !== undefined) {
    const s: Sample = structuredClone(toRaw(sample));
    const g = json_pointer.get(s, pointer);
    json_pointer.set(s, pointer, value);
    return await update_sample(s);
  }
}

export function update_method(sample_id: string, stage_name: string, method_index: number, field_name: string, field_value) {
  const sample = get_sample_by_id(sample_id);
  if (sample !== undefined) {
    const s: Sample = structuredClone(toRaw(sample));
    const { stages } = s;
    const stage = stages[stage_name];
    const method = stage.methods[method_index];
    method[field_name] = field_value;
    update_sample(s);
  }
}

export function get_number_of_methods(sample_id: string, stage_name: string) {
    const sample = get_sample_by_id(sample_id);
    if (sample !== undefined) {
      const s: Sample = structuredClone(toRaw(sample));
      const { stages } = s;
      const stage = stages[stage_name];
      return stage.methods.length
    }
    
    return 0
  }

export function move_method(sample_id: string, stage_name: string, method_index: number, new_index: number) {
    const sample = get_sample_by_id(sample_id);
    if (sample !== undefined) {
      const s: Sample = structuredClone(toRaw(sample));
      const { stages } = s;
      const stage = stages[stage_name];
      if (new_index >= 0 && new_index < stage.methods.length) {
        var deleted_method = stage.methods.splice(method_index, 1);
        stage.methods.splice(new_index, 0, deleted_method[0])
        update_sample(s);
        active_method_index.value = new_index
      }
    }
  }

  export function copy_method(sample_id: string, stage_name: string, method_index: number) {
    const sample = get_sample_by_id(sample_id);
    if (sample !== undefined) {
      const s: Sample = structuredClone(toRaw(sample));
      const { stages } = s;
      const stage = stages[stage_name];
      const method = stage.methods[method_index];
      const new_method = structuredClone(toRaw(method))
      new_method.id = null
      stage.methods.splice(method_index + 1, 0, method);
      update_sample(s);
      active_stage.value = stage_name;
      active_method_index.value = method_index + 1;
    }
  }

  export function reuse_method(sample_id: string, stage_name: string, method_index: number) {
    const sample = get_sample_by_id(sample_id);
    if (sample !== undefined) {
      const s: Sample = structuredClone(toRaw(sample));
      const { stages } = s;
      const stage = stages[stage_name];
      const method = stage.active[method_index];
      const new_method = structuredClone(toRaw(method))
      new_method.id = null
      new_method.tasks = []
      new_method.status = 'inactive'
      const num_methods = stage.methods.push(new_method);
      update_sample(s);
      active_stage.value = stage_name;
      active_method_index.value = num_methods - 1;
    }
  }

export function remove_method(sample_id: string, stage_name: string, method_index: number) {
  const sample = get_sample_by_id(sample_id);
  if (sample !== undefined) {
    const s: Sample = structuredClone(toRaw(sample));
    const { stages } = s;
    const stage = stages[stage_name];
    stage.methods.splice(method_index, 1);
    const num_methods = stage.methods.length;
    update_sample(s);
    active_stage.value = stage_name;
    active_method_index.value = num_methods - 1;
  }
}

export function set_location(method_index: number, name: WellFieldName, rack_id: string, well_number: number, sample_id: string, stage_name: string) {
  const sample = get_sample_by_id(sample_id);
  if (sample !== undefined) {
    const s: Sample = structuredClone(toRaw(sample));
    const { stages } = s;
    const stage = stages[stage_name];
    const method = stage.methods[method_index];
    method[name] = { rack_id, well_number };
    update_sample(s);
  }
}

export function pick_handler(well_location: WellLocation) {
  if (active_sample_index.value !== null && active_stage.value !== null && active_sample_index.value !== null && active_method_index.value !== null) {
    const sample = samples.value[active_sample_index.value];
    const s: Sample = structuredClone(toRaw(sample));
    const stage = s?.stages?.[active_stage.value];
    const method = stage?.methods?.[active_method_index.value] ?? {};
    const well_field = active_well_field.value;
    // console.log({sample, stage, method, well_field});
    if (well_field != null && well_field in method) {
      method[well_field] = well_location;
      if (well_field === 'Source') {
        source_well.value = well_location;
      }
      else if (well_field === 'Target') {
        target_well.value = well_location;
      }
      update_sample(s);
      return
    }
  }
  console.warn("no active well field to set");
}

export async function update_well_contents(base_address: string, well: Well) {
  console.log("updating well: ", well, JSON.stringify(well));
  const update_result = await fetch(base_address + "/GUI/UpdateWell", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(well)
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function remove_well_definition(base_address, well: Well) {
  const update_result = await fetch(base_address + "/GUI/RemoveWellDefinition", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(well)
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function run_sample(sample_obj: Sample, stage: string[] = ['prep', 'inject']): Promise<object> {
  const { name, id, NICE_uuid, NICE_slotID } = sample_obj;
  const uuid = NICE_uuid ?? null;
  const slotID = NICE_slotID ?? null; // don't send undefined.
  const data = { name, id, uuid, slotID, stage };
  console.log({data});
  const update_result = await fetch("/GUI/RunSample/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function run_method(sample_id: string, stage: string, method_index: number ): Promise<object> {
  const sample = get_sample_by_id(sample_id);
  if (sample !== undefined) {
    const s: Sample = structuredClone(toRaw(sample));
    const { name, id, NICE_uuid, NICE_slotID, stages } = s;
    const method = stages[stage].methods[method_index];
    const method_id = method.id;
    const uuid = NICE_uuid ?? null;
    const slotID = NICE_slotID ?? null; // don't send undefined.
    const data = { name, id, uuid, slotID, stage, method_id };
    console.log({data});
    const update_result = await fetch("/GUI/RunMethod/", {
      method: "POST",
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    const response_body = await update_result.json();
    return response_body;
  }
}

export async function resubmit_all_tasks(sample_id: string, stage: string, method_index: number ): Promise<object> {
  const sample = get_sample_by_id(sample_id);
  if (sample !== undefined) {
    const s: Sample = structuredClone(toRaw(sample));
    const method = s.stages[stage].active[method_index];
    const incomplete_tasks = method.tasks.filter((task) => (task.status === 'pending') || (task.status === 'error'));
    const tasklist = incomplete_tasks.map((task) => {
      return task.task;
    });
    if (tasklist.length) {
      const update_result = await fetch("/GUI/ResubmitTasks/", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tasks: tasklist })
      });
      const response_body = await update_result.json();
      return response_body;
    }
  }
}

export async function resubmit_task(task: TaskType): Promise<object> {
  const update_result = await fetch("/GUI/ResubmitTasks/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({tasks: [task]})
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function cancel_task(task: TaskType, include_active_queue: boolean = false, drop_material: boolean = false): Promise<object> {
  const data = { tasks: [task], include_active_queue, drop_material }
  const update_result = await fetch("/GUI/CancelTasks/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function explode_stage(sample_obj: Sample, stage: string): Promise<object> {
  const { id } = sample_obj;
  const data = { id, stage };
  const update_result = await fetch("/GUI/ExplodeSample/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function getDeviceLayout(base_address: string) {
  const layout = await fetch(base_address + "/GUI/GetLayout")
                            .then( response => {
                            if (!response.ok) { return undefined }
                            return response.json()})
  console.log({ layout });
  return { layout };
}

function dedupe<T>(arr: T[]): T[] {
  const strings = arr.map((el) => JSON.stringify(el));
  const set = new Set(strings);
  const vals = Array.from(set).map((s) => JSON.parse(s));
  return vals;
}

export async function getDeviceWells(base_address: string) {
  const wells = await fetch(base_address + "/GUI/GetWells").then( response => {
                        if (!response.ok) { return [] }
                        return response.json()}) as WellWithZone[];
  const solvents = {} as {[name: string]: (Solvent & { zone: string })[]};
  const solutes = {} as {[name: string]: (Solute & { zone: string })[]};
  if (wells !== null) {
    wells.forEach((well) => {
      const { zone } = well;
      well.composition.solvents.forEach((s) => {
        if (!(s.name in solvents)) {
          solvents[s.name] = [];
        }
        solvents[s.name].push({ ...s, zone });
      });
      well.composition.solutes.forEach((s) => {
        if (!(s.name in solutes)) {
          solutes[s.name] = [];
        }
        solutes[s.name].push({ ...s, zone });
      });
    });
  };
  const source_components = { solvents, solutes };
  return { source_components, wells }
}

export async function refreshWells(device_name: string) {
  const new_wells = await getDeviceWells(device_defs.value[device_name].address);
  const current_layout = device_layouts.value[device_name];
  current_layout.wells = new_wells.wells;
  current_layout.source_components = new_wells.source_components;
  device_layouts.value = { ...device_layouts.value, ...{[device_name]: current_layout}};
}

export async function refreshSamples() {
  const { samples: { samples: new_samples_in,  n_channels: num_channels_in } } = await (await fetch('/GUI/GetSamples/')).json() as { samples: { samples: Sample[], n_channels: number } };
  samples.value = new_samples_in;
  num_channels.value = num_channels_in;
  console.log({num_channels_in});
  console.log({new_samples_in});
  // filter samples to extract only what the GUI will edit:
  // const new_samples = new_samples_in.map((s) => {
  //   const { description, stages: unfiltered_stages, name, id } = s;
  //   const stages = Object.fromEntries(Object.entries(unfiltered_stages).map(([stage, { methods }]) => [stage, { methods }]));
  //   return { description, name, id, stages };
  // });
  // samples.value = new_samples;
}

export async function refreshSampleStatus() {
  const new_sample_status = await (await fetch('/GUI/GetSampleStatus/')).json();
  sample_status.value = new_sample_status;
  console.log({new_sample_status});
}

export async function refreshMethodDefs() {
  const { methods } = await (await fetch("/GUI/GetAllMethods/")).json() as {methods: Record<string, MethodDef>};
  method_defs.value = methods;
  console.log({methods});
}

export async function refreshDeviceDefs() {
  const { devices } = await (await fetch("/GUI/GetAllDevices/")).json() as {devices: Record<string, DeviceType>};
  device_defs.value = devices;
  console.log({devices});
}

export async function refreshDeviceLayouts() {
  await refreshDeviceDefs();
  await refreshWaste();
  const layouts = {};
  for (const device_name in device_defs.value) {
    console.log('Updating ' + device_name);
    const new_layout = await getDeviceLayout(device_defs.value[device_name].address);
    if (new_layout !== undefined) {
      const new_wells = await getDeviceWells(device_defs.value[device_name].address);
      layouts[device_name] = { ...new_layout, ...new_wells };
    }
  }
  device_layouts.value = layouts;
}

export async function refreshWaste() {
  const new_layout = await getDeviceLayout("/Waste");
  if (new_layout !== undefined) {
    const new_wells = await getDeviceWells("/Waste");
    waste_layout.value = { ...new_layout, ...new_wells };
  }
  else {
    console.log('Waste layout not found')
    waste_layout.value = undefined;
  }
};

export async function empty_waste() {
  const update_result = await fetch("/Waste/EmptyWaste", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  });
  const response_body = await update_result.json();
  return response_body;
};

export async function add_waste(volume: number, composition: {solvents: Solvent[], solutes: Solute[]}) {
  const update_result = await fetch("/Waste/AddWaste", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ volume, composition })
  });
  const response_body = await update_result.json();
  return response_body;
};


export async function update_device(device_name: string, param_name: string, param_value: any) {
  const update_result = await fetch("/GUI/UpdateDevice/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_name, param_name, param_value })
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function initialize_devices() {
  const update_result = await fetch("/GUI/InitializeDevices/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function remove_sample(sample_id: string) {
  const update_result = await fetch("/GUI/RemoveSample/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({id: sample_id})
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function duplicate_sample(sample_id: string, channel: number) {
  const update_result = await fetch("/GUI/DuplicateSample/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({id: sample_id, channel })
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function refreshComponents() {
  const new_source_components = await (await fetch("/GUI/GetComponents/")).json();
  source_components.value = new_source_components;
  console.log({new_source_components});
}

export async function refreshMaterials() {
  const { materials: new_materials } = await (await fetch("/Materials/all/")).json();
  materials.value = new_materials;
  console.log({new_materials});
}

export async function add_material(material: Material) {
  const update_result = await fetch("/Materials/update/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(material)
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function delete_material(material: Material) {
  const update_result = await fetch("/Materials/delete/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(material)
  });
  const response_body = await update_result.json();
  return response_body;
}

export const source_well = ref<WellLocation | null>(null);
export const target_well = ref<WellLocation | null>(null);

export const active_sample_index = ref<number | null>(null);
export const active_method_index = ref<number | null>(null);
export const active_stage = ref<string | null>(null);
export const active_stage_label = ref<string | null>(null);
export const active_well_field = ref<WellFieldName | null>(null);