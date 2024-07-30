import { computed, ref, shallowRef, toRaw } from 'vue';
import json_pointer from 'json-pointer';
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
export type Solute = {name: string, concentration: number, units: string};
export type Solvent = {name: string, fraction: number};

export interface Well {
  composition: {solvents: Solvent[], solutes: Solute[]},
  rack_id: string,
  volume: number,
  well_number: number,
}

interface WellWithZone extends Well {
  zone: string,
}

interface SourceComponents {
  solutes: Component[],
  solvents: Component[]
}

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
//     display_units: Optional[str] = None

export interface Material {
  uuid: string,
  name: string,
  pubchem_cid: number | null,
  iupac_name: string | null,
  molecular_weight: number | null,
  metadata: object | null,
  type: string | null,
  density: number | null,
  display_units: string | null,
}

export const method_defs = shallowRef<Record<string, MethodDef>>({});
export const layout = ref<{racks: {[rack_id: string]: {rows: number, columns: number, style: 'grid' | 'staggered', max_volume: number}} }>();
export const samples = ref<Sample[]>([]);
export const sample_status = ref<SampleStatusMap>({});
export const source_components = ref<SourceComponents>();
export const wells = ref<Well[]>([]);
export const well_editor_active = ref(false);
export const well_to_edit = ref<WellLocation>();
export const materials = ref<Material[]>([]);

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

export function add_method(sample_id: string, stage_name: StageName, event: Event) {
  const sample = get_sample_by_id(sample_id);
  // event comes from a select element:
  const event_target = event.target as HTMLOptionElement;
  const method_name = event_target.value;
  if (sample !== undefined) {
    const s: Sample = structuredClone(toRaw(sample));
    const { stages } = s;
    const stage = stages[stage_name];
    const num_methods = stage.methods.push({method_name});
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

export function get_number_of_methods(sample_id: string, stage_name: StageName) {
    const sample = get_sample_by_id(sample_id);
    if (sample !== undefined) {
      const s: Sample = structuredClone(toRaw(sample));
      const { stages } = s;
      const stage = stages[stage_name];
      return stage.methods.length
    }
    
    return 0
  }

export function move_method(sample_id: string, stage_name: StageName, method_index: number, new_index: number) {
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

export async function update_well_contents(well: Well) {
  console.log("updating well: ", well, JSON.stringify(well));
  const update_result = await fetch("/GUI/UpdateWell/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(well)
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function remove_well_definition(well: Well) {
  const update_result = await fetch("/GUI/RemoveWellDefinition/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(well)
  });
  const response_body = await update_result.json();
  return response_body;
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

export async function explode_stage(sample_obj: Sample, stage: StageName): Promise<object> {
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

export async function refreshLayout() {
  const new_layout = await (await fetch("/GUI/GetLayout/")).json();
  console.log({new_layout});
  layout.value = new_layout;
}

function dedupe<T>(arr: T[]): T[] {
  const strings = arr.map((el) => JSON.stringify(el));
  const set = new Set(strings);
  const vals = Array.from(set).map((s) => JSON.parse(s));
  return vals;
}

export async function refreshWells() {
  const new_wells = await (await fetch("/GUI/GetWells/")).json() as WellWithZone[];
  const solvent_zones: Component[] = new_wells.map((well) => (well.composition.solvents.map((s) => ([s.name, well.zone] as Component)))).flat();
  const solute_zones: Component[] = new_wells.map((well) => (well.composition.solutes.map((s) => ([s.name, well.zone] as Component)))).flat();
  const dedup_solvent_zones = dedupe(solvent_zones);
  const dedup_solute_zones = dedupe(solute_zones);
  source_components.value = {solvents: dedup_solvent_zones, solutes: dedup_solute_zones};
  wells.value = new_wells;
  console.log({new_wells});
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

export async function remove_sample(sample_id: string) {
  const update_result = await fetch("/GUI/RemoveSample/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({id: sample_id})
  });
  const response_body = await update_result.json();
  return response_body;
}

export async function duplicate_sample(sample_id: string) {
  const update_result = await fetch("/GUI/DuplicateSample/", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({id: sample_id})
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
export const active_stage = ref<StageName | null>(null);
export const active_well_field = ref<WellFieldName | null>(null);