import { afterEach, describe, expect, it, vi } from 'vitest'
import { providerService } from './provider.service'

const settingsPayload = {
  configured: true,
  status: 'ready',
  provider: 'openai-compatible',
  modelId: 'demo-model',
  detail: 'Provider 已就绪。',
  originAllowlisted: true,
  transport: 'https',
}

const healthPayload = {
  status: 'ready',
  provider: 'openai-compatible',
  modelId: 'demo-model',
  detail: 'ok',
  capabilities: {
    tools: ['read_file'],
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

function stubFetch(payload: unknown) {
  const fetchMock = vi.fn(async () => ({
    ok: true,
    json: async () => payload,
  }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('providerService（HTTP-only）', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('GET /provider/health', async () => {
    const fetchMock = stubFetch(healthPayload)
    const health = await providerService.getHealth()
    expect(String(fetchMock.mock.calls[0][0])).toContain('/provider/health')
    expect(health.status).toBe('ready')
    expect(health.capabilities.tools).toEqual(['read_file'])
  })

  it('GET /provider/settings 返回安全视图，响应不含 key/baseUrl', async () => {
    const fetchMock = stubFetch(settingsPayload)
    const settings = await providerService.getSettings()
    expect(String(fetchMock.mock.calls[0][0])).toContain('/provider/settings')
    expect(settings.configured).toBe(true)
    expect(settings.status).toBe('ready')
    // 安全不变量：设置响应绝不含凭据或完整 URL
    expect(JSON.stringify(settings)).not.toMatch(/apiKey|baseUrl|sk-|Bearer/i)
  })

  it('POST /provider/settings/test 请求体与 ProviderTestRequest 严格一致（extra=forbid）', async () => {
    const fetchMock = stubFetch({ ok: true, code: '', detail: '' })
    const resp = await providerService.testConnection({
      provider: 'openai-compatible',
      baseUrl: 'https://api.example.com/v1',
      apiKey: 'sk-test-secret',
      modelId: 'demo-model',
    })
    expect(resp.ok).toBe(true)
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/provider/settings/test')
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body as string)
    // 后端 ProviderTestRequest 为 extra=forbid：字段严格一致，无多余字段
    expect(Object.keys(body).sort()).toEqual(['apiKey', 'baseUrl', 'modelId', 'provider'])
  })

  it('POST /provider/settings 测试并保存，响应无 key/baseUrl', async () => {
    const fetchMock = stubFetch(settingsPayload)
    const settings = await providerService.saveSettings({
      provider: 'openai-compatible',
      baseUrl: 'https://api.example.com/v1',
      apiKey: 'sk-test-secret',
      modelId: 'demo-model',
    })
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/provider/settings')
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body as string)
    expect(Object.keys(body).sort()).toEqual(['apiKey', 'baseUrl', 'modelId', 'provider'])
    expect(settings.status).toBe('ready')
    expect(JSON.stringify(settings)).not.toContain('sk-test-secret')
  })

  it('DELETE /provider/settings 清除运行期配置', async () => {
    const fetchMock = stubFetch({ ...settingsPayload, configured: false })
    const settings = await providerService.clearSettings()
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/provider/settings')
    expect(init.method).toBe('DELETE')
    expect(settings.configured).toBe(false)
  })
})
