from pathlib import Path
import os
import shutil

import pandas as pd
import polars as pl
import pytest

import services.crispritz as crispritz

INTEGRATION = os.getenv("RUN_INTEGRATION") == "1"


def _write_targets_file(path: Path, rows: list[dict[str, str]]) -> None:
    header = (
        "#Bulge type\tcrRNA\tDNA\tChromosome\tPosition\tCluster Position\tDirection\t" \
        "Mismatches\tBulge Size\tTotal\tAnnotation_Type"
    )
    with path.open("w", encoding="utf-8") as handle:
        handle.write(header + "\n")
        for row in rows:
            handle.write("\t".join(
                [
                    row.get("#Bulge type", ""),
                    row.get("crRNA", ""),
                    row.get("DNA", ""),
                    row.get("Chromosome", ""),
                    str(row.get("Position", "")),
                    str(row.get("Cluster Position", "")),
                    row.get("Direction", ""),
                    str(row.get("Mismatches", "")),
                    str(row.get("Bulge Size", "")),
                    str(row.get("Total", "")),
                    row.get("Annotation_Type", ""),
                ]
            ) + "\n")


def _write_profile_file(path: Path, rows: list[dict[str, str]]) -> None:
    columns = ["Guide", "ONT", "OFFT", "0MM", "1MM", "2MM", "3MM", "4MM"]
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            handle.write("\t".join(str(row.get(col, "")) for col in columns) + "\n")


def test_run_crispritz_returns_empty_when_no_candidates(tmp_path: Path):
    result = crispritz.run_crispritz([], {}, results_dir=tmp_path)
    assert result == []


def test_run_crispritz_skips_when_index_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_INDEX", None)
    result = crispritz.run_crispritz([{"protospacer": "A" * 20, "pam": "GGG"}], {}, results_dir=tmp_path)
    assert result == []


