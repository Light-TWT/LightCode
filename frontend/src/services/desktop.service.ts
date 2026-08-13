import type { RegisteredWorkspace } from '@/types/agent'

/**
 * Typed adapter over the Electron preload bridge (`window.lightcode`).
 *
 * The renderer never receives a path; a successful folder selection returns a
 * path-free {@link RegisteredWorkspace}. In a plain browser (non-desktop) this
 * adapter reports itself unavailable and callers degrade gracefully.
 */

export interface SelectFolderResultCancel {
  cancelled: true
}

export interface SelectFolderResultError {
  cancelled: false
  error: string
}

export interface SelectFolderResultOk {
  cancelled: false
  workspace: RegisteredWorkspace
}

export type SelectFolderResult =
  | SelectFolderResultCancel
  | SelectFolderResultError
  | SelectFolderResultOk

interface DesktopBridge {
  workspace: {
    selectFolder: () => Promise<SelectFolderResult>
  }
}

interface WindowWithBridge {
  lightcode?: DesktopBridge
}

export function isDesktopAvailable(): boolean {
  if (typeof window === 'undefined') return false
  const bridge = (window as WindowWithBridge).lightcode
  return Boolean(bridge?.workspace?.selectFolder)
}

export async function selectFolder(): Promise<SelectFolderResult | null> {
  if (!isDesktopAvailable()) return null
  return (window as WindowWithBridge).lightcode!.workspace.selectFolder()
}