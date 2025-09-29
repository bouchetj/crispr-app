import { post } from './client'
import type { DesignRequestPayload, DesignResponsePayload } from '../types'

export function submitDesign(payload: DesignRequestPayload) {
  return post<DesignResponsePayload>('/api/design', payload)
}
