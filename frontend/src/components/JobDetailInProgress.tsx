import { useMemo } from 'react'
import { Paper, Progress, Stack, Text, Stepper, Group, HoverCard, Avatar } from '@mantine/core'
import { IconCheck, IconInfoCircle } from '@tabler/icons-react'
import type { JobStatusRecord } from '../types'

type StageConfig = {
  key: string
  matches: string[]
  label: string
  description: string
  completeOnMatch?: boolean
}

const STAGE_ORDER: StageConfig[] = [
  {
    key: 'queued',
    matches: ['queued'],
    label: 'Queued',
    description: 'Job submitted and waiting for execution.',
  },
  {
    key: 'starting',
    matches: ['starting'],
    label: 'Initializing design',
    description: 'Preparing CRISPR design pipeline and resources.',
  },
  {
    key: 'design-guides',
    matches: ['identifying_candidates', 'candidates_identified'],
    label: 'Designing guides',
    description: 'Generating candidate guide sequences for the target.',
  },
  {
    key: 'crispritz-search',
    matches: ['crispritz:search'],
    label: 'Off-targets search',
    description: 'Scanning the genome for potential off-target sites.',
  },
  {
    key: 'crispritz-annotate',
    matches: ['crispritz:annotate', 'crispritz:complete'],
    label: 'Annotating results',
    description: 'Annotating off-target sites.',
  },
  {
    key: 'completed',
    matches: ['parsing_results', 'scoring_results', 'finalizing', 'completed'],
    label: 'Finalizing',
    description: 'Wrapping up outputs and job metadata.',
    completeOnMatch: true,
  },
]

interface JobDetailInProgressProps {
  job: JobStatusRecord
  progressValue?: number
}

export function JobDetailInProgress({ job, progressValue }: JobDetailInProgressProps) {
  const activeStep = useMemo(() => {
    const stage = job.stage
    if (!stage) return 0

    const index = STAGE_ORDER.findIndex((item) =>
      item.matches.some((match) => stage.startsWith(match)),
    )

    if (index < 0) return 0

    const matchedStage = STAGE_ORDER[index]
    return matchedStage.completeOnMatch ? Math.min(index + 1, STAGE_ORDER.length) : index
  }, [job.stage])
  const details = job.details as { total_guides?: number } | null
  const totalGuides = typeof details?.total_guides === 'number' ? details.total_guides : undefined

  return (
    <Paper shadow="sm" radius="xl" p="xl" withBorder>

      <Stack gap="xl">

        <Stack gap={4}>
          <Group justify="space-between" align="center">
            <Text fw={600} mb={4}>Overall progress</Text>
            <HoverCard width={300} shadow="md" position="top-start">
              <HoverCard.Target>
                <Avatar color="blue" radius='xl' variant="transparent"> 
                  <IconInfoCircle size={20} />
                </Avatar>
              </HoverCard.Target>
              <HoverCard.Dropdown>
                <Text size="sm">
                  Processing multiple guides may take over an hour. You can save your job ID and return later to check the status, or find it anytime on the Previous Jobs page.
                </Text>
              </HoverCard.Dropdown>
            </HoverCard>
          </Group>
          
          <Progress value={progressValue ?? 5} animated />
          {progressValue != null && <Text size="sm" mt={6}>{progressValue}%</Text>}
        </Stack>

        <Stack gap={4}>
          <Text fw={600} mb={4}>Workflow steps</Text>
          <Stepper
            orientation="vertical"
            active={activeStep}
            iconSize={26}
            completedIcon={<IconCheck size={16} />}
            color="blue"
          >
            {STAGE_ORDER.map((item, index) => {
              const isDesignStep = item.matches.includes('candidates_identified')
              const isDesignCompleted = isDesignStep && activeStep > index
              const stepDescription = isDesignCompleted && totalGuides != null ? `${item.description} Found ${totalGuides} guides.` : item.description
              return (
                <Stepper.Step
                  key={item.key}
                  label={item.label}
                  description={stepDescription}
                  loading={index === activeStep && activeStep !== STAGE_ORDER.length}
                />
              )
            })}
          </Stepper>
        </Stack>

      </Stack>

    </Paper>
  )
}
