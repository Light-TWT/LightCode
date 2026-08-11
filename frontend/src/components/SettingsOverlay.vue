<script setup lang="ts">
/** 工作区设置层：模态层容器 + 可访问性交互，不承载 Provider 业务状态。
 *  通过 Teleport 挂载到 body，避免工作区布局/overflow/stacking context 裁剪。
 *  关闭（关闭按钮 / Esc / 遮罩点击）后把焦点还给触发按钮，工作区组件树不卸载。 */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import SettingsContent from './SettingsContent.vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const panelEl = ref<HTMLElement | null>(null)
/** 打开时记录触发元素（设置按钮），关闭后恢复焦点 */
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
      // 关闭后焦点还给触发设置按钮，供键盘用户继续工作
      triggerEl?.focus()
    }
  },
)

function onKeydown(e: KeyboardEvent) {
  if (!props.open || e.key !== 'Escape') return
  // 「添加供应商」弹层打开时，Esc 只关闭该弹层（由 AddProviderModal 处理），不关闭设置层
  if (document.querySelector('.modal-backdrop')) return
  emit('close')
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="overlay" data-testid="settings-overlay" @click.self="emit('close')">
      <section
        ref="panelEl"
        class="settings-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-overlay-title"
        data-testid="settings-modal"
        tabindex="-1"
      >
        <header class="modal-head">
          <h2 id="settings-overlay-title">设置</h2>
          <button
            type="button"
            class="modal-close"
            data-testid="settings-overlay-close"
            aria-label="关闭设置"
            @click="emit('close')"
          >×</button>
        </header>
        <SettingsContent />
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed; inset: 0; z-index: 60;
  display: grid; place-items: center;
  padding: 24px;
  background: rgba(74, 61, 45, .34);
  backdrop-filter: blur(2px);
}
.settings-modal {
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
.modal-head h2 {
  margin: 0;
  font-family: 'Caveat', cursive; font-size: 30px; font-weight: 700;
  color: #1a1a1a;
}
.modal-close {
  width: 34px; height: 34px; flex-shrink: 0;
  border: 1.5px solid #aaa092; border-radius: 50%;
  background: rgba(255,253,248,.8); color: #2a2a2a;
  font-size: 24px; line-height: 1; cursor: pointer;
}
.modal-close:hover { background: rgba(184,48,48,.12); color: #b83030; border-color: #b83030; }

@media (prefers-reduced-motion: reduce) {
  .settings-modal { animation: none; }
}
</style>
