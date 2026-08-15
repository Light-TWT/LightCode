import { afterEach, describe, expect, it } from 'vitest'

interface LightcodeStub {
  lightcode?: { workspace?: unknown; apiBaseUrl?: string }
}

afterEach(() => {
  delete (window as LightcodeStub).lightcode
})

describe('runtime apiBaseUrl resolution', () => {
  it('uses the Electron bridge base URL when present (desktop sidecar port)', async () => {
    ;(window as LightcodeStub).lightcode = {
      workspace: {},
      apiBaseUrl: 'http://127.0.0.1:54321/api/v1',
    }
    const mod = await import('./runtime?bridge=1')
    expect(mod.apiBaseUrl).toBe('http://127.0.0.1:54321/api/v1')
  })

  it('falls back to the development default without a desktop bridge', async () => {
    const mod = await import('./runtime?nobridge=1')
    expect(mod.apiBaseUrl).toBe('http://127.0.0.1:8000/api/v1')
  })

  it('ignores an empty bridge apiBaseUrl', async () => {
    ;(window as LightcodeStub).lightcode = { workspace: {}, apiBaseUrl: '' }
    const mod = await import('./runtime?empty=1')
    expect(mod.apiBaseUrl).toBe('http://127.0.0.1:8000/api/v1')
  })
})
