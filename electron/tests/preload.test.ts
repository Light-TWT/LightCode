import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { IPC_CHANNELS } from '../src/ipc'

const preloadSrc = readFileSync(resolve(__dirname, '../src/preload.ts'), 'utf8')

describe('sandboxed preload bridge', () => {
  it('keeps the preload self-contained (no local runtime require)', () => {
    // Sandboxed preload scripts cannot `require` local CommonJS files — a
    // runtime `import ... from './ipc'` compiles to `require('./ipc')` which
    // throws "module not found" and leaves window.lightcode undefined.
    // Only a type-only import from ./ipc is allowed.
    const runtimeLocalImport =
      /^\s*import\s+\{(?:[^}]*)\}\s+from\s+'\.\/ipc'/m.test(preloadSrc)
    expect(runtimeLocalImport).toBe(false)
    expect(preloadSrc).toContain("import type { SelectFolderResult } from './ipc'")
  })

  it('inlines the channel values in sync with IPC_CHANNELS', () => {
    for (const channel of Object.values(IPC_CHANNELS)) {
      expect(preloadSrc).toContain(`'${channel}'`)
    }
  })

  it('exposes the API base URL handoff via sendSync', () => {
    expect(preloadSrc).toContain(
      `const GET_API_BASE_URL_CHANNEL = '${IPC_CHANNELS.getApiBaseUrl}'`,
    )
    expect(preloadSrc).toContain('ipcRenderer.sendSync(GET_API_BASE_URL_CHANNEL)')
    expect(preloadSrc).toContain('apiBaseUrl:')
  })
})