def test_run_crispritz_executes_commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_INDEX", "/index")
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_PAM_TXT", "/pam.txt")
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_ANNOTATIONS_BED", "/annot.bed")
    monkeypatch.setattr(crispritz.logger, "warning", lambda *args, **kwargs: None)

    search_calls: list[tuple[str, ...]] = []
    annotate_calls: list[tuple[str, ...]] = []

    class Completed:
        def __init__(self, *, returncode: int = 0, stdout: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout

    def fake_run(cmd, **kwargs):
        if len(cmd) >= 2 and cmd[1] == "search":
            search_calls.append(tuple(cmd))
            return Completed(stdout="search ok")
        if len(cmd) >= 2 and cmd[1] == "annotate-results":
            annotate_calls.append(tuple(cmd))
            return Completed(stdout="annotate ok")
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(crispritz.subprocess, "run", fake_run)
    monkeypatch.setattr(crispritz, "_parse_crispritz_results", lambda path, wt: [{"protospacer": "A" * 20}])

    candidates = [{"protospacer": "A" * 20, "pam": "GGG"}]
    wt_lookup = {"A" * 20: "A" * 23}

    progress_payloads = []

    def progress(**payload):
        progress_payloads.append(payload)

    result = crispritz.run_crispritz(
        candidates,
        wt_lookup,
        progress_callback=progress,
        results_dir=tmp_path,
    )

    assert result == [{"protospacer": "A" * 20}]
    assert len(search_calls) == 1
    assert len(annotate_calls) == 1
    assert progress_payloads
    for payload in progress_payloads:
        details = payload.get("details") or {}
        assert "crispritz_search_percent" not in details
        assert "crispritz_annotate_percent" not in details


def test_run_crispritz_raises_when_search_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_INDEX", "/index")
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_PAM_TXT", "/pam.txt")
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_ANNOTATIONS_BED", "/annot.bed")
    monkeypatch.setattr(crispritz.logger, "warning", lambda *args, **kwargs: None)

    class Completed:
        def __init__(self, returncode: int, stdout: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout

    def fake_run(cmd, **kwargs):
        if len(cmd) >= 2 and cmd[1] == "search":
            return Completed(returncode=1, stdout="error")
        raise AssertionError("Annotate command should not run when search fails")

    monkeypatch.setattr(crispritz.subprocess, "run", fake_run)

    candidates = [{"protospacer": "A" * 20, "pam": "GGG"}]

    with pytest.raises(RuntimeError, match="search command failed"):
        crispritz.run_crispritz(candidates, {"A" * 20: "A" * 23}, results_dir=tmp_path)


def test_run_crispritz_raises_when_annotation_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_INDEX", "/index")
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_PAM_TXT", "/pam.txt")
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_ANNOTATIONS_BED", "/annot.bed")
    monkeypatch.setattr(crispritz.logger, "warning", lambda *args, **kwargs: None)

    class Completed:
        def __init__(self, returncode: int, stdout: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout

    def fake_run(cmd, **kwargs):
        if len(cmd) >= 2 and cmd[1] == "search":
            return Completed(returncode=0, stdout="ok")
        if len(cmd) >= 2 and cmd[1] == "annotate-results":
            return Completed(returncode=1, stdout="annotate error")
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(crispritz.subprocess, "run", fake_run)

    candidates = [{"protospacer": "A" * 20, "pam": "GGG"}]

    with pytest.raises(RuntimeError, match="annotate command failed"):
        crispritz.run_crispritz(candidates, {"A" * 20: "A" * 23}, results_dir=tmp_path)


def test_run_crispritz_persists_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_INDEX", "/index")
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_PAM_TXT", "/pam.txt")
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_ANNOTATIONS_BED", "/annot.bed")

    class Completed:
        def __init__(self, stdout: str = "ok") -> None:
            self.returncode = 0
            self.stdout = stdout

    def fake_run(cmd, **kwargs):
        return Completed()

    monkeypatch.setattr(crispritz.subprocess, "run", fake_run)
    monkeypatch.setattr(crispritz, "_parse_crispritz_results", lambda path, wt: [{"protospacer": "A" * 20}])

    candidates = [{"protospacer": "A" * 20, "pam": "GGG"}]
    wt_lookup = {"A" * 20: "A" * 23}
    persist_dir = tmp_path / "persist"

    result = crispritz.run_crispritz(
        candidates,
        wt_lookup,
        results_dir=persist_dir,
    )

    assert result == [{"protospacer": "A" * 20}]
    assert (persist_dir / "guides.txt").exists()
    assert (persist_dir / "outputs").exists()


def test_build_crispritz_search_command_requires_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_INDEX", None)
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_PAM_TXT", None)
    cmd = crispritz._build_crispritz_search_command(Path("guides.txt"), Path("out"))
    assert cmd is None


def test_build_crispritz_search_command_returns_args(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_INDEX", Path("/idx"))
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_PAM_TXT", Path("/pam.txt"))
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_THREADS", 4)
    cmd = crispritz._build_crispritz_search_command(Path("guides.txt"), Path("out"))
    assert cmd[:2] == ["crispritz.py", "search"]
    assert "-mm" in cmd
    assert cmd[-2:] == ["-th", "4"]


def test_build_crispritz_annotate_command(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_ANNOTATIONS_BED", Path("/annot.bed"))
    cmd = crispritz._build_crispritz_annotate_command(Path("out"))
    assert cmd[1] == "annotate-results"


def test_build_crispritz_annotate_command_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_ANNOTATIONS_BED", None)
    assert crispritz._build_crispritz_annotate_command(Path("out")) is None


def test_load_targets_roundtrip(tmp_path: Path):
    targets_path = tmp_path / "out.Annotation.targets.txt"
    parquet_path = tmp_path / "out.Annotation.targets.parquet"
    _write_targets_file(
        targets_path,
        [
            {
                "#Bulge type": "DNA",
                "crRNA": "acgtacgtacgtacgtacgtNNN",
                "DNA": "ACGTACGTACGTACGTACGTGGG",
                "Chromosome": "chr1",
                "Position": "10",
                "Cluster Position": "10",
                "Direction": "+",
                "Mismatches": "0",
                "Bulge Size": "0",
                "Total": "1",
                "Annotation_Type": "exon",
            }
        ],
    )

    lazy_frame = crispritz._load_targets(targets_path, parquet_path)

    assert parquet_path.exists()
    df = lazy_frame.collect()
    assert df.height == 1
    assert set(df.columns) == {
        "Bulge_Type",
        "crRNA",
        "DNA",
        "Chromosome",
        "Position",
        "Direction",
        "Mismatches",
        "Bulge_Size",
        "Total",
        "Annotation_Type",
        "Guide",
    }
    assert df["Guide"][0] == "ACGTACGTACGTACGTACGTNNN"


def test_load_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    raw = pd.DataFrame(
        [
            {
                "GUIDE": "AAAAA",
                "BP": "unused",
                "BP.1": "unused",
                "Unnamed: 0": "unused",
                "0MM": "1",
            }
        ]
    )
    monkeypatch.setattr(crispritz.pd, "read_csv", lambda *args, **kwargs: raw)
    df = crispritz._load_profile(str(tmp_path / "out.profile.xls"))
    assert "Guide" in df.columns
    assert "BP" not in df.columns


def test_summarize_one_guide(monkeypatch: pytest.MonkeyPatch):
    guide_seq = "GAGTCCGAGCAGAAGAAGAAGGG"
    off_target_rows = [
        {
            "Chromosome": "chr1",
            "Direction": "+",
            "Position": 10,
            "Mismatches": 0,
            "Annotation_Type": "exon",
            "Bulge_Size": 0,
            "Bulge_Type": None,
            "DNA": "ACGTACGTACGTACGTACGTGGG",
        },
        {
            "Chromosome": "chr2",
            "Direction": "-",
            "Position": 20,
            "Mismatches": 2,
            "Annotation_Type": "intergenic",
            "Bulge_Size": 1,
            "Bulge_Type": "RNA",
            "DNA": "GGGTTT",
        },
    ]

    profile_row = pd.Series(
        {
            "Guide": guide_seq,
            "ONT": "1",
            "OFFT": "2",
            "0MM": "1",
            "1MM": "2",
            "2MM": "3",
            "3MM": "4",
            "4MM": "5",
        }
    )

    monkeypatch.setattr(crispritz, "calc_cfd", lambda wt, off: 0.7)
    wt_lookup = {guide_seq[:-3]: guide_seq}

    summary = crispritz.summarize_one_guide(off_target_rows, guide_seq, profile_row, wt_lookup, K_top=10, J_bulged=10)

    assert summary["protospacer"] == guide_seq[:-3]
    assert summary["on_target_present"] is True
    assert summary["num_perfect_sites"] == 1
    assert summary["off_targets"].num_hits == 1
    assert summary["off_targets"].mismatch_bins[0] == 0
    assert summary["specificity"] == pytest.approx(1)
    assert summary["off_targets"].num_bulged_hits == 1
    assert summary["top_bulged"][0].bulge_type == "RNA"


def test_parse_crispritz_results_valid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    guide_seq = "A" * 20 + "GGG"
    protospacer = guide_seq[:-3]
    targets_path = tmp_path / "out.Annotation.targets.txt"
    profile_path = tmp_path / "out.profile.xls"

    _write_targets_file(
        targets_path,
        [
            {
                "#Bulge type": "DNA",
                "crRNA": guide_seq,
                "DNA": "ACGTACGTACGTACGTACGTGGG",
                "Chromosome": "chr1",
                "Position": "10",
                "Cluster Position": "10",
                "Direction": "+",
                "Mismatches": "0",
                "Bulge Size": "0",
                "Total": "1",
                "Annotation_Type": "exon",
            },
            {
                "#Bulge type": "RNA",
                "crRNA": guide_seq,
                "DNA": "ACGTACGTACGTACGTACGTGGG",
                "Chromosome": "chr1",
                "Position": "15",
                "Cluster Position": "15",
                "Direction": "+",
                "Mismatches": "1",
                "Bulge Size": "1",
                "Total": "1",
                "Annotation_Type": "intron",
            },
        ],
    )

    _write_profile_file(
        profile_path,
        [
            {
                "Guide": guide_seq,
                "ONT": "1",
                "OFFT": "2",
                "0MM": "1",
                "1MM": "1",
                "2MM": "0",
                "3MM": "0",
                "4MM": "0",
            }
        ],
    )

    monkeypatch.setattr(crispritz, "calc_cfd", lambda wt, off: 0.5)

    results = crispritz._parse_crispritz_results(tmp_path, {protospacer: guide_seq})

    assert len(results) == 1
    summary = results[0]
    assert summary["protospacer"] == protospacer
    assert summary["on_target_present"] is True
    assert summary["num_perfect_sites"] == 1
    assert summary["top_bulged"]
    assert summary["top_bulged"][0].bulge_type == "RNA"


def test_parse_crispritz_results_missing_target_columns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    guide_seq = "A" * 20 + "GGG"
    monkeypatch.setattr(crispritz, "_load_targets", lambda *args, **kwargs: pl.DataFrame({"crRNA": [guide_seq]}).lazy())
    profile = pd.DataFrame(
        [
            {
                "Guide": guide_seq,
                "ONT": "1",
                "OFFT": "1",
                "0MM": "1",
                "1MM": "0",
                "2MM": "0",
                "3MM": "0",
                "4MM": "0",
            }
        ]
    )
    monkeypatch.setattr(crispritz, "_load_profile", lambda path: profile)

    with pytest.raises(pl.exceptions.ColumnNotFoundError):
        crispritz._parse_crispritz_results(tmp_path, {guide_seq[:-3]: guide_seq})


def test_parse_crispritz_results_missing_profile_columns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    guide_seq = "A" * 20 + "GGG"
    targets_path = tmp_path / "out.Annotation.targets.txt"
    _write_targets_file(
        targets_path,
        [
            {
                "#Bulge type": "DNA",
                "crRNA": guide_seq,
                "DNA": "ACGTACGTACGTACGTACGTGGG",
                "Chromosome": "chr1",
                "Position": "10",
                "Cluster Position": "10",
                "Direction": "+",
                "Mismatches": "0",
                "Bulge Size": "0",
                "Total": "1",
                "Annotation_Type": "exon",
            }
        ],
    )

    monkeypatch.setattr(crispritz, "_load_profile", lambda path: pd.DataFrame({"Guide": [guide_seq]}))

    with pytest.raises(ValueError):
        crispritz._parse_crispritz_results(tmp_path, {guide_seq[:-3]: guide_seq})


@pytest.mark.integration
@pytest.mark.skipif(not INTEGRATION, reason="set RUN_INTEGRATION=1 to run")
def test_run_crispritz_with_fixture_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    data_dir = Path(__file__).parent.parent / "data" / "crispritz"
    targets_src = data_dir / "out.targets.txt"
    profile_src = data_dir / "out.profile.xls"
    assert targets_src.exists() and profile_src.exists(), "Provide CRISPRitz sample outputs under tests/data/crispritz"

    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_INDEX", "/fake/index")
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_PAM_TXT", "/fake/pam.txt")
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_ANNOTATIONS_BED", "/fake/annot.bed")
    monkeypatch.setattr(crispritz.settings, "CRISPRITZ_RESULTS_DIR", str(tmp_path))
    monkeypatch.setattr(crispritz, "calc_cfd", lambda wt, off: 0.5)

    class Completed:
        def __init__(self, stdout: str = "") -> None:
            self.returncode = 0
            self.stdout = stdout

    def fake_run(cmd, **kwargs):
        if len(cmd) >= 2 and cmd[1] == "search":
            out_prefix = Path(cmd[5])
            outputs_dir = out_prefix.parent
            outputs_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(targets_src, outputs_dir / "out.Annotation.targets.txt")
            shutil.copy(targets_src, outputs_dir / "out.targets.txt")
            shutil.copy(profile_src, outputs_dir / "out.profile.xls")
            return Completed(stdout="search ok")
        if len(cmd) >= 2 and cmd[1] == "annotate-results":
            return Completed(stdout="annotate ok")
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(crispritz.subprocess, "run", fake_run)

    candidates = [{"protospacer": "GAGTCCGAGCAGAAGAAGAA", "pam": "GGG"}]
    wt_lookup = {"GAGTCCGAGCAGAAGAAGAA": "GAGTCCGAGCAGAAGAAGAAGGG"}

    persist_dir = tmp_path / "job"
    results = crispritz.run_crispritz(candidates, wt_lookup, results_dir=persist_dir)

    assert len(results) == 1
    summary = results[0]
    assert summary["protospacer"] == "GAGTCCGAGCAGAAGAAGAA"
    assert summary["on_target_present"] is False
    assert summary["num_perfect_sites"] == 0
    assert summary["top_bulged"]
    assert summary["top_bulged"][0].bulge_type == "RNA+DNA"
    assert (persist_dir / "guides.txt").exists()
    assert (persist_dir / "outputs" / "out.profile.xls").exists()
