<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { providerService } from '@/services/provider.service'

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

/** 连接测试失败只渲染稳定错误码对应的固定文案（M-03），不渲染服务端自由 message */
const TEST_ERROR_TEXTS: Record<string, string> = {
  PROVIDER_SETTINGS_INVALID: 'Provider 配置不完整或未满足安全要求。',
  PROVIDER_CONNECTION_FAILED: '无法连接模型 Provider，请检查 Base URL 与网络。',
}

/** 供应商协议模板 → 默认展示名（选中后自动填入配置名称） */
const PROVIDER_TEMPLATES = [
  'OpenAI',
  'OpenAI Compatible',
  'DeepSeek',
  'Qwen',
  'Kimi',
  'OpenRouter',
  'SiliconFlow',
  'Ollama',
]

const form = reactive({
  provider: 'openai-compatible',
  name: 'OpenAI',
  baseUrl: '',
  apiKey: '',
  modelId: '',
  enabled: true,
})

const testing = ref(false)
const saving = ref(false)
type FormMessage = { kind: 'ok' | 'err'; text: string } | null
const message = ref<FormMessage>(null)

const canSubmit = ref(false)

function selectTemplate(template: string) {
  form.name = template
  // 协议类型保持 openai-compatible（当前后端仅支持该协议）
}

function onInput() {
  canSubmit.value = Boolean(form.baseUrl.trim() && form.modelId.trim() && form.apiKey.trim())
  if (message.value) message.value = null
}

async function testConnection() {
  if (testing.value || saving.value) return
  testing.value = true
  message.value = null
  try {
    const resp = await providerService.testConnection({
      provider: form.provider,
      baseUrl: form.baseUrl,
      apiKey: form.apiKey,
      modelId: form.modelId,
    })
    message.value = resp.ok
      ? { kind: 'ok', text: '连接测试成功，可点击「测试并添加」。' }
      : {
          kind: 'err',
          text: `连接测试失败（${resp.code || 'UNKNOWN'}）：${TEST_ERROR_TEXTS[resp.code] ?? '请检查配置后重试。'}`,
        }
  } catch (err) {
    message.value = { kind: 'err', text: err instanceof Error ? err.message : String(err) }
  } finally {
    testing.value = false
  }
}

