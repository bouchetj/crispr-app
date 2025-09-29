import pickle
from pathlib import Path
import os
import pytest

import services.cfd_score as cfd_score
from services.cfd_score import (
    _calc_cfd,
    _load_scores,
    calc_cfd,
    get_mm_pam_scores,
    load_pickle,
    revcom,
    validate_sequence,
)

INTEGRATION = os.getenv("RUN_INTEGRATION") == "1"


@pytest.fixture(autouse=True)
def clear_load_scores_cache():
    _load_scores.cache_clear()
    yield
    _load_scores.cache_clear()


def test_revcom_basic():
    assert revcom("ACGT") == "ACGT"
    assert revcom("AATTGGAATCC") == "GGATTCCAATT"


def test_revcom_invalid_base_raises():
    with pytest.raises(ValueError):
        revcom("ABX")


def test_load_pickle(tmp_path: Path):
    data = {"a": 1.0}
    pkl_path = tmp_path / "data.pkl"
    with pkl_path.open("wb") as handle:
        pickle.dump(data, handle)
    assert load_pickle(pkl_path) == data


def test_get_mm_pam_scores_success(tmp_path: Path):
    mm = {"key": 0.5}
    pam = {"GG": 0.9}
    mm_path = tmp_path / "mm.pkl"
    pam_path = tmp_path / "pam.pkl"
    for content, path in ((mm, mm_path), (pam, pam_path)):
        with path.open("wb") as handle:
            pickle.dump(content, handle)

    scores = get_mm_pam_scores(mm_path, pam_path)
    assert scores == (mm, pam)


def test_get_mm_pam_scores_missing_file(tmp_path: Path):
    mm_path = tmp_path / "missing_mm.pkl"
    pam_path = tmp_path / "missing_pam.pkl"
    with pytest.raises(FileNotFoundError):
        get_mm_pam_scores(mm_path, pam_path)


def test_calc_cfd_internal_helper():
    wt = "A" + "C" * 19 + "GGG"
    sg = "T" + "C" * 19
    pam = "GG"
    mm_scores = {"rA:dA,1": 0.5}
    pam_scores = {"GG": 0.8}
    score = _calc_cfd(wt, sg, pam, mm_scores, pam_scores)
    assert score == pytest.approx(0.4)


def test_calc_cfd_missing_mismatch_key():
    wt = "A" + "C" * 19 + "GGG"
    sg = "T" + "C" * 19
    pam = "GG"
    with pytest.raises(KeyError):
        _calc_cfd(wt, sg, pam, {}, {"GG": 1.0})


def test_calc_cfd_missing_pam_key():
    wt = "A" + "C" * 19 + "GGG"
    sg = "T" + "C" * 19
    pam = "GG"
    with pytest.raises(KeyError):
        _calc_cfd(wt, sg, pam, {"rA:dA,1": 1.0}, {})


def test_validate_sequence_allows_acgt():
    validate_sequence("label", "ACGT")


def test_validate_sequence_rejects_invalid():
    with pytest.raises(ValueError):
        validate_sequence("guide", "ABCD")


def test_load_scores_reads_from_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mm = {"rA:dA,1": 0.5}
    pam = {"GG": 0.8}
    mm_path = tmp_path / "mm.pkl"
    pam_path = tmp_path / "pam.pkl"
    for data, path in ((mm, mm_path), (pam, pam_path)):
        with path.open("wb") as handle:
            pickle.dump(data, handle)

    monkeypatch.setattr(cfd_score.settings, "MISMATCH_SCORES", str(mm_path))
    monkeypatch.setattr(cfd_score.settings, "PAM_SCORES", str(pam_path))

    mm_scores, pam_scores = _load_scores()
    assert mm_scores == mm
    assert pam_scores == pam


def test_load_scores_missing_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cfd_score.settings, "MISMATCH_SCORES", "")
    monkeypatch.setattr(cfd_score.settings, "PAM_SCORES", "")
    with pytest.raises(RuntimeError):
        _load_scores()


def test_calc_cfd_validates_and_uses_scores(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cfd_score, "_load_scores", lambda: (
        {"rA:dA,1": 0.5},
        {"GG": 0.8},
    ))
    wt = "A" + "C" * 19 + "GGG"
    off = "T" + "C" * 19 + "GGG"
    score = calc_cfd(wt, off)
    assert score == pytest.approx(0.4)


def test_calc_cfd_validates_length(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cfd_score, "_load_scores", lambda: ({}, {}))
    with pytest.raises(ValueError):
        calc_cfd("A" * 22, "A" * 22)


def test_calc_cfd_validates_characters(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cfd_score, "_load_scores", lambda: ({}, {}))
    with pytest.raises(ValueError):
        calc_cfd("ACGTZ" + "A" * 18, "A" * 23)


@pytest.mark.integration
@pytest.mark.skipif(not INTEGRATION, reason="set RUN_INTEGRATION=1 to run")
def test_calc_cfd_with_real_pickles():
    base = Path("data/CFD_scoring_matrix")
    mm_path = base / "mismatch_score.pkl"
    pam_path = base / "pam_scores.pkl"
    assert mm_path.exists() and pam_path.exists(), "CFD pickles missing"

    monkeypatch = pytest.MonkeyPatch()
    import services.cfd_score as cfd
    monkeypatch.setattr(cfd.settings, "MISMATCH_SCORES", str(mm_path))
    monkeypatch.setattr(cfd.settings, "PAM_SCORES", str(pam_path))
    cfd._load_scores.cache_clear()

    wt = "ACGT" * 5 + "GGG"
    off = wt  # perfect match should yield score == 1.0
    score = cfd.calc_cfd(wt, off)
    assert score == 1.0