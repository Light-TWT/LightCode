// Runtime DTO validation for Skill management responses (2026-08-12).
import { ContractValidationError } from '@/contracts/real-task.schema'
import type {
  SkillDeleteResult,
  SkillDetail,
  SkillDocument,
  SkillSource,
  SkillStatus,
  SkillSummary,
} from '@/types/agent'

const SKILL_SOURCES: readonly SkillSource[] = ['builtin', 'uploaded']
const SKILL_STATUSES: readonly SkillStatus[] = ['disabled', 'enabled']
const FORBIDDEN_KEYS = ['rootPath', 'filePath', 'storagePath', 'packagePath', 'baseUrl'] as const

function isString(v: unknown): v is string {
  return typeof v === 'string'
}
function isNumber(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}
function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

function hasForbiddenKey(raw: Record<string, unknown>): boolean {
  return FORBIDDEN_KEYS.some((key) => key in raw)
}

function assertSafeKeys(raw: Record<string, unknown>, kind: string): void {
  if (hasForbiddenKey(raw)) {
    throw new ContractValidationError(`${kind} 不应包含路径或密钥字段`)
  }
}

function assertSource(
  raw: Record<string, unknown>,
  kind: string,
): asserts raw is Record<string, unknown> & { source: SkillSource } {
  if (!isString(raw.source) || !SKILL_SOURCES.includes(raw.source as SkillSource)) {
    throw new ContractValidationError(`${kind}.source 非法: ${String(raw.source)}`)
  }
}

function assertStatus(
  raw: Record<string, unknown>,
  kind: string,
): asserts raw is Record<string, unknown> & { status: SkillStatus } {
  if (!isString(raw.status) || !SKILL_STATUSES.includes(raw.status as SkillStatus)) {
    throw new ContractValidationError(`${kind}.status 非法: ${String(raw.status)}`)
  }
}

function assertSkillId(
  raw: Record<string, unknown>,
  kind: string,
): asserts raw is Record<string, unknown> & { id: string } {
  if (!isString(raw.id) || !/^skill_[0-9a-f]{32}$/.test(raw.id)) {
    throw new ContractValidationError(`${kind}.id 非法: ${String(raw.id)}`)
  }
}

export function parseSkillSummary(raw: unknown): SkillSummary {
  if (!isObject(raw)) throw new ContractValidationError('skill 不是对象')
  assertSafeKeys(raw, 'skill')
  assertSkillId(raw, 'skill')
  assertSource(raw, 'skill')
  assertStatus(raw, 'skill')
  if (!isString(raw.name) || !raw.name.trim()) {
    throw new ContractValidationError('skill.name 缺失或为空')
  }
  if (!isString(raw.summary)) throw new ContractValidationError('skill.summary 缺失')
  if (!isNumber(raw.documentBytes)) throw new ContractValidationError('skill.documentBytes 非法')
  if (!isNumber(raw.resourceCount)) throw new ContractValidationError('skill.resourceCount 非法')
  if (!isNumber(raw.sectionCount)) throw new ContractValidationError('skill.sectionCount 非法')
  if (!isString(raw.createdAt)) throw new ContractValidationError('skill.createdAt 缺失')
  if (!isString(raw.updatedAt)) throw new ContractValidationError('skill.updatedAt 缺失')
  return {
    id: raw.id,
    name: raw.name,
    source: raw.source as SkillSource,
    status: raw.status as SkillStatus,
    summary: raw.summary,
    documentBytes: raw.documentBytes,
    resourceCount: raw.resourceCount,
    sectionCount: raw.sectionCount,
    createdAt: raw.createdAt,
    updatedAt: raw.updatedAt,
  }
}

export function parseSkillDetail(raw: unknown): SkillDetail {
  const summary = parseSkillSummary(raw)
  const object = raw as Record<string, unknown>
  if (!isString(object.documentSha256) || !/^[0-9a-f]{64}$/.test(object.documentSha256)) {
    throw new ContractValidationError('skill.documentSha256 非法')
  }
  if (!isNumber(object.packageBytes)) throw new ContractValidationError('skill.packageBytes 非法')
  return { ...summary, documentSha256: object.documentSha256, packageBytes: object.packageBytes }
}

export function parseSkillDocument(raw: unknown): SkillDocument {
  if (!isObject(raw)) throw new ContractValidationError('skill document 不是对象')
  assertSafeKeys(raw, 'skill document')
  assertSkillId(raw, 'skill document')
  assertSource(raw, 'skill document')
  assertStatus(raw, 'skill document')
  if (!isString(raw.name) || !raw.name.trim()) {
    throw new ContractValidationError('skill document.name 缺失')
  }
  if (!isString(raw.content)) throw new ContractValidationError('skill document.content 缺失')
  if (!isString(raw.documentSha256) || !/^[0-9a-f]{64}$/.test(raw.documentSha256)) {
    throw new ContractValidationError('skill document.documentSha256 非法')
  }
  return {
    id: raw.id,
    name: raw.name,
    source: raw.source as SkillSource,
    status: raw.status as SkillStatus,
    content: raw.content,
    documentSha256: raw.documentSha256,
  }
}

export function parseSkillDelete(raw: unknown): SkillDeleteResult {
  if (!isObject(raw)) throw new ContractValidationError('skill delete 响应不是对象')
  assertSkillId(raw, 'skill delete')
  if (raw.deleted !== true) throw new ContractValidationError('skill delete.deleted 非法')
  return { id: raw.id, deleted: true }
}

export function parseSkillList(raw: unknown): SkillSummary[] {
  if (!Array.isArray(raw)) throw new ContractValidationError('skill 列表不是数组')
  return raw.map(parseSkillSummary)
}