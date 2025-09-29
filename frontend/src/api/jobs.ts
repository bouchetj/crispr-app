import { get } from './client'
import type { JobStatusRecord } from '../types'

export function fetchJob(jobId: string) {
  return get<JobStatusRecord>(`/api/jobs/${jobId}`)
}

export function fetchJobs(limit = 25, offset = 0) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  return get<JobStatusRecord[]>(`/api/jobs?${params.toString()}`)
}
