<script setup lang="ts">
/** 设置分类栏：当前仅“模型与供应商”与“关于”。
 *  视觉沿用 docs/design/settings-providers.html 的暖纸 `.settings-nav`。 */
defineProps<{ category: string }>()
defineEmits<{ (e: 'update:category', value: string): void }>()
</script>

<template>
  <aside class="settings-nav" aria-label="设置分类">
    <p class="eyebrow">LightCode</p>
    <h1>设置</h1>
    <nav class="nav-list">
      <button
        type="button"
        class="nav-item"
        :class="{ active: category === 'providers' }"
        data-testid="settings-cat-providers"
        @click="$emit('update:category', 'providers')"
      >
        <span class="nav-symbol" aria-hidden="true">✦</span>模型与供应商
      </button>
      <button
        type="button"
        class="nav-item"
        :class="{ active: category === 'about' }"
        data-testid="settings-cat-about"
        @click="$emit('update:category', 'about')"
      >
        <span class="nav-symbol" aria-hidden="true">ⓘ</span>关于
      </button>
    </nav>
    <p class="nav-note">供应商凭据仅存储在本机安全存储中，不会进入会话或日志。</p>
    <p class="version">LIGHTCODE / LOCAL BUILD</p>
  </aside>
</template>

<style scoped>
.settings-nav {
  width: 230px; flex: 0 0 auto; min-height: 0;
  padding: 26px 22px 20px;
  border-right: 1.5px solid #d8d0c4;
  background: rgba(255,253,248,.3);
  display: flex; flex-direction: column;
}
.eyebrow {
  margin: 0 0 4px;
  color: #3a6090;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px; font-weight: 600;
  letter-spacing: .12em; text-transform: uppercase;
}
h1 { margin: 0; font-family: 'Caveat', cursive; font-size: 40px; line-height: 1; color: #1a1a1a; }
.nav-list { display: grid; gap: 6px; margin-top: 40px; }
.nav-item {
  width: 100%;
  display: flex; align-items: center; gap: 12px;
  padding: 12px;
  border: 1.5px solid transparent;
  border-radius: 8px 11px 9px 10px;
  color: #6e665c;
  background: transparent;
  text-align: left;
  font-family: inherit; font-size: 15px; cursor: pointer;
}
.nav-item:hover { color: #2a2a2a; background: rgba(212,160,23,.08); }
.nav-item.active {
  color: #2a2a2a;
  border-color: #e2cf91;
  background: rgba(212,160,23,.14);
  transform: rotate(-.5deg);
}
.nav-symbol { width: 20px; text-align: center; font-family: Arial, sans-serif; }
.nav-note {
  margin: 26px 0 0;
  color: #6e665c;
  font-family: 'Patrick Hand', cursive;
  font-size: 15px; line-height: 1.4;
}
.version { margin-top: auto; padding-top: 32px; color: #978e82; font-family: 'JetBrains Mono', monospace; font-size: 10px; }

@media (max-width: 900px) {
  .settings-nav { width: 100%; border-right: 0; border-bottom: 1.5px solid #d8d0c4; }
}
</style>
