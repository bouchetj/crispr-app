import pytest

from api.routes import validate as validate_route
from schemas.validate import ValidateSequenceRequest


def test_validate_sequence_with_no_valid_bases():
    req = ValidateSequenceRequest(sequence="12345!!!")
    resp = validate_route.validate_sequence(req)
    assert resp.length == 0
    assert resp.normalized_sequence == ""
    assert resp.errors == [
        "No valid DNA letters (A/C/G/T/N or IUPAC ambiguity codes) after cleaning"
    ]
    assert "Low GC content" not in resp.warnings


def test_validate_sequence_short_and_high_gc():
    req = ValidateSequenceRequest(sequence="GGGGGGGGGGGGGGGGGGGG")
    resp = validate_route.validate_sequence(req)
    assert resp.length == 20
    assert resp.gc_content == pytest.approx(1.0)
    assert "Sequence is short (<40 nt)" in resp.warnings
    assert "High GC content (>75%)" in resp.warnings
    assert not resp.errors


def test_validate_sequence_long_and_low_gc():
    req = ValidateSequenceRequest(sequence="A" * 10001)
    resp = validate_route.validate_sequence(req)
    assert resp.length == 10001
    assert resp.gc_content == pytest.approx(0.0)
    assert "Sequence is long (>10k nt)" in resp.warnings
    assert "Low GC content (<25%)" in resp.warnings
    assert not resp.errors
