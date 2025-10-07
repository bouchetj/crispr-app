import { Badge, Box, Paper, Stack, Text, Title, Tooltip } from '@mantine/core'
import { BarChart } from '@mantine/charts'
import { MantineReactTable, type MRT_ColumnDef, useMantineReactTable, MRT_BottomToolbar } from 'mantine-react-table'
import { useMemo } from 'react'
import type { Guide } from '../types'

function MismatchBinsChart({ bins }: { bins?: number[] }) {
  if (!bins || bins.length === 0) {
    return <Text span c="dimmed">—</Text>
  }

  const values = bins.slice(0, 5)
  const data = values.map((count, idx) => ({ bucket: `${idx}`, count }))
  const tooltipLabel = values
    .map((count, idx) => `${idx}: ${count}`)
    .join(', ')

  return (
    <Tooltip label={tooltipLabel} withArrow position="top">
      <Box w={100} h={80}>
        <BarChart
          h={75}
          data={data}
          dataKey="bucket"
          withTooltip={false}
          series={[{ name: 'count', color: 'blue.6' }]}
          barProps={{ barSize: 8, radius: 2 }}
          tickLine="none"
          withYAxis={false}
        />
      </Box>
    </Tooltip>
  )
}

function SpecificityBadge({ value }: { value?: number }) {
  if (value == null || Number.isNaN(value)) {
    return <Text c="dimmed">—</Text>
  }

  const val = Math.round(Math.min(Math.max(100 * value, 0), 100))
  let gradient: { from: string; to: string }

  if (val < 40) {
    gradient = { from: 'red.6', to: 'red.8' }
  } else if (val < 60) {
    gradient = { from: 'orange.6', to: 'orange.8' }
  } else if (val < 80) {
    gradient = { from: 'yellow.5', to: 'yellow.7' }
  } else {
    gradient = { from: 'teal.5', to: 'green.6' }
  }

  return (
    <Badge variant="gradient" gradient={gradient} tt="none" fw={600} px={10}>
      {val}
    </Badge>
  )
}

function Rs3Badge({ value }: { value?: number }) {
  if (value == null || Number.isNaN(value)) {
    return <Text c="dimmed">—</Text>
  }

  let gradient: { from: string; to: string }

  if (value <= -1) {
    gradient = { from: 'red.6', to: 'red.8' }
  } else if (value <= -0.5) {
    gradient = { from: 'orange.6', to: 'orange.8' }
  } else if (value < 0.5) {
    gradient = { from: 'gray.5', to: 'gray.7' }
  } else if (value < 1.0) {
    gradient = { from: 'teal.5', to: 'green.6' }
  } else {
    gradient = { from: 'teal.5', to: 'indigo.6' }
  }

  return (
    <Badge variant="gradient" gradient={gradient} tt="none" fw={600} px={10}>
      {value.toFixed(2)}
    </Badge>
  )
}

function GuidesTable({ guides }: { guides: Guide[] }) {
  if (!guides || guides.length === 0) {
    return <Text c="dimmed">No guides were returned for this job.</Text>
  }

  const columns = useMemo<MRT_ColumnDef<Guide>[]>(() => [
    {
      id: 'guide',
      header: 'Guide',
      accessorFn: (row) => `${row.protospacer}${row.pam}`,
      Cell: ({ row }) => {
        const guideSequence = `${row.original.protospacer}${row.original.pam}`
        return (
          <Text ff="monospace" fw={500}>
            {guideSequence}
          </Text>
        )
      },
      enableClickToCopy: true,
    },
    {
      id: 'strand',
      header: 'Strand',
      accessorKey: 'strand',
      Cell: ({ cell }) => {
        const value = cell.getValue<'+' | '-' | null | undefined>()
        return <Text ta="center">{value ?? '—'}</Text>
      },
    },
    {
      id: 'cutSite',
      header: 'Cut Site',
      accessorKey: 'cut_site',
      Cell: ({ cell }) => {
        const value = cell.getValue<number | null | undefined>()
        return <Text ta="center">{value ?? '—'}</Text>
      },
    },
    {
      id: 'specificity',
      header: 'Specificity (CFD)',
      accessorKey: 'specificity',
      Cell: ({ row }) => (
        <Box ta="center">
          <SpecificityBadge value={row.original.specificity} />
        </Box>
      ),
    },
    {
      id: 'rs3',
      header: 'Efficiency (RS3)',
      accessorKey: 'rs3_score',
      Cell: ({ row }) => (
        <Box ta="center">
          <Rs3Badge value={row.original.rs3_score} />
        </Box>
      ),
    },
    {
      id: 'perfectHits',
      header: 'Perfect hits',
      accessorKey: 'num_perfect_sites',
      Cell: ({ cell }) => {
        const value = cell.getValue<number | null | undefined>()
        return <Text ta="center">{value ?? '—'}</Text>
      },
    },
    {
      id: 'nonBulged',
      header: 'Non-bulged mismatches',
      accessorFn: (row) => {
        const offTargets = row.off_targets
        if (!offTargets) {
          return null
        }
        return Math.max(offTargets.num_hits - offTargets.num_bulged_hits, 0)
      },
      Cell: ({ cell }) => {
        const value = cell.getValue<number | null>()
        return <Text ta="center">{value ?? '—'}</Text>
      },
    },
    {
      id: 'mismatchBins',
      header: 'Mismatch Bins',
      accessorFn: (row) => row.off_targets?.mismatch_bins,
      Cell: ({ row }) => (
        <Box ta="center">
          <MismatchBinsChart bins={row.original.off_targets?.mismatch_bins} />
        </Box>
      ),
    },
    {
      id: 'bulged',
      header: 'Bulged mismatches',
      accessorFn: (row) => row.off_targets?.num_bulged_hits,
      Cell: ({ cell }) => {
        const value = cell.getValue<number | null>()
        return <Text ta="center">{value ?? '—'}</Text>
      },
    },
  ], [])

  const table = useMantineReactTable({
    columns,
    data: guides,
    initialState: { density: 'xs' },
    renderBottomToolbar: ({ table }) => (<Box w="100%" ta="right" px="md" py="sm"><MRT_BottomToolbar table={table} /></Box>),
    enableTopToolbar: false,
    enableColumnActions: false,
    enableColumnFilters: false,
    enableSorting: false,
    mantineTableProps: {
      striped: true,
      highlightOnHover: true,
    },
    mantinePaperProps: {
      shadow: 'none',
      withBorder: false,
      radius: 'md',
      style: { backgroundColor: 'transparent' },
    },
    defaultColumn: {
    minSize: 10,
    maxSize: 200,
    size: 50,
  },
  })

  return <MantineReactTable table={table} />
}

interface JobDetailResultsProps {
  guides: Guide[]
}

export function JobDetailResults({ guides }: JobDetailResultsProps) {
  return (
    <Paper shadow="sm" radius="xl" p="xl" withBorder>

      <Stack gap="lg">

        <Stack gap={4}>
          <Title order={3}>Results</Title>
        </Stack>

        <GuidesTable guides={guides} />

      </Stack>

    </Paper>
  )
}
