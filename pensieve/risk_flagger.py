"""
pensieve/risk_flagger.py
------------------------
Task 4 — Table Risk Flagging

Assesses structural risk for a single extracted table.  This is a
modular, tunable component — all thresholds live in config.py.  The
flag does NOT trigger auto-correction; it exists so:

  • Phase 6 (frontend) can show "verify this table against source page"
  • Phase 4 (numeric verification) can treat numbers from flagged
    tables with lower confidence

Design rationale (from Phase 0 validation):
  - A naive "two number-like tokens in one cell" heuristic both
    over-flags (dense text tables) and under-flags (scrambled tables
    with merged multi-row headers).
  - The clearest real failure pattern: Docling occasionally merges
    multiple separate tables into one garbled table, especially where
    multi-row/multi-column headers repeat.
  - Three independent signals are combined into one flag + reason list.

Public API
----------
    assess_table_risk(
        grid: list[list[str]],
        num_rows: int,
        num_cols: int,
    ) -> tuple[bool, list[str]]
"""

from __future__ import annotations

import re
from collections import Counter

from pensieve.config import (
    MULTI_VALUE_CELL_MIN_NUMBERS,
    MULTI_VALUE_ROW_FRACTION,
    REPEATED_PHRASE_MIN_OCCURRENCES,
    REPEATED_PHRASE_MIN_WORDS,
    ROW_LABEL_DUPLICATION_RATIO,
    ROW_LABEL_MIN_DISTINCT,
)
from pensieve.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Matches individual number tokens (integers, decimals, percentages,
# numbers with commas).  NOTE: \s is intentionally excluded from the
# character class so that "100 90" counts as TWO tokens, not one.
_NUMBER_RE = re.compile(r"\b\d[\d,.]*\d\b|\b\d+\b")


def _number_token_count(cell_text: str) -> int:
    """Count the number-like tokens in a single cell string."""
    return len(_NUMBER_RE.findall(cell_text))


# Pre-compiled pattern to strip non-alphanumeric characters from a word.
_PUNCTUATION_STRIP_RE = re.compile(r"[^\w]", re.UNICODE)

# Minimum character length for a word to be included in n-gram phrase analysis.
# This filters financial abbreviations (cr, mn, bn), single letters, and
# currency symbols that legitimately repeat in column headers.
_PHRASE_MIN_WORD_LEN = 3


def _words_from_cell(cell_text: str) -> list[str]:
    """Extract meaningful words from a cell for repeated-phrase analysis.

    Lowercases, strips punctuation/symbols from each token, and keeps
    only purely-alphabetic words of at least _PHRASE_MIN_WORD_LEN chars.
    This filters out:
    - Currency symbols (₹, $, €)
    - Brackets and punctuation attached to words like "(Cr)"
    - Common financial abbreviations (cr, mn, bn, yoy) that repeat
      legitimately in column headers
    """
    result: list[str] = []
    for token in cell_text.lower().split():
        cleaned = _PUNCTUATION_STRIP_RE.sub("", token)
        if cleaned.isalpha() and len(cleaned) >= _PHRASE_MIN_WORD_LEN:
            result.append(cleaned)
    return result


def _ngrams(words: list[str], n: int) -> list[str]:
    """Return all n-grams from a word list as joined strings."""
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


# ---------------------------------------------------------------------------
# Signal 1 — Repeated header-like phrase
# ---------------------------------------------------------------------------

def _is_sublabel_row(row: list[str]) -> bool:
    """Return True if row 1 looks like a sub-label row rather than a data row.

    Sub-label rows typically contain column subtitles or unit labels
    (e.g. "Amount", "Ratio", "₹ Cr", "in thousands", short text labels)
    with few or no numeric values.
    """
    if not row:
        return False
    non_empty = [c.strip() for c in row if c.strip()]
    if not non_empty:
        return True
    num_numeric = sum(1 for c in non_empty if _number_token_count(c) > 0)
    # If fewer than 35% of non-empty cells contain numbers, treat as sub-label
    return (num_numeric / len(non_empty)) < 0.35


def _check_repeated_header_phrase(grid: list[list[str]]) -> list[str]:
    """Return risk reasons if data rows have a repeated multi-word phrase,
    or if a header cell has an internal duplicated phrase.

    Header rows (row 0, and row 1 if sub-label) legitimately repeat
    column labels across different columns (e.g. 'Amount'/'Ratio' across
    year columns, or 'December 31' across date columns).  Those are
    excluded from cross-column repetition checks.

    Data rows (rows after detected header rows) are scanned for repeated
    phrases across non-adjacent column positions, which indicates merged
    or scrambled sub-tables.
    """
    if not grid:
        return []

    # Treat row 0 as a header row always.
    # Also treat row 1 as a header row if it looks like a sub-label row.
    header_row_indices = {0}
    if len(grid) > 1 and _is_sublabel_row(grid[1]):
        header_row_indices.add(1)

    reasons: list[str] = []

    for row_idx, row in enumerate(grid):
        is_header_row = (row_idx in header_row_indices)

        if is_header_row:
            # In header rows, normal cross-column repetition of labels (e.g.
            # Amount/Ratio, Dec 31, Term/Definition) is expected and skipped.
            # However, if a single cell internally duplicates a phrase
            # (e.g. "Revolving Loans Revolving Loans"), it indicates an OCR/
            # cell-boundary collapse defect.
            for cell_idx, cell in enumerate(row):
                cell_words = _words_from_cell(cell)
                n = REPEATED_PHRASE_MIN_WORDS
                if len(cell_words) < n * REPEATED_PHRASE_MIN_OCCURRENCES:
                    continue
                counts = Counter(_ngrams(cell_words, n))
                internal_reps = [
                    p for p, c in counts.items()
                    if c >= REPEATED_PHRASE_MIN_OCCURRENCES
                    and not all(w in _STOP_WORDS for w in p.split())
                ]
                if internal_reps:
                    reasons.append(
                        f"row {row_idx} cell {cell_idx}: phrase repeated within single cell — "
                        + ", ".join(f'"{p}" ×{counts[p]}' for p in internal_reps[:3])
                    )
            continue

        # Data row: scan for repeated phrases across cells
        cell_words_map: list[list[str]] = [_words_from_cell(cell) for cell in row]
        row_words: list[str] = []
        for words in cell_words_map:
            row_words.extend(words)

        n = REPEATED_PHRASE_MIN_WORDS
        if len(row_words) < n:
            continue

        phrase_counts = Counter(_ngrams(row_words, n))
        candidate_phrases = [
            phrase
            for phrase, count in phrase_counts.items()
            if count >= REPEATED_PHRASE_MIN_OCCURRENCES
            and not all(w in _STOP_WORDS for w in phrase.split())
        ]

        if not candidate_phrases:
            continue

        valid_repeated = []
        for phrase in candidate_phrases:
            cells_with_phrase = [
                idx for idx, words in enumerate(cell_words_map)
                if phrase in " ".join(words)
            ]
            if len(cells_with_phrase) >= 2:
                # Avoid false positives on glossary/dictionary tables where adjacent
                # cells repeat the term in the definition (e.g. "Economic Aid Act" in col i
                # and "Economic Aid to..." in col i+1). Require occurrences to span
                # non-adjacent columns (separated by at least one column).
                has_separated = any(
                    (cells_with_phrase[b] - cells_with_phrase[a] >= 2)
                    for a in range(len(cells_with_phrase))
                    for b in range(a + 1, len(cells_with_phrase))
                )
                if has_separated:
                    valid_repeated.append(phrase)
            elif phrase_counts[phrase] >= REPEATED_PHRASE_MIN_OCCURRENCES:
                # Repeated multiple times within the same cell
                valid_repeated.append(phrase)

        if valid_repeated:
            reasons.append(
                f"row {row_idx}: repeated phrase(s) detected — "
                + ", ".join(f'"{p}" ×{phrase_counts[p]}' for p in valid_repeated[:3])
            )

    return reasons


# Common stopwords to avoid flagging trivial repeated phrases.
_STOP_WORDS = frozenset(
    {
        "the", "a", "an", "of", "in", "on", "at", "to", "and",
        "or", "for", "with", "by", "as", "is", "are", "was",
        "be", "it", "its", "this", "that", "from", "not",
    }
)


# ---------------------------------------------------------------------------
# Signal 2 — Implausible row-count relative to distinct leading-column labels
# ---------------------------------------------------------------------------

def _check_row_label_duplication(
    grid: list[list[str]],
    num_rows: int,
) -> list[str]:
    """Return risk reasons if row labels appear implausibly duplicated.

    If num_rows / distinct_leading_labels > ROW_LABEL_DUPLICATION_RATIO
    (and there are at least ROW_LABEL_MIN_DISTINCT distinct labels),
    it suggests rows were split or duplicated incorrectly during extraction.
    """
    if num_rows < 2:
        return []

    leading_labels = [
        row[0].strip().lower() for row in grid if row and row[0].strip()
    ]
    if not leading_labels:
        return []

    distinct_labels = len(set(leading_labels))

    # Avoid false positives on tiny tables or tables with basically one label.
    if distinct_labels < ROW_LABEL_MIN_DISTINCT:
        return []

    ratio = num_rows / distinct_labels
    if ratio > ROW_LABEL_DUPLICATION_RATIO:
        return [
            f"row-label duplication ratio {ratio:.1f} "
            f"({num_rows} rows / {distinct_labels} distinct leading labels) "
            f"exceeds threshold {ROW_LABEL_DUPLICATION_RATIO}"
        ]

    return []


# ---------------------------------------------------------------------------
# Signal 3 — Multi-value cells (two or more numeric tokens in one cell)
# ---------------------------------------------------------------------------

def _check_multi_value_cells(grid: list[list[str]], num_rows: int) -> list[str]:
    """Return risk reasons if too many rows contain multi-value cells.

    A cell is "multi-value" if it contains ≥ MULTI_VALUE_CELL_MIN_NUMBERS
    number-like tokens.  The signal fires only when the fraction of rows
    with at least one such cell exceeds MULTI_VALUE_ROW_FRACTION, to
    avoid false positives on tables that legitimately contain dense text.
    """
    if num_rows == 0:
        return []

    flagged_rows = 0
    for row in grid:
        for cell in row:
            if _number_token_count(cell) >= MULTI_VALUE_CELL_MIN_NUMBERS:
                flagged_rows += 1
                break  # one multi-value cell is enough to count this row

    fraction = flagged_rows / num_rows
    if fraction > MULTI_VALUE_ROW_FRACTION:
        return [
            f"{flagged_rows}/{num_rows} rows ({fraction:.0%}) contain cells "
            f"with ≥{MULTI_VALUE_CELL_MIN_NUMBERS} numeric tokens "
            f"(threshold {MULTI_VALUE_ROW_FRACTION:.0%})"
        ]

    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess_table_risk(
    grid: list[list[str]],
    num_rows: int,
    num_cols: int,
) -> tuple[bool, list[str]]:
    """Assess structural risk for a single extracted table.

    Runs three independent signals and combines them into a single
    boolean flag + an inspectable list of reasons.

    Parameters
    ----------
    grid:
        2-D list of cell strings (row-major order).
    num_rows:
        Number of rows (should equal len(grid)).
    num_cols:
        Number of columns (should equal max(len(row) for row in grid)).

    Returns
    -------
    (risk_flag, risk_reasons)
        risk_flag:    True if any signal fired.
        risk_reasons: Human-readable explanation of which signals fired
                      and why.  Empty list when risk_flag is False.
    """
    if not grid or num_rows == 0 or num_cols == 0:
        return False, []

    all_reasons: list[str] = []

    # --- Signal 1: repeated header phrase ---
    reasons_s1 = _check_repeated_header_phrase(grid)
    if reasons_s1:
        all_reasons.extend(
            f"[repeated-header] {r}" for r in reasons_s1
        )

    # --- Signal 2: row-label duplication ---
    reasons_s2 = _check_row_label_duplication(grid, num_rows)
    if reasons_s2:
        all_reasons.extend(
            f"[row-label-duplication] {r}" for r in reasons_s2
        )

    # --- Signal 3: multi-value cells ---
    reasons_s3 = _check_multi_value_cells(grid, num_rows)
    if reasons_s3:
        all_reasons.extend(
            f"[multi-value-cells] {r}" for r in reasons_s3
        )

    risk_flag = bool(all_reasons)

    if risk_flag:
        log.debug(
            "Table risk flag raised (%d signal(s)): %s",
            len(all_reasons),
            "; ".join(all_reasons),
        )

    return risk_flag, all_reasons
