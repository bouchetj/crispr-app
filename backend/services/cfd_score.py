"""Cutting Frequency Determination (CFD) score helpers."""

from __future__ import annotations

import pickle
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple

from backend.core.config import settings


def revcom(seq: str) -> str:
    """Return the reverse complement of a guide sequence."""

    basecomp = {"A": "T", "C": "G", "G": "C", "T": "A", "U": "A"}
    try:
        return "".join(basecomp[base] for base in reversed(seq))
    except KeyError as exc:
        raise ValueError(f"Unexpected base '{exc.args[0]}' in sequence '{seq}'") from exc


def load_pickle(path: Path) -> Dict[str, float]:
    with path.open("rb") as handle:
        return pickle.load(handle)


def get_mm_pam_scores(
    mismatch_path: Path, pam_path: Path
) -> Tuple[Dict[str, float], Dict[str, float]]:
    try:
        mm_scores = load_pickle(mismatch_path)
        pam_scores = load_pickle(pam_path)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "Could not find mismatch or PAM score pickles."
        ) from exc
    except pickle.UnpicklingError as exc:
        raise ValueError("Mismatch or PAM score pickle could not be unpickled.") from exc

    return mm_scores, pam_scores


def _calc_cfd(
    wt: str, sg: str, pam: str, mm_scores: Dict[str, float], pam_scores: Dict[str, float]
) -> float:
    score = 1.0
    sg = sg.replace("T", "U")
    wt = wt.replace("T", "U")
    for idx, (wt_base, sg_base) in enumerate(zip(wt, sg), start=1):
        if wt_base != sg_base:
            key = f"r{wt_base}:d{revcom(sg_base)},{idx}"
            try:
                score *= mm_scores[key]
            except KeyError as exc:
                raise KeyError(f"Mismatch key '{key}' not found in mismatch scores") from exc
    try:
        score *= pam_scores[pam]
    except KeyError as exc:
        raise KeyError(f"PAM '{pam}' not found in PAM scores") from exc
    return float(score)


def validate_sequence(label: str, sequence: str) -> None:
    if not re.fullmatch(r"[ACGT]+", sequence):
        raise ValueError(f"{label} must contain only the characters A, C, G, and T")


@lru_cache(maxsize=1)
def _load_scores() -> Tuple[Dict[str, float], Dict[str, float]]:
    mismatch_path = settings.MISMATCH_SCORES
    pam_path = settings.PAM_SCORES
    if not mismatch_path or not pam_path:
        raise RuntimeError("MISMATCH_SCORES and PAM_SCORES settings must be configured")

    mismatch_file = Path(mismatch_path)
    pam_file = Path(pam_path)
    return get_mm_pam_scores(mismatch_file, pam_file)


def calc_cfd(wt: str, off: str) -> float:
    """Compute the CFD score given a wild-type and off-target 23-mer guide."""

    if not wt or not off:
        raise ValueError("Both WT and off-target sequences must be provided")

    wt = wt.upper()
    off = off.upper()
    validate_sequence("WT guide", wt)
    validate_sequence("Off-target guide", off)
    if len(wt) != 23 or len(off) != 23:
        raise ValueError("WT and off-target sequences must be 23 nucleotides long")

    pam = off[-2:]
    sg = off[:-3]
    mm_scores, pam_scores = _load_scores()
    return _calc_cfd(wt, sg, pam, mm_scores, pam_scores)
