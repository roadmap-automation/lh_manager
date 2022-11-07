<script setup>
// This starter template is using Vue 3 <script setup> SFCs
// Check out https://vuejs.org/api/sfc-script-setup.html#script-setup
import LiquidHandler from './components/LiquidHandler.vue';
import { onMounted } from 'vue';
</script>

<template>
  <div class="h-100 d-flex flex-column">
    <nav class="navbar navbar-light bg-light p-2">
      <div class="container-fluid">
        <div class="navbar-brand">
          <img src="./assets/f_nist-logo-centerforneutronresearch-black_nist-logo-centerforneutronresearch-black.png"
            alt="" height="50" class="d-inline-block align-text-middle">
          Reflectometry Liquid Handling
        </div>
      </div>
    </nav>
    <LiquidHandler />
  </div>
</template>

<style scoped>
.logo {
  height: 6em;
  padding: 1.5em;
  will-change: filter;
}

.logo:hover {
  filter: drop-shadow(0 0 2em #646cffaa);
}

.logo.vue:hover {
  filter: drop-shadow(0 0 2em #42b883aa);
}
</style>
