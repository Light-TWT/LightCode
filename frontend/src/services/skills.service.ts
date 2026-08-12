import { requestJsonValidated } from '@/services/http'
import {
  parseSkillDelete,
  parseSkillDetail,
  parseSkillDocument,
  parseSkillList,
} from '@/contracts/skill.schema'
import type {
  SkillDeleteResult,
  SkillDetail,
  SkillDocument,
  SkillStatus,
  SkillSummary,
} from '@/types/agent'

export const skillsService = {
  list(): Promise<SkillSummary[]> {
    return requestJsonValidated('/skills', undefined, parseSkillList)
  },
  get(id: string): Promise<SkillDetail> {
    return requestJsonValidated(`/skills/${encodeURIComponent(id)}`, undefined, parseSkillDetail)
  },
  document(id: string): Promise<SkillDocument> {
    return requestJsonValidated(
      `/skills/${encodeURIComponent(id)}/document`,
      undefined,
      parseSkillDocument,
    )
  },
  upload(file: File): Promise<SkillDetail> {
    const body = new FormData()
    body.append('package', file)
    // multipart 边界由浏览器生成：绝不手动设置 Content-Type
    return requestJsonValidated('/skills/upload', { method: 'POST', body }, parseSkillDetail)
  },
  setStatus(id: string, status: SkillStatus): Promise<SkillDetail> {
    return requestJsonValidated(
      `/skills/${encodeURIComponent(id)}/status`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      },
      parseSkillDetail,
    )
  },
  remove(id: string): Promise<SkillDeleteResult> {
    return requestJsonValidated(
      `/skills/${encodeURIComponent(id)}`,
      { method: 'DELETE' },
      parseSkillDelete,
    )
  },
}