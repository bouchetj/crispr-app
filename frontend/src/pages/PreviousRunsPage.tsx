import { useNavigate } from 'react-router-dom'
import {
  Badge,
  Button,
  Paper,
  Group,
  Loader,
  ScrollArea,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { IconArrowLeft } from '@tabler/icons-react'
import { useJobsList } from '../hooks/useJobs'

export function PreviousRunsPage() {
  const navigate = useNavigate()
  const { data, isLoading, isError } = useJobsList(50)

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
        ) : data && data.length > 0 ? (
          <ScrollArea>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Job ID</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Message</Table.Th>
                  <Table.Th>Created</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.map((job) => (
                  <Table.Tr key={job.job_id} onClick={() => navigate(`/jobs/${job.job_id}`)} style={{ cursor: 'pointer' }}>
                    <Table.Td>{job.job_id}</Table.Td>
                    <Table.Td>
                      <Badge color={job.status === 'succeeded' ? 'green' : job.status === 'failed' ? 'red' : 'blue'}>{job.status}</Badge>
                    </Table.Td>
                    <Table.Td>{job.message ?? '—'}</Table.Td>
                    <Table.Td>{job.created_at}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        ) : (
          <Text c="dimmed">No jobs have been submitted yet.</Text>
        )}

      </Paper>

    </Stack>
  )
}
