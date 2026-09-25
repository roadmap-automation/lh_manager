<script setup>
import { computed, ref } from 'vue';
import { num_channels } from '../store';
import SampleList from './SampleList.vue';
import MaintenanceTab from './MaintenanceTab.vue';

const active_tab = ref<'maintenance' | number>(0);
const channels = computed(() => Array.from({ length: num_channels.value }, (_, i) => i));

</script>

<template>
  <ul class="nav nav-tabs" id="channel_tabs" role="tablist">
    <li class="nav-item" role="presentation">
      <button
        :class="{'nav-link': true, active: active_tab === 'maintenance'}"
        id="maintenance-tab"
        @click="active_tab = 'maintenance'"
        type="button" role="tab" :aria-selected="active_tab === 'maintenance'">
        Maintenance
      </button>
    </li>
    <li class="nav-item" role="presentation" v-for="channel in channels" :key="channel">
      <button
        :class="{'nav-link': true, active: (channel === active_tab)}"
        :id="`channel-tab-${channel}`"
        @click="active_tab = channel"
        type="button" role="tab" :aria-selected="channel === active_tab">
        Channel {{ channel }}
      </button>
    </li>
  </ul>
  <MaintenanceTab v-if="active_tab === 'maintenance'" />
  <SampleList v-else :channel="active_tab as number" />
</template>
