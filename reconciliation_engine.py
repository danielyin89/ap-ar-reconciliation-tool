"""
AP/AR Reconciliation & Exception Reporting Tool

Automates source-to-ledger reconciliation across high-volume AP/AR workflows.
Matches bank statement transactions against GL records using multi-pass logic,
flags anomalies with standardized reason codes, and routes low-confidence
matches to a human review queue.

Author: Daniel Yin (github.com/danielyin89)
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────
AMOUNT_TOLERANCE = 0.01          # Exact match threshold
AMOUNT_VARIANCE_LIMIT = 50.00   # Max $ variance before flagging
TIMING_WINDOW_DAYS = 3          # Days allowed for timing mismatch
CONFIDENCE_THRESHOLD = 0.70     # Below this → human review queue

REASON_CODES = {
    "RC-100": "Exact Match",
    "RC-200": "Timing Mismatch (within window)",
    "RC-300": "Amount Discrepancy",
    "RC-400": "GL Record - No Bank Match",
    "RC-500": "Bank Record - No GL Match",
    "RC-600": "Duplicate Payment Detected",
    "RC-700": "Partial Match - Low Confidence",
}


def load_data(gl_path: str, bank_path: str):
    gl = pd.read_csv(gl_path, parse_dates=["gl_date"])
    bank = pd.read_csv(bank_path, parse_dates=["bank_date"])
    print(f"Loaded {len(gl)} GL records, {len(bank)} bank records")
    return gl, bank


def detect_duplicates(bank: pd.DataFrame) -> pd.DataFrame:
    """Flag duplicate bank entries by reference + amount."""
    dup_mask = bank.duplicated(subset=["reference", "bank_amount"], keep=False)
    dupes = bank[dup_mask].copy()
    if not dupes.empty:
        dupes["reason_code"] = "RC-600"
        dupes["reason"] = REASON_CODES["RC-600"]
        dupes["confidence"] = 0.95
        # Keep first occurrence for matching, flag rest as duplicates
        first_idx = bank[dup_mask].drop_duplicates(subset=["reference", "bank_amount"], keep="first").index
        dupes = dupes[~dupes.index.isin(first_idx)]
    return dupes


def pass_1_exact_match(gl: pd.DataFrame, bank: pd.DataFrame):
    """Pass 1: Match on reference + exact amount + same date."""
    merged = gl.merge(bank, on="reference", how="inner")
    date_match = merged["gl_date"] == merged["bank_date"]
    exact = merged[date_match & (abs(merged["gl_amount"] - merged["bank_amount"]) <= AMOUNT_TOLERANCE)].copy()
    exact["reason_code"] = "RC-100"
    exact["reason"] = REASON_CODES["RC-100"]
    exact["confidence"] = 1.00
    exact["variance"] = 0.00
    matched_gl_refs = set(exact["reference"])
    matched_bank_refs = set(exact["reference"])
    return exact, matched_gl_refs, matched_bank_refs


def pass_2_timing_mismatch(gl: pd.DataFrame, bank: pd.DataFrame, matched_gl: set, matched_bank: set):
    """Pass 2: Same reference + amount but different dates within window."""
    gl_remaining = gl[~gl["reference"].isin(matched_gl)]
    bank_remaining = bank[~bank["reference"].isin(matched_bank)]
    merged = gl_remaining.merge(bank_remaining, on="reference", how="inner")
    amount_match = abs(merged["gl_amount"] - merged["bank_amount"]) <= AMOUNT_TOLERANCE
    date_diff = abs((merged["gl_date"] - merged["bank_date"]).dt.days)
    timing = merged[amount_match & (date_diff <= TIMING_WINDOW_DAYS) & (date_diff > 0)].copy()
    timing["reason_code"] = "RC-200"
    timing["reason"] = REASON_CODES["RC-200"]
    timing["confidence"] = 0.90
    timing["variance"] = 0.00
    timing["days_offset"] = abs((timing["gl_date"] - timing["bank_date"]).dt.days)
    return timing, set(timing["reference"])


def pass_3_amount_discrepancy(gl: pd.DataFrame, bank: pd.DataFrame, matched_gl: set, matched_bank: set):
    """Pass 3: Same reference but amount differs within variance limit."""
    gl_remaining = gl[~gl["reference"].isin(matched_gl)]
    bank_remaining = bank[~bank["reference"].isin(matched_bank)]
    merged = gl_remaining.merge(bank_remaining, on="reference", how="inner")
    variance = abs(merged["gl_amount"] - merged["bank_amount"])
    amount_disc = merged[(variance > AMOUNT_TOLERANCE) & (variance <= AMOUNT_VARIANCE_LIMIT)].copy()
    amount_disc["variance"] = round(amount_disc["gl_amount"] - amount_disc["bank_amount"], 2)
    amount_disc["reason_code"] = "RC-300"
    amount_disc["reason"] = REASON_CODES["RC-300"]
    amount_disc["confidence"] = amount_disc["variance"].abs().apply(
        lambda v: round(max(0.50, 1.0 - (v / AMOUNT_VARIANCE_LIMIT)), 2)
    )
    return amount_disc, set(amount_disc["reference"])


def pass_4_fuzzy_match(gl: pd.DataFrame, bank: pd.DataFrame, matched_gl: set, matched_bank: set):
    """Pass 4: No reference match — attempt amount + date proximity matching."""
    gl_remaining = gl[~gl["reference"].isin(matched_gl)].copy()
    bank_remaining = bank[~bank["reference"].isin(matched_bank)].copy()
    fuzzy_matches = []

    for _, gl_row in gl_remaining.iterrows():
        candidates = bank_remaining[
            (abs(bank_remaining["bank_amount"] - gl_row["gl_amount"]) <= AMOUNT_TOLERANCE) &
            (abs((bank_remaining["bank_date"] - gl_row["gl_date"]).dt.days) <= TIMING_WINDOW_DAYS)
        ]
        if len(candidates) == 1:
            match = candidates.iloc[0]
            fuzzy_matches.append({
                "reference": gl_row["reference"],
                "gl_date": gl_row["gl_date"],
                "gl_amount": gl_row["gl_amount"],
                "vendor_id": gl_row["vendor_id"],
                "vendor_name": gl_row["vendor_name"],
                "type": gl_row["type"],
                "bank_date": match["bank_date"],
                "bank_amount": match["bank_amount"],
                "bank_ref": match["bank_ref"],
                "reason_code": "RC-700",
                "reason": REASON_CODES["RC-700"],
                "confidence": 0.60,
                "variance": round(gl_row["gl_amount"] - match["bank_amount"], 2),
            })
            bank_remaining = bank_remaining[bank_remaining["bank_ref"] != match["bank_ref"]]

    return pd.DataFrame(fuzzy_matches) if fuzzy_matches else pd.DataFrame(), set(
        m["reference"] for m in fuzzy_matches
    )


def flag_unmatched(gl: pd.DataFrame, bank: pd.DataFrame, matched_gl: set, matched_bank: set):
    """Flag remaining unmatched records on both sides."""
    gl_unmatched = gl[~gl["reference"].isin(matched_gl)].copy()
    gl_unmatched["reason_code"] = "RC-400"
    gl_unmatched["reason"] = REASON_CODES["RC-400"]
    gl_unmatched["confidence"] = 0.00

    bank_unmatched = bank[~bank["reference"].isin(matched_bank)].copy()
    bank_unmatched["reason_code"] = "RC-500"
    bank_unmatched["reason"] = REASON_CODES["RC-500"]
    bank_unmatched["confidence"] = 0.00

    return gl_unmatched, bank_unmatched


def generate_exception_report(results: dict, output_path: str):
    """Generate Excel exception report with multiple tabs."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"{output_path}/exception_report_{timestamp}.xlsx"

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # Summary tab
        summary_data = []
        total_items = 0
        for code, label in REASON_CODES.items():
            count = len(results.get(code, []))
            total_items += count
            summary_data.append({"Reason Code": code, "Description": label, "Count": count})
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        # Human Review Queue
        review_items = []
        for code in ["RC-300", "RC-600", "RC-700", "RC-400", "RC-500"]:
            if code in results and not results[code].empty:
                df = results[code].copy()
                if "confidence" in df.columns:
                    review_items.append(df[df["confidence"] < CONFIDENCE_THRESHOLD])
                else:
                    review_items.append(df)
        if review_items:
            review_df = pd.concat(review_items, ignore_index=True)
            cols = [c for c in ["reference", "reason_code", "reason", "confidence", "gl_amount",
                                "bank_amount", "variance", "vendor_name", "gl_date", "bank_date"] if c in review_df.columns]
            review_df[cols].to_excel(writer, sheet_name="Human Review Queue", index=False)

        # All exceptions detail
        for code, label in REASON_CODES.items():
            if code in results and not results[code].empty:
                sheet_name = f"{code} {label[:20]}"
                results[code].to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"\nException report saved: {filepath}")
    return filepath


