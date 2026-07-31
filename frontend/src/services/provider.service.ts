import { isApiMode } from '@/config/runtime'
import { requestJson } from '@/services/http'
import type { ProviderHealth } from '@/types/agent'

/** Mock 模式下的 Provider 健康：模型默认关闭，仅描述只读能力，绝不携带 key/baseUrl */
const mockProviderHealth: ProviderHealth = {
  status: 'disabled',
  provider: 'none',
  modelId: '',
  detail: '模型提供方未启用（默认关闭）。',
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
    apiKeyConfigured: false,
    transport: 'none',
    originAllowlisted: false,
    followRedirects: false,
    trustEnvProxies: false,
  },
}

export interface ProviderService {
  /** 读取 Provider 健康状态（config 派生，不发网络请求） */
  getHealth(): Promise<ProviderHealth>
}

export const mockProviderService: ProviderService = {
  async getHealth() {
    return structuredClone(mockProviderHealth)
  },
}

export const httpProviderService: ProviderService = {
  getHealth() {
    return requestJson<ProviderHealth>('/provider/health')
  },
}

export const providerService = isApiMode ? httpProviderService : mockProviderService
