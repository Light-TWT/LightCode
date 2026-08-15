<script setup lang="ts">
/** Skill 管理视图：暖纸视觉语言，行式列表 + 搜索/来源筛选 + ZIP 上传 +
 *  详情模态层（含页脚内联删除确认）。
 *  组件不直接调用 fetch、不解析 ZIP、不保存文档到 localStorage。 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import SettingsOverlay from '@/components/SettingsOverlay.vue'
import SkillDetailOverlay from '@/components/SkillDetailOverlay.vue'
import { useSkillsStore } from '@/stores/skills.store'
import type { SkillStatus } from '@/types/agent'

const route = useRoute()
const router = useRouter()
const workspaceId = String(route.params.workspaceId ?? '')
const store = useSkillsStore()

const sidebarCollapsed = ref(false)
/** 设置层：大型模态层，与工作区页一致（不再跳转独立设置页） */
const settingsOverlayOpen = ref(false)
const uploadInput = ref<HTMLInputElement | null>(null)
/** 待删除确认的技能 id（非 null 时详情页脚显示确认区） */
const confirmDeleteId = ref<string | null>(null)

/** 侧边导航项：工作区/文件浏览/会话 → 跳到工作区页并打开对应面板 */
function goPanel(key: 'workspace' | 'files' | 'sessions') {
  router.push({ path: `/workspace/${workspaceId}`, query: { panel: key } })
}

onMounted(() => {
  void store.load()
})

function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || store.uploading) return
  void store.upload(file)
  input.value = ''
}

function openRow(id: string) {
  void store.open(id)
}

function toggleStatus(id: string, current: SkillStatus) {
  void store.setStatus(id, current === 'enabled' ? 'disabled' : 'enabled')
}

function requestDelete() {
  if (store.detail) confirmDeleteId.value = store.detail.id
}

function confirmDelete() {
  if (!confirmDeleteId.value) return
  const id = confirmDeleteId.value
  confirmDeleteId.value = null
  void store.remove(id)
}

function cancelDelete() {
  confirmDeleteId.value = null
}

function closeOverlay() {
  confirmDeleteId.value = null
  store.close()
}
</script>

