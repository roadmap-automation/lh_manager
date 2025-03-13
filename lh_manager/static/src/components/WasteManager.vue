<script setup lang="ts">
import { ref, computed } from 'vue';
import BedLayout from './BedLayout.vue';
import { waste_timestamp_table, generate_waste_report, add_waste_active, waste_layout, empty_waste } from '../store';

</script>

<template>
<div class="card m-3">
    <div class="card-body">
        <div class="col flex-column d-flex flex-fill">
            <div class="m-0 row">
            <h5 class="card-title">Waste Contents</h5>
            </div>

            <div class="m-3 row">
            <div class="col col-sm-auto">
                <button type="button" class="m-3 btn btn-primary text-no-wrap" @click="add_waste_active=true">Add Waste</button>
            </div>
            <div class="col col-sm-auto">
                <button type="button" class="m-3 btn btn-primary btn-danger text-no-wrap" @click="empty_waste()">Empty Waste</button>
            </div>
            </div>
            <div class="m-3 row">
                Carboy ID: {{ waste_layout?.wells[0].id }}
            </div>
            <div class="m-3 row vh-100">
                <BedLayout class="vh-100" v-if="(waste_layout?.layout !== null)" device_name="Waste System" :layout="waste_layout"/>
            </div>
        </div>  
        </div>
    </div>
    <div class="card m-3">
        <div class="card-body">
        <div class="col d-flex flex-fill">
            <div class="m-0 row flex-row flex-grow-1">
                <div class="row flex-grow-1">
                    <div class="col">
                        <h5>Waste History</h5>
                        <table class="table table-sm">
                        <thead>
                            <tr class="sticky-top text-body bg-white">
                            <th scope="col">Carboy ID</th>
                            <th scope="col">First entry</th>
                            <th scope="col">Last entry</th>
                            <th scope="col" title="report"></th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="carboy in waste_timestamp_table?.timestamp_table">
                            <td>{{ carboy[0] }}</td>
                            <td>{{ carboy[1] }}</td>
                            <td>{{ carboy[2] }}</td>
                            <td><button class="btn btn-outline-danger" @click="generate_waste_report(carboy[0])">Report</button></td>
                            </tr>
                        </tbody>
                        </table>
                    </div>
                </div>
            </div>  
        </div>
    </div>
</div>
</template>

<style scoped>
  select:has(option[value="null"]:checked) {
    color: gray;
  }
  option[value="null"] {
    color: gray;
  }
  .form-floating>label {
    padding-left: 0.1rem;
  }
</style>