import { createRouter, createWebHistory } from 'vue-router'
import AgentWorkspaceView from '@/views/AgentWorkspaceView.vue'
import RealTaskView from '@/views/RealTaskView.vue'
import RealWorkspaceListView from '@/views/RealWorkspaceListView.vue'
import RealWorkspaceView from '@/views/RealWorkspaceView.vue'
import SessionHistoryView from '@/views/SessionHistoryView.vue'
import SettingsView from '@/views/SettingsView.vue'
import WorkspaceHomeView from '@/views/WorkspaceHomeView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: WorkspaceHomeView },
    { path: '/workspace/:id', name: 'agent-workspace', component: AgentWorkspaceView },
    { path: '/workspace/:id/history', name: 'session-history', component: SessionHistoryView },
    { path: '/settings', name: 'settings', component: SettingsView },
    // Phase 1 真实闭环
    { path: '/real', name: 'real-workspace-list', component: RealWorkspaceListView },
    { path: '/real/:id', name: 'real-workspace', component: RealWorkspaceView },
    { path: '/real/:id/task/:taskId', name: 'real-task', component: RealTaskView },
  ],
})
