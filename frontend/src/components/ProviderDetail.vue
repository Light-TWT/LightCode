<script setup lang="ts">
import type { ProviderSummary } from '@/types/agent'

defineProps<{ provider: ProviderSummary | null }>()
defineEmits<{ (e: 'clear'): void }>()

function initials(name: string): string {
  return name.replace(/[^a-zA-Z0-9]/g, '').slice(0, 2).toUpperCase() || 'AI'
}

/** 状态徽章文案：ready → 已启用，其余 → 等待测试 */
function badgeText(provider: ProviderSummary): string {
  return provider.enabled ? '已启用' : '等待测试'
}
</script>

<template>
  <section class="detail-panel" aria-label="供应商配置详情">
    <div v-if="!provider" class="empty-detail" data-testid="detail-empty">
      <div class="empty-detail-card">
        <div class="empty-symbol" aria-hidden="true">✦</div>
        <h2>选择一个供应商</h2>
        <p>在左侧查看配置状态，或添加新的模型供应商。密钥不会在这里显示。</p>
      </div>
    </div>

    <template v-else>
      <div class="detail-header">
        <div class="detail-title">
          <div class="provider-icon" aria-hidden="true">{{ initials(provider.name) }}</div>
          <div>
            <h2 data-testid="detail-name">{{ provider.name }}</h2>
            <p data-testid="detail-model">{{ provider.modelId }}</p>
          </div>
        </div>
        <span
          class="badge"
          :class="{ pending: !provider.enabled }"
          data-testid="detail-badge"
        >{{ badgeText(provider) }}</span>
      </div>

      <div class="detail-grid">
        <div class="safe-card">
          <strong>运行期配置</strong>
          <span>仅后端持有凭据 · 本次会话可用</span>
        </div>
        <div class="safe-card">
          <strong>模型权限</strong>
          <span>只读检索 · 模型只能提出变更 · 写入必须经过显式审批</span>
        </div>
        <div class="safe-card">
          <strong>安全视图</strong>
          <span>不展示 API Key、完整 Base URL 或上游原始响应</span>
        </div>
      </div>

      <div class="detail-actions">
        <button type="button" class="clear-btn" data-testid="btn-clear" @click="$emit('clear')">
          清除运行期配置
        </button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.detail-panel {
  flex: 1; min-width: 0; min-height: 0;
  padding: 32px 42px;
  overflow-y: auto;
}
.empty-detail { min-height: 100%; display: grid; place-items: center; text-align: center; color: #6e665c; }
.empty-detail-card { max-width: 330px; }
.empty-symbol {
  width: 62px; height: 62px; display: grid; place-items: center;
  margin: 0 auto 18px;
  border: 1.5px dashed #aaa092; border-radius: 50% 46% 52% 44%;
  color: #d4a017; font-size: 28px; transform: rotate(-8deg);
}
.empty-detail h2 { margin: 0; color: #2a2a2a; font-family: 'Caveat', cursive; font-size: 32px; }
.empty-detail p { margin: 12px 0 0; font-family: 'Patrick Hand', cursive; font-size: 18px; line-height: 1.45; }
.detail-header {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;
  padding-bottom: 24px; border-bottom: 1px dashed #aaa092;
}
.detail-title { display: flex; align-items: center; gap: 13px; }
.detail-title h2 { margin: 0; font-family: 'Caveat', cursive; font-size: 35px; color: #1a1a1a; }
.detail-title p { margin: 2px 0 0; color: #6e665c; font-family: 'JetBrains Mono', monospace; font-size: 11px; }
.provider-icon {
  width: 40px; height: 40px; display: grid; place-items: center;
  border: 1.5px solid #aaa092; border-radius: 10px 8px 10px 7px;
  background: #fffdf8; color: #2a2a2a;
  font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 600;
}
.badge {
  padding: 5px 9px; color: #2d7a3a;
  border: 1px solid #a9cbaa; border-radius: 99px;
  background: rgba(45,122,58,.08);
  font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 600;
}
.badge.pending { color: #2a2a2a; border-color: #e2cf91; background: rgba(212,160,23,.12); }
.detail-grid { display: grid; gap: 13px; max-width: 660px; margin-top: 26px; }
.safe-card {
  padding: 15px 17px;
  border: 1.5px solid #d8d0c4; border-radius: 7px 10px 8px 11px;
  background: rgba(255,253,248,.6);
}
.safe-card strong { display: block; font-size: 15px; }
.safe-card span { display: block; margin-top: 5px; color: #6e665c; font-family: 'JetBrains Mono', monospace; font-size: 11px; line-height: 1.5; }
.detail-actions { margin-top: 26px; }
.clear-btn {
  border: 1.5px dashed #b83030; color: #b83030; background: none;
  border-radius: 4px; padding: 7px 16px;
  font-family: inherit; font-size: 13px; cursor: pointer;
}
.clear-btn:hover { background: rgba(184,48,48,.05); }
</style>