<template>
  <div class="skills-page">
    <AppSidebar
      :active-nav="null"
      :collapsed="sidebarCollapsed"
      @toggle="goPanel"
      @toggle-collapse="sidebarCollapsed = !sidebarCollapsed"
      @open-settings="settingsOverlayOpen = true"
    />

    <main class="skills-main">
      <header class="page-head">
        <p class="page-kicker">技能</p>
        <h1 class="page-title" data-testid="skills-title">技能管理</h1>
        <p class="page-sub">上传 ZIP 技能包并查看文档；启用后该技能才能被 Agent 使用。</p>
      </header>

      <div class="toolbar">
        <input
          v-model="store.query"
          type="search"
          class="search"
          placeholder="搜索技能名称或摘要"
          aria-label="搜索技能"
          data-testid="skill-search-input"
        />
        <div class="filters" role="group" aria-label="来源筛选">
          <button
            type="button"
            class="filter-btn"
            :class="{ active: store.sourceFilter === 'all' }"
            data-testid="skills-filter-all"
            @click="store.sourceFilter = 'all'"
          >全部 <span class="count">{{ store.items.length }}</span></button>
          <button
            type="button"
            class="filter-btn"
            :class="{ active: store.sourceFilter === 'builtin' }"
            data-testid="skills-filter-builtin"
            @click="store.sourceFilter = 'builtin'"
          >内置 <span class="count">{{ store.items.filter((item) => item.source === 'builtin').length }}</span></button>
          <button
            type="button"
            class="filter-btn"
            :class="{ active: store.sourceFilter === 'uploaded' }"
            data-testid="skills-filter-uploaded"
            @click="store.sourceFilter = 'uploaded'"
          >已上传 <span class="count">{{ store.items.filter((item) => item.source === 'uploaded').length }}</span></button>
        </div>
        <button
          type="button"
          class="upload-btn"
          data-testid="skill-upload-button"
          :disabled="store.uploading"
          @click="uploadInput?.click()"
        >{{ store.uploading ? '正在识别…' : '上传技能' }}</button>
        <input
          ref="uploadInput"
          type="file"
          accept=".zip,application/zip"
          class="visually-hidden"
          data-testid="skill-upload-input"
          @change="onFileSelected"
        />
      </div>

      <p v-if="store.error" class="error" data-testid="skills-error" role="alert">{{ store.error }}</p>
      <p v-if="store.loading" class="empty" data-testid="skills-loading">正在加载…</p>
      <p v-else-if="store.filtered.length === 0" class="empty" data-testid="skills-empty">没有匹配的技能。</p>

      <ul class="list" data-testid="skill-list">
        <li
          v-for="skill in store.filtered"
          :key="skill.id"
          class="row"
          data-testid="skill-row"
          @click="openRow(skill.id)"
        >
          <span class="row-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M4.5 5.5A1.5 1.5 0 0 1 6 4h4.5a2.5 2.5 0 0 1 2.5 2.5V20a2.5 2.5 0 0 0-2.5-2.5H6A1.5 1.5 0 0 0 4.5 19Z"/>
              <path d="M19.5 5.5A1.5 1.5 0 0 0 18 4h-4.5A2.5 2.5 0 0 0 11 6.5V20a2.5 2.5 0 0 1 2.5-2.5H18a1.5 1.5 0 0 1 1.5 1.5Z"/>
              <path d="M8 8h2M14 8h2"/>
            </svg>
          </span>
          <span class="row-main">
            <span class="row-name">{{ skill.name }}</span>
            <span class="row-summary">{{ skill.summary || '（无摘要）' }}</span>
          </span>
          <span class="row-source" :data-testid="`skill-source-${skill.source}`">
            {{ skill.source === 'uploaded' ? '已上传' : '内置' }}
          </span>
          <span class="row-status" :data-testid="`skill-row-status-${skill.status}`">
            {{ skill.status === 'enabled' ? '已启用' : '未启用' }}
          </span>
          <button
            type="button"
            class="switch"
            :class="{ on: skill.status === 'enabled' }"
            :data-testid="`skill-toggle-${skill.id}`"
            :aria-label="`${skill.status === 'enabled' ? '停用' : '启用'} ${skill.name}`"
            :disabled="store.updatingId === skill.id"
            @click.stop="toggleStatus(skill.id, skill.status)"
          ><span class="switch-knob" /></button>
        </li>
      </ul>
    </main>

    <SkillDetailOverlay
      :open="Boolean(store.detail && store.document)"
      :detail="store.detail"
      :document="store.document"
      :updating="Boolean(store.updatingId && store.updatingId === store.detail?.id)"
      :deleting="Boolean(store.deletingId)"
      :confirming-delete="confirmDeleteId !== null"
      @close="closeOverlay"
      @set-status="(status) => { if (store.detail) void store.setStatus(store.detail.id, status) }"
      @request-delete="requestDelete"
      @confirm-delete="confirmDelete"
      @cancel-delete="cancelDelete"
    />

    <!-- 设置层：大型模态层（不再跳转独立设置页） -->
    <SettingsOverlay :open="settingsOverlayOpen" @close="settingsOverlayOpen = false" />
  </div>
</template>

