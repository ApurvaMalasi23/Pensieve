"""
tests/test_risk_flagger.py
--------------------------
Unit tests for pensieve.risk_flagger.assess_table_risk().

Tests cover:
  - Clean tables that should NOT be flagged
  - Each individual signal firing in isolation
  - Multiple signals firing together
  - Edge cases (empty tables, single-row, single-column)
"""

from __future__ import annotations

import pytest

from pensieve.risk_flagger import assess_table_risk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def flag(grid: list[list[str]]) -> tuple[bool, list[str]]:
    """Convenience wrapper that infers num_rows / num_cols from the grid."""
    num_rows = len(grid)
    num_cols = max((len(row) for row in grid), default=0)
    return assess_table_risk(grid, num_rows, num_cols)


# ---------------------------------------------------------------------------
# Edge cases — should never crash, should return False
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_grid(self):
        risk, reasons = assess_table_risk([], 0, 0)
        assert risk is False
        assert reasons == []

    def test_single_cell(self):
        risk, reasons = flag([["Revenue"]])
        assert risk is False

    def test_single_row(self):
        risk, reasons = flag([["Revenue", "100", "200"]])
        assert risk is False

    def test_all_empty_cells(self):
        grid = [["", "", ""], ["", "", ""], ["", "", ""]]
        risk, reasons = flag(grid)
        assert risk is False


# ---------------------------------------------------------------------------
# Signal 1 — Repeated header phrase
# ---------------------------------------------------------------------------

class TestRepeatedHeaderPhrase:
    def test_no_repeated_phrase(self):
        """Normal financial table — no repeated phrases."""
        grid = [
            ["Particulars", "FY2024", "FY2023"],
            ["Revenue", "1000", "900"],
            ["EBITDA", "200", "180"],
            ["PAT", "120", "100"],
        ]
        risk, reasons = flag(grid)
        # Should not fire — "FY2024" and "FY2023" are different
        repeated_reasons = [r for r in reasons if "repeated-header" in r]
        assert not repeated_reasons

    def test_row0_cross_column_repetition_not_flagged(self):
        """Row 0 column headers legitimately repeat (e.g. December 31 across columns)."""
        grid = [
            ["", "December 31, 2024", "December 31, 2023", "December 31, 2022"],
            ["Company A", "100", "90", "80"],
            ["Company B", "200", "180", "160"],
        ]
        risk, reasons = flag(grid)
        repeated_reasons = [r for r in reasons if "repeated-header" in r]
        assert not repeated_reasons

    def test_sublabel_row1_repetition_not_flagged(self):
        """Row 1 sub-labels legitimately repeat across year columns (e.g. Amount / Ratio)."""
        grid = [
            ["", "2024", "", "2023", ""],
            ["Metric", "Amount", "Ratio", "Amount", "Ratio"],
            ["Assets", "1000", "12.5%", "900", "11.8%"],
        ]
        risk, reasons = flag(grid)
        repeated_reasons = [r for r in reasons if "repeated-header" in r]
        assert not repeated_reasons

    def test_glossary_adjacent_cells_not_flagged(self):
        """In glossary rows, definition repeating term name in adjacent cell should not fire."""
        grid = [
            ["Term", "Definition", "Term", "Definition"],
            ["ACLC", "Credit Losses", "Economic Aid Act", "Economic Aid to Hard-Hit Small Businesses"],
            ["Patriot Act", "U.S. Patriot Act", "Green Dot", "Green Dot Corporation"],
        ]
        risk, reasons = flag(grid)
        repeated_reasons = [r for r in reasons if "repeated-header" in r]
        assert not repeated_reasons

    def test_data_row_repeated_phrase_fires(self):
        """Simulates merged segment tables with repeated group headers in data rows."""
        grid = [
            ["Header 1", "Header 2", "Header 3", "Header 4", "Header 5"],
            ["Sub 1", "Sub 2", "Sub 3", "Sub 4", "Sub 5"],
            ["Segment", "republic processing group", "revenue", "republic processing group", "cost"],
            ["India", "500", "200", "450", "180"],
            ["USA", "300", "120", "280", "110"],
        ]
        risk, reasons = flag(grid)
        repeated_reasons = [r for r in reasons if "repeated-header" in r]
        assert len(repeated_reasons) >= 1
        assert risk is True

    def test_header_row_single_cell_repetition_fires(self):
        """Single header cell containing internal duplicated phrase (e.g. OCR defect) fires."""
        grid = [
            ["(in thousands)", "Term Loans Amortized", "Revolving Loans Revolving Loans Amortized"],
            ["2024", "100", "200"],
        ]
        risk, reasons = flag(grid)
        repeated_reasons = [r for r in reasons if "repeated-header" in r]
        assert len(repeated_reasons) >= 1
        assert risk is True

    def test_stopword_only_phrase_not_flagged(self):
        """Phrases made entirely of stopwords should not trigger the signal."""
        # "of the" is a stopword-only phrase
        grid = [
            ["Name of the entity", "Value of the asset", "Cost of the item"],
            ["Company A", "100", "90"],
            ["Company B", "200", "180"],
        ]
        risk, reasons = flag(grid)
        repeated_reasons = [r for r in reasons if "repeated-header" in r]
        assert not repeated_reasons


