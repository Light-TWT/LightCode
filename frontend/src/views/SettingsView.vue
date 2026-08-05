<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { providerService } from '@/services/provider.service'
import type { ProviderHealth, ProviderSettingsResponse } from '@/types/agent'

const router = useRouter()

const settings = ref<ProviderSettingsResponse | null>(null)
const health = ref<ProviderHealth | null>(null)
const loadingError = ref(false)
const refreshing = ref(false)

/** 配置表单。API Key 仅在提交瞬间存在于内存，提交后清空，绝不写入
 *  localStorage/sessionStorage；后端也只保存在进程内存。 */
const form = reactive({
  provider: 'openai-compatible',
  baseUrl: '',
  apiKey: '',
  modelId: '',
})

const testing = ref(false)
const saving = ref(false)
const clearing = ref(false)

type FormMessage = { kind: 'ok' | 'err'; text: string } | null
const message = ref<FormMessage>(null)

const statusBadgeClass = computed(() => {
  switch (settings.value?.status) {
    case 'ready': return 'badge-ready'
    case 'degraded': return 'badge-degraded'
    case 'unconfigured': return 'badge-unconfigured'
    default: return 'badge-disabled'
  }
})

const statusLabel = computed(() => {
  switch (settings.value?.status) {
    case 'ready': return '就绪'
    case 'degraded': return '降级'
    case 'unconfigured': return '未配置'
    case 'disabled': return '未启用'
    default: return '未知'
  }
})

function formatBytes(bytes: number | undefined): string {
  if (!bytes) return '—'
  if (bytes >= 1024 * 1024) return `${bytes} 字节（${(bytes / 1024 / 1024).toFixed(1)} MB）`
  if (bytes >= 1024) return `${bytes} 字节（${Math.round(bytes / 1024)} KB）`
  return `${bytes} 字节`
}

/** 连接测试失败只渲染稳定错误码对应的固定文案，不渲染服务端自由 message（M-03） */
const TEST_ERROR_TEXTS: Record<string, string> = {
  PROVIDER_SETTINGS_INVALID: 'Provider 配置不完整或未满足安全要求。',
  PROVIDER_CONNECTION_FAILED: '无法连接模型 Provider，请检查 Base URL 与网络。',
}

async function loadSettings() {
  loadingError.value = false
  try {
    settings.value = await providerService.getSettings()
  } catch {
    loadingError.value = true
  }
}

async function loadHealth() {
  try {
    health.value = await providerService.getHealth()
  } catch {
    health.value = null
  }
}

async function refresh() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await Promise.all([loadSettings(), loadHealth()])
  } finally {
    refreshing.value = false
  }
}

async function testConnection() {
  testing.value = true
  message.value = null
  try {
    const resp = await providerService.testConnection({
      provider: form.provider,
      baseUrl: form.baseUrl,
      apiKey: form.apiKey,
      modelId: form.modelId,
    })
    if (resp.ok) {
      message.value = { kind: 'ok', text: '连接测试成功，可点击「测试并保存」保存配置。' }
    } else {
      message.value = {
        kind: 'err',
        text: `连接测试失败（${resp.code || 'UNKNOWN'}）：${TEST_ERROR_TEXTS[resp.code] ?? '请检查配置后重试。'}`,
      }
    }
  } catch (err) {
    message.value = { kind: 'err', text: err instanceof Error ? err.message : String(err) }
  } finally {
    testing.value = false
  }
}

/** 测试并保存：成功后刷新安全状态卡片；无论成败都清空 key 输入框。 */
async function saveSettings() {
  saving.value = true
  message.value = null
  try {
    const resp = await providerService.saveSettings({
      provider: form.provider,
      baseUrl: form.baseUrl,
      apiKey: form.apiKey,
      modelId: form.modelId,
    })
    settings.value = resp
    await loadHealth()
    message.value = { kind: 'ok', text: '配置已保存到后端进程内存并生效。' }
  } catch (err) {
    message.value = { kind: 'err', text: err instanceof Error ? err.message : String(err) }
  } finally {
    form.apiKey = ''
    saving.value = false
  }
}

