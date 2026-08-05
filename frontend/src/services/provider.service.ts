import { requestJson } from '@/services/http'
import type {
  ProviderHealth,
  ProviderSettingsInput,
  ProviderSettingsResponse,
  ProviderTestResponse,
} from '@/types/agent'

export interface ProviderService {
  /** 读取 Provider 健康状态（config 派生，不发网络请求） */
  getHealth(): Promise<ProviderHealth>
  /** GET /provider/settings —— 安全视图（无 key、无完整 baseUrl） */
  getSettings(): Promise<ProviderSettingsResponse>
  /** POST /provider/settings —— 测试并保存运行期凭据；失败返回 {code, message} 错误体 */
  saveSettings(input: ProviderSettingsInput): Promise<ProviderSettingsResponse>
  /** POST /provider/settings/test —— 只测试连接，不保存 */
  testConnection(input: ProviderSettingsInput): Promise<ProviderTestResponse>
  /** DELETE /provider/settings —— 清除运行期凭据（回退到环境变量配置） */
  clearSettings(): Promise<ProviderSettingsResponse>
}

export const providerService: ProviderService = {
  getHealth() {
    return requestJson<ProviderHealth>('/provider/health')
  },

  getSettings() {
    return requestJson<ProviderSettingsResponse>('/provider/settings')
  },

  saveSettings(input) {
    // 请求体与后端 ProviderSettingsRequest 严格一致（extra=forbid），
    // 不含 rootPath/filePath/patch/command；响应绝不含 key/baseUrl。
    return requestJson<ProviderSettingsResponse>('/provider/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: input.provider,
        baseUrl: input.baseUrl,
        apiKey: input.apiKey,
        modelId: input.modelId,
      }),
    })
  },

  testConnection(input) {
    return requestJson<ProviderTestResponse>('/provider/settings/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: input.provider,
        baseUrl: input.baseUrl,
        apiKey: input.apiKey,
        modelId: input.modelId,
      }),
    })
  },

  clearSettings() {
    return requestJson<ProviderSettingsResponse>('/provider/settings', { method: 'DELETE' })
  },
}
