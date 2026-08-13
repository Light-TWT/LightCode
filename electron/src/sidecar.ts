/**
 * FastAPI sidecar lifecycle helpers.
 *
 * The sidecar is a loopback-only process. Electron picks a free port and a
 * per-launch token, then spawns the bundled executable with the desktop data
 * root and token injected through the process environment. All failure output
 * is redacted: no absolute path, token or provider secret is logged.
 */

import { spawn, type ChildProcess } from 'node:child_process'
import crypto from 'node:crypto'
import net from 'node:net'

export interface SidecarEnv {
  dataDir: string
  token: string
  port: number
  host: string
}

export interface SpawnedSidecar {
  proc: ChildProcess
  stop: () => Promise<void>
}

export function generateToken(): string {
  return crypto.randomBytes(24).toString('hex')
}

export function chooseFreePort(host = '127.0.0.1'): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.unref()
    server.on('error', reject)
    server.listen(0, host, () => {
      const address = server.address()
      const port = typeof address === 'object' && address ? address.port : 0
      server.close(() => resolve(port))
    })
  })
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function waitForHealth(
  port: number,
  host: string,
  timeoutMs: number,
  fetchFn: typeof fetch = fetch,
): Promise<void> {
  const deadline = Date.now() + timeoutMs
  let lastError: unknown
  while (Date.now() < deadline) {
    try {
      const response = await fetchFn(`http://${host}:${port}/health`)
      if (response.ok) return
      lastError = new Error('sidecar not healthy')
    } catch (error) {
      lastError = error
    }
    await sleep(200)
  }
  throw new Error(lastError ? 'sidecar did not become healthy' : 'sidecar health check timed out')
}

export function spawnSidecar(env: SidecarEnv, exePath: string): SpawnedSidecar {
  const proc = spawn(exePath, [], {
    env: {
      ...process.env,
      LIGHTCODE_DESKTOP_DATA_DIR: env.dataDir,
      LIGHTCODE_SIDECAR_TOKEN: env.token,
      LIGHTCODE_SIDECAR_PORT: String(env.port),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  // Redacted diagnostics: never print the data dir, token or any path.
  proc.stderr?.on('data', () => {})
  proc.stdout?.on('data', () => {})
  return { proc, stop: () => gracefulStop(proc) }
}

async function gracefulStop(proc: ChildProcess, timeoutMs = 4000): Promise<void> {
  if (proc.exitCode !== null || proc.killed) return
  proc.kill()
  const result = await Promise.race([
    new Promise<boolean>((resolve) => proc.once('exit', () => resolve(true))),
    new Promise<boolean>((resolve) => setTimeout(() => resolve(false), timeoutMs)),
  ])
  if (!result) procureForceKill(proc)
}

function procureForceKill(proc: ChildProcess): void {
  try {
    proc.kill('SIGKILL')
  } catch {
    // Already gone.
  }
}