import { createRouter, createWebHistory } from 'vue-router'
import RealTaskView from '@/views/RealTaskView.vue'
import SettingsView from '@/views/SettingsView.vue'
import WorkspaceHomeView from '@/views/WorkspaceHomeView.vue'
import WorkspaceView from '@/views/WorkspaceView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: WorkspaceHomeView },
    // 核心 Agent 更新（阶段 A）：工作区聊天主界面（会话参数可选）
    { path: '/workspace/:workspaceId', name: 'workspace', component: WorkspaceView },
    { path: '/workspace/:workspaceId/session/:sessionId', name: 'workspace-session', component: WorkspaceView },
    // 审查深链：完整 Diff 只在审查页展示（聊天内仅紧凑摘要）
    { path: '/workspace/:workspaceId/task/:taskId', name: 'real-task', component: RealTaskView },
    { path: '/settings', name: 'settings', component: SettingsView },
  ],
})
