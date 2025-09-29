export type NucleaseOption = 'SpCas9'
export type GenomeOption = 'hg38'
export type PamOption = 'NGG'

export interface DesignRequestPayload {
  sequence: string
  nuclease: NucleaseOption
  pam: PamOption
  genome: GenomeOption
}

export interface OffTargetHit {
  chrom: string
  pos: number
  strand: '+' | '-'
  mismatches: number
  sequence?: string
  bulge_type?: 'DNA' | 'RNA' | 'RNA+DNA'
  bulge_size?: number
  cfd?: number
  annotation?: string
}

export interface OffTargetSummary {
  num_hits: number
  cfd_sum: number
  mismatch_bins: number[]
  num_bulged_hits: number
}

export interface Guide {
  protospacer: string
  pam: string
  strand: '+' | '-'
  start: number
  end: number
  cut_site: number
  context_30mer?: string
  rs3_score?: number
  on_target_present: boolean
  num_perfect_sites: number
  specificity: number
  off_targets: OffTargetSummary
  top_offtargets?: OffTargetHit[]
  top_bulged?: OffTargetHit[]
  rank?: number
}

export interface JobResultPayload {
  guides?: Guide[]
  num_candidates?: number
  crispritz_results_dir?: string
}

export type JobStatusValue = 'queued' | 'running' | 'succeeded' | 'failed'

export interface JobStatusRecord {
  job_id: string
  status: JobStatusValue
  message?: string
  stage?: string
  progress?: number | null
  details?: Record<string, unknown> | null
  result?: JobResultPayload | null
  created_at: string
  updated_at: string
}

export interface DesignResponsePayload {
  job_id: string
  status: JobStatusValue
  message?: string
  num_candidates?: number
  guides?: Guide[]
}
