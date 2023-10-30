import { ref, shallowRef, toRaw } from 'vue';
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
}

export type MethodType = {
  display_name: string,
  method_name: string,
  Source?: WellLocation,
  Target?: WellLocation,
  [fieldname: string]: string | number | WellLocation | null | undefined,
}

// Class representing a list of methods representing one LH job. Allows dividing
// prep and inject operations for a single sample.
export interface MethodList {
    LH_id: number | null,
    createdDate: string | null,
    methods: MethodType[],
    methods_complete: boolean[], 
    status: StatusType,
}

export type StageName = 'prep' | 'inject';
export type WellFieldName = 'Source' | 'Target';

export interface Sample {
  id: string,
  name: string,
  description: string,
  stages: {[stagename in StageName]: MethodList},
  NICE_uuid: string,
  NICE_slotID: number | null,
  current_contents: string,
}

export type StatusType = 'pending' | 'active' | 'completed' | 'inactive' | 'partially complete';

export interface SampleStatus {
  status?: StatusType,
  methods_complete?: boolean[]
}

export interface SampleStatusMap {
  [sample_id: string]: {
    status: StatusType,
    stages: {
      [stage_name in StageName]: SampleStatus
    }
  }
}

type Component = [name: string, zone: string];

interface SourceComponents {
  solutes: Component[],
  solvents: Component[]
}

export const method_defs = shallowRef<Record<string, MethodDef>>({});
export const layout = ref<{racks: {[rack_id: string]: {rows: number, columns: number, style: 'grid' | 'staggered'}} }>();
export const samples = ref<Sample[]>([]);
export const sample_status = ref<SampleStatusMap>({});
export const source_components = ref<SourceComponents>();

type Events = {
  well_picked: WellLocation
  [event_name: string]: object,
}

export const emitter = mitt<Events>();

export async function update_sample(sample_obj: Partial<Sample>): Promise<object> {
  const update_result = await fetch("/GUI/UpdateSample", {
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

export function add_method(sample_id: string, stage_name: StageName, method_name: string) {
  const sample = get_sample_by_id(sample_id);
  if (sample !== undefined) {
    const s: Sample = structuredClone(toRaw(sample));
    const { stages } = s;
    const stage = stages[stage_name];
    const num_methods = stage.methods.push({method_name});
    update_sample(s);
    active_stage.value = stage_name;
    active_method_index.value = num_methods - 1;
  }
}

export function update_method(sample_id: string, stage_name: StageName, method_index: number, field_name: string, field_value) {
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

export function remove_method(sample_id: string, stage_name: StageName, method_index: number) {
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

export function set_location(method_index: number, name: WellFieldName, rack_id: string, well_number: number, sample_id: string, stage_name: StageName) {
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
  if (active_sample_index.value !== null && active_stage.value !== null && active_sample_index.value !== null) {
    const sample = samples.value[active_sample_index.value];
    const s: Sample = structuredClone(toRaw(sample));
    const stage = s?.stages?.[active_stage.value];
    const method = stage?.methods?.[active_method_index.value] ?? {};
    const well_field = active_well_field.value;
    console.log({sample, stage, method, well_field});
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

export async function run_sample(sample_obj: Sample, stage: StageName[] = ['prep', 'inject'] ): Promise<object> {
  const { name, id, NICE_uuid, NICE_slotID } = sample_obj;
  const uuid = NICE_uuid ?? null;
  const slotID = NICE_slotID ?? null; // don't send undefined.
  const data = { name, id, uuid, slotID, stage };
  console.log({data});
  const update_result = await fetch("/NICE/RunSamplewithUUID/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  const response_body = await update_result.json();
  return response_body;
}


export async function refreshLayout() {
  const new_layout = await (await fetch("/GUI/GetLayout")).json();
  console.log({new_layout});
  layout.value = new_layout;
}

export async function refreshSamples() {
  const { samples: { samples: new_samples_in } } = await (await fetch('/GUI/GetSamples/')).json() as { samples: { samples: Sample[] }};
  samples.value = new_samples_in;
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

export function remove_sample(id) {
  const idx_to_remove = samples.value.findIndex((s) => s.id == id);
  if (idx_to_remove != null) {
    samples.value.splice(idx_to_remove, 1);
  }
}

export async function refreshComponents() {
  const new_source_components = await (await fetch("/GUI/GetComponents/")).json();
  source_components.value = new_source_components;
  console.log({new_source_components});
}

export const source_well = ref<WellLocation | null>(null);
export const target_well = ref<WellLocation | null>(null);

export const active_sample_index = ref<number | null>(null);
export const active_method_index = ref<number | null>(null);
export const active_stage = ref<StageName | null>(null);
export const active_well_field = ref<WellFieldName | null>(null);