<style scoped>
.visually-hidden {
  position: absolute; width: 1px; height: 1px;
  clip: rect(0 0 0 0); overflow: hidden; white-space: nowrap;
}
.skills-page {
  height: 100vh; min-height: 0;
  display: flex;
  background:
    linear-gradient(rgba(255,253,248,.6), rgba(255,253,248,.6)),
    repeating-linear-gradient(0deg, transparent, transparent 27px, rgba(120,105,85,.05) 28px),
    #f5f0e8;
}
.skills-main {
  flex: 1; min-width: 0; min-height: 0;
  overflow-y: auto;
  padding: 28px 40px 48px;
  color: #2a2a2a;
  font-family: 'Architects Daughter', cursive;
}
.page-head { margin-bottom: 18px; }
.page-kicker {
  margin: 0 0 2px;
  font-size: 12px; letter-spacing: .14em; text-transform: uppercase;
  color: #c87020;
}
.page-title {
  margin: 0;
  font-family: 'Caveat', cursive; font-size: 34px; font-weight: 700;
  color: #1a1a1a;
}
.page-sub { margin: 6px 0 0; font-size: 14px; color: #6b7d8e; }

.toolbar {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.search {
  flex: 1; min-width: 180px; height: 40px;
  padding: 0 14px;
  border: 1.5px solid #aaa092; border-radius: 8px;
  background: rgba(255,253,248,.85);
  font-family: inherit; font-size: 14px; color: #2a2a2a;
}
.search:focus { outline: none; border-color: #c87020; }
.filters { display: flex; gap: 6px; }
.filter-btn {
  height: 36px; padding: 0 12px;
  border: 1.5px solid #aaa092; border-radius: 999px;
  background: rgba(255,253,248,.85); color: #6b5b44;
  font-family: inherit; font-size: 13px; cursor: pointer;
}
.filter-btn .count {
  margin-left: 4px; font-size: 12px; color: #c87020;
}
.filter-btn.active {
  background: rgba(212,160,23,.22); color: #c87020;
  border-color: rgba(200,112,32,.55);
}
.upload-btn {
  height: 40px; padding: 0 18px;
  border: 1.5px solid #2a2a2a; border-radius: 8px;
  background: #2a2a2a; color: #f5f0e8;
  font-family: inherit; font-size: 14px; cursor: pointer;
}
.upload-btn:hover:not(:disabled) { background: #c87020; border-color: #c87020; }
.upload-btn:disabled { opacity: .55; cursor: default; }

.error {
  padding: 10px 14px; margin: 0 0 12px;
  border: 1.5px solid rgba(184,48,48,.5); border-radius: 8px;
  background: rgba(184,48,48,.08); color: #b83030;
  font-size: 13px;
}
.empty { margin: 24px 0; color: #6b7d8e; font-size: 14px; }

.list {
  margin: 0; padding: 0;
  list-style: none;
  display: flex; flex-direction: column; gap: 8px;
}
.row {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px;
  border: 1.5px solid #aaa092; border-radius: 10px 12px 9px 11px;
  background: rgba(255,253,248,.85);
  cursor: pointer;
  transition: border-color .15s ease, background .15s ease;
}
.row:hover { border-color: #c87020; background: rgba(255,253,248,.98); }
.row-icon {
  width: 34px; height: 34px; flex-shrink: 0;
  display: grid; place-items: center;
  border-radius: 8px; background: rgba(212,160,23,.18); color: #c87020;
}
.row-icon svg { width: 20px; height: 20px; stroke: currentColor; fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.row-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.row-name {
  font-family: 'Caveat', cursive; font-size: 18px; font-weight: 700; color: #1a1a1a;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.row-summary {
  font-size: 13px; color: #6b7d8e;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.row-source {
  flex-shrink: 0; font-size: 12px; color: #6b5b44;
  padding: 2px 10px; border: 1px solid #aaa092; border-radius: 999px;
}
.row-status { flex-shrink: 0; font-size: 12px; color: #6b7d8e; }
.switch {
  flex-shrink: 0; width: 42px; height: 24px;
  border: 1.5px solid #aaa092; border-radius: 999px;
  background: rgba(120,105,85,.18);
  position: relative; cursor: pointer;
}
.switch .switch-knob {
  position: absolute; top: 2px; left: 2px;
  width: 16px; height: 16px; border-radius: 50%;
  background: #f5f0e8; border: 1px solid #aaa092;
  transition: left .16s ease;
}
.switch.on { background: rgba(200,112,32,.55); border-color: #c87020; }
.switch.on .switch-knob { left: 22px; }
.switch:disabled { opacity: .55; cursor: default; }

@media (max-width: 860px) {
  .skills-main { padding: 20px 16px 32px; }
}
</style>