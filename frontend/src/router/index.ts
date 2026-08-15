import {
  createRouter,
  createWebHashHistory,
  createWebHistory,
  type RouterHistory,
} from 'vue-router'
import RealTaskView from '@/views/RealTaskView.vue'
import SettingsView from '@/views/SettingsView.vue'
import SkillsView from '@/views/SkillsView.vue'
import WorkspaceHomeView from '@/views/WorkspaceHomeView.vue'
import WorkspaceView from '@/views/WorkspaceView.vue'

export function createAppHistory(protocol = window.location.protocol): RouterHistory {
  return protocol === 'file:' ? createWebHashHistory() : createWebHistory()
}

export const router = createRouter({
  history: createAppHistory(),
  routes: [
    { path: '/', name: 'home', component: WorkspaceHomeView },
    // 核心 Agent 更新（阶段 A）：工作区聊天主界面（会话参数可选）
    { path: '/workspace/:workspaceId', name: 'workspace', component: WorkspaceView },
    { path: '/workspace/:workspaceId/session/:sessionId', name: 'workspace-session', component: WorkspaceView },
    // Skill 管理（2026-08-12）：独立的技能管理路由
    { path: '/workspace/:workspaceId/skills', name: 'skills', component: SkillsView },
    // 审查深链：完整 Diff 只在审查页展示（聊天内仅紧凑摘要）
    { path: '/workspace/:workspaceId/task/:taskId', name: 'real-task', component: RealTaskView },
    { path: '/settings', name: 'settings', component: SettingsView },
  ],
})
