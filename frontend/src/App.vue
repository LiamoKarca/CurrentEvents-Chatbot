<!-- utf-8-sig -->
<template>
  <!-- 只交由路由決定要顯示哪個頁面 -->
  <RouterView />
</template>

<script setup lang="ts">
// 無需額外邏輯
</script>

<style>
/* 可選：全域背景與重置 */
html, body, #app {
  margin: 0;
  height: 100%;
}
</style>
