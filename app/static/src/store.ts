import { ref, shallowRef } from 'vue';
import mitt from 'mitt';

export interface MethodDef {
  display_name: string,
  fields: string[],
  schema: {
    properties: string[]
  }
}

export interface WellLocation {
  rack_id: string,
  well_number: number,
}

export interface TransferWithRinse {
  Source: WellLocation,
  Target: WellLocation,
  Volume: number, // float = 1.0
  Flow_Rate: number, // float = 2.5
  display_name: 'Transfer With Rinse',
  method_name: 'NCNR_TransferWithRinse',
}

export interface MixWithRinse {
  //"""Inject with rinse"""
  Target: WellLocation,
  Volume: number, // = 1.0
  Flow_Rate: number, // float = 2.5
  Number_of_Mixes: number, // int = 3
  display_name: 'Mix With Rinse',
  method_name: 'NCNR_MixWithRinse',
}

export interface InjectWithRinse {
  //"""Inject with rinse"""
  Source: WellLocation, // defined in InjectMethod
  Volume: number, // float = 1.0
  Aspirate_Flow_Rate: number, // float = 2.5
  Flow_Rate: number, // float = 2.5
  display_name: 'Inject With Rinse',
  method_name: 'NCNR_InjectWithRinse',
}

export interface Sleep{
  //"""Sleep"""
  Time: number, // float = 1.0
  display_name: 'Sleep',
  method_name: 'NCNR_Sleep',
}

type MethodsType = TransferWithRinse | MixWithRinse | InjectWithRinse | Sleep;

// Class representing a list of methods representing one LH job. Allows dividing
// prep and inject operations for a single sample.
export interface MethodList {
    LH_id: number | null,
    createdDate: string | null,
    methods: MethodsType[],
    methods_complete: boolean[], 
    status: StatusType,
}

export type StageName = 'prep' | 'inject';

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

export const method_defs = shallowRef<Record<string, MethodDef>>({});
export const layout = ref<{racks: {[rack_id: string]: {rows: number, columns: number, style: 'grid' | 'staggered'}} }>();
export const samples = ref<object[]>([]);

type Events = {
  well_picked: WellLocation
  [event_name: string]: object,
}

export const emitter = mitt<Events>();

export async function update_sample(sample_obj: Sample): Promise<object> {
  const update_result = await fetch("/GUI/UpdateSample", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sample_obj)
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

export const source_well = ref<WellLocation | null>(null);
export const target_well = ref<WellLocation | null>(null);

export const active_item = ref<number | null>(null);
export const active_method = ref<number | null>(null);
export const active_stage = ref<'prep' | 'inject' | null>(null);