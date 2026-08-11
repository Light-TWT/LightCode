<script setup lang="ts">
/** 独立设置页（/settings）：保留直接访问与深链兼容。
 *  设置业务内容与工作区设置层共用 SettingsContent，避免两套实现漂移。
 *  设置按钮（openSettings）在此维持当前展示，不再打开新页面。 */
import AppSidebar from '@/components/AppSidebar.vue'
import SettingsContent from '@/components/SettingsContent.vue'
</script>

<template>
  <div class="settings-page">
    <div class="columns">
      <AppSidebar
        :active-nav="null"
        :collapsed="false"
        :settings-active="true"
        @toggle="() => undefined"
        @toggle-collapse="() => undefined"
      />

      <SettingsContent show-back />
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  min-height: 100vh; max-height: 100vh; overflow: hidden;
  background: #f5f0e8; color: #2a2a2a;
  font-family: 'Architects Daughter', cursive;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
.columns {
  height: 100vh;
  display: flex; align-items: stretch;
}

@media (max-width: 900px) {
  .columns { flex-direction: column; overflow-y: auto; }
  .settings-page { max-height: none; overflow: auto; }
}
</style>
