import { apiBaseUrl } from '@/config/runtime'
import { parseTaskEvent } from '@/contracts/real-task.schema'
import type { TaskEvent } from '@/types/agent'

export interface SubscribeOptions {
  /** 断点续传：只回放 sequence 大于该值的事件（对应后端 ?after_sequence=） */
  afterSequence?: number
  /** 是否让后端在回放后继续 tail 轮询（对应 ?tail=true） */
  tail?: boolean
  /** 服务端正常结束（stream.end，含 tail 超时）时回调；不用于网络错误重试 */
  onEnd?: () => void
}

function buildEventUrl(basePath: string, options?: SubscribeOptions): string {
  const params = new URLSearchParams()
  if (options?.afterSequence && options.afterSequence > 0) {
    params.set('after_sequence', String(options.afterSequence))
  }
  if (options?.tail) {
    params.set('tail', 'true')
  }
  const query = params.toString()
  return `${apiBaseUrl}${basePath}${query ? `?${query}` : ''}`
}

function subscribe(
  basePath: string,
  onEvent: (event: TaskEvent) => void,
  onError: (error: Event) => void,
  options?: SubscribeOptions,
): () => void {
  // 浏览器断线自动重连时会自带 Last-Event-ID 头（后端 SSE 帧含 id: 字段），
  // 首次连接的续传位置通过 after_sequence 查询参数显式传入。
  const source = new EventSource(buildEventUrl(basePath, options))
  source.addEventListener('task.event', (event: MessageEvent) => {
    try {
      const parsed = parseTaskEvent(JSON.parse(event.data))
      onEvent(parsed as TaskEvent)
    } catch {
      // 畸形事件：丢弃而非污染状态机
    }
  })
  source.addEventListener('error', onError)
  source.addEventListener('stream.end', () => {
    source.close()
    options?.onEnd?.()
  })
  source.addEventListener('stream.error', () => {
    source.close()
    onError(new Event('stream.error'))
  })
  return () => source.close()
}

/** Phase 0.5 Mock 任务事件流：GET /tasks/{id}/events */
export function subscribeTaskEvents(
  taskId: string,
  onEvent: (event: TaskEvent) => void,
  onError: (error: Event) => void,
  options?: SubscribeOptions,
): () => void {
  return subscribe(`/tasks/${taskId}/events`, onEvent, onError, options)
}

/** Phase 1 真实任务事件流：GET /real-tasks/{id}/events（支持续传） */
export function subscribeRealTaskEvents(
  taskId: string,
  onEvent: (event: TaskEvent) => void,
  onError: (error: Event) => void,
  options?: SubscribeOptions,
): () => void {
  return subscribe(`/real-tasks/${taskId}/events`, onEvent, onError, options)
}
