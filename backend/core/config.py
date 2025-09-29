import os
from pydantic import BaseModel

class Settings(BaseModel):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    JOBS_REDIS_URL: str = os.getenv("JOBS_REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    HG38_REFERENCE_FASTA: str = os.getenv("HG38_REFERENCE_FASTA", "/data/genomes/hg38/hg38.fa")
    CRISPRITZ_INDEX: str = os.getenv("CRISPRITZ_INDEX")
    CRISPRITZ_PAM_TXT: str = os.getenv("CRISPRITZ_PAM_TXT")
    CRISPRITZ_ANNOTATIONS_BED: str = os.getenv("CRISPRITZ_ANNOTATIONS_BED", "/data/genomes/hg38/hg38Annotation.bed")
    CRISPRITZ_RESULTS_DIR: str = os.getenv("CRISPRITZ_RESULTS_DIR", "/data/results")
    CRISPRITZ_THREADS: int = int(os.getenv("CRISPRITZ_THREADS", "1"))
    MISMATCH_SCORES: str = os.getenv("MISMATCH_SCORES", "/data/CFD_scoring_matrix/mismatch_score.pkl")
    PAM_SCORES: str = os.getenv("PAM_SCORES", "/data/CFD_scoring_matrix/pam_scores.pkl")

settings = Settings()