async function clearSettings() {
  clearing.value = true
  message.value = null
  try {
    const resp = await providerService.clearSettings()
    settings.value = resp
    await loadHealth()
    message.value = { kind: 'ok', text: '已清除运行期配置，回退到环境变量配置。' }
  } catch (err) {
    message.value = { kind: 'err', text: err instanceof Error ? err.message : String(err) }
  } finally {
    form.apiKey = ''
    clearing.value = false
  }
}

onMounted(() => refresh())
</script>

<template>
  <div class="settings-page">
    <header class="top-bar">
      <button class="back-btn" type="button" data-testid="back-home-btn" @click="router.push('/')">← 返回</button>
      <div class="brand">LightCode · 设置</div>
      <button class="refresh-btn" type="button" :disabled="refreshing" data-testid="refresh-btn" @click="refresh">
        <span class="refresh-icon" :class="{ spinning: refreshing }">↻</span> 刷新状态
      </button>
    </header>

    <div class="content">
      <section class="card" aria-label="Provider 状态">
        <p class="card-kicker">Provider 状态（安全视图 · 无 key / 无完整 Base URL）</p>
        <div class="status-row">
          <span class="status-badge" :class="statusBadgeClass" data-testid="settings-status">{{ settings?.status ?? '加载中…' }}</span>
          <span v-if="settings?.configured" class="configured-tag" data-testid="configured-tag">已配置运行期凭据</span>
          <span v-else class="configured-tag off" data-testid="configured-tag">仅环境变量/未配置</span>
        </div>
        <div v-if="loadingError" class="error-line">无法获取 Provider 设置，请确认后端已启动。</div>
        <template v-else-if="settings">
          <div class="info-row"><span class="info-label">状态</span><span class="info-value">{{ statusLabel }}</span></div>
          <div class="info-row"><span class="info-label">Provider</span><span class="info-value">{{ settings.provider || '—' }}</span></div>
          <div class="info-row"><span class="info-label">模型 ID</span><span class="info-value" data-testid="settings-model">{{ settings.modelId || '—' }}</span></div>
          <div class="info-row"><span class="info-label">说明</span><span class="info-value">{{ settings.detail }}</span></div>
          <div class="info-row"><span class="info-label">来源域名放行</span><span class="info-value">{{ settings.originAllowlisted ? '是' : '否' }}</span></div>
          <div class="info-row"><span class="info-label">传输</span><span class="info-value">{{ settings.transport }}</span></div>
        </template>
        <p class="card-note">数据来源：后端 GET /api/v1/provider/settings。响应不含 API Key、不含完整 Base URL。</p>
      </section>

      <section class="card" aria-label="Provider 配置表单">
        <p class="card-kicker">Provider 配置（OpenAI 兼容）</p>
        <form class="config-form" data-testid="provider-form" @submit.prevent="saveSettings">
          <label class="field">
            <span class="field-label">Provider</span>
            <select v-model="form.provider" class="text-input" data-testid="input-provider">
              <option value="openai-compatible">openai-compatible</option>
            </select>
          </label>
          <label class="field">
            <span class="field-label">Base URL</span>
            <input v-model="form.baseUrl" class="text-input" type="text" placeholder="https://api.example.com/v1" data-testid="input-base-url">
          </label>
          <label class="field">
            <span class="field-label">API Key</span>
            <input v-model="form.apiKey" class="text-input" type="password" autocomplete="off" placeholder="仅本次提交，不保存到浏览器" data-testid="input-api-key">
          </label>
          <label class="field">
            <span class="field-label">Model ID</span>
            <input v-model="form.modelId" class="text-input" type="text" placeholder="如 gpt-4o-mini" data-testid="input-model-id">
          </label>
          <div class="form-actions">
            <button type="button" class="btn-test" data-testid="btn-test" :disabled="testing" @click="testConnection">
              {{ testing ? '测试中…' : '测试连接' }}
            </button>
            <button type="submit" class="btn-save" data-testid="btn-save" :disabled="saving">
              {{ saving ? '保存中…' : '测试并保存' }}
            </button>
            <button type="button" class="btn-clear" data-testid="btn-clear" :disabled="clearing" @click="clearSettings">
              {{ clearing ? '清除中…' : '清除运行期配置' }}
            </button>
          </div>
        </form>
        <div v-if="message" class="form-message" :class="message.kind" data-testid="form-message">{{ message.text }}</div>
        <p class="card-note">
          安全说明：Web 开发期凭据仅保存在后端进程内存，重启后需重新配置；Electron 阶段将迁移为系统密钥库。
          API Key 不会进入 SQLite、事件、日志或前端存储（localStorage/sessionStorage）。
        </p>
      </section>

      <section v-if="health" class="card" aria-label="Provider 健康详情">
        <p class="card-kicker">能力与安全（GET /provider/health · 只读）</p>
        <div class="info-row"><span class="info-label">工具</span><span class="info-value">{{ health.capabilities.tools.join(', ') }}</span></div>
        <div class="info-row"><span class="info-label">可写文件</span><span class="info-value">{{ health.capabilities.canWriteFiles ? '是' : '否' }}</span></div>
        <div class="info-row"><span class="info-label">可执行命令</span><span class="info-value">{{ health.capabilities.canRunCommands ? '是' : '否' }}</span></div>
        <div class="info-row"><span class="info-label">最大工具轮次</span><span class="info-value">{{ health.capabilities.maxToolRounds }}</span></div>
        <div class="info-row"><span class="info-label">单任务最大请求</span><span class="info-value">{{ health.capabilities.maxRequestsPerTask }}</span></div>
        <div class="info-row"><span class="info-label">最大输入</span><span class="info-value">{{ formatBytes(health.capabilities.maxInputBytes) }}</span></div>
        <div class="info-row"><span class="info-label">最大输出</span><span class="info-value">{{ health.capabilities.maxOutputTokens }} tokens</span></div>
        <div class="info-row"><span class="info-label">最大并发任务</span><span class="info-value">{{ health.capabilities.maxConcurrentTasks }}</span></div>
        <div class="info-row"><span class="info-label">API Key 已配置</span><span class="info-value">{{ health.security.apiKeyConfigured ? '是' : '否' }}</span></div>
        <div class="info-row"><span class="info-label">传输</span><span class="info-value">{{ health.security.transport }}</span></div>
        <div class="info-row"><span class="info-label">来源域名放行</span><span class="info-value">{{ health.security.originAllowlisted ? '是' : '否' }}</span></div>
        <div class="info-row"><span class="info-label">跟随重定向</span><span class="info-value">{{ health.security.followRedirects ? '是' : '否' }}</span></div>
        <div class="info-row"><span class="info-label">信任环境变量代理</span><span class="info-value">{{ health.security.trustEnvProxies ? '是' : '否' }}</span></div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  min-height: 100vh; max-height: 100vh; overflow: hidden;
  display: flex; flex-direction: column;
  padding: 18px 48px;
  background: #f5f0e8; color: #2a2a2a;
  font-family: 'Architects Daughter', cursive;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
.top-bar {
  display: flex; align-items: center; gap: 16px;
  padding-bottom: 12px; border-bottom: 2px solid #2a2a2a;
  margin-bottom: 16px; flex-shrink: 0;
}
.back-btn { background: none; border: none; cursor: pointer; font-family: inherit; font-size: 13px; color: #6b7d8e; padding: 0; }
.back-btn:hover { color: #2a2a2a; }
.brand { font-family: 'Caveat', cursive; font-size: 24px; font-weight: 700; }
.refresh-btn {
  margin-left: auto;
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  color: #4a5a68; background: rgba(255,255,255,.4);
  border: 1px solid #c5b9a8; border-radius: 4px; padding: 4px 12px;
  cursor: pointer; display: inline-flex; align-items: center; gap: 5px;
}
.refresh-btn:disabled { opacity: .55; cursor: default; }
.refresh-icon { display: inline-block; font-size: 13px; line-height: 1; }
.refresh-icon.spinning { animation: spin .7s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.content { flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; padding-right: 6px; max-width: 760px; }
.card {
  border: 1.5px solid #d8d0c4; border-radius: 6px;
  background: rgba(255,255,255,.25); padding: 14px 18px;
}
.card-kicker {
  font-family: 'JetBrains Mono', monospace; font-size: 9px;
  text-transform: uppercase; letter-spacing: 1.5px; color: #aaa; margin-bottom: 10px;
}
.status-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.status-badge {
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  padding: 3px 12px; border-radius: 12px; text-transform: uppercase; letter-spacing: 1px;
}
.badge-disabled { color: #6b7d8e; background: rgba(107,125,144,.1); border: 1px solid rgba(107,125,144,.25); }
.badge-unconfigured { color: #c87020; background: rgba(212,160,23,.1); border: 1px solid rgba(200,112,32,.3); }
.badge-ready { color: #2d7a3a; background: rgba(45,122,58,.1); border: 1px solid rgba(45,122,58,.3); }
.badge-degraded { color: #b83030; background: rgba(184,48,48,.08); border: 1px solid rgba(184,48,48,.3); }
.configured-tag {
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  color: #2d7a3a; border: 1px solid rgba(45,122,58,.3); border-radius: 3px; padding: 2px 8px;
}
.configured-tag.off { color: #888; border-color: #d8d0c4; }
.error-line { color: #b83030; font-size: 13px; margin-bottom: 8px; }
.info-row { display: flex; gap: 12px; padding: 7px 0; border-bottom: 1px dashed #e0d8cc; }
.info-row:last-child { border-bottom: none; }
.info-label { font-family: 'Architects Daughter', cursive; font-size: 13px; color: #666; min-width: 120px; flex-shrink: 0; }
.info-value { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #2a2a2a; word-break: break-all; }
.card-note {
  font-family: 'Patrick Hand', cursive; font-size: 13px;
  color: #6b7d8e; margin-top: 12px; line-height: 1.7;
}
.config-form { display: flex; flex-direction: column; gap: 10px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field-label { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: 1px; }
.text-input {
  font-family: inherit; font-size: 13px;
  border: 1.5px solid #d8d0c4; border-radius: 4px; padding: 7px 10px;
  background: rgba(255,255,255,.6); color: #2a2a2a;
}
.text-input:focus { outline: none; border-color: #6b7d8e; }
.form-actions { display: flex; gap: 10px; margin-top: 6px; flex-wrap: wrap; }
.btn-test, .btn-save, .btn-clear { font-family: inherit; font-size: 13px; cursor: pointer; border-radius: 4px; padding: 7px 16px; }
.btn-test { border: 1.5px solid #2d5a7a; color: #2d5a7a; background: rgba(45,90,122,.08); }
.btn-save { border: 2px solid #2a2a2a; color: #2a2a2a; background: rgba(212,160,23,.15); font-weight: 600; }
.btn-clear { border: 1.5px dashed #b83030; color: #b83030; background: none; }
.btn-test:disabled, .btn-save:disabled, .btn-clear:disabled { opacity: .5; cursor: not-allowed; }
.form-message { margin-top: 10px; padding: 8px 12px; border-radius: 4px; font-size: 13px; }
.form-message.ok { color: #2d7a3a; border: 1px solid rgba(45,122,58,.3); background: rgba(45,122,58,.05); }
.form-message.err { color: #b83030; border: 1px solid rgba(184,48,48,.25); background: rgba(184,48,48,.04); }
</style>
