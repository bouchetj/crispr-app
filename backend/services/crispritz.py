"""CRISPRitz wrapper to enumerate off-target hits for candidate guides."""

import heapq
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Union

import polars as pl
import pandas as pd

from core.config import settings
from schemas.design import OffTargetHit, OffTargetSummary
from services.cfd_score import calc_cfd

logger = logging.getLogger(__name__)

def run_crispritz(
    candidates: List[dict],
    wt_lookup: Dict[str, str],
    progress_callback: Optional[Callable[..., None]] = None,
    results_dir: Optional[Union[str, Path]] = None,
) -> List[Dict]:
    """Execute CRISPRitz to enumerate off-target hits for the candidate guides."""
    if not candidates:
        logger.debug("Skipping CRISPRitz run: no candidates provided")
        return []

    if not settings.CRISPRITZ_INDEX:
        logger.debug("CRISPRitz index not configured; skipping off-target enumeration")
        return []

    if not results_dir:
        logger.error("CRISPRitz results directory not provided; pass results_dir or configure CRISPRITZ_RESULTS_DIR per job")
        raise ValueError("CRISPRitz results directory is not configured")

    persist_dir = Path(results_dir)

    persist_dir.mkdir(parents=True, exist_ok=True)
    guide_txt = persist_dir / "guides.txt"
    guide_txt.write_text("".join(f"{cand['protospacer']}NNN\n" for cand in candidates))
    persist_outputs_dir = persist_dir / "outputs"
    if persist_outputs_dir.exists():
        shutil.rmtree(persist_outputs_dir)

    with tempfile.TemporaryDirectory(prefix="crispritz-run-") as work_dir:
        work_path = Path(work_dir)
        tmp_guide_txt = work_path / "guides.txt"
        tmp_guide_txt.write_text(guide_txt.read_text())
        tmp_outputs_dir = work_path / "outputs"
        tmp_outputs_dir.mkdir(parents=True, exist_ok=True)

        # Build and run the CRISPRitz search command
        search_cmd = _build_crispritz_search_command(tmp_guide_txt, tmp_outputs_dir)
        if not search_cmd:
            logger.debug("Search command could not be constructed; skipping CRISPRitz")
            return []

        if progress_callback:
            progress_callback(
                stage="crispritz:search",
                message="Scanning for off-targets",
                progress=0.2,
            )

        try:
            search_completed = subprocess.run(
                search_cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            logger.warning("CRISPRitz launch failed: %s", exc)
            raise RuntimeError("CRISPRitz search command failed; check logs for details") from exc

        if search_completed.returncode != 0:
            logger.warning(
                "CRISPRitz search failed with exit code %s: %s",
                search_completed.returncode,
            )
            raise RuntimeError("CRISPRitz search command failed; check logs for details")

        # Build and run the annotation command
        annotate_cmd = _build_crispritz_annotate_command(tmp_outputs_dir)
        if not annotate_cmd:
            logger.debug("Annotate command could not be constructed; skipping CRISPRitz annotation")
            return []

        if progress_callback:
            progress_callback(
                stage="crispritz:annotate",
                message="Annotating off-targets",
                progress=0.6,
            )

        try:
            annotate_completed = subprocess.run(
                annotate_cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            logger.warning("CRISPRitz annotation launch failed: %s", exc)
            raise RuntimeError("CRISPRitz annotate command failed; check logs for details") from exc

        if annotate_completed.returncode != 0:
            logger.warning(
                "CRISPRitz annotate failed with exit code %s: %s",
                annotate_completed.returncode,
            )
            raise RuntimeError("CRISPRitz annotate command failed; check logs for details")

        shutil.copytree(tmp_outputs_dir, persist_outputs_dir)

    if progress_callback:
        progress_callback(
            stage="crispritz:complete",
            message="Parsing results",
            progress=0.8,
        )

    summaries = _parse_crispritz_results(persist_outputs_dir, wt_lookup)

    return summaries


def _build_crispritz_search_command(guide_txt: Path, output_dir: Path) -> Optional[List[str]]:
    """Return the CRISPRitz search command arguments or ``None`` if misconfigured."""
    if not (settings.CRISPRITZ_INDEX and settings.CRISPRITZ_PAM_TXT):
        logger.debug("CRISPRitz settings not configured")
        return None

    threads = getattr(settings, "CRISPRITZ_THREADS", 1)
    try:
        threads_int = int(threads)
    except (TypeError, ValueError):
        threads_int = 1
    if threads_int <= 0:
        threads_int = 1

    return [
        "crispritz.py",
        "search",
        str(settings.CRISPRITZ_INDEX),
        str(settings.CRISPRITZ_PAM_TXT),
        str(guide_txt),
        str(output_dir / "out"),
        "-index",
        "-mm", "4",
        "-bDNA", "1",
        "-bRNA", "1",
        "-t",
        "-th", str(threads_int),
    ]


def _build_crispritz_annotate_command(output_dir: Path) -> Optional[List[str]]:
    """Return the CRISPRitz annotate command arguments or ``None`` if unavailable."""
    if not (settings.CRISPRITZ_ANNOTATIONS_BED):
        logger.debug("CRISPRitz annotations BED not configured in settings")
        return None

    return [
        "crispritz.py",
        "annotate-results",
        str(output_dir / "out.targets.txt"),
        str(settings.CRISPRITZ_ANNOTATIONS_BED),
        str(output_dir / "out"),
    ]


def _parse_crispritz_results(output_dir: Path, wt_lookup: Dict[str, str]) -> List[Dict]:
    """Load CRISPRitz outputs and construct per-guide summaries."""

    targets_txt = output_dir / "out.Annotation.targets.txt"
    targets_parquet = output_dir / "out.Annotation.targets.parquet"
    targets_lazy = _load_targets(targets_txt, targets_parquet)

    profile = _load_profile(str(output_dir / "out.profile.xls"))
    required_p = {'Guide', 'ONT', 'OFFT', '0MM', '1MM', '2MM', '3MM', '4MM'}
    missing = required_p - set(profile.columns)
    if missing:
        logger.error("Profile file missing required columns: %s", sorted(missing))
        raise ValueError(f"ERROR: Missing required columns in profile: {sorted(missing)}")

    summaries: List[Dict] = []

    for guide in set(profile["Guide"]):
        
        guide_hits = (
            targets_lazy.filter(pl.col("Guide") == guide)
            .collect(engine="streaming")
        )

        if guide_hits.height == 0:
            continue

        summaries.append(
            summarize_one_guide(
                guide_hits.iter_rows(named=True),
                guide,
                profile.loc[profile["Guide"] == guide].iloc[0],
                wt_lookup,
            )
        )

    return summaries


ACGTN_RE = re.compile(r"[ACGTNacgtn]")

def _load_targets(path: Path, parquet_path: Path) -> pl.LazyFrame:
    """Load targets via Polars, materializing to Parquet for streaming per guide."""

    logger.debug("Loading CRISPRitz targets from %s", path)

    schema = {
        "#Bulge type":    pl.Utf8,
        "crRNA":          pl.Utf8,
        "DNA":            pl.Utf8,
        "Chromosome":     pl.Categorical,
        "Position":       pl.Int32,
        "Cluster Position": pl.Int32,
        "Direction":      pl.Categorical,
        "Mismatches":     pl.UInt8,
        "Bulge Size":     pl.UInt8,
        "Total":          pl.UInt8,
        "Annotation_Type": pl.Utf8,
    }

    rename_map = {
        "#Bulge type":      "Bulge_Type",
        "Bulge Size":       "Bulge_Size",
        "Cluster Position": "Cluster_Position",
    }

    try:
        lf = (
            pl.scan_csv(
                str(path),
                separator="\t",
                has_header=True,
                schema=schema,
            )
            .rename(rename_map)
            .with_columns([
                pl.col("crRNA")
                  .str.replace_all(r"[^ACGTNacgtn]", "")
                  .str.to_uppercase()
                  .alias("Guide"),
            ])
            .select([
                "Bulge_Type", "crRNA", "DNA", "Chromosome", "Position",
                "Direction", "Mismatches", "Bulge_Size", "Total",
                "Annotation_Type", "Guide",
            ])
        )
    except Exception as e:
        logger.exception("Failed to scan TSV with Polars: %s", path)
        raise ValueError(f"Failed to read CRISPRitz targets TSV at {path}: {e}\n") from e
    
    
    lf.sink_parquet(str(parquet_path), compression="zstd")

    return pl.scan_parquet(str(parquet_path))


def _load_profile(path: str) -> pd.DataFrame:
    """Load the CRISPRitz ``.profile`` summary table as a DataFrame."""
    logger.debug("Loading CRISPRitz profile from %s", path)
    df = pd.read_csv(path, sep=r"\t", engine="python", comment=None, dtype=str)
    df = df.drop(df.filter(regex=r'^(BP(\.\d+)?|Unnamed)').columns, axis=1)
    df.rename(columns={"GUIDE": "Guide"}, inplace=True)
    return df


def summarize_one_guide(
    rows: Iterable[Mapping[str, object]],
    guide: str,
    profile_row: Mapping[str, object],
    wt_lookup: Dict[str, str],
    K_top: int = 50,
    J_bulged: int = 20,
) -> Dict:
    """Build the off-target summary payload for a single guide."""

    summary = OffTargetSummary()
    nonbulged_heap: List[tuple[float, int, OffTargetHit]] = []
    bulged_heap: List[tuple[float, int, OffTargetHit]] = []
    hit_counter = 0
    num_perfect = 0
    primary_perfect: Optional[OffTargetHit] = None
    primary_cfd = 0.0

    protospacer = guide[:-3]

    for row in rows:
        chrom = str(row.get("Chromosome"))
        strand = str(row.get("Direction"))
        pos = int(row.get("Position"))
        mm = int(row.get("Mismatches"))
        annotation_raw = row.get("Annotation_Type")
        annotation = None if annotation_raw in (None, "", "n") else str(annotation_raw)

        bulge_size_value = row.get("Bulge_Size")
        bulge_size = int(bulge_size_value) if bulge_size_value is not None else 0
        bulge_type = None
        bulge_type_raw = row.get("Bulge_Type")
        if bulge_type_raw:
            bt = str(bulge_type_raw).upper()
            if "RNA,DNA" in bt:
                bulge_type = "RNA+DNA"
            elif "DNA" in bt:
                bulge_type = "DNA"
            elif "RNA" in bt:
                bulge_type = "RNA"

        dna_seq = str(row.get("DNA"))
        s23 = "".join(ACGTN_RE.findall(dna_seq)).upper()

        if bulge_size == 0 and len(s23) == 23:
            wt = wt_lookup.get(protospacer)
            if not wt or len(wt) != 23:
                logger.debug("Skipping CFD: missing WT sequence for %s", guide)
                cfd = None
            else:
                cfd = calc_cfd(wt, s23)

            hit = OffTargetHit(
                chrom=chrom,
                pos=pos,
                strand=strand,
                mismatches=mm,
                sequence=s23,
                bulge_type=None,
                bulge_size=0,
                cfd=cfd,
                annotation=annotation,
            )

            summary.num_hits += 1
            if cfd is not None:
                summary.cfd_sum += cfd

            score = cfd or 0.0
            entry = (score, hit_counter, hit)
            if len(nonbulged_heap) < K_top:
                heapq.heappush(nonbulged_heap, entry)
            elif score > nonbulged_heap[0][0]:
                heapq.heapreplace(nonbulged_heap, entry)

            if mm == 0 and s23.endswith("GG"):
                num_perfect += 1
                if primary_perfect is None:
                    primary_perfect = hit
                    primary_cfd = cfd or 0.0

        else:
            hit = OffTargetHit(
                chrom=chrom,
                pos=pos,
                strand=strand,
                mismatches=mm,
                sequence=dna_seq,
                bulge_type=bulge_type,
                bulge_size=bulge_size,
                cfd=None,
                annotation=annotation,
            )

            summary.num_hits += 1
            summary.num_bulged_hits += 1

            score = mm * 1000 - (bulge_size or 0)
            entry = (-score, hit_counter, hit)
            if len(bulged_heap) < J_bulged:
                heapq.heappush(bulged_heap, entry)
            elif entry > bulged_heap[0]:
                heapq.heapreplace(bulged_heap, entry)

        hit_counter += 1

    summary.mismatch_bins = profile_row[["0MM", "1MM", "2MM", "3MM", "4MM"]].astype(int).tolist()

    on_target_present = num_perfect >= 1

    specificity = 100 / (100 + summary.cfd_sum)

    sorted_nonbulged = sorted(nonbulged_heap, key=lambda h: (h[0], h[1]), reverse=True)
    top_offtargets: List[OffTargetHit] = []
    for _, _, hit in sorted_nonbulged:
        if hit is primary_perfect:
            continue
        top_offtargets.append(hit)
    if len(top_offtargets) > K_top:
        top_offtargets = top_offtargets[:K_top]

    top_bulged = sorted(
        (entry[2] for entry in bulged_heap),
        key=lambda h: (h.mismatches, -(h.bulge_size or 0), h.chrom, h.pos),
    )
    if len(top_bulged) > J_bulged:
        top_bulged = top_bulged[:J_bulged]

    return {
        "protospacer": protospacer,
        "on_target_present": on_target_present,
        "num_perfect_sites": num_perfect,
        "specificity": specificity,
        "off_targets": summary,
        "top_offtargets": top_offtargets,
        "top_bulged": top_bulged,
    }
