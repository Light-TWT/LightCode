/**
 * Preload bridge. Runs in a sandboxed renderer and exposes a single, narrow,
 * typed API to the web content. Node globals, the filesystem, shell, raw
 * ipcRenderer and path strings are never exposed.
 */

import { contextBridge, ipcRenderer } from 'electron'
import { IPC_CHANNELS, type SelectFolderResult } from './ipc'

const lightcode = {
  workspace: {
    selectFolder: (): Promise<SelectFolderResult> =>
      ipcRenderer.invoke(IPC_CHANNELS.selectWorkspaceFolder) as Promise<SelectFolderResult>,
  },
}

contextBridge.exposeInMainWorld('lightcode', lightcode)

export type LightCodeBridge = typeof lightcode