// Runtime DTO validation for Phase 1 HTTP / SSE responses.
import type { ModelTaskResponse } from '@/types/agent'
import { MODEL_TASK_EVENT_TYPES } from '@/types/agent'
//
// The backend is the only authority and already validates with Pydantic
// (extra="forbid"), but the browser must still guard against malformed or
// unexpected payloads before they reach the UI/state machine. These guards run
// at the service boundary: a failing payload surfaces a recoverable "协议不兼容"
// error instead of crashing the view or silently injecting bad data.

export class ContractValidationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ContractValidationError'
  }
}

function isString(v: unknown): v is string {
  return typeof v === 'string'
}
function isNumber(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}
function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

const REAL_TASK_STATES = new Set([
  'awaiting_approval',
  'applying_change',
  'completed',
  'failed',
  'cancelled',
])

export function parseRegisteredWorkspace(raw: unknown): {
  id: string
  displayName: string
  enabled: boolean
  capabilities: string[]
  policyVersion: string
} {
  if (!isObject(raw)) throw new ContractValidationError('registered workspace 不是对象')
  if (!isString(raw.id)) throw new ContractValidationError('workspace.id 缺失或非字符串')
  if (!isString(raw.displayName)) throw new ContractValidationError('workspace.displayName 缺失')
  if (typeof raw.enabled !== 'boolean') {
    throw new ContractValidationError('workspace.enabled 缺失或非布尔')
  }
  if (!Array.isArray(raw.capabilities) || !raw.capabilities.every(isString)) {
    throw new ContractValidationError('workspace.capabilities 非法')
  }
  if (!isString(raw.policyVersion)) {
    throw new ContractValidationError('workspace.policyVersion 缺失')
  }
  // 关键不变量：公共 DTO 绝不携带真实根路径
  if ('rootPath' in raw) {
    throw new ContractValidationError('workspace 不应包含 rootPath')
  }
  return {
    id: raw.id,
    displayName: raw.displayName,
    enabled: raw.enabled,
    capabilities: raw.capabilities,
    policyVersion: raw.policyVersion,
  }
}

export function parseRealTask(raw: unknown): {
  id: string
  workspaceId: string
  state: string
  title: string
  targetFile?: string | null
  changeSet?: unknown
} {
  if (!isObject(raw)) throw new ContractValidationError('real task 不是对象')
  if (!isString(raw.id)) throw new ContractValidationError('task.id 缺失')
  if (!isString(raw.workspaceId)) throw new ContractValidationError('task.workspaceId 缺失')
  if (!isString(raw.state) || !REAL_TASK_STATES.has(raw.state)) {
    throw new ContractValidationError(`task.state 非法: ${String(raw.state)}`)
  }
  if (!isString(raw.title)) throw new ContractValidationError('task.title 缺失')
  return {
    id: raw.id,
    workspaceId: raw.workspaceId,
    state: raw.state,
    title: raw.title,
    targetFile: 'targetFile' in raw ? (raw.targetFile as string | null) : null,
    changeSet: 'changeSet' in raw ? raw.changeSet : undefined,
  }
}

export function parseTaskEvent(raw: unknown): {
  sequence: number
  eventType: string
  payload: Record<string, unknown>
} {
  if (!isObject(raw)) throw new ContractValidationError('task event 不是对象')
  if (!isNumber(raw.sequence)) throw new ContractValidationError('event.sequence 缺失')
  if (!isString(raw.eventType)) throw new ContractValidationError('event.eventType 缺失')
  if (!isObject(raw.payload)) throw new ContractValidationError('event.payload 缺失')
  return {
    sequence: raw.sequence,
    eventType: raw.eventType,
    payload: raw.payload,
  }
}

const MODEL_TASK_STATES = new Set(['awaiting_approval', 'failed', 'planning'])

export function parseModelTask(raw: unknown): ModelTaskResponse {
  if (!isObject(raw)) throw new ContractValidationError('model task 不是对象')
  if (!isString(raw.id)) throw new ContractValidationError('task.id 缺失')
  if (!isString(raw.workspaceId)) throw new ContractValidationError('task.workspaceId 缺失')
  if (!isString(raw.state) || !MODEL_TASK_STATES.has(raw.state)) {
    throw new ContractValidationError(`task.state 非法: ${String(raw.state)}`)
  }
  if (!isString(raw.detail)) throw new ContractValidationError('task.detail 缺失')
  const cs = raw.changeSetId
  if (cs !== null && cs !== undefined && !isString(cs)) {
    throw new ContractValidationError('task.changeSetId 非法')
  }
  // 关键不变量：模型任务 DTO 绝不携带真实根路径
  if ('rootPath' in raw) {
    throw new ContractValidationError('model task 不应包含 rootPath')
  }
  return {
    id: raw.id,
    workspaceId: raw.workspaceId,
    state: raw.state,
    changeSetId: cs == null ? null : cs,
    detail: raw.detail,
  }
}

/**
 * 模型任务事件 payload 的防御性校验。后端已用 Pydantic 校验，浏览器再校验一次
 * 以避免畸形/意外 payload 进入状态机：未知事件类型或缺失必填字段一律抛错，
 * 调用方应静默丢弃而非崩溃 UI。
 */
export function parseModelLifecycleEvent(eventType: string, payload: Record<string, unknown>): void {
  if (!MODEL_TASK_EVENT_TYPES.includes(eventType as (typeof MODEL_TASK_EVENT_TYPES)[number])) {
    throw new ContractValidationError(`未知模型任务事件类型: ${eventType}`)
  }
  if (eventType === 'task.reading_workspace') {
    if (!isString(payload.target)) {
      throw new ContractValidationError('reading_workspace 缺少 target')
    }
  } else if (eventType === 'task.generating_diff') {
    if (!isString(payload.changeSetId)) {
      throw new ContractValidationError('generating_diff 缺少 changeSetId')
    }
    if (typeof payload.additions !== 'number' || typeof payload.deletions !== 'number') {
      throw new ContractValidationError('generating_diff 缺少 additions/deletions')
    }
  } else if (eventType === 'task.awaiting_approval') {
    if (!isString(payload.changeSetId)) {
      throw new ContractValidationError('awaiting_approval 缺少 changeSetId')
    }
  } else if (eventType === 'task.failed') {
    if (!isString(payload.code) || !isString(payload.message)) {
      throw new ContractValidationError('failed 缺少 code/message')
    }
  }
}
