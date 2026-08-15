/**
 * Preload bridge. Runs in a sandboxed renderer and exposes a single, narrow,
 * typed API to the web content. Node globals, the filesystem, shell, raw
 * ipcRenderer and path strings are never exposed.
 */

import { contextBridge, ipcRenderer } from 'electron'
import type { SelectFolderResult } from './ipc'

// Sandboxed preload scripts run with a polyfilled `require` that only supports a
// fixed subset of Electron/Node built-ins — it CANNOT load local CommonJS files
// (relative `require('./ipc')` throws "module not found"). Keep this module
// self-contained; the channel constants are intentionally inlined instead of
// imported from ./ipc. Must stay in sync with `IPC_CHANNELS` in ./ipc.
const SELECT_WORKSPACE_FOLDER_CHANNEL = 'lightcode:select-workspace-folder'
const GET_API_BASE_URL_CHANNEL = 'lightcode:get-api-base-url'

const lightcode = {
  workspace: {
    selectFolder: (): Promise<SelectFolderResult> =>
      ipcRenderer.invoke(SELECT_WORKSPACE_FOLDER_CHANNEL) as Promise<SelectFolderResult>,
  },
  // The sidecar runs on a loopback port chosen per-launch by main. The renderer
  // needs that URL synchronously at module load, so main returns it via
  // sendSync before the page loads (a one-time, path-free loopback URL).
  apiBaseUrl: ipcRenderer.sendSync(GET_API_BASE_URL_CHANNEL) as string,
}

contextBridge.exposeInMainWorld('lightcode', lightcode)

export type LightCodeBridge = typeof lightcode