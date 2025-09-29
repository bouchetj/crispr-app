from pathlib import Path
from typing import List

import pytest

import services.design as design_service
from schemas.design import Guide, OffTargetSummary


def test_pam_matches_ngg():
    assert design_service._pam_matches_ngg("AGG")
    assert not design_service._pam_matches_ngg("AAA")
    assert not design_service._pam_matches_ngg("GG")


def test_find_spcas9_ngg_positive_strand():
    seq = "A" * 20 + "GGG" + "TTTT"
    hits = list(design_service.find_spcas9_ngg(seq))
    assert len(hits) == 1
    hit = hits[0]
    assert hit["strand"] == "+"
    assert hit["protospacer"] == "A" * 20
    assert hit["pam"] == "GGG"


def test_find_spcas9_ngg_negative_strand():
    seq = "CCCTTTTTTTTTTTTTTTTTTTT"
    hits = list(design_service.find_spcas9_ngg(seq))
    assert len(hits) == 1
    hit = hits[0]
    assert hit["strand"] == "-"
    assert hit["protospacer"] == "A" * 20
    assert hit["pam"] == "GGG"


def test_emit_progress_invokes_callback():
    calls: List[dict] = []

    def callback(**payload):
        calls.append(payload)

    design_service._emit_progress(callback, stage="stage", message="done", progress=0.5)
    assert calls == [{"stage": "stage", "message": "done", "progress": 0.5, "details": None}]


def test_emit_progress_ignores_missing_callback():
    design_service._emit_progress(None, stage="s", message="m")


def test_guide_sort_key_penalizes_missing_on_target():
    summary = OffTargetSummary()
    guide = Guide(
        protospacer="A" * 20,
        pam="GGG",
        strand="+",
        start=0,
        end=20,
        cut_site=17,
        context_30mer="N" * 30,
        rs3_score=0.8,
        on_target_present=False,
        num_perfect_sites=0,
        specificity=0.5,
        off_targets=summary,
        top_offtargets=[],
        top_bulged=[],
    )
    assert design_service._guide_sort_key(guide) < -1e8


def test_guide_sort_key_penalizes_multiple_perfect_sites():
    summary = OffTargetSummary()
    guide = Guide(
        protospacer="A" * 20,
        pam="GGG",
        strand="+",
        start=0,
        end=20,
        cut_site=17,
        context_30mer="N" * 30,
        rs3_score=0.8,
        on_target_present=True,
        num_perfect_sites=3,
        specificity=0.5,
        off_targets=summary,
        top_offtargets=[],
        top_bulged=[],
    )
    score = design_service._guide_sort_key(guide)
    assert score < 0.8


def test_score_rs3_returns_none_when_package_missing():
    result = design_service._score_rs3("N" * 30)
    assert result is None


def test_score_rs3_uses_predict_seq(monkeypatch: pytest.MonkeyPatch):
    import sys
    import types

    fake_rs3 = types.ModuleType("rs3.seq")

    def predict_seq(payload, sequence_tracr):
        assert payload == ["N" * 30]
        assert sequence_tracr == "Hsu2013"
        return [0.37]

    fake_rs3.predict_seq = predict_seq
    monkeypatch.setitem(sys.modules, "rs3", types.ModuleType("rs3"))
    monkeypatch.setitem(sys.modules, "rs3.seq", fake_rs3)

    try:
        assert design_service._score_rs3("N" * 30) == pytest.approx(0.37)
    finally:
        monkeypatch.delitem(sys.modules, "rs3", raising=False)
        monkeypatch.delitem(sys.modules, "rs3.seq", raising=False)


def test_design_requires_supported_configuration():
    with pytest.raises(ValueError):
        design_service.design("A" * 23, nuclease="SaCas9")


def test_design_ranks_guides(monkeypatch: pytest.MonkeyPatch):
    sequence = "A" * 20 + "GGG" + "TTTT"

    def fake_run_crispritz(candidates, wt_lookup, progress_callback=None, results_dir=None):
        assert len(candidates) == 1
        assert results_dir is None
        guide_seq = candidates[0]["protospacer"]
        summary = OffTargetSummary(num_hits=1, cfd_sum=0.1, mismatch_bins=[1, 0, 0, 0, 0])
        return [{
            "protospacer": guide_seq,
            "on_target_present": True,
            "num_perfect_sites": 1,
            "specificity": 0.9,
            "off_targets": summary,
            "top_offtargets": [],
            "top_bulged": [],
        }]

    monkeypatch.setattr(design_service, "run_crispritz", fake_run_crispritz)
    monkeypatch.setattr(design_service, "_score_rs3", lambda ctx: 0.8)

    guides = design_service.design(sequence, max_guides=1)
    assert len(guides) == 1
    guide = guides[0]
    assert guide.rank == 1
    assert guide.rs3_score == pytest.approx(0.8)
    assert guide.specificity == pytest.approx(0.9)


def test_design_passes_results_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    sequence = "A" * 20 + "GGG" + "TTTT"
    received = {}

    def fake_run_crispritz(candidates, wt_lookup, progress_callback=None, results_dir=None):
        received["results_dir"] = results_dir
        guide_seq = candidates[0]["protospacer"]
        summary = OffTargetSummary(num_hits=1, cfd_sum=0.0, mismatch_bins=[1, 0, 0, 0, 0])
        return [{
            "protospacer": guide_seq,
            "on_target_present": True,
            "num_perfect_sites": 1,
            "specificity": 1.0,
            "off_targets": summary,
            "top_offtargets": [],
            "top_bulged": [],
        }]

    monkeypatch.setattr(design_service, "run_crispritz", fake_run_crispritz)
    monkeypatch.setattr(design_service, "_score_rs3", lambda ctx: 0.5)

    guides = design_service.design(sequence, crispritz_results_dir=tmp_path)
    assert guides
    assert received["results_dir"] == tmp_path


def test_design_raises_when_summary_missing(monkeypatch: pytest.MonkeyPatch):
    sequence = "A" * 20 + "GGG" + "TTTT"

    monkeypatch.setattr(design_service, "run_crispritz", lambda *args, **kwargs: [])

    with pytest.raises(ValueError):
        design_service.design(sequence)
