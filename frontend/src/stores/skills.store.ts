import { defineStore } from 'pinia'
import { skillsService } from '@/services/skills.service'
import type {
  SkillDetail,
  SkillDocument,
  SkillSource,
  SkillStatus,
  SkillSummary,
} from '@/types/agent'

export type SkillSourceFilter = 'all' | SkillSource

// 固定中文文案：绝不把服务端自由 message/异常文本渲染到 UI。
const SKILL_ERROR_TEXT: Record<string, string> = {
  SKILL_PACKAGE_TYPE_DENIED: '仅支持 .zip 技能包。',
  SKILL_PACKAGE_SIZE_DENIED: '技能包超出大小限制。',
  SKILL_PACKAGE_INVALID: '技能包无法识别，请检查压缩文件。',
  SKILL_PACKAGE_STRUCTURE_DENIED: '技能包结构不符合要求。',
  SKILL_DOCUMENT_MISSING: '技能包中未找到 SKILL.md。',
  SKILL_DOCUMENT_DUPLICATED: '技能包包含多个 SKILL.md。',
  SKILL_DOCUMENT_INVALID: 'SKILL.md 格式不符合要求。',
  SKILL_ALREADY_EXISTS: '同名技能已存在。',
  SKILL_STORAGE_FAILED: '技能状态更新失败，请稍后重试。',
  SKILL_NOT_FOUND: '技能不存在或已被删除。',
  SKILL_DELETE_DENIED: '内置技能不可删除。',
}

const SKILL_ERROR_FALLBACK = '技能操作失败，请稍后重试。'

function skillErrorMessage(err: unknown): string {
  const code = err instanceof Error ? err.message : String(err)
  return SKILL_ERROR_TEXT[code] ?? SKILL_ERROR_FALLBACK
}

function isZipFile(file: File): boolean {
  return file.name.toLowerCase().endsWith('.zip')
}

export const useSkillsStore = defineStore('skills', {
  state: () => ({
    items: [] as SkillSummary[],
    detail: null as SkillDetail | null,
    document: null as SkillDocument | null,
    query: '',
    sourceFilter: 'all' as SkillSourceFilter,
    loading: false,
    uploading: false,
    updatingId: null as string | null,
    deletingId: null as string | null,
    error: null as string | null,
  }),

  getters: {
    /** 搜索与来源筛选只作用于内存安全摘要，不改动 API 列表。 */
    filtered(state): SkillSummary[] {
      const keyword = state.query.trim().toLowerCase()
      return state.items.filter((item) => {
        if (state.sourceFilter !== 'all' && item.source !== state.sourceFilter) return false
        if (!keyword) return true
        return (
          item.name.toLowerCase().includes(keyword) ||
          item.summary.toLowerCase().includes(keyword)
        )
      })
    },
  },

  actions: {
    async load(): Promise<void> {
      this.loading = true
      this.error = null
      try {
        this.items = await skillsService.list()
      } catch {
        this.error = SKILL_ERROR_FALLBACK
      } finally {
        this.loading = false
      }
    },

    async open(id: string): Promise<void> {
      this.error = null
      try {
        this.detail = await skillsService.get(id)
        this.document = await skillsService.document(id)
      } catch (err) {
        this.error = skillErrorMessage(err)
      }
    },

    close(): void {
      this.detail = null
      this.document = null
    },

    async upload(file: File): Promise<void> {
      if (!isZipFile(file)) {
        this.error = '仅支持 .zip 技能包。'
        return
      }
      this.uploading = true
      this.error = null
      try {
        const created = await skillsService.upload(file)
        this.items = [created, ...this.items.filter((item) => item.id !== created.id)]
        this.detail = created
        this.document = await skillsService.document(created.id)
      } catch (err) {
        this.error = skillErrorMessage(err)
      } finally {
        this.uploading = false
      }
    },

    async setStatus(id: string, status: SkillStatus): Promise<void> {
      const previousItem = this.items.find((item) => item.id === id)
      if (!previousItem || previousItem.status === status) return
      const previousStatus = previousItem.status

      // 乐观更新：列表行与打开的详情/文档同时翻转；失败回滚。
      this.items = this.items.map((item) =>
        item.id === id ? { ...item, status } : item,
      )
      if (this.detail?.id === id) this.detail = { ...this.detail, status }
      if (this.document?.id === id) this.document = { ...this.document, status }

      this.updatingId = id
      this.error = null
      try {
        const updated = await skillsService.setStatus(id, status)
        this.items = this.items.map((item) => (item.id === id ? updated : item))
        if (this.detail?.id === id) this.detail = updated
        if (this.document?.id === id) {
          this.document = { ...this.document, status: updated.status }
        }
      } catch (err) {
        this.items = this.items.map((item) =>
          item.id === id ? { ...item, status: previousStatus } : item,
        )
        if (this.detail?.id === id) this.detail = { ...this.detail, status: previousStatus }
        if (this.document?.id === id) {
          this.document = { ...this.document, status: previousStatus }
        }
        this.error = skillErrorMessage(err)
      } finally {
        this.updatingId = null
      }
    },

    async remove(id: string): Promise<void> {
      this.deletingId = id
      this.error = null
      try {
        await skillsService.remove(id)
        this.items = this.items.filter((item) => item.id !== id)
        if (this.detail?.id === id) {
          this.detail = null
          this.document = null
        }
      } catch (err) {
        this.error = skillErrorMessage(err)
      } finally {
        this.deletingId = null
      }
    },
  },
})