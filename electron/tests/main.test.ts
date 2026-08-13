import { beforeEach, describe, expect, it, vi } from 'vitest'

const browserWindowOpts: unknown[] = []
const handledChannels: string[] = []

vi.mock('electron', () => ({
  app: {
    getPath: () => 'C:\\fake\\userData',
    whenReady: () => ({ then: () => ({}) }),
    on: vi.fn(),
    quit: vi.fn(),
  },
  BrowserWindow: class {
    constructor(opts: unknown) {
      browserWindowOpts.push(opts)
    }
    loadURL(): void {}
    loadFile(): void {}
  },
  dialog: { showOpenDialog: vi.fn() },
  ipcMain: {
    handle: (channel: string) => {
      handledChannels.push(channel)
    },
  },
}))

import { createWindow, registerIpc } from '../src/main'

describe('Electron main security boundary', () => {
  beforeEach(() => {
    browserWindowOpts.length = 0
    handledChannels.length = 0
  })

  it('creates a sandboxed window with node integration disabled', () => {
    createWindow()
    expect(browserWindowOpts).toHaveLength(1)
    const opts = browserWindowOpts[0] as {
      webPreferences: {
        contextIsolation: boolean
        sandbox: boolean
        nodeIntegration: boolean
        webSecurity: boolean
      }
    }
    expect(opts.webPreferences.contextIsolation).toBe(true)
    expect(opts.webPreferences.sandbox).toBe(true)
    expect(opts.webPreferences.nodeIntegration).toBe(false)
    expect(opts.webPreferences.webSecurity).toBe(true)
  })

  it('registers only the narrow folder-selection channel', () => {
    registerIpc('tok', 8123)
    expect(handledChannels).toEqual(['lightcode:select-workspace-folder'])
  })
})