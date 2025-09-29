from fastapi import APIRouter
from schemas.validate import ValidateSequenceRequest, ValidateSequenceResponse
from services.sequence import gc_content, sanitize, _VALID_IUPAC

router = APIRouter()

@router.post("/validate-sequence", response_model=ValidateSequenceResponse)
def validate_sequence(payload: ValidateSequenceRequest):
    """Validate and analyze a DNA sequence."""

    orig = payload.sequence or ""
    normalized = sanitize(orig)
    length = len(normalized)
    gc = gc_content(normalized)
    warnings, errors = [], []
    if length == 0:
        errors.append("No valid DNA letters (A/C/G/T/N or IUPAC ambiguity codes) after cleaning")
    if 0 < length < 40:
        warnings.append("Sequence is short (<40 nt)")
    if length > 10000:
        warnings.append("Sequence is long (>10k nt)")
    if gc < 0.25:
        warnings.append("Low GC content (<25%)")
    if gc > 0.75:
        warnings.append("High GC content (>75%)")
    invalid_iupac = {
        ch.upper()
        for ch in orig
        if ch.isalpha() and ch.upper() not in _VALID_IUPAC and ch.upper() != "U"
    }
    if invalid_iupac:
        warnings.append("Sequence contains non-IUPAC characters. They will be ignored.")
    return ValidateSequenceResponse(
        length=length,
        normalized_sequence=normalized,
        gc_content=round(gc,4),
        warnings=warnings,
        errors=errors
    )
