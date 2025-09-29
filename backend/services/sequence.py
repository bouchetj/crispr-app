from typing import Set

_COMPLEMENT = str.maketrans({
    "A": "T",
    "C": "G",
    "G": "C",
    "T": "A",
    "N": "N",
    "R": "Y",
    "Y": "R",
    "K": "M",
    "M": "K",
    "S": "S",
    "W": "W",
    "B": "V",
    "D": "H",
    "H": "D",
    "V": "B"
})

_VALID_IUPAC: Set[str] = set("ACGTNRYKMSWBDHV")

def sanitize(seq: str) -> str:
    """
    Clean a sequence:
    - remove non-letter characters
    - map U -> T (case-insensitive)
    - keep canonical bases A,C,G,T and IUPAC ambiguity codes (uppercased)
    - return uppercase string
    """
    if not seq:
        return ""
    sanitized = []
    for ch in seq:
        if not ch.isalpha():
            continue
        upper = ch.upper()
        if upper == "U":
            upper = "T"
        if upper in _VALID_IUPAC:
            sanitized.append(upper)
    return "".join(sanitized)

def gc_content(seq_upper: str) -> float:
    """
    Compute GC fraction among canonical bases A/C/G/T.
    Ambiguous bases (N, R, etc.) are excluded from the denominator.
    Returns 0.0 if no canonical bases are present.
    """
    if not seq_upper:
        return 0.0
    s = seq_upper.upper()
    gc = s.count("G") + s.count("C")
    denom = s.count("A") + s.count("C") + s.count("G") + s.count("T")
    return (gc / denom) if denom else 0.0


def reverse_complement(seq_upper: str) -> str:
    """Return the reverse complement of a DNA sequence."""
    if not seq_upper:
        return ""
    return seq_upper.upper().translate(_COMPLEMENT)[::-1]


def context_window(
    seq_upper: str,
    start: int,
    end: int,
    flank_left: int = 4,
    flank_right: int = 3,
) -> str:
    """Return a 30nt context: 4bp upstream, 20bp protospacer, PAM, then 3bp downstream."""
    pam_len = 3

    prefix = seq_upper[max(0, start - flank_left):start]
    core = seq_upper[start:end]
    pam = seq_upper[end:end + pam_len]
    suffix = seq_upper[end + pam_len:end + pam_len + flank_right]

    # Pad with N if near sequence boundaries to maintain constant window size
    if len(prefix) < flank_left:
        prefix = ("N" * (flank_left - len(prefix))) + prefix
    if len(pam) < pam_len:
        pam = pam + ("N" * (pam_len - len(pam)))
    if len(suffix) < flank_right:
        suffix = suffix + ("N" * (flank_right - len(suffix)))

    return prefix + core + pam + suffix
