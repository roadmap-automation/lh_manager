<script setup>
import { computed, ref } from 'vue';
import { num_channels } from '../store';
import SampleList from './SampleList.vue';

const active_channel = ref(0);
const channels = computed(() => Array.from({ length: num_channels.value }, (_, i) => i));

</script>

<template>
  <ul class="nav nav-tabs" id="channel_tabs" role="tablist">
    <li class="nav-item" role="presentation" v-for="channel in channels" :key="channel">
      <button 
        :class="{'nav-link': true, active: (channel === active_channel)}" 
        :id="`channel-tab-${channel}`"
        @click="active_channel = channel"
        type="button" role="tab" :aria-selected="channel === active_channel">
        Channel {{ channel }}
      </button>
    </li>
  </ul>
  <SampleList :channel="active_channel" />
</template>