import { createRouter, createWebHistory } from 'vue-router'
import AgentWorkspaceView from '@/views/AgentWorkspaceView.vue'
import SessionHistoryView from '@/views/SessionHistoryView.vue'
import WorkspaceHomeView from '@/views/WorkspaceHomeView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: WorkspaceHomeView },
    { path: '/workspace/:id', name: 'agent-workspace', component: AgentWorkspaceView },
    { path: '/workspace/:id/history', name: 'session-history', component: SessionHistoryView },
  ],
})
