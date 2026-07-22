import { defineStore } from 'pinia'
import { mockTaskService } from '@/services/task.service'
import type { HistoryTaskDetail, HistoryTaskEntry } from '@/types/agent'

export type FilterType = 'all' | 'waiting' | 'done' | 'fail' | 'cancelled'

export const useHistoryStore = defineStore('history', {
  state: () => ({
    entries: [] as HistoryTaskEntry[],
    detail: null as HistoryTaskDetail | null,
    detailOpen: false,
    detailWidth: 500,
    activeFilter: 'all' as FilterType,
    searchQuery: '',
    loading: false,
    detailLoading: false,
  }),
  getters: {
    filteredEntries(state) {
      let result = state.entries
      if (state.activeFilter !== 'all') {
        result = result.filter(e => e.status === state.activeFilter)
      }
      if (state.searchQuery.trim()) {
        const q = state.searchQuery.toLowerCase()
        result = result.filter(e =>
          e.title.toLowerCase().includes(q) ||
          e.summary.toLowerCase().includes(q) ||
          e.files.some(f => f.name.toLowerCase().includes(q)),
        )
      }
      return result
    },
    filterCounts(state) {
      const all = state.entries.length
      const waiting = state.entries.filter(e => e.status === 'waiting').length
      const done = state.entries.filter(e => e.status === 'done').length
      const fail = state.entries.filter(e => e.status === 'fail').length
      const cancelled = state.entries.filter(e => e.status === 'cancelled').length
      return { all, waiting, done, fail, cancelled }
    },
  },
  actions: {
    async load(workspaceId: string) {
      this.loading = true
      try {
        this.entries = await mockTaskService.getTaskHistory(workspaceId)
      } finally {
        this.loading = false
      }
    },
    async openDetail(taskId: string) {
      this.detailLoading = true
      try {
        this.detail = await mockTaskService.getTaskDetail(taskId)
        this.detailOpen = true
      } finally {
        this.detailLoading = false
      }
    },
    closeDetail() {
      this.detailOpen = false
      this.detail = null
    },
    setFilter(filter: FilterType) {
      this.activeFilter = filter
    },
    setSearch(q: string) {
      this.searchQuery = q
    },
  },
})
