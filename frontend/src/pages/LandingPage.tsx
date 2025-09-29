import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Avatar,
  Badge,
  Button,
  Paper,
  Group,
  HoverCard,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core'
import { IconAlertCircle, IconArrowRight, IconInfoCircle } from '@tabler/icons-react'
import { useDebouncedValue } from '@mantine/hooks'
import { useQuery } from '@tanstack/react-query'
import { useDesignSubmit } from '../hooks/useJobs'
import type { DesignRequestPayload } from '../types'
import { validateSequence, type ValidateResponse } from '../api/validation'
import { notifications } from '@mantine/notifications'

const DEFAULT_REQUEST: DesignRequestPayload = {
  sequence: '',
  genome: 'hg38',
  nuclease: 'SpCas9',
  pam: 'NGG',
}

export function LandingPage() {
  const navigate = useNavigate()
  const designMutation = useDesignSubmit()
  const [formState, setFormState] = useState<DesignRequestPayload>(DEFAULT_REQUEST)
  const [debouncedSequence] = useDebouncedValue(formState.sequence, 400)

  const validationQuery = useQuery<ValidateResponse>({
    queryKey: ['validate-sequence', debouncedSequence],
    queryFn: () => validateSequence(debouncedSequence),
    enabled: debouncedSequence.trim().length > 0,
    staleTime: 0,
  })

  const hasValidationErrors = Boolean(validationQuery.data?.errors?.length)

  const handleSequenceChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setFormState((prev) => ({ ...prev, sequence: event.target.value }))
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!formState.sequence.trim()) {
      return
    }
    try {
      const response = await designMutation.submitAsync({ ...formState })
      navigate(`/jobs/${response.job_id}`)
    } catch (error) {
      console.error('Failed to submit design request', error)
    }
  }

  useEffect(() => {
    if (designMutation.isError) {
      notifications.show({
        color: 'red',
        title: 'Request failed',
        message: 'Unable to submit the design job. Please try again.',
        icon: <IconAlertCircle size={16} />,
      })
    }
  }, [designMutation.isError])

  useEffect(() => {
    if (validationQuery.isError) {
      notifications.show({
        color: 'red',
        title: 'Validation request failed',
        message: 'Unable to validate the sequence. Please try again.',
        icon: <IconAlertCircle size={16} />,
      })
    }
  }, [validationQuery.isError])

  return (
    <Stack gap="xl">

      <Stack gap={8} align="center">
        <Title order={2}>Design a CRISPR Run</Title>
        <Text c="dimmed">Provide your target sequence and launch the pipeline.</Text>
      </Stack>

      <Paper
        component="form"
        onSubmit={handleSubmit}
        shadow="sm"
        radius="xl"
        p="xl"
        withBorder
      >

        <Stack gap="sm">

          <Group justify="space-between" align="center">
            <Title order={4} style={{ marginLeft: '1rem' }}>Input Sequence</Title>
            <HoverCard width={300} shadow="md" position="top-start">
              <HoverCard.Target>
                <Avatar color="blue" radius='xl' variant="transparent"> 
                  <IconInfoCircle size={20} />
                </Avatar>
              </HoverCard.Target>
              <HoverCard.Dropdown>
                <Text size="sm">
                  Currently, the CRISPR design tool supports the hg38 reference genome, NGG PAM, and SpCas9 nuclease.
                </Text>
              </HoverCard.Dropdown>
            </HoverCard>
          </Group>

          <Textarea
            placeholder="Paste your sequence here"
            autosize
            minRows={6}
            value={formState.sequence}
            onChange={handleSequenceChange}
            radius="lg"
            required
          />

          {validationQuery.isSuccess && (
            <Group gap="xs">
              <Badge color="blue" variant="light">
                Length: {validationQuery.data.length}
              </Badge>
              <Badge color="cyan" variant="light">
                GC: {(validationQuery.data.gc_content * 100).toFixed(1)}%
              </Badge>
              {validationQuery.data.warnings.map((warning) => (
                <Badge key={warning} color="yellow" variant="dot">
                  {warning}
                </Badge>
              ))}
              {validationQuery.data.errors.map((error) => (
                <Badge key={error} color="red" variant="filled">
                  {error}
                </Badge>
              ))}
            </Group>
          )}

          <Group justify="center">
            <Button
              type="submit"
              rightSection={<IconArrowRight size={16} />}
              loading={designMutation.isPending}
              disabled={!formState.sequence.trim() || validationQuery.isError || hasValidationErrors}
            >
              Run design
            </Button>
          </Group>
          
        </Stack>

      </Paper>

    </Stack>
  )
}
