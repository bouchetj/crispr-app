import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Badge,
  Button,
  Paper,
  Group,
  Loader,
  Stack,
  Text,
  Title,
  Box,
} from '@mantine/core'
import { IconArrowLeft } from '@tabler/icons-react'
import { MantineReactTable, type MRT_ColumnDef, useMantineReactTable, MRT_BottomToolbar } from 'mantine-react-table'
import { useJobsList } from '../hooks/useJobs'
import type { JobStatusRecord } from '../types'

export function PreviousRunsPage() {
  const navigate = useNavigate()
  const { data, isLoading, isError } = useJobsList(50)
  const jobs = data ?? []

  const columns = useMemo<MRT_ColumnDef<JobStatusRecord>[]>(() => [
    {
      id: 'jobId',
      header: 'Job ID',
      accessorKey: 'job_id',
      Cell: ({ cell }) => <Text ff="monospace">{cell.getValue<string>()}</Text>,
      enableClickToCopy: true,
    },
    {
      id: 'status',
      header: 'Status',
      accessorKey: 'status',
      Cell: ({ cell }) => {
        const status = cell.getValue<JobStatusRecord['status']>()
        const color =
          status === 'succeeded'
            ? 'green'
            : status === 'failed'
            ? 'red'
            : status === 'running'
            ? 'blue'
            : 'gray'
        return <Badge color={color}>{status}</Badge>
      },
    },
    {
      id: 'message',
      header: 'Message',
      accessorKey: 'message',
      Cell: ({ cell }) => <Text>{cell.getValue<string | null>() ?? '—'}</Text>,
    },
    {
      id: 'created',
      header: 'Created',
      accessorKey: 'created_at',
      Cell: ({ cell }) => <Text>{cell.getValue<string>()}</Text>,
    },
  ], [])

  const table = useMantineReactTable({
    columns,
    data: jobs,
    initialState: { density: 'xs' },
    renderBottomToolbar: ({ table }) => (<Box w="100%" ta="right" px="md" py="sm"><MRT_BottomToolbar table={table} /></Box>),
    enableColumnActions: false,
    enableColumnFilters: false,
    enableSorting: false,
    enableTopToolbar: false,
    mantineTableBodyRowProps: ({ row }) => ({
      onClick: () => navigate(`/jobs/${row.original.job_id}`),
      style: { cursor: 'pointer' },
    }),
    mantinePaperProps: {
      shadow: 'none',
      withBorder: false,
      radius: 'md',
      style: { backgroundColor: 'transparent' },
    },
    mantineTableProps: {
      striped: true,
      highlightOnHover: true,
    },
  })

  return (
    <Stack gap="xl">

      <Group justify="flex-start" align="center">

        <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => navigate(-1)}>
          Back
        </Button>

        <Stack gap={4}>
          <Title order={2}>Previous runs</Title>
          <Text c="dimmed">Select a job to view its current status or results.</Text>
        </Stack>

      </Group>

      <Paper shadow="sm" radius="xl" p="xl" withBorder>

        {isLoading ? (
          <Group>
            <Loader size="sm" />
            <Text>Loading jobs...</Text>
          </Group>
        ) : isError ? (
          <Text color="red">Unable to load jobs. Please try again later.</Text>
        ) : jobs.length > 0 ? (
          <MantineReactTable table={table} />
        ) : (
          <Text c="dimmed">No jobs have been submitted yet.</Text>
        )}

      </Paper>

    </Stack>
  )
}
