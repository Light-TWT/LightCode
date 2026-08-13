/**
 * Electron main process. Owns the native window, the bundled FastAPI sidecar
 * lifecycle and the Windows folder picker. The renderer stays sandboxed; the
 * only bridge is the typed folder-selection IPC, and the selected folder is
 * sent to the sidecar registration endpoint over the trusted loopback channel.
 */

import { app, BrowserWindow, dialog, ipcMain } from 'electron'
import path from 'node:path'
import {
  IPC_CHANNELS,
  isSafeWorkspaceDto,
  type SelectFolderResult,
} from './ipc'
import {
  chooseFreePort,
  generateToken,
  spawnSidecar,
  waitForHealth,
  type SpawnedSidecar,
} from './sidecar'

const HOST = '127.0.0.1'
let mainWindow: BrowserWindow | null = null
let sidecar: SpawnedSidecar | null = null

export function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      webSecurity: true,
    },
  })
  const devServer = process.env.VITE_DEV_SERVER
  if (devServer) {
    void window.loadURL(devServer)
  } else {
    void window.loadFile(path.join(__dirname, '..', 'frontend-dist', 'index.html'))
  }
  return window
}

function sidecarExecutable(): string {
  const override = process.env.LIGHTCODE_SIDECAR_EXE
  if (override) return override
  return path.join(process.resourcesPath, 'sidecar', 'lightcode-sidecar.exe')
}

export function registerIpc(token: string, port: number): void {
  ipcMain.handle(IPC_CHANNELS.selectWorkspaceFolder, async (): Promise<SelectFolderResult> => {
    if (!mainWindow) return { cancelled: true }
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
    })
    if (result.canceled || !result.filePaths[0]) {
      return { cancelled: true }
    }
    const rootPath = result.filePaths[0]
    try {
      const response = await fetch(`http://${HOST}:${port}/api/v1/desktop/workspaces/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-LightCode-Sidecar-Token': token,
        },
        body: JSON.stringify({ rootPath }),
      })
      const body: unknown = await response.json()
      if (!response.ok || !isSafeWorkspaceDto(body)) {
        return { cancelled: false, error: '工作区注册失败' }
      }
      return { cancelled: false, workspace: body }
    } catch {
      return { cancelled: false, error: '无法连接到本地服务' }
    }
  })
}

app.whenReady().then(async () => {
  const port = await chooseFreePort(HOST)
  const token = generateToken()
  const dataDir = app.getPath('userData')
  sidecar = spawnSidecar({ dataDir, token, port, host: HOST }, sidecarExecutable())
  await waitForHealth(port, HOST, 15000)
  registerIpc(token, port)
  mainWindow = createWindow()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  void sidecar?.stop()
})