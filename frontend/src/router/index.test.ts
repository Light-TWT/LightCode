import { describe, expect, it } from 'vitest'
import { createAppHistory } from './index'

describe('router history', () => {
  it('uses hash history for file protocol desktop loads', () => {
    const history = createAppHistory('file:')

    expect(history.createHref('/')).toContain('#/')
  })
})
