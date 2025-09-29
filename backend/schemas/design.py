from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_serializer
from zoneinfo import ZoneInfo

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")

BulgeType = Literal["DNA", "RNA", "RNA+DNA"]

class OffTargetHit(BaseModel):
    chrom: str
    pos: int
    strand: Literal["+", "-"]
    mismatches: int
    sequence: Optional[str] = None
    bulge_type: Optional[BulgeType] = None
    bulge_size: Optional[int] = None
    cfd: Optional[float] = None 
    annotation: Optional[str] = None

class OffTargetSummary(BaseModel):
    num_hits: int = 0
    cfd_sum: float = 0.0
    mismatch_bins: List[int] = Field(default_factory=lambda: [0, 0, 0, 0, 0])
    num_bulged_hits: int = 0

class Guide(BaseModel):
    protospacer: str
    pam: str
    strand: Literal["+", "-"]
    start: int
    end: int
    cut_site: int
    context_30mer: Optional[str] = None
    rs3_score: Optional[float] = None
    on_target_present: bool
    num_perfect_sites: int
    specificity: float
    off_targets: OffTargetSummary
    top_offtargets: List[OffTargetHit] = Field(default_factory=list)
    top_bulged: List[OffTargetHit] = Field(default_factory=list)
    rank: Optional[int] = None

class DesignRequest(BaseModel):
    sequence: str
    nuclease: Literal["SpCas9"] = "SpCas9"
    pam: str = "NGG"
    genome: Literal["hg38"] = "hg38"

class DesignResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"] = "queued"
    message: Optional[str] = None
    num_candidates: Optional[int] = None
    guides: Optional[List[Guide]] = None

class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued","running","succeeded","failed"]
    message: Optional[str] = None
    stage: Optional[str] = None
    progress: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    details: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _serialize_timestamp(self, value: datetime) -> str:
        local_dt = value.astimezone(PACIFIC_TZ)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
