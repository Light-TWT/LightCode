<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useWorkspaceStore } from '@/stores/workspace.store'
import { isDesktopAvailable, selectFolder } from '@/services/desktop.service'
import type { RegisteredWorkspace } from '@/types/agent'

const store = useWorkspaceStore()
const open = ref(false)
const picking = ref(false)
const folderError = ref('')

const emit = defineEmits<{ (e: 'select', ws: RegisteredWorkspace): void }>()

function toggle() {
  open.value = !open.value
  folderError.value = ''
}

function close() {
  open.value = false
}

function choose(ws: RegisteredWorkspace) {
  if (!ws.enabled) return
  emit('select', ws)
  close()
}

async function pickFolder() {
  folderError.value = ''
  if (!isDesktopAvailable()) {
    folderError.value = '当前环境不支持选择文件夹'
    return
  }
  picking.value = true
  try {
    const result = await selectFolder()
    if (!result || result.cancelled) return
    if ('error' in result) {
      folderError.value = result.error
      return
    }
    // Refresh the recent list and select the newly registered workspace.
    await store.loadWorkspaces()
    emit('select', result.workspace)
    close()
  } catch {
    folderError.value = '选择文件夹失败'
  } finally {
    picking.value = false
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="picker" data-testid="workspace-picker">
    <button
      type="button"
      class="picker-trigger"
      :aria-expanded="open"
      data-testid="picker-trigger"
      @click="toggle"
    >
      <span class="picker-label">{{
        store.currentWorkspaceId
          ? store.workspaces.find((w) => w.id === store.currentWorkspaceId)?.displayName ?? '工作区'
          : '选择工作文件夹'
      }}</span>
      <span class="picker-caret" aria-hidden="true">▾</span>
    </button>

    <div v-if="open" class="popover" role="menu" data-testid="picker-popover">
      <p v-if="store.workspaces.length" class="popover-title">最近工作区</p>
      <button
        v-for="ws in store.workspaces"
        :key="ws.id"
        type="button"
        role="menuitem"
        class="ws-row"
        :class="{ active: ws.id === store.currentWorkspaceId, disabled: !ws.enabled }"
        data-testid="picker-workspace-row"
        @click="choose(ws)"
      >
        <span class="ws-name">{{ ws.displayName }}</span>
        <span class="ws-meta">{{ ws.enabled ? '已启用' : '已停用' }}</span>
      </button>

      <button
        type="button"
        class="pick-folder"
        :disabled="picking"
        data-testid="pick-folder-btn"
        @click="pickFolder"
      >
        {{ picking ? '读取中…' : '选择工作文件夹' }}
      </button>
      <p v-if="folderError" class="folder-error" data-testid="picker-error">{{ folderError }}</p>
    </div>
  </div>
</template>

<style scoped>
.picker { position: relative; }
.picker-trigger {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: #2a2a2a; background: rgba(255,255,255,.35);
  border: 1.5px solid #d8d0c4; border-radius: 4px; padding: 6px 10px;
  cursor: pointer;
}
.picker-trigger:hover { background: rgba(255,255,255,.55); }
.picker-caret { color: #888; }
.popover {
  position: absolute; left: 0; bottom: calc(100% + 8px);
  min-width: 260px; max-height: 320px; overflow: auto;
  background: #fbf8f0; border: 1.5px solid #d8d0c4; border-radius: 6px;
  padding: 10px; box-shadow: 0 6px 20px rgba(0,0,0,.08);
  z-index: 20;
}
.popover-title {
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  text-transform: uppercase; letter-spacing: 1.5px; color: #888;
  margin-bottom: 6px;
}
.ws-row {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  width: 100%; text-align: left; padding: 8px 10px; margin-bottom: 4px;
  font-family: inherit; color: #2a2a2a; cursor: pointer;
  border: 1px solid transparent; border-radius: 4px; background: none;
}
.ws-row:hover { background: rgba(212,160,23,.1); }
.ws-row.active { border-color: #c9a227; background: rgba(212,160,23,.12); }
.ws-row.disabled { opacity: .5; cursor: not-allowed; }
.ws-name { font-family: Caveat, cursive; font-size: 18px; font-weight: 700; }
.ws-meta { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #888; }
.pick-folder {
  width: 100%; margin-top: 6px; padding: 8px;
  font-family: inherit; font-size: 13px; cursor: pointer;
  border: 2px solid #2a2a2a; border-radius: 4px;
  background: rgba(212,160,23,.15); color: #2a2a2a; font-weight: 600;
}
.pick-folder:disabled { opacity: .5; cursor: not-allowed; }
.folder-error { margin-top: 6px; font-size: 12px; color: #b83030; }
</style>