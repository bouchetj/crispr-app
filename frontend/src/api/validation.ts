import { post } from './client'

export type ValidateResponse = {
  length: number
  normalized_sequence: string
  gc_content: number
  warnings: string[]
  errors: string[]
}

export function validateSequence(sequence: string) {
  return post<ValidateResponse>('/api/validate-sequence', { sequence })
}
