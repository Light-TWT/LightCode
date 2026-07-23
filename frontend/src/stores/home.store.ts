import { defineStore } from 'pinia'
import { workspaceService } from '@/services/workspace.service'
import type { WorkspaceEntry } from '@/types/agent'

export const useHomeStore = defineStore('home', {
  state: () => ({
    recentWorkspaces: [] as WorkspaceEntry[],
    allWorkspaces: [] as WorkspaceEntry[],
    drawerOpen: false,
    searchQuery: '',
    loading: false,
  }),
  getters: {
    filteredWorkspaces(state) {
      if (!state.searchQuery) return state.allWorkspaces
      const q = state.searchQuery.toLowerCase()
      return state.allWorkspaces.filter(
        w => w.name.toLowerCase().includes(q) || w.rootPath.toLowerCase().includes(q),
      )
    },
  },
  actions: {
    async load() {
      this.loading = true
      try {
        const [recent, all] = await Promise.all([
          workspaceService.getRecentWorkspaces(),
          workspaceService.getAllWorkspaces(),
        ])
        this.recentWorkspaces = recent
        this.allWorkspaces = all
      } finally {
        this.loading = false
      }
    },
    openDrawer() {
      this.drawerOpen = true
      this.searchQuery = ''
    },
    closeDrawer() {
      this.drawerOpen = false
      this.searchQuery = ''
    },
  },
})
