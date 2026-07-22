<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

type SettingsCategory = 'general' | 'model' | 'permissions' | 'commands' | 'data'

const router = useRouter()
const activeCategory = ref<SettingsCategory>('general')

const categories: { key: SettingsCategory; label: string }[] = [
  { key: 'general', label: '通用' },
  { key: 'model', label: '模型' },
  { key: 'permissions', label: '工作区权限' },
  { key: 'commands', label: '命令策略' },
  { key: 'data', label: '本地数据' },
]

function goBack() {
  router.push('/')
}

function switchCategory(key: SettingsCategory) {
  activeCategory.value = key
}
</script>

<template>
  <div class="settings-shell">
    <nav class="sidebar">
      <a class="sidebar-back" href="#" @click.prevent="goBack">
        <span class="arrow">&#8592;</span> 返回工作区
      </a>
      <div class="sidebar-title">设置</div>
      <div class="nav-list">
        <div
          v-for="cat in categories"
          :key="cat.key"
          class="nav-item"
          :class="{ active: activeCategory === cat.key }"
          data-testid="settings-nav-item"
          @click="switchCategory(cat.key)"
        >{{ cat.label }}</div>
      </div>
      <div class="sidebar-version">LightCode v0.1.0</div>
    </nav>

    <div class="detail">
      <div class="detail-scroll">
        <!-- 通用 -->
        <div class="page" :class="{ active: activeCategory === 'general' }">
          <div class="detail-header">
            <div class="detail-title">通用</div>
          </div>
          <div class="content-card">
            <div class="info-row">
              <span class="info-label">本地运行状态</span>
              <span class="runtime-inline">Local runtime ready</span>
            </div>
            <div class="info-row">
              <span class="info-label">当前工作区</span>
              <span class="info-value">~/workspace/login-service</span>
            </div>
            <div class="info-row">
              <span class="info-label">开发阶段</span>
              <span class="info-value" style="color:#888;">前端 Mock 原型</span>
            </div>
            <div class="info-note">
              当前为前端 Mock 原型，后续将接入本地 FastAPI Runtime 作为真实执行引擎。所有配置和数据仅保存在本机。
            </div>
          </div>
        </div>

        <!-- 模型 -->
        <div class="page" :class="{ active: activeCategory === 'model' }">
          <div class="detail-header">
            <div class="detail-title">模型</div>
          </div>

          <div class="mode-block active-mode" data-testid="mode-mock">
            <div class="mode-label-row">
              <div class="mode-dot"></div>
              <span class="mode-name">Mock Mode</span>
              <span class="mode-badge badge-active">当前启用</span>
            </div>
            <div class="mode-desc">不调用外部模型，所有响应由内置 Mock 引擎生成，用于本地流程演示。</div>
          </div>

          <div class="mode-block disabled-mode" data-testid="mode-api">
            <div class="mode-label-row">
              <div class="mode-dot"></div>
              <span class="mode-name">OpenAI Compatible API</span>
              <span class="mode-badge badge-coming">第二阶段可用</span>
            </div>
            <div class="mode-desc">接入 OpenAI 兼容的 API 端点，使用真实模型生成代码。</div>

            <div class="api-fields">
              <div class="api-fields-label">配置项（当前不可编辑）</div>
              <div class="field-row">
                <span class="field-key">Base URL</span>
                <span class="field-val">&mdash;</span>
              </div>
              <div class="field-row">
                <span class="field-key">Model</span>
                <span class="field-val">&mdash;</span>
              </div>
              <div class="field-row">
                <span class="field-key">API Key</span>
                <span class="field-val masked">未配置</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 工作区权限 -->
        <div class="page" :class="{ active: activeCategory === 'permissions' }">
          <div class="detail-header">
            <div class="detail-title">工作区权限</div>
          </div>

          <div class="perm-root-bar" data-testid="perm-root">
            <span class="icon">&#x1F4C2;</span>
            <span class="label">授权根目录</span>
            <span class="path">~/workspace/login-service</span>
          </div>

          <div class="perm-columns" data-testid="perm-columns">
            <div class="perm-group allowed">
              <div class="perm-group-title">&#x2713; 允许</div>
              <ul class="perm-list">
                <li class="perm-item">读取工作区内文件</li>
                <li class="perm-item">生成 Diff 变更预览</li>
                <li class="perm-item">经批准后写入文件</li>
                <li class="perm-item">运行预设测试命令</li>
              </ul>
            </div>
            <div class="perm-group denied">
              <div class="perm-group-title">&#x2717; 禁止</div>
              <ul class="perm-list">
                <li class="perm-item">访问工作区外路径</li>
                <li class="perm-item">删除文件</li>
                <li class="perm-item">读取 .env 文件</li>
                <li class="perm-item">读取密钥文件</li>
                <li class="perm-item">Git 写操作（commit / push / reset）</li>
              </ul>
            </div>
          </div>
        </div>

        <!-- 命令策略 -->
        <div class="page" :class="{ active: activeCategory === 'commands' }">
          <div class="detail-header">
            <div class="detail-title">命令策略</div>
          </div>

          <div class="cmd-columns" data-testid="cmd-columns">
            <div class="cmd-group safe">
              <div class="cmd-group-title">安全预设 &#183; 直接执行</div>
              <div class="cmd-item"><span class="cmd-dot"></span>pytest</div>
              <div class="cmd-item"><span class="cmd-dot"></span>python -m pytest</div>
              <div class="cmd-item"><span class="cmd-dot"></span>npm test</div>
              <div class="cmd-item"><span class="cmd-dot"></span>npm run lint</div>
            </div>
            <div class="cmd-group review">
              <div class="cmd-group-title">非预设命令 &#183; 需审批</div>
              <div class="cmd-item"><span class="cmd-dot"></span>其他所有命令</div>
            </div>
          </div>

          <div class="cmd-denied-bar cmd-group denied" style="display:inline-flex;">
            <span class="label">高风险命令 &#183; 默认拒绝</span>
            <span class="examples">rm -rf &#183; git push --force &#183; curl | sh</span>
          </div>
        </div>

        <!-- 本地数据 -->
        <div class="page" :class="{ active: activeCategory === 'data' }">
          <div class="detail-header">
            <div class="detail-title">本地数据</div>
          </div>

          <div class="data-path-block" data-testid="data-path">
            <div class="data-path-label">SQLite 数据库路径</div>
            <div class="data-path">~/Library/Application Support/LightCode/lightcode.db</div>
          </div>

          <div class="data-columns" data-testid="data-columns">
            <div class="data-group stored">
              <div class="data-group-title">&#x2713; 保存</div>
              <div class="data-item">会话记录</div>
              <div class="data-item">任务执行历史</div>
              <div class="data-item">工具调用日志</div>
              <div class="data-item">审批记录</div>
              <div class="data-item">测试运行日志</div>
            </div>
            <div class="data-group not-stored">
              <div class="data-group-title">&#x2717; 不保存</div>
              <div class="data-item">源代码副本</div>
              <div class="data-item">API Key</div>
            </div>
          </div>

          <div class="data-note" data-testid="data-note">
            <span class="data-note-icon">&#x1F4A1;</span>
            Electron 阶段将支持选择本地数据目录
          </div>
        </div>
      </div>

      <div class="footer-bar" data-testid="footer-bar">
        <span style="font-size:10px;color:#ccc;">&#x1F512;</span>
        <span class="footer-note-text">所有配置和数据仅存储在本机 &#183; 不上传任何内容</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-shell {
  display: flex;
  height: 100vh;
  max-width: 100%;
  width: 100%;
  padding: 18px 60px 18px 150px;
  background: var(--color-paper, #f5f0e8);
  color: var(--color-pencil, #2a2a2a);
  font-family: 'Architects Daughter', 'Patrick Hand', cursive;
}

/* Sidebar */
.sidebar {
  width: 240px;
  min-width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding-right: 24px;
  border-right: 2px solid var(--color-pencil, #2a2a2a);
  margin-right: 28px;
}

.sidebar-back {
  font-family: 'Architects Daughter', cursive;
  font-size: 13px;
  color: var(--color-blue-grey, #6b7d8e);
  cursor: pointer;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 5px;
  transition: color 0.12s;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.sidebar-back:hover {
  color: var(--color-pencil, #2a2a2a);
}

.sidebar-back .arrow {
  font-size: 11px;
}

.sidebar-title {
  font-family: 'Caveat', cursive;
  font-size: 28px;
  font-weight: 700;
  color: var(--color-marker-dark, #1a1a1a);
  transform: rotate(-0.4deg);
  margin-bottom: 12px;
  flex-shrink: 0;
  padding-bottom: 10px;
  border-bottom: 1.5px dashed #d8d0c4;
}

.nav-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.nav-item {
  font-family: 'Architects Daughter', cursive;
  font-size: 15px;
  padding: 9px 12px;
  border-radius: 5px;
  cursor: pointer;
  border: 1.5px solid transparent;
  transition: all 0.12s;
  color: #555;
  user-select: none;
}

.nav-item:hover {
  color: var(--color-pencil, #2a2a2a);
  background: rgba(0, 0, 0, 0.03);
}

.nav-item.active {
  color: var(--color-pencil, #2a2a2a);
  font-weight: 600;
  background: rgba(212, 160, 23, 0.1);
  border-color: var(--color-pencil, #2a2a2a);
  transform: rotate(-0.15deg);
}

.sidebar-version {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #aaa;
  padding-top: 12px;
  border-top: 1.5px dashed #d8d0c4;
  margin-top: 12px;
  flex-shrink: 0;
}

/* Detail */
.detail {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 6px;
}

.detail-scroll::-webkit-scrollbar {
  width: 5px;
}

.detail-scroll::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.03);
  border-radius: 4px;
}

.detail-scroll::-webkit-scrollbar-thumb {
  background: #c5b9a8;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.detail-scroll::-webkit-scrollbar-thumb:hover {
  background: #a99e8d;
}

.detail-scroll {
  scrollbar-width: thin;
  scrollbar-color: #c5b9a8 rgba(0, 0, 0, 0.03);
}

.detail-header {
  margin-top: 33px;
  margin-bottom: 14px;
  flex-shrink: 0;
  padding-bottom: 10px;
  border-bottom: 1.5px dashed #d8d0c4;
}

.detail-title {
  font-family: 'Caveat', cursive;
  font-size: 28px;
  font-weight: 700;
  color: var(--color-marker-dark, #1a1a1a);
  transform: rotate(-0.3deg);
}

/* Page visibility */
.page {
  display: none;
}

.page.active {
  display: block;
}

/* Common card */
.content-card {
  border: 1.5px solid #d8d0c4;
  border-radius: 5px;
  padding: 14px 18px;
  background: rgba(255, 255, 255, 0.15);
}

.info-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px dashed #e0d8cc;
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  font-family: 'Architects Daughter', cursive;
  font-size: 14px;
  color: #666;
  min-width: 120px;
  flex-shrink: 0;
}

.info-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: var(--color-pencil, #2a2a2a);
}

.runtime-inline {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--color-green-ink, #2d7a3a);
  border: 1.5px solid var(--color-green-ink, #2d7a3a);
  border-radius: 4px;
  padding: 3px 10px;
  background: rgba(45, 122, 58, 0.06);
}

.runtime-inline::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-green-ink, #2d7a3a);
}

.info-note {
  font-family: 'Patrick Hand', cursive;
  font-size: 14px;
  color: var(--color-blue-grey, #6b7d8e);
  margin-top: 14px;
  line-height: 1.7;
  transform: rotate(-0.05deg);
}

/* Model modes */
.mode-block {
  margin-bottom: 14px;
  padding: 16px 18px;
  border-radius: 5px;
}

.mode-block.active-mode {
  border: 2.5px solid var(--color-orange-ink, #c87020);
  background: rgba(212, 160, 23, 0.06);
  transform: rotate(-0.15deg);
}

.mode-block.disabled-mode {
  border: 1.5px solid #d8d0c4;
  background: rgba(0, 0, 0, 0.015);
  opacity: 0.6;
}

.mode-label-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}

.mode-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.active-mode .mode-dot {
  background: var(--color-orange-ink, #c87020);
}

.disabled-mode .mode-dot {
  background: transparent;
  border: 1.5px solid #bbb;
}

.mode-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-pencil, #2a2a2a);
}

.disabled-mode .mode-name {
  color: #888;
}

.mode-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 3px;
  flex-shrink: 0;
}

.badge-active {
  color: var(--color-orange-ink, #c87020);
  background: rgba(212, 160, 23, 0.12);
  border: 1px solid rgba(200, 112, 32, 0.3);
}

.badge-coming {
  color: var(--color-blue-grey, #6b7d8e);
  background: rgba(107, 125, 144, 0.08);
  border: 1px solid rgba(107, 125, 144, 0.2);
}

.mode-desc {
  font-family: 'Architects Daughter', cursive;
  font-size: 13px;
  color: #555;
  line-height: 1.6;
}

.disabled-mode .mode-desc {
  color: #999;
}

/* API fields */
.api-fields {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e0d8cc;
}

.api-fields-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: #aaa;
  margin-bottom: 8px;
}

.field-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.field-key {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #888;
  min-width: 80px;
  flex-shrink: 0;
}

.field-val {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #bbb;
  background: rgba(0, 0, 0, 0.03);
  border: 1px dashed #e0d8cc;
  border-radius: 3px;
  padding: 3px 10px;
  flex: 1;
}

.field-val.masked {
  color: #aaa;
  font-style: italic;
}

/* Permissions */
.perm-root-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border: 1.5px solid #d8d0c4;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.25);
  margin-bottom: 16px;
  transform: rotate(-0.1deg);
}

.perm-root-bar .icon {
  font-size: 14px;
  opacity: 0.5;
  flex-shrink: 0;
}

.perm-root-bar .label {
  font-family: 'Architects Daughter', cursive;
  font-size: 13px;
  color: #666;
  flex-shrink: 0;
}

.perm-root-bar .path {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--color-pencil, #2a2a2a);
  font-weight: 500;
}

.perm-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.perm-group {
  padding: 12px 14px;
  border-radius: 4px;
}

.perm-group.allowed {
  border: 1.5px solid rgba(45, 122, 58, 0.25);
  background: rgba(45, 122, 58, 0.03);
}

.perm-group.denied {
  border: 1.5px solid rgba(184, 48, 48, 0.2);
  background: rgba(184, 48, 48, 0.02);
}

.perm-group-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  margin-bottom: 8px;
}

.allowed .perm-group-title {
  color: var(--color-green-ink, #2d7a3a);
}

.denied .perm-group-title {
  color: var(--color-red-ink, #b83030);
}

.perm-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.perm-item {
  font-family: 'Architects Daughter', cursive;
  font-size: 13px;
  color: #444;
  padding: 3px 0;
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.perm-item::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
  top: -1px;
}

.allowed .perm-item::before {
  background: var(--color-green-ink, #2d7a3a);
}

.denied .perm-item::before {
  background: var(--color-red-ink, #b83030);
}

.denied .perm-item {
  color: #666;
}

/* Command policy */
.cmd-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}

.cmd-group {
  padding: 12px 14px;
  border-radius: 4px;
}

.cmd-group.safe {
  border: 1.5px solid rgba(45, 122, 58, 0.25);
  background: rgba(45, 122, 58, 0.03);
}

.cmd-group.review {
  border: 1.5px solid rgba(200, 112, 32, 0.25);
  background: rgba(200, 112, 32, 0.03);
}

.cmd-group.denied {
  border: 1.5px solid rgba(184, 48, 48, 0.2);
  background: rgba(184, 48, 48, 0.02);
}

.cmd-group-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  margin-bottom: 8px;
}

.safe .cmd-group-title {
  color: var(--color-green-ink, #2d7a3a);
}

.review .cmd-group-title {
  color: var(--color-orange-ink, #c87020);
}

.denied .cmd-group-title {
  color: var(--color-red-ink, #b83030);
}

.cmd-item {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  padding: 4px 10px;
  margin-bottom: 4px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  gap: 7px;
}

.safe .cmd-item {
  color: var(--color-green-ink, #2d7a3a);
  background: rgba(45, 122, 58, 0.06);
  border: 1px solid rgba(45, 122, 58, 0.12);
}

.review .cmd-item {
  color: var(--color-orange-ink, #c87020);
  background: rgba(200, 112, 32, 0.06);
  border: 1px solid rgba(200, 112, 32, 0.12);
}

.denied .cmd-item {
  color: var(--color-red-ink, #b83030);
  background: rgba(184, 48, 48, 0.04);
  border: 1px solid rgba(184, 48, 48, 0.1);
  text-decoration: line-through;
  opacity: 0.7;
}

.cmd-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.safe .cmd-dot {
  background: var(--color-green-ink, #2d7a3a);
}

.review .cmd-dot {
  background: var(--color-orange-ink, #c87020);
}

.denied .cmd-dot {
  background: var(--color-red-ink, #b83030);
}

.cmd-denied-bar {
  padding: 10px 14px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.cmd-denied-bar .label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--color-red-ink, #b83030);
}

.cmd-denied-bar .examples {
  font-family: 'Architects Daughter', cursive;
  font-size: 12px;
  color: var(--color-red-ink, #b83030);
}

/* Local data */
.data-path-block {
  padding: 12px 16px;
  border: 1.5px solid #d8d0c4;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.25);
  margin-bottom: 16px;
  transform: rotate(-0.1deg);
}

.data-path-label {
  font-family: 'Architects Daughter', cursive;
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.data-path {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--color-pencil, #2a2a2a);
  word-break: break-all;
}

.data-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 14px;
}

.data-group {
  padding: 12px 14px;
  border-radius: 4px;
}

.data-group.stored {
  border: 1.5px solid rgba(45, 122, 58, 0.2);
  background: rgba(45, 122, 58, 0.03);
}

.data-group.not-stored {
  border: 1.5px dashed rgba(184, 48, 48, 0.25);
  background: rgba(184, 48, 48, 0.015);
}

.data-group-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  margin-bottom: 6px;
}

.stored .data-group-title {
  color: var(--color-green-ink, #2d7a3a);
}

.not-stored .data-group-title {
  color: var(--color-red-ink, #b83030);
}

.data-item {
  font-family: 'Architects Daughter', cursive;
  font-size: 13px;
  color: #444;
  padding: 3px 0;
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.data-item::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
  top: -1px;
}

.stored .data-item::before {
  background: var(--color-green-ink, #2d7a3a);
}

.not-stored .data-item::before {
  background: transparent;
  border: 1.5px dashed var(--color-red-ink, #b83030);
}

.not-stored .data-item {
  color: #777;
}

.data-note {
  font-family: 'Patrick Hand', cursive;
  font-size: 13px;
  color: var(--color-blue-grey, #6b7d8e);
  padding: 10px 14px;
  border: 1px dashed #d8d0c4;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.2);
  transform: rotate(-0.08deg);
  display: flex;
  align-items: center;
  gap: 8px;
}

.data-note-icon {
  font-size: 13px;
  opacity: 0.5;
  flex-shrink: 0;
}

/* Footer */
.footer-bar {
  flex-shrink: 0;
  padding: 10px 0 0;
  border-top: 1.5px dashed #d8d0c4;
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
}

.footer-note-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #aaa;
}

/* Responsive */
@media (max-width: 900px) {
  .settings-shell {
    padding: 14px 24px;
  }
  .sidebar {
    width: 180px;
    min-width: 180px;
    margin-right: 16px;
  }
}

@media (max-width: 640px) {
  .settings-shell {
    flex-direction: column;
    padding: 10px 16px;
  }
  .sidebar {
    width: 100%;
    min-width: 0;
    flex-direction: row;
    flex-wrap: wrap;
    border-right: none;
    border-bottom: 2px solid var(--color-pencil, #2a2a2a);
    margin-right: 0;
    margin-bottom: 14px;
    padding-right: 0;
    padding-bottom: 10px;
    gap: 4px;
    align-items: center;
  }
  .sidebar-title {
    margin-bottom: 0;
    font-size: 20px;
    border-bottom: none;
    padding-bottom: 0;
  }
  .nav-list {
    flex-direction: row;
    flex-wrap: wrap;
    gap: 2px;
  }
  .sidebar-version {
    display: none;
  }
  .detail-scroll {
    padding-top: 0;
  }
  .detail-header {
    margin-top: 0;
  }
  .perm-columns,
  .cmd-columns,
  .data-columns {
    grid-template-columns: 1fr;
  }
}
</style>
