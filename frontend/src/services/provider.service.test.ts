import { afterEach, describe, expect, it, vi } from 'vitest'
import { httpProviderService, mockProviderService } from './provider.service'

describe('mockProviderService', () => {
  it('reports disabled status with read-only capabilities and no key', async () => {
    const health = await mockProviderService.getHealth()

    expect(health.status).toBe('disabled')
    expect(health.security.apiKeyConfigured).toBe(false)
    expect(health.security.transport).toBe('none')
    expect(health.capabilities.canWriteFiles).toBe(false)
    expect(health.capabilities.canRunCommands).toBe(false)
    expect(health.capabilities.tools).toEqual(['read_file', 'search_files'])
  })
})

describe('httpProviderService', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  function stubFetch(payload: unknown) {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => payload,
    }))
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('fetches GET /provider/health and returns the parsed payload', async () => {
    const payload = {
      status: 'ready',
      provider: 'openai-compatible',
      modelId: 'demo-model',
      detail: 'ok',
      capabilities: {
        tools: ['read_file', 'search_files'],
        canWriteFiles: false,
        canRunCommands: false,
        maxToolRounds: 8,
        maxRequestsPerTask: 10,
        maxInputBytes: 262144,
        maxOutputTokens: 2048,
        maxConcurrentTasks: 1,
      },
      security: {
        apiKeyConfigured: true,
        transport: 'https',
        originAllowlisted: true,
        followRedirects: false,
        trustEnvProxies: false,
      },
    }
    const fetchMock = stubFetch(payload)

    const health = await httpProviderService.getHealth()

    const [url, maybeInit] = fetchMock.mock.calls[0] as unknown as [string, RequestInit | undefined]
    expect(url).toContain('/provider/health')
    expect(maybeInit?.method ?? 'GET').toBe('GET')
    expect(health.status).toBe('ready')
    expect(health.modelId).toBe('demo-model')
  })
})
