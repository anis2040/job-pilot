import { describe, expect, it } from 'vitest'
import { shouldFetchFullDescription } from '@/utils/jobDescription'

describe('shouldFetchFullDescription', () => {
  it('fetches when the description is missing', () => {
    expect(shouldFetchFullDescription({ job_id: 'li_1', description: '' })).toBe(true)
  })

  it('fetches short StepStone snippets', () => {
    expect(shouldFetchFullDescription({ job_id: 'ss_1', description: 'Remote work possible' })).toBe(true)
  })

  it('does not refresh non-StepStone descriptions just because they are short', () => {
    expect(shouldFetchFullDescription({ job_id: 'li_1', description: 'Short but final' })).toBe(false)
  })

  it('does not refresh long StepStone descriptions', () => {
    expect(shouldFetchFullDescription({ job_id: 'ss_1', description: 'x'.repeat(600) })).toBe(false)
  })
})
