<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ProviderSummary } from '@/types/agent'

const props = defineProps<{
  providers: ProviderSummary[]
  selectedId: string | null
}>()

const emit = defineEmits<{
  (e: 'select', id: string): void
  (e: 'openAdd'): void
}>()

const query = ref('')

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return props.providers
  return props.providers.filter(
    (p) => p.name.toLowerCase().includes(q) || p.modelId.toLowerCase().includes(q),
  )
})

function initials(name: string): string {
  return name.replace(/[^a-zA-Z0-9]/g, '').slice(0, 2).toUpperCase() || 'AI'
}
</script>

<template>
  <section class="provider-list" aria-label="供应商列表">
    <div class="section-heading">
      <h2>供应商</h2>
      <span class="count" data-testid="provider-count">{{ filtered.length }} 个配置</span>
    </div>

    <div class="search-wrap">
      <span class="search-icon" aria-hidden="true">⌕</span>
      <input
        v-model="query"
        class="search"
        type="search"
        placeholder="搜索供应商"
        aria-label="搜索供应商"
        data-testid="provider-search"
      >
    </div>

    <div class="provider-items">
      <button
        v-for="provider in filtered"
        :key="provider.id"
        type="button"
        class="provider-row"
        :class="{ selected: provider.id === selectedId }"
        :data-testid="`provider-row-${provider.id}`"
        @click="emit('select', provider.id)"
      >
        <span class="provider-icon" aria-hidden="true">{{ initials(provider.name) }}</span>
        <span class="provider-text">
          <span class="provider-name">{{ provider.name }}</span>
          <span class="provider-meta">{{ provider.modelId }}</span>
        </span>
        <span
          class="status-dot"
          :class="{ pending: !provider.enabled }"
          :title="provider.enabled ? '已启用' : '等待测试'"
          aria-hidden="true"
        />
      </button>
      <p v-if="filtered.length === 0" class="empty-list" data-testid="provider-empty">
        没有找到匹配的供应商
      </p>
    </div>

    <button type="button" class="add-provider" data-testid="open-add" @click="emit('openAdd')">
      ＋ 添加供应商
    </button>
  </section>
</template>

<style scoped>
.provider-list {
  width: 300px; flex: 0 0 auto; min-height: 0;
  display: flex; flex-direction: column;
  padding: 26px 20px 20px;
  border-right: 1.5px solid #d8d0c4;
  background: rgba(255,253,248,.28);
}
.section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
.section-heading h2 { margin: 0; font-family: 'Caveat', cursive; font-size: 30px; line-height: 1; color: #1a1a1a; }
.count { color: #6e665c; font-family: 'JetBrains Mono', monospace; font-size: 11px; }
.search-wrap { position: relative; margin-top: 22px; }
.search-icon { position: absolute; top: 11px; left: 13px; color: #6e665c; }
.search {
  width: 100%;
  padding: 10px 12px 10px 36px;
  border: 1.5px solid #aaa092; border-radius: 8px 10px 9px 11px;
  outline: none; color: #2a2a2a; background: rgba(255,253,248,.75);
  font-family: inherit; font-size: 14px;
}
.search:focus { border-color: #3a6090; box-shadow: 0 0 0 3px rgba(58,96,144,.1); }
.provider-items { display: grid; gap: 8px; margin-top: 18px; overflow-y: auto; }
.provider-row {
  width: 100%;
  display: grid; grid-template-columns: 38px 1fr auto; align-items: center; gap: 10px;
  padding: 11px;
  border: 1.5px solid transparent; border-radius: 9px 11px 8px 12px;
  text-align: left; color: #2a2a2a; background: transparent;
  font-family: inherit; cursor: pointer;
}
.provider-row:hover { background: rgba(255,253,248,.7); border-color: #d8d0c4; }
.provider-row.selected { border-color: #d6bf75; background: rgba(212,160,23,.12); }
.provider-icon {
  width: 36px; height: 36px; display: grid; place-items: center;
  border: 1.5px solid #aaa092; border-radius: 10px 8px 10px 7px;
  background: #fffdf8; color: #2a2a2a;
  font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600;
}
.provider-text { min-width: 0; }
.provider-name { display: block; font-size: 15px; }
.provider-meta { display: block; margin-top: 2px; color: #6e665c; font-family: 'JetBrains Mono', monospace; font-size: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-dot { width: 9px; height: 9px; border-radius: 50%; background: #2d7a3a; box-shadow: 0 0 0 3px rgba(45,122,58,.15); }
.status-dot.pending { background: #d4a017; box-shadow: 0 0 0 3px rgba(212,160,23,.2); }
.empty-list { padding: 40px 14px; color: #6e665c; text-align: center; font-family: 'Patrick Hand', cursive; font-size: 17px; }
.add-provider {
  margin-top: auto; padding-top: 18px;
  width: 100%; padding: 12px 16px;
  border: 2px solid #2a2a2a; border-radius: 9px 11px 10px 8px;
  color: #2a2a2a; background: #f3e1a5;
  font-family: inherit; font-weight: 700; font-size: 15px; cursor: pointer;
  box-shadow: 3px 3px 0 rgba(42,42,42,.18);
  transition: transform .18s ease, box-shadow .18s ease;
}
.add-provider:hover { transform: translate(-1px, -1px); box-shadow: 5px 5px 0 rgba(42,42,42,.18); }

@media (max-width: 900px) {
  .provider-list { width: 100%; border-right: 0; border-bottom: 1.5px solid #d8d0c4; }
}
</style>
