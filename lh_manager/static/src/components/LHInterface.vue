<script setup lang="ts">
import { toRaw } from 'vue';
import { active_lh_job, lh_status, clear_lh_error, clear_lh_job, resubmit_lh_job, lh_pauseresume } from '../store';

</script>

<template>
 <div class="row flex-grow-1">
      <div class="col">
        <div class="p-2 row">
            <h5>Gilson Liquid Handler Interface</h5>
        </div>
        <div class="p-2 row card">
            <div class="col card-body">
                <div class="row card-header alert" :class="{'alert-danger': lh_status=='error', 'alert-success': lh_status=='up', 'alert-warning': lh_status=='down', 'alert-info': lh_status=='busy'}">
                    <div class="col-auto">
                        <h6>Status: {{ lh_status }}</h6>
                    </div>
                    <div class="col">
                        <button type="button" class="btn m-8" :class="{'btn-outline-danger': lh_status!='down', 'btn-outline-success': lh_status=='down'}" @click="lh_pauseresume">{{ (lh_status=='down') ? "Resume" : "Pause" }}</button>
                    </div>

                </div>
                <div v-if="lh_status=='error'" class="row">
                    <div class="p-2 col-auto">
                        <button type="button" class="btn btn-warning m-8" @click="clear_lh_error">Clear error</button>
                    </div>
                    <div class="p-2 col">
                        <span class="text-left align-middle">Clear the error state. Use after an error has occurred and is resolved to signal a ready status.</span>
                    </div>
                </div>
                <div v-if="active_lh_job !== null" class="p-2 row">
                    <div class="col">
                        <div class="row">
                            <details>
                                <summary>Active job</summary>
                                <pre>{{ JSON.stringify(toRaw(active_lh_job), null, 2) }}</pre>
                            </details>
                        </div>                        
                        <div class="row">
                            <div class="p-2 col-auto">
                                <button type="button" class="btn btn-primary m-8" @click="resubmit_lh_job">Resubmit active job</button>
                            </div>
                            <div class="p-2 col">
                                <span class="text-left align-middle">Resubmit active job with incremented sample list ID. Use after stopping the liquid handler to rerun the stopped job.</span>
                            </div>
                        </div>
                        <div class="row">
                            <div class="p-2 col-auto">
                                <button type="button" class="btn btn-danger m-8" @click="clear_lh_job">Clear active job</button>
                            </div>
                            <div class="p-2 col">
                                <span class="text-left align-middle">Clear the active job and reset the busy status to idle.</span>
                            </div>
                        </div>
                    </div>
                </div>                        
            </div>
        </div>        
      </div>
  </div>
</template>
