import { apiBaseUrl } from '@/config/runtime'
import type { TaskEvent } from '@/types/agent'

export function subscribeTaskEvents(
  taskId: string,
  onEvent: (event: TaskEvent) => void,
  onError: (error: Event) => void,
): () => void {
  const source = new EventSource(`${apiBaseUrl}/tasks/${taskId}/events`)
  source.addEventListener('task.event', (event: MessageEvent) => onEvent(JSON.parse(event.data)))
  source.addEventListener('error', onError)
  source.addEventListener('stream.end', () => source.close())
  return () => source.close()
}