def generate_reconciliation_summary(gl: pd.DataFrame, bank: pd.DataFrame, results: dict):
    """Print reconciliation summary to console."""
    total_gl = len(gl)
    total_bank = len(bank)
    matched = sum(len(results.get(code, [])) for code in ["RC-100", "RC-200"])
    exceptions = sum(len(results.get(code, [])) for code in ["RC-300", "RC-400", "RC-500", "RC-600", "RC-700"])
    human_review = sum(
        len(results[code][results[code]["confidence"] < CONFIDENCE_THRESHOLD])
        for code in results if not results[code].empty and "confidence" in results[code].columns
    )
    match_rate = (matched / total_gl * 100) if total_gl > 0 else 0

    total_gl_amt = gl["gl_amount"].sum()
    total_bank_amt = bank["bank_amount"].sum()
    net_variance = total_gl_amt - total_bank_amt

    print("\n" + "=" * 60)
    print("  AP/AR RECONCILIATION SUMMARY")
    print("=" * 60)
    print(f"  GL Records:              {total_gl:>8}")
    print(f"  Bank Records:            {total_bank:>8}")
    print(f"  ─────────────────────────────────")
    print(f"  Exact Matches (RC-100):  {len(results.get('RC-100', [])):>8}")
    print(f"  Timing Mismatch (RC-200):{len(results.get('RC-200', [])):>8}")
    print(f"  Amount Variance (RC-300):{len(results.get('RC-300', [])):>8}")
    print(f"  GL Only (RC-400):        {len(results.get('RC-400', [])):>8}")
    print(f"  Bank Only (RC-500):      {len(results.get('RC-500', [])):>8}")
    print(f"  Duplicates (RC-600):     {len(results.get('RC-600', [])):>8}")
    print(f"  Low Confidence (RC-700): {len(results.get('RC-700', [])):>8}")
    print(f"  ─────────────────────────────────")
    print(f"  Auto-Match Rate:         {match_rate:>7.1f}%")
    print(f"  → Human Review Queue:    {human_review:>8}")
    print(f"  ─────────────────────────────────")
    print(f"  GL Total:           ${total_gl_amt:>12,.2f}")
    print(f"  Bank Total:         ${total_bank_amt:>12,.2f}")
    print(f"  Net Variance:       ${net_variance:>12,.2f}")
    print("=" * 60)


def run_reconciliation(gl_path: str, bank_path: str, output_path: str = "output"):
    """Execute full reconciliation pipeline."""
    gl, bank = load_data(gl_path, bank_path)
    results = {}

    # Step 0: Detect duplicate bank entries
    dupes = detect_duplicates(bank)
    results["RC-600"] = dupes
    bank_clean = bank.drop(dupes.index)

    # Step 1: Exact match
    exact, matched_gl, matched_bank = pass_1_exact_match(gl, bank_clean)
    results["RC-100"] = exact

    # Step 2: Timing mismatch
    timing, timing_refs = pass_2_timing_mismatch(gl, bank_clean, matched_gl, matched_bank)
    results["RC-200"] = timing
    matched_gl |= timing_refs
    matched_bank |= timing_refs

    # Step 3: Amount discrepancy
    amount_disc, disc_refs = pass_3_amount_discrepancy(gl, bank_clean, matched_gl, matched_bank)
    results["RC-300"] = amount_disc
    matched_gl |= disc_refs
    matched_bank |= disc_refs

    # Step 4: Fuzzy match (low confidence)
    fuzzy, fuzzy_refs = pass_4_fuzzy_match(gl, bank_clean, matched_gl, matched_bank)
    results["RC-700"] = fuzzy
    matched_gl |= fuzzy_refs

    # Step 5: Flag unmatched
    gl_unmatched, bank_unmatched = flag_unmatched(gl, bank_clean, matched_gl, matched_bank)
    results["RC-400"] = gl_unmatched
    results["RC-500"] = bank_unmatched

    # Generate outputs
    generate_reconciliation_summary(gl, bank, results)
    report_path = generate_exception_report(results, output_path)

    return results, report_path


if __name__ == "__main__":
    run_reconciliation("data/gl_export.csv", "data/bank_statement.csv")
