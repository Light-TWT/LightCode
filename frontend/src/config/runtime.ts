/**
 * API base URL resolution.
 *
 * In the Electron desktop shell the FastAPI sidecar listens on a loopback port
 * chosen per-launch by Electron main. The preload bridge exposes that URL
 * synchronously as `window.lightcode.apiBaseUrl` (path-free, loopback only), so
 * the renderer must prefer it over any baked-in default. In a plain browser
 * (dev server / static hosting) it falls back to the build-time env value and
 * then to the development default.
 */
interface DesktopBridge {
  workspace: unknown
  apiBaseUrl?: string
}

interface WindowWithBridge {
  lightcode?: DesktopBridge
}

function desktopApiBaseUrl(): string | null {
  if (typeof window === 'undefined') return null
  const bridge = (window as WindowWithBridge).lightcode
  if (bridge && typeof bridge.apiBaseUrl === 'string' && bridge.apiBaseUrl) {
    return bridge.apiBaseUrl
  }
  return null
}

export const apiBaseUrl =
  desktopApiBaseUrl() ??
  import.meta.env.VITE_LIGHTCODE_API_BASE_URL ??
  'http://127.0.0.1:8000/api/v1'
