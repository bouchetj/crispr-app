import { Badge, Box, Paper, ScrollArea, Stack, Table, Text, Title, Tooltip } from '@mantine/core'
import { BarChart } from '@mantine/charts'
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

  const val = Math.round(Math.min(Math.max(value, 0), 100))
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

  return (
    <ScrollArea>
      <Table striped highlightOnHover verticalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Guide</Table.Th>
            <Table.Th ta="center">Strand</Table.Th>
            <Table.Th ta="center">Cut site</Table.Th>
            <Table.Th ta="center">Specificity (CFD)</Table.Th>
            <Table.Th ta="center">Efficiency (RS3)</Table.Th>
            <Table.Th ta="center">Perfect hits</Table.Th>
            <Table.Th ta="center">Non-bulged mismatches</Table.Th>
            <Table.Th ta="center">Mismatch bins</Table.Th>
            <Table.Th ta="center">Bulged mismatches</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {guides.map((guide, idx) => {
            const guideSequence = `${guide.protospacer}${guide.pam}`
            const offTargets = guide.off_targets
            const nonBulged = offTargets ? Math.max(offTargets.num_hits - offTargets.num_bulged_hits, 0) : null

            return (
              <Table.Tr key={`${guide.protospacer}-${guide.pam}-${guide.rank ?? idx}`}>
                <Table.Td>
                  <Text ff="monospace" fw={500}>
                    {guideSequence}
                  </Text>
                </Table.Td>
                <Table.Td ta="center">{guide.strand}</Table.Td>
                <Table.Td ta="center">{guide.cut_site}</Table.Td>
                <Table.Td ta="center">
                  <SpecificityBadge value={guide.specificity} />
                </Table.Td>
                <Table.Td ta="center">
                  <Rs3Badge value={guide.rs3_score} />
                </Table.Td>
                <Table.Td ta="center">{guide.num_perfect_sites}</Table.Td>
                <Table.Td ta="center">{nonBulged ?? '—'}</Table.Td>
                <Table.Td ta="center">
                  <MismatchBinsChart bins={offTargets?.mismatch_bins} />
                </Table.Td>
                <Table.Td ta="center">{offTargets?.num_bulged_hits ?? '—'}</Table.Td>
              </Table.Tr>
            )
          })}
        </Table.Tbody>
      </Table>
    </ScrollArea>
  )
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
          <Text c="dimmed">Guides and summary are displayed below.</Text>
        </Stack>

        <GuidesTable guides={guides} />

      </Stack>

    </Paper>
  )
}
