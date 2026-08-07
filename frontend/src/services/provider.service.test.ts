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

const profilesPayload = [
  {
    id: 'default',
    name: 'openai-compatible',
    provider: 'openai-compatible',
    modelId: 'demo-model',
    enabled: true,
    status: 'ready',
    baseUrlHost: 'provider.example',
  },
]

describe('providerService（HTTP-only）', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('GET /provider/profiles 返回安全摘要列表，不含 key/完整 URL', async () => {
    const fetchMock = stubFetch(profilesPayload)
    const profiles = await providerService.listProviders()
    expect(String(fetchMock.mock.calls[0][0])).toContain('/provider/profiles')
    expect(profiles.length).toBe(1)
    expect(profiles[0]).toMatchObject({
      id: 'default',
      name: 'openai-compatible',
      provider: 'openai-compatible',
      modelId: 'demo-model',
      enabled: true,
      status: 'ready',
      baseUrlHost: 'provider.example',
    })
    // 安全不变量：无 apiKey、无 sk-、无 Bearer、无完整 https:// 地址
    const raw = JSON.stringify(profiles)
    expect(raw).not.toMatch(/apiKey|sk-|Bearer/i)
    expect(raw).not.toContain('https://')
  })

  it('POST /provider/profiles 请求体与 ProviderProfileCreate 严格一致（extra=forbid）', async () => {
    const fetchMock = stubFetch(profilesPayload[0])
    const created = await providerService.createProvider({
      name: 'DeepSeek',
      provider: 'openai-compatible',
      baseUrl: 'https://api.deepseek.com/v1',
      apiKey: 'sk-test-secret',
      modelId: 'deepseek-chat',
      enabled: true,
    })
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/provider/profiles')
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body as string)
    expect(Object.keys(body).sort()).toEqual([
      'apiKey',
      'baseUrl',
      'enabled',
      'modelId',
      'name',
      'provider',
    ])
    expect(created.id).toBe('default')
    expect(JSON.stringify(created)).not.toContain('sk-test-secret')
    // 安全不变量：响应对象不含 apiKey 字段（baseUrlHost 是合法 hostname 字段）
    expect(Object.keys(created)).not.toContain('apiKey')
    expect(JSON.stringify(created)).not.toContain('https://')
  })

  it('DELETE /provider/profiles/:id', async () => {
    const fetchMock = stubFetch({ ok: true })
    const result = await providerService.deleteProvider('abc123')
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/provider/profiles/abc123')
    expect(init.method).toBe('DELETE')
    expect(result.ok).toBe(true)
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
