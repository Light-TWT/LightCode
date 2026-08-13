import { describe, expect, it } from 'vitest'
import { generateToken, waitForHealth } from '../src/sidecar'

describe('sidecar helpers', () => {
  it('generates a random per-launch token', () => {
    const a = generateToken()
    const b = generateToken()
    expect(a).toMatch(/^[0-9a-f]{48}$/)
    expect(a).not.toBe(b)
  })

  it('returns once the health endpoint responds ok', async () => {
    const fetchFn = async () => new Response('{"status":"ok"}', { status: 200 })
    await expect(waitForHealth(8123, '127.0.0.1', 2000, fetchFn)).resolves.toBeUndefined()
  })

  it('rejects when the sidecar never becomes healthy', async () => {
    const fetchFn = async () => new Response('down', { status: 503 })
    await expect(waitForHealth(8123, '127.0.0.1', 700, fetchFn)).rejects.toThrow(
      'sidecar did not become healthy',
    )
  })
})