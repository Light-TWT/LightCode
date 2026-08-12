<script setup lang="ts">
/** 技能详情模态层：纯文本渲染 SKILL.md，无内部侧栏/标签/识别信息页。
 *  参照 SettingsOverlay 的可访问性模式：Teleport + role=dialog + 焦点管理。
 *  组件不承载业务状态：状态切换/删除只向上 emit，由 SkillsView 连接 store。 */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { SkillDetail, SkillDocument, SkillStatus } from '@/types/agent'

const props = defineProps<{
  open: boolean
  detail: SkillDetail | null
  document: SkillDocument | null
  updating: boolean
  deleting: boolean
  /** 页脚内联删除确认（不使用浏览器原生 confirm） */
  confirmingDelete?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'setStatus', status: SkillStatus): void
  (e: 'requestDelete'): void
  (e: 'confirmDelete'): void
  (e: 'cancelDelete'): void
}>()

const panelEl = ref<HTMLElement | null>(null)
let triggerEl: HTMLElement | null = null

watch(
  () => props.open,
  async (open) => {
    if (open) {
      triggerEl = document.activeElement instanceof HTMLElement ? document.activeElement : null
      await nextTick()
      panelEl.value?.focus()
    } else if (
      document.activeElement === document.body ||
      (panelEl.value && panelEl.value.contains(document.activeElement))
    ) {
      triggerEl?.focus()
    }
  },
)

function onKeydown(e: KeyboardEvent) {
  if (!props.open || e.key !== 'Escape') return
  emit('close')
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open && detail && document"
      class="skill-overlay"
      data-testid="skill-detail-overlay"
      @click.self="emit('close')"
    >
      <section
        ref="panelEl"
        class="skill-modal"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`skill-detail-title-${detail.id}`"
        data-testid="skill-detail-modal"
        tabindex="-1"
      >
        <header class="modal-head">
          <div class="modal-title">
            <h2 :id="`skill-detail-title-${detail.id}`">{{ detail.name }}</h2>
            <p class="meta">
              <span class="source-tag" :data-testid="`skill-source-${detail.source}`">
                {{ detail.source === 'uploaded' ? '已上传' : '内置' }}
              </span>
            </p>
          </div>
          <button
            type="button"
            class="modal-close"
            data-testid="skill-detail-close"
            aria-label="关闭技能详情"
            @click="emit('close')"
          >×</button>
        </header>

        <div class="document-scroll">
          <pre class="document" data-testid="skill-document">{{ document.content }}</pre>
        </div>

        <footer class="modal-foot">
          <template v-if="confirmingDelete">
            <div class="confirm" data-testid="skill-delete-confirmation">
              <span class="confirm-text">确定删除「{{ detail.name }}」？删除后 Agent 将不再读取该技能。</span>
              <div class="actions">
                <button
                  type="button"
                  class="plain"
                  data-testid="skill-delete-cancel"
                  :disabled="deleting"
                  @click="emit('cancelDelete')"
                >取消</button>
                <button
                  type="button"
                  class="danger"
                  data-testid="skill-delete-confirm"
                  :disabled="deleting"
                  @click="emit('confirmDelete')"
                >删除</button>
              </div>
            </div>
          </template>
          <template v-else>
            <span class="hint" :data-testid="`skill-status-hint-${detail.status}`">
              {{ detail.status === 'enabled' ? '当前可被 Agent 使用' : '启用后可被 Agent 使用' }}
            </span>
            <div class="actions">
              <button
                v-if="detail.source === 'uploaded'"
                type="button"
                class="danger"
                data-testid="skill-delete-request"
                :disabled="deleting"
                @click="emit('requestDelete')"
              >删除</button>
              <button
                type="button"
                class="primary"
                :data-testid="detail.status === 'enabled' ? 'skill-disable' : 'skill-enable'"
                :disabled="updating || deleting"
                @click="emit('setStatus', detail.status === 'enabled' ? 'disabled' : 'enabled')"
              >{{ detail.status === 'enabled' ? '停用' : '启用' }}</button>
            </div>
          </template>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.skill-overlay {
  position: fixed; inset: 0; z-index: 70;
  display: grid; place-items: center;
  padding: 24px;
  background: rgba(74, 61, 45, .34);
  backdrop-filter: blur(2px);
}
.skill-modal {
  width: 78vw; height: 76vh;
  max-width: calc(100vw - 48px); max-height: calc(100vh - 48px);
  display: flex; flex-direction: column;
  overflow: hidden;
  border: 2px solid #2a2a2a;
  border-radius: 16px 20px 15px 18px;
  background:
    linear-gradient(rgba(255,253,248,.72), rgba(255,253,248,.72)),
    repeating-linear-gradient(0deg, transparent, transparent 27px, rgba(120,105,85,.06) 28px),
    #f5f0e8;
  box-shadow: 0 16px 44px rgba(68,52,32,.22), 7px 8px 0 rgba(42,42,42,.16);
  color: #2a2a2a;
  font-family: 'Architects Daughter', cursive;
  animation: rise .22s ease-out;
}
@keyframes rise {
  from { opacity: 0; transform: translateY(10px) scale(.985); }
  to { opacity: 1; transform: none; }
}
.modal-head {
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 16px 26px 12px;
  border-bottom: 1.5px dashed #aaa092;
}
.modal-title h2 {
  margin: 0;
  font-family: 'Caveat', cursive; font-size: 30px; font-weight: 700;
  color: #1a1a1a;
}
.meta { margin: 4px 0 0; display: flex; gap: 8px; align-items: center; }
.source-tag {
  font-size: 12px; padding: 2px 10px;
  border: 1.5px solid #aaa092; border-radius: 999px;
  color: #6b5b44; background: rgba(255,253,248,.8);
}
.modal-close {
  width: 34px; height: 34px; flex-shrink: 0;
  border: 1.5px solid #aaa092; border-radius: 50%;
  background: rgba(255,253,248,.8); color: #2a2a2a;
  font-size: 24px; line-height: 1; cursor: pointer;
}
.modal-close:hover { background: rgba(184,48,48,.12); color: #b83030; border-color: #b83030; }

/* 滚动只发生在文档正文：pre 区域 */
.document-scroll {
  flex: 1; min-height: 0;
  overflow: auto;
  padding: 18px 26px;
}
.document {
  margin: 0;
  font-family: 'Caveat', cursive;
  font-size: 15px; line-height: 1.65;
  white-space: pre-wrap; word-break: break-word;
  color: #2a2a2a;
}

.modal-foot {
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 12px 26px 16px;
  border-top: 1.5px dashed #aaa092;
}
.hint { font-size: 13px; color: #6b7d8e; }
.actions { display: flex; gap: 10px; }
.actions button {
  height: 38px; padding: 0 18px;
  border-radius: 8px; border: 1.5px solid #2a2a2a;
  font-family: inherit; font-size: 14px; cursor: pointer;
}
.confirm {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  width: 100%;
}
.confirm-text { font-size: 14px; color: #b83030; }
.actions .plain { background: rgba(255,253,248,.8); color: #2a2a2a; }
.actions .plain:disabled { opacity: .55; cursor: default; }
.actions .plain:hover:not(:disabled) { border-color: #2a2a2a; background: rgba(0,0,0,.05); }
.actions .primary { background: #2a2a2a; color: #f5f0e8; }
.actions .primary:disabled { opacity: .55; cursor: default; }
.actions .primary:hover:not(:disabled) { background: #c87020; border-color: #c87020; }
.actions .danger { background: rgba(184,48,48,.08); color: #b83030; border-color: #b83030; }
.actions .danger:disabled { opacity: .55; cursor: default; }
.actions .danger:hover:not(:disabled) { background: #b83030; color: #fff; }

@media (prefers-reduced-motion: reduce) {
  .skill-modal { animation: none; }
}
</style>