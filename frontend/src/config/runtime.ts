export const apiBaseUrl = import.meta.env.VITE_LIGHTCODE_API_BASE_URL
  ?? 'http://127.0.0.1:8000/api/v1'

/** 单一事实来源：是否运行在真实 API 模式（否则为 Mock 演示模式） */
export const isApiMode = import.meta.env.VITE_LIGHTCODE_RUNTIME === 'api'