async function submit() {
  if (saving.value || !canSubmit.value) return
  saving.value = true
  message.value = null
  try {
    await providerService.saveSettings({
      provider: form.provider,
      baseUrl: form.baseUrl,
      apiKey: form.apiKey,
      modelId: form.modelId,
    })
    emit('saved')
  } catch (err) {
    message.value = { kind: 'err', text: err instanceof Error ? err.message : String(err) }
  } finally {
    form.apiKey = ''
    saving.value = false
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modal-title" @click.self="$emit('close')">
    <section class="modal">
      <div class="modal-top">
        <div>
          <h2 id="modal-title">添加供应商</h2>
          <p class="modal-intro">先选择协议模板，再填写这份独立配置。</p>
        </div>
        <button type="button" class="close" aria-label="关闭" data-testid="modal-close" @click="$emit('close')">×</button>
      </div>

      <p class="form-title">选择供应商</p>
      <div class="provider-options" data-testid="provider-templates">
        <button
          v-for="template in PROVIDER_TEMPLATES"
          :key="template"
          type="button"
          class="provider-option"
          :class="{ active: form.name === template }"
          :data-testid="`template-${template.replace(/\s+/g, '-')}`"
          @click="selectTemplate(template)"
        >
          {{ form.name === template ? '✓ ' : '' }}{{ template }}
        </button>
      </div>

      <div class="fields">
        <label>
          配置名称
          <input v-model="form.name" type="text" autocomplete="off" data-testid="modal-name" @input="onInput">
        </label>
        <label>
          模型 ID
          <input v-model="form.modelId" type="text" placeholder="如 gpt-4o-mini" autocomplete="off" data-testid="modal-model-id" @input="onInput">
        </label>
        <label class="field full">
          API Key
          <span class="hint">仅提交给本机后端，不写入浏览器持久化状态</span>
          <input v-model="form.apiKey" type="password" placeholder="粘贴 API Key" autocomplete="new-password" data-testid="modal-api-key" @input="onInput">
        </label>
        <label class="field full">
          Base URL
          <input v-model="form.baseUrl" type="text" placeholder="https://api.example.com/v1" autocomplete="off" data-testid="modal-base-url" @input="onInput">
        </label>
        <div class="toggle-row">
          <div>
            <strong>启用此供应商</strong>
            <p>通过连接测试后，才可以作为模型任务的候选配置。</p>
          </div>
          <button
            type="button"
            class="switch"
            :class="{ on: form.enabled }"
            role="switch"
            :aria-checked="form.enabled"
            aria-label="启用供应商"
            data-testid="modal-enabled"
            @click="form.enabled = !form.enabled"
          />
        </div>
      </div>

      <div v-if="message" class="form-message" :class="message.kind" data-testid="modal-message">
        {{ message.text }}
      </div>

      <div class="modal-actions">
        <button type="button" class="button test-button" data-testid="modal-test" :disabled="testing || saving" @click="testConnection">
          {{ testing ? '正在测试…' : '测试连接' }}
        </button>
        <button type="button" class="button save-button" data-testid="modal-save" :disabled="saving || !canSubmit" @click="submit">
          {{ saving ? '保存中…' : '＋ 测试并添加' }}
        </button>
      </div>
      <p class="security-note">
        安全边界：密钥不会写入 SQLite、聊天记录、日志或 SSE 事件；正式实现还需要将每个供应商配置绑定到独立的安全凭据引用。
      </p>
    </section>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed; inset: 0; z-index: 10;
  display: flex; align-items: center; justify-content: center;
  padding: 32px;
  background: rgba(74,61,45,.34);
  backdrop-filter: blur(2px);
}
.modal {
  width: min(920px, 94vw);
  max-height: calc(100vh - 64px); overflow: auto;
  padding: 28px 34px 30px;
  border: 2px solid #2a2a2a;
  border-radius: 16px 20px 15px 18px;
  background:
    linear-gradient(rgba(255,253,248,.9), rgba(255,253,248,.9)),
    repeating-linear-gradient(0deg, transparent, transparent 27px, rgba(120,105,85,.075) 28px);
  box-shadow: 0 16px 44px rgba(68,52,32,.16), 7px 8px 0 rgba(42,42,42,.16);
  color: #2a2a2a;
}
.modal-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
.modal h2 { margin: 0; font-family: 'Caveat', cursive; font-size: 38px; color: #1a1a1a; }
.modal-intro { margin: 4px 0 0; color: #6e665c; font-family: 'Patrick Hand', cursive; font-size: 17px; }
.close {
  width: 34px; height: 34px; border: 0; border-radius: 50%;
  color: #2a2a2a; background: transparent; font-size: 29px; line-height: 1; cursor: pointer;
}
.close:hover { background: rgba(184,48,48,.12); color: #b83030; }
.form-title {
  margin: 23px 0 10px; color: #6e665c;
  font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 600;
  letter-spacing: .1em; text-transform: uppercase;
}
.provider-options { display: grid; grid-template-columns: repeat(4, 1fr); gap: 9px; }
.provider-option {
  padding: 11px 9px;
  border: 1.5px solid #aaa092; border-radius: 8px 10px 9px 7px;
  color: #2a2a2a; background: rgba(255,253,248,.6);
  font-family: 'JetBrains Mono', monospace; font-size: 12px; cursor: pointer;
}
.provider-option:hover { border-color: #2a2a2a; }
.provider-option.active { border: 2px solid #2a2a2a; background: #f3e1a5; box-shadow: 2px 2px 0 rgba(42,42,42,.14); }
.fields { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 23px; }
.field.full { grid-column: 1 / -1; }
label { display: grid; gap: 6px; color: #2a2a2a; font-size: 14px; }
.hint { color: #6e665c; font-family: 'JetBrains Mono', monospace; font-size: 10px; }
input {
  width: 100%; padding: 11px 12px;
  border: 1.5px solid #aaa092; border-radius: 6px 9px 7px 8px;
  outline: none; color: #2a2a2a; background: rgba(255,253,248,.84);
  font-family: 'JetBrains Mono', monospace; font-size: 13px;
}
input:focus { border-color: #3a6090; box-shadow: 0 0 0 3px rgba(58,96,144,.1); }
.toggle-row {
  display: flex; justify-content: space-between; align-items: center; gap: 15px;
  grid-column: 1 / -1;
  padding: 13px 15px; border: 1.5px dashed #aaa092; border-radius: 8px;
}
.toggle-row p { margin: 2px 0 0; color: #6e665c; font-family: 'Patrick Hand', cursive; font-size: 14px; }
.switch {
  position: relative; width: 48px; height: 26px; flex-shrink: 0;
  border: 1.5px solid #2a2a2a; border-radius: 999px; cursor: pointer;
  background: #f3e1a5;
}
.switch::after {
  content: ''; position: absolute; top: 3px; right: 3px;
  width: 17px; height: 17px;
  border: 1px solid #2a2a2a; border-radius: 50%; background: #fffdf8;
}
.form-message { margin-top: 14px; padding: 8px 12px; border-radius: 4px; font-size: 13px; }
.form-message.ok { color: #2d7a3a; border: 1px solid rgba(45,122,58,.3); background: rgba(45,122,58,.05); }
.form-message.err { color: #b83030; border: 1px solid rgba(184,48,48,.25); background: rgba(184,48,48,.04); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 26px; }
.button { padding: 11px 15px; border-radius: 7px 10px 8px 9px; font-family: inherit; font-weight: 700; font-size: 14px; cursor: pointer; }
.button:disabled { opacity: .5; cursor: not-allowed; }
.test-button { border: 1.5px solid #3a6090; color: #3a6090; background: rgba(58,96,144,.08); }
.save-button { border: 2px solid #2a2a2a; color: #2a2a2a; background: #f3e1a5; box-shadow: 2px 2px 0 rgba(42,42,42,.16); }
.security-note { margin: 18px 0 0; color: #6e665c; font-family: 'Patrick Hand', cursive; font-size: 15px; line-height: 1.4; }
</style>
