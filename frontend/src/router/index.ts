import { createRouter, createWebHistory } from 'vue-router'
import AgentWorkspaceView from '@/views/AgentWorkspaceView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/workspace/workspace-login-service' },
    { path: '/workspace/:id', name: 'agent-workspace', component: AgentWorkspaceView },
  ],
})
