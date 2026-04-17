# Automated AP/AR Reconciliation & Exception Reporting Tool

A Python-based reconciliation engine that automates source-to-ledger matching across high-volume AP/AR workflows. Flags transaction anomalies with standardized reason codes, generates audit-ready exception reports, and routes low-confidence matches to a human review queue.

## Business Problem

Manual cross-referencing of bank statements against general ledger records is time-consuming, error-prone, and difficult to scale. In environments processing 400–600+ daily transactions across multiple channels, undetected discrepancies can lead to revenue leakage, delayed close cycles, and audit findings.

## Solution

This tool replaces manual reconciliation with a multi-pass matching engine:

| Pass | Logic | Confidence |
|------|-------|------------|
| **Pass 1** | Exact match on reference + amount | 100% |
| **Pass 2** | Same reference + amount, date within 3-day window | 90% |
| **Pass 3** | Same reference, amount variance within $50 tolerance | 50–99% |
| **Pass 4** | No reference match — amount + date proximity | 60% |
| **Unmatched** | GL-only or Bank-only records flagged for review | 0% |

## Reason Code Framework

| Code | Description | Action |
|------|-------------|--------|
| RC-100 | Exact Match | Auto-reconciled |
| RC-200 | Timing Mismatch (within window) | Auto-reconciled, logged |
| RC-300 | Amount Discrepancy | Human review if variance > threshold |
| RC-400 | GL Record — No Bank Match | Investigate: missing payment or recording error |
| RC-500 | Bank Record — No GL Match | Investigate: unrecorded receipt or bank error |
| RC-600 | Duplicate Payment Detected | Immediate review required |
| RC-700 | Partial Match — Low Confidence | Human review queue |

## Human Review Queue

All records with confidence score below 0.70 are automatically routed to a human review queue. **The tool flags — the analyst decides.** No transaction is auto-cleared without meeting the confidence threshold, and no record is left without a disposition.

## Output

The tool generates an Excel exception report with:
- **Summary tab**: Count by reason code
- **Human Review Queue**: All items requiring analyst attention
- **Detail tabs**: One per reason code with full transaction details

## Tech Stack

- **Python 3.10+**
- **Pandas** — data manipulation and matching logic
- **openpyxl** — Excel report generation

## Quick Start

```bash
# Generate sample data (250+ transactions with built-in anomalies)
python generate_sample_data.py

# Run reconciliation
python reconciliation_engine.py
```

Output is saved to `output/exception_report_[timestamp].xlsx`.

## Sample Output

```
============================================================
  AP/AR RECONCILIATION SUMMARY
============================================================
  GL Records:                   222
  Bank Records:                 230
  ─────────────────────────────────
  Exact Matches (RC-100):       135
  Timing Mismatch (RC-200):      48
  Amount Variance (RC-300):      14
  GL Only (RC-400):              25
  Bank Only (RC-500):            17
  Duplicates (RC-600):           16
  Low Confidence (RC-700):        0
  ─────────────────────────────────
  Auto-Match Rate:            82.4%
  → Human Review Queue:          52
============================================================
```

## Design Decisions

- **Multi-pass architecture**: Exact matches are cleared first to reduce the candidate pool for fuzzy matching, improving both speed and accuracy.
- **Configurable thresholds**: Amount tolerance, timing window, and confidence cutoff are parameterized for different business contexts.
- **Reason codes over free text**: Standardized codes enable downstream root-cause tracking, trend analysis, and SOP development.
- **Confidence scoring**: Amount discrepancy confidence is inversely proportional to variance magnitude — larger variances get lower scores and mandatory human review.

## Author

Daniel Yin — [github.com/danielyin89](https://github.com/danielyin89)
