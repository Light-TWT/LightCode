import { apiBaseUrl } from '@/config/runtime'
import { ContractValidationError } from '@/contracts/real-task.schema'

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? response.statusText)
  }
  return response.json() as Promise<T>
}

/** 同 requestJson，但在解析后对载荷做运行时契约校验，失败抛出
 *  ContractValidationError（协议不兼容），绝不把畸形数据送入状态机。 */
export async function requestJsonValidated<T>(
  path: string,
  init: RequestInit | undefined,
  parse: (raw: unknown) => T,
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? response.statusText)
  }
  const raw = await response.json()
  try {
    return parse(raw)
  } catch (err) {
    if (err instanceof ContractValidationError) throw err
    throw new ContractValidationError(`响应契约校验失败: ${String(err)}`)
  }
}
