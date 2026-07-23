import { describe, expect, it, vi } from 'vitest'
import { requestJson } from './http'

describe('requestJson', () => {
  it('throws the API detail for a failed response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Workspace not found: missing' }),
      { status: 404, headers: { 'content-type': 'application/json' } },
    )))

    await expect(requestJson('/workspaces/missing')).rejects.toThrow(
      'Workspace not found: missing',
    )
  })
})
