<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import SettingsNav from '@/components/SettingsNav.vue'
import ProviderList from '@/components/ProviderList.vue'
import ProviderDetail from '@/components/ProviderDetail.vue'
import AddProviderModal from '@/components/AddProviderModal.vue'
import { providerService } from '@/services/provider.service'
import type { ProviderSummary } from '@/types/agent'

const router = useRouter()

/** 设置分类：当前仅「模型与供应商」与「关于」 */
const category = ref<'providers' | 'about'>('providers')

/** 供应商安全摘要列表（只读，后端 config 派生） */
const profiles = ref<ProviderSummary[]>([])
const loadingError = ref(false)
const refreshing = ref(false)

/** 当前选中供应商；默认选中列表第一条 */
const selectedId = ref<string | null>(null)
const selectedProvider = computed(
  () => profiles.value.find((p) => p.id === selectedId.value) ?? null,
)

/** 添加供应商弹层 */
const modalOpen = ref(false)

const clearing = ref(false)
const formMessage = ref<{ kind: 'ok' | 'err'; text: string } | null>(null)

async function loadProfiles() {
  loadingError.value = false
  try {
    const list = await providerService.listProviders()
    profiles.value = list
    if (selectedId.value === null || !list.some((p) => p.id === selectedId.value)) {
      selectedId.value = list.length > 0 ? list[0].id : null
    }
  } catch {
    loadingError.value = true
  }
}

async function refresh() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await loadProfiles()
  } finally {
    refreshing.value = false
  }
}

async function clearSettings() {
  if (clearing.value) return
  clearing.value = true
  formMessage.value = null
  try {
    const resp = await providerService.clearSettings()
    formMessage.value = {
      kind: resp.configured ? 'err' : 'ok',
      text: resp.configured ? '清除失败，运行期配置仍然生效。' : '已清除运行期配置，回退到环境变量配置。',
    }
    await loadProfiles()
  } catch (err) {
    formMessage.value = { kind: 'err', text: err instanceof Error ? err.message : String(err) }
  } finally {
    clearing.value = false
  }
}

async function onSaved() {
  modalOpen.value = false
  formMessage.value = { kind: 'ok', text: '供应商已添加并通过连接测试。' }
  await loadProfiles()
}

onMounted(() => refresh())
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

      <SettingsNav v-model:category="category" />

      <template v-if="category === 'providers'">
        <ProviderList
          :providers="profiles"
          :selected-id="selectedId"
          @select="selectedId = $event"
          @open-add="modalOpen = true"
        />

        <div class="detail-column">
          <header class="top-bar">
            <button class="back-btn" type="button" data-testid="back-home-btn" @click="router.push('/')">← 返回</button>
            <div class="page-title">LightCode · 设置</div>
            <button class="refresh-btn" type="button" :disabled="refreshing" data-testid="refresh-btn" @click="refresh">
              <span class="refresh-icon" :class="{ spinning: refreshing }">↻</span> 刷新状态
            </button>
          </header>
          <div v-if="loadingError" class="error-banner" data-testid="settings-error">
            无法获取供应商列表，请确认后端已启动。
          </div>
          <div v-if="formMessage" class="form-message" :class="formMessage.kind" data-testid="form-message">
            {{ formMessage.text }}
          </div>
          <ProviderDetail :provider="selectedProvider" @clear="clearSettings" />
        </div>
      </template>

      <section v-else class="about-panel" data-testid="about-panel">
        <p class="eyebrow">LightCode</p>
        <h2>关于</h2>
        <p class="about-note">关于内容后续补充。</p>
      </section>
    </div>

    <AddProviderModal
      v-if="modalOpen"
      @close="modalOpen = false"
      @saved="onSaved"
    />
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
.detail-column {
  flex: 1; min-width: 0; min-height: 0;
  display: flex; flex-direction: column;
  padding: 20px 28px;
  overflow-y: auto;
}
.top-bar {
  display: flex; align-items: center; gap: 16px;
  padding-bottom: 12px; border-bottom: 2px solid #2a2a2a;
  margin-bottom: 14px; flex-shrink: 0;
}
.back-btn { background: none; border: none; cursor: pointer; font-family: inherit; font-size: 13px; color: #6b7d8e; padding: 0; }
.back-btn:hover { color: #2a2a2a; }
.page-title { font-family: 'Caveat', cursive; font-size: 22px; font-weight: 700; color: #1a1a1a; }
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
.error-banner {
  border: 1.5px solid rgba(184,48,48,.35); background: rgba(184,48,48,.05);
  color: #b83030; border-radius: 5px; padding: 8px 14px; margin-bottom: 10px; font-size: 13px;
}
.form-message { margin-bottom: 10px; padding: 8px 12px; border-radius: 4px; font-size: 13px; }
.form-message.ok { color: #2d7a3a; border: 1px solid rgba(45,122,58,.3); background: rgba(45,122,58,.05); }
.form-message.err { color: #b83030; border: 1px solid rgba(184,48,48,.25); background: rgba(184,48,48,.04); }

/* 「关于」分类占位 */
.about-panel { flex: 1; padding: 40px 48px; overflow-y: auto; }
.eyebrow {
  color: #3a6090;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px; font-weight: 600;
  letter-spacing: .12em; text-transform: uppercase;
}
.about-panel h2 { margin-top: 4px; font-family: 'Caveat', cursive; font-size: 40px; color: #1a1a1a; }
.about-note { margin-top: 18px; color: #6e665c; font-family: 'Patrick Hand', cursive; font-size: 18px; }

@media (max-width: 900px) {
  .columns { flex-direction: column; overflow-y: auto; }
  .settings-page { max-height: none; overflow: auto; }
}
</style>
