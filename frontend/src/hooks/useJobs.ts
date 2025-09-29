import { useMemo } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { fetchJob, fetchJobs } from '../api/jobs'
import { submitDesign } from '../api/design'
import type { DesignRequestPayload, DesignResponsePayload, JobStatusRecord } from '../types'

export function useJobStatus(jobId: string | undefined) {
  return useQuery<JobStatusRecord, Error>({
    queryKey: ['job', jobId],
    queryFn: () => fetchJob(jobId ?? ''),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status) return 2000
      return status === 'succeeded' || status === 'failed' ? false : 2000
    },
  })
}

export function useJobsList(limit = 25, offset = 0) {
  return useQuery<JobStatusRecord[]>({
    queryKey: ['jobs', limit, offset],
    queryFn: () => fetchJobs(limit, offset),
    staleTime: 1000 * 10,
  })
}

export function useDesignSubmit() {
  const mutation = useMutation<DesignResponsePayload, unknown, DesignRequestPayload>({
    mutationFn: submitDesign,
  })

  return useMemo(() => ({
    submit: mutation.mutate,
    submitAsync: mutation.mutateAsync,
    ...mutation,
  }), [mutation])
}