# ---------------------------------------------------------------------------
# Signal 2 — Row-label duplication
# ---------------------------------------------------------------------------

class TestRowLabelDuplication:
    def test_normal_table_no_flag(self):
        """10 rows, 8 distinct labels — ratio 1.25, well below threshold."""
        grid = [
            [f"Label {i}", "100", "90"]
            for i in range(10)
        ]
        risk, reasons = flag(grid)
        duplication_reasons = [r for r in reasons if "row-label-duplication" in r]
        assert not duplication_reasons

    def test_high_duplication_fires(self):
        """20 rows, 3 distinct labels — ratio ~6.7, well above default threshold of 2.5."""
        labels = ["Revenue", "Cost", "Profit"] * 7  # 21 items
        grid = [[label, str(i * 10), str(i * 9)] for i, label in enumerate(labels[:20])]
        risk, reasons = flag(grid)
        duplication_reasons = [r for r in reasons if "row-label-duplication" in r]
        assert len(duplication_reasons) >= 1
        assert risk is True

    def test_small_table_not_flagged(self):
        """Tables with < ROW_LABEL_MIN_DISTINCT distinct labels are skipped."""
        # Only 2 distinct labels — below the min_distinct threshold
        grid = [
            ["Revenue", "100"],
            ["Revenue", "200"],
            ["Cost", "90"],
            ["Cost", "80"],
            ["Cost", "70"],
        ]
        risk, reasons = flag(grid)
        duplication_reasons = [r for r in reasons if "row-label-duplication" in r]
        assert not duplication_reasons


# ---------------------------------------------------------------------------
# Signal 3 — Multi-value cells
# ---------------------------------------------------------------------------

class TestMultiValueCells:
    def test_clean_number_table(self):
        """One number per cell — should not trigger multi-value signal."""
        grid = [
            ["Revenue", "1,000", "900"],
            ["EBITDA", "200", "180"],
            ["PAT", "120", "100"],
            ["EPS", "10.5", "9.2"],
        ]
        risk, reasons = flag(grid)
        mv_reasons = [r for r in reasons if "multi-value" in r]
        assert not mv_reasons

    def test_multi_value_fires_when_fraction_exceeded(self):
        """Most cells contain 2+ numbers — signal should fire."""
        # Each data cell has two numbers squished together (extraction artifact)
        grid = [
            ["Metric", "Value 1", "Value 2"],
        ] + [
            [f"Item {i}", f"{i * 100} {i * 90}", f"{i * 50} {i * 45}"]
            for i in range(1, 11)  # 10 data rows
        ]
        risk, reasons = flag(grid)
        mv_reasons = [r for r in reasons if "multi-value" in r]
        assert len(mv_reasons) >= 1
        assert risk is True

    def test_sparse_multi_value_does_not_fire(self):
        """Only 1 multi-value cell in 10 rows — fraction below threshold."""
        grid = [
            ["Revenue", "1,000", "900"],
            ["EBITDA", "200", "180"],
            ["PAT", "120", "100"],
            ["EPS", "10.5", "9.2"],
            ["Debt", "500", "450"],
            ["Cash", "300", "280"],
            ["Capex", "150", "130"],
            ["Dividend", "25", "20"],
            # ONE bad cell with two numbers:
            ["Other income", "45 12", "38"],
            ["Tax", "60", "55"],
        ]
        risk, reasons = flag(grid)
        mv_reasons = [r for r in reasons if "multi-value" in r]
        assert not mv_reasons


# ---------------------------------------------------------------------------
# Combined signals
# ---------------------------------------------------------------------------

class TestCombinedSignals:
    def test_multiple_signals_combine(self):
        """A deeply broken table should fire multiple signals."""
        # Repeated header phrase in data rows + high row-label duplication
        repeated_labels = ["Revenue", "Cost", "Margin"] * 8  # 24 items
        grid = [
            ["Table Title", "Header 1", "Header 2", "Header 3", "Header 4"],
            ["Segment", "ACME Corp", "revenue 100", "ACME Corp", "cost 50"],
        ] + [
            [label, str(i * 10), str(i * 9), str(i * 8), str(i * 7)]
            for i, label in enumerate(repeated_labels[:12])
        ]
        risk, reasons = flag(grid)
        assert risk is True
        # Should have at least 2 distinct signal prefixes
        prefixes = {r.split("]")[0] + "]" for r in reasons}
        assert len(prefixes) >= 2

    def test_known_clean_simple_table(self):
        """A textbook clean 4-col financial table should not be flagged."""
        grid = [
            ["Particulars", "FY2024 (₹ Cr)", "FY2023 (₹ Cr)", "YoY Change"],
            ["Revenue from Operations", "15,234", "13,876", "+9.8%"],
            ["Other Income", "312", "287", "+8.7%"],
            ["Total Income", "15,546", "14,163", "+9.8%"],
            ["Total Expenses", "13,102", "12,015", "+9.0%"],
            ["EBIT", "2,444", "2,148", "+13.8%"],
            ["Finance Costs", "145", "132", "+9.8%"],
            ["PBT", "2,299", "2,016", "+14.0%"],
            ["Tax", "578", "508", "+13.8%"],
            ["PAT", "1,721", "1,508", "+14.1%"],
        ]
        risk, reasons = flag(grid)
        assert risk is False
        assert reasons == []


