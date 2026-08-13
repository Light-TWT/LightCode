import { describe, expect, it, vi } from 'vitest'
import { isDesktopAvailable, selectFolder } from '@/services/desktop.service'

describe('desktop.service（桌面桥接）', () => {
  it('reports unavailable when no preload bridge exists', () => {
    expect(isDesktopAvailable()).toBe(false)
  })

  it('reports available when window.lightcode exposes selectFolder', () => {
    ;(window as unknown as { lightcode: unknown }).lightcode = {
      workspace: { selectFolder: vi.fn() },
    }
    expect(isDesktopAvailable()).toBe(true)
    delete (window as unknown as { lightcode?: unknown }).lightcode
  })

  it('returns null when the bridge is unavailable', async () => {
    expect(await selectFolder()).toBeNull()
  })
})