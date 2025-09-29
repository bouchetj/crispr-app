from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from schemas.design import Guide
from services.sequence import context_window, reverse_complement
from services.crispritz import run_crispritz

logger = logging.getLogger(__name__)


def _pam_matches_ngg(pam: str) -> bool:
    """Return True when pam matches the canonical NGG motif."""
    if len(pam) != 3:
        return False
    pam = pam.upper()
    return pam[1:] == "GG" and pam[0] in "ACGTN"


def find_spcas9_ngg(seq: str) -> Iterable[dict]:
    """Yield candidate protospacers on both strands with an NGG PAM."""
    n = len(seq)
    for start in range(0, n - 23 + 1):
        protospacer = seq[start:start + 20]
        pam = seq[start + 20:start + 23]
        if _pam_matches_ngg(pam):
            yield {
                "protospacer": protospacer,
                "pam": pam,
                "strand": "+",
                "start": start,
                "end": start + 20,
                "cut_site": start + 17,
            }

    rc_seq = reverse_complement(seq)
    for i in range(0, n - 23 + 1):
        protospacer = rc_seq[i:i + 20]
        pam = rc_seq[i + 20:i + 23]
        if _pam_matches_ngg(pam):
            # Map back to original coordinates
            start = n - (i + 20)
            end = n - i
            yield {
                "protospacer": protospacer,
                "pam": pam,
                "strand": "-",
                "start": start,
                "end": end,
                "cut_site": start + 3,
            }


ProgressCallback = Callable[..., None]


def _emit_progress(
    progress_callback: Optional[ProgressCallback],
    *,
    stage: str,
    message: str,
    progress: Optional[float] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    if progress_callback:
        progress_callback(stage=stage, message=message, progress=progress, details=details)


def design(
    sequence: str,
    nuclease: str = "SpCas9",
    pam: str = "NGG",
    genome: str = "hg38",
    max_guides: Optional[int] = 50,
    progress_callback: Optional[ProgressCallback] = None,
    crispritz_results_dir: Optional[Union[str, Path]] = None,
) -> List[Guide]:
    """
    Compute scored guide candidates for an input sequence.
    Currently only SpCas9 with an NGG PAM on the hg38 genome is supported.
    """
    seq_upper = sequence.upper()

    if nuclease != "SpCas9" or pam != "NGG" or genome != "hg38":
        raise ValueError("Only SpCas9 NGG design on hg38 is currently supported")

    logger.debug(
        "Starting guide design for nuclease=%s pam=%s genome=%s length=%d",
        nuclease,
        pam,
        genome,
        len(seq_upper),
    )

    _emit_progress(
        progress_callback,
        stage="identifying_candidates",
        message="Scanning sequence for NGG candidate guides",
        progress=0.05,
    )

    # Identify candidate guides
    candidates = list(find_spcas9_ngg(seq_upper))
    _emit_progress(
        progress_callback,
        stage="candidates_identified",
        message=f"Identified {len(candidates)} candidate guides",
        progress=0.1,
        details={"total_guides": len(candidates), "completed_guides": 0},
    )
    logger.debug("Identified %d NGG candidates", len(candidates))

    wt_by_protospacer = {
        cand["protospacer"]: f"{cand['protospacer']}{cand['pam']}"
        for cand in candidates
    }
    scored_guides: List[Guide] = []

    # Get off-target summary for all candidates
    off_target_summary = run_crispritz(
        candidates,
        wt_by_protospacer,
        progress_callback=progress_callback,
        results_dir=crispritz_results_dir,
    )
    _emit_progress(
        progress_callback,
        stage="parsing_results",
        message="Parsing outputs",
        progress=0.85,
        details={"total_guides": len(candidates), "completed_guides": 0},
    )
    summary_by_guide = {s["protospacer"]: s for s in off_target_summary}

    total_guides = len(candidates)

    # Score each candidate and assemble Guide objects
    for idx, cand in enumerate(candidates, start=1):
        summary = summary_by_guide.get(cand["protospacer"])
        if summary is None:
            logger.error(
                "Missing off-target summary for guide %s%s",
                cand["protospacer"],
                cand["pam"],
            )
            raise ValueError(
                f"Off-target summary not found for guide {cand['protospacer']}{cand['pam']}"
            )

        ctx = context_window(seq_upper, cand["start"], cand["end"])
        rs3_score = _score_rs3(ctx)

        guide = Guide(
            protospacer=cand["protospacer"],
            pam=cand["pam"],
            strand=cand["strand"],
            start=cand["start"],
            end=cand["end"],
            cut_site=cand["cut_site"],
            context_30mer=ctx,
            rs3_score=rs3_score,
            on_target_present=summary["on_target_present"],
            num_perfect_sites=summary["num_perfect_sites"],
            specificity=summary["specificity"],
            off_targets=summary["off_targets"],
            top_offtargets=summary["top_offtargets"],
            top_bulged=summary["top_bulged"],
        )
        scored_guides.append(guide)

        if total_guides:
            progress_fraction = 0.85 + (0.11 * (idx / total_guides))
            _emit_progress(
                progress_callback,
                stage="scoring_guides",
                message=f"Scoring candidate guides ({idx}/{total_guides})",
                progress=progress_fraction,
                details={"total_guides": total_guides, "completed_guides": idx},
            )

    # Rank guides by composite score
    scored_guides.sort(key=_guide_sort_key, reverse=True)
    for rank, guide in enumerate(scored_guides, start=1):
        guide.rank = rank

    _emit_progress(
        progress_callback,
        stage="finalizing",
        message="Finalizing ranked guides",
        progress=0.96,
        details={"total_guides": total_guides, "completed_guides": total_guides},
    )

    if max_guides is not None:
        logger.debug(
            "Returning top %d of %d guides after ranking",
            min(len(scored_guides), max_guides),
            len(scored_guides),
        )
        return scored_guides[:max_guides]
    logger.debug("Returning all %d guides after ranking", len(scored_guides))
    return scored_guides


def _guide_sort_key(g: Guide) -> float:
    """Return a composite score used to rank guides."""
    # 1) hard rejects: send to the bottom
    if not g.on_target_present:
        return -1e9

    # 2) base score: efficacy + specificity (normalize disparate scales)
    rs3 = g.rs3_score
    spec = g.specificity

    # RS3 ranges roughly (-1, 1); map to [0, 1] while clamping to guard outliers
    normalized_rs3 = 0.0 if rs3 is None else max(0.0, min(1.0, (rs3 + 1.0) / 2.0))
    # Specificity ranges 0-100; scale to [0, 1]
    normalized_spec = 0.0 if spec is None else max(0.0, min(1.0, spec / 100.0))

    base = 0.5 * normalized_rs3 + 0.5 * normalized_spec

    # 3) multiplicative penalties
    penalty = 1.0

    # multi-targeting (count extra perfect copies as off-targets)
    if getattr(g, "num_perfect_sites", 1) > 1:
        penalty *= 0.2 ** (g.num_perfect_sites - 1)

    score = base * penalty

    return score


def _score_rs3(context_30mer: str) -> Optional[float]:
    """Return the RS3 efficacy score for a 30-mer context."""
    try:
        from rs3.seq import predict_seq
    except ImportError:
        logger.warning("rs3 package not available; skipping RS3 score")
        return None

    try:
        score = predict_seq([context_30mer], sequence_tracr='Hsu2013')[0]
        return float(score)
    except Exception as exc:
        logger.warning("RS3 scoring failed: %s", exc)
        return None