# ---------------------------------------------------------------------------
# Known manual review cases from TEST DOC - 1.pdf
# ---------------------------------------------------------------------------

class TestKnownDocumentCases:
    def test_glossary_table_page_7_unflagged(self):
        """Glossary table with 'Term | Definition' columns should not be flagged."""
        grid = [
            ["Term", "Definition", "Term", "Definition", "Term", "Definition"],
            ["2023 Tax", "December 2022 through February 2023", "DTL", "Deferred Tax Liabilities", "NM", "Not Meaningful"],
            ["ACH", "Automated Clearing House", "Economic Aid Act", "Economic Aid to Hard-Hit Small Businesses, Nonprofits, and Venues Act", "OREO", "Other Real Estate Owned"],
            ["ACLC", "Allowance for Credit Losses", "ERA", "Early Season Refund Advance", "Patriot Act", "U.S. Patriot Act"],
            ["CCAD", "Commercial Credit Administration", "Green Dot", "Green Dot Corporation", "SAC", "Special Asset Committee"],
        ]
        risk, reasons = flag(grid)
        assert risk is False
        assert reasons == []

    def test_capital_ratio_page_25_unflagged(self):
        """Capital ratio table with sub-labels 'Amount | Ratio' repeated across years should not be flagged."""
        grid = [
            ["", "2024", "", "2023", ""],
            ["December 31, (dollars in thousands)", "Amount", "Ratio", "Amount", "Ratio"],
            ["Total capital to risk-weighted assets", "", "", "", ""],
            ["Republic Bancorp, Inc.", "$ 1,042,149", "16.98 %", "$ 968,844", "16.10 %"],
            ["Republic Bank & Trust Company", "989,800", "16.14", "931,923", "15.50"],
        ]
        risk, reasons = flag(grid)
        assert risk is False
        assert reasons == []

    def test_stock_performance_page_44_unflagged(self):
        """Stock performance table with 'December 31, YYYY' repeating across columns should not be flagged."""
        grid = [
            ["", "December 31, 2019", "December 31, 2020", "December 31, 2021", "December 31, 2022", "December 31, 2023", "December 31, 2024"],
            ["Republic Class A Common Stock (RBCAA)", "$ 100.00", "$ 79.82", "$ 115.37", "$ 95.83", "$ 133.55", "$ 173.98"],
            ["S&P 500 Index", "100.00", "118.40", "152.39", "124.79", "157.59", "197.02"],
            ["KBW NASDAQ Bank Index", "100.00", "89.69", "124.06", "97.52", "96.65", "132.60"],
        ]
        risk, reasons = flag(grid)
        assert risk is False
        assert reasons == []

    def test_interest_rate_page_89_stays_flagged(self):
        """Interest rate sensitivity table with high multi-value cells stays flagged."""
        grid = [
            ["", "Change in Rates", "", "", "", "", "", "", ""],
            ["", "-400 Basis Points", "-300 Basis Points", "-200 Basis Points", "-100 Basis Points", "+100 Basis Points", "+200 Basis Points", "+300 Basis Points", "+400 Basis Points"],
            ["% Change from base net interest income as of December 31, 2024", "3.4 %", "4.4 %", "(0.2) %", "0.2 %", "1.5 %", "3.1 %", "4.4 %", "6.0 %"],
            ["% Change from base net interest income as of December 31, 2023", "6.4 %", "5.0 %", "0.1 %", "0.2 %", "(1.0)%", "(2.1)%", "(3.1)%", "(4.1) %"],
        ]
        risk, reasons = flag(grid)
        assert risk is True
        assert any("multi-value" in r for r in reasons)

    def test_loan_schedules_page_124_stays_flagged(self):
        """Scrambled loan schedule with internal phrase duplication in cell stays flagged."""
        grid = [
            ["(in thousands)", "Term Loans Amortized Cost Basis by Origination Year (Continued)", "", "", "", "", "", "Revolving Loans Revolving Loans Amortized Converted", "", ""],
            ["As of December 31, 2023", "2023", "2022 2021", "", "2020", "2019", "Prior", "Cost Basis", "to Term", "Total"],
            ["Commercial and industrial:", "", "", "", "", "", "", "", "", ""],
            ["Risk Rating", "", "", "", "", "", "", "", "", ""],
            ["Pass or not rated", "$ 140,753 $", "87,497 $", "70,149 $", "13,150", "$ 10,175", "$ 10,782", "$ 120,069", "$ 3,968", "$ 456,543"],
        ]
        risk, reasons = flag(grid)
        assert risk is True
        assert any("repeated-header" in r for r in reasons)
