import pytest

from services.sequence import context_window, gc_content, reverse_complement, sanitize


def test_sanitize_cleans_sequence():
    assert sanitize("a c-g_tu123") == "ACGTT"


def test_sanitize_returns_empty_for_no_letters():
    assert sanitize("12345-=-") == ""


def test_gc_content_computes_fraction():
    seq = "AACCGGTTNN"
    assert gc_content(seq) == pytest.approx(0.5)


def test_gc_content_handles_no_canonical_bases():
    assert gc_content("NNNNRRYY") == 0.0


def test_reverse_complement_basic():
    assert reverse_complement("ACGTN") == "NACGT"


def test_context_window_pads_at_sequence_edges():
    seq = "ACGT"
    window = context_window(seq, 0, 1)
    assert window == "NNNNACGTNNN"


def test_context_window_internal_region():
    seq = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    window = context_window(seq, 5, 10)
    assert window == "BCDEFGHIJKLMNOP"


def test_context_window_returns_30mer_for_spcas9_candidate():
    seq = "TTTT" + ("A" * 20) + "GGG" + "CCC"
    window = context_window(seq, 4, 24)
    assert len(window) == 30
    assert window == "TTTT" + ("A" * 20) + "GGG" + "CCC"
