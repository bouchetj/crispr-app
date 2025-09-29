import { useNavigate, useParams } from 'react-router-dom'
import {
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  Stack,
  Text,
  Title,
  CopyButton,
} from '@mantine/core'
import { IconArrowLeft, IconCopy, IconCheck } from '@tabler/icons-react'
import { JobDetailInProgress } from '../components/JobDetailInProgress'
import { JobDetailResults } from '../components/JobDetailResults'
import { useJobStatus } from '../hooks/useJobs'
import type { Guide } from '../types'

export function JobDetailPage() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const { data: job, isLoading, isError, error } = useJobStatus(jobId)

  if (isLoading) {
    return (
      <Stack gap="lg">
        <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => navigate(-1)}>
          Back
        </Button>
        <Group gap="md">
          <Loader />
          <Text>Loading job details...</Text>
        </Group>
      </Stack>
    )
  }

  if (isError || !job) {
    return (
      <Stack gap="lg">
        <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => navigate(-1)}>
          Back
        </Button>
        <Alert color="red" title="Unable to load job">
          {error instanceof Error ? error.message : 'Something went wrong while fetching the job.'}
        </Alert>
      </Stack>
    )
  }

  const isCompleted = job.status === 'succeeded'
  const guides: Guide[] = job.result?.guides ?? []
  const progressValue = job.progress != null ? Math.round(job.progress * 100) : undefined
  return (
    <Stack gap="xl">

      <Group justify="space-between" align="center">

        <Button variant='subtle' leftSection={<IconArrowLeft size={16} />} onClick={() => navigate(-1)}>
          Back
        </Button>

        <Stack gap={4} align="flex-start">
          <Group gap="xs" align="center">
            <Title order={2}>Job</Title>
            <CopyButton value={job.job_id} timeout={1000}>
              {({ copied, copy }) => (
                <Badge
                  variant="light"
                  size="xl"
                  radius="sm"
                  onClick={copy}
                  rightSection={copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                  style={{ cursor: 'pointer' }}
                  title={copied ? 'Copied!' : 'Copy job ID'}
                  component="button"
                  type="button"
                >
                  {job.job_id}
                </Badge>
              )}
            </CopyButton>
          </Group>
          <Group gap="sm">
            <Badge color={isCompleted ? 'green' : job.status === 'failed' ? 'red' : 'blue'}>{job.status}</Badge>
            {job.message && <Text c="dimmed">{job.message}</Text>}
          </Group>
        </Stack>

        <Text size="sm" c="dimmed">Created at: {job.created_at}</Text>
      </Group>

      {!isCompleted ? <JobDetailInProgress job={job} progressValue={progressValue} /> : <JobDetailResults guides={guides} />}
      
    </Stack>
  )
}
