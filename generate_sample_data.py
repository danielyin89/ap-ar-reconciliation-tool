"""
Generate sample bank statement and GL export data for reconciliation testing.
Simulates real-world scenarios: exact matches, timing mismatches, missing entries,
duplicate payments, and amount discrepancies.
"""
import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)

def generate_data():
    base_date = datetime(2026, 3, 1)
    vendors = [
        ("V001", "Metro Food Supply Co."),
        ("V002", "Pacific Packaging Inc."),
        ("V003", "Summit Equipment Rental"),
        ("V004", "Westside Logistics LLC"),
        ("V005", "Crown Cleaning Services"),
        ("V006", "Atlas Office Supplies"),
        ("V007", "Harbor Insurance Group"),
        ("V008", "Nexus IT Solutions"),
        ("V009", "Premier Staffing Agency"),
        ("V010", "Valley Utilities Corp."),
    ]

    gl_records = []
    bank_records = []
    ref_counter = 1000

    for day in range(31):
        tx_date = base_date + timedelta(days=day)
        if tx_date.weekday() >= 5:
            continue
        num_tx = random.randint(8, 15)

        for _ in range(num_tx):
            ref_counter += 1
            ref = f"INV-2026-{ref_counter}"
            vendor_id, vendor_name = random.choice(vendors)
            amount = round(random.uniform(150, 12000), 2)
            tx_type = random.choice(["AP-Payment", "AP-Payment", "AP-Payment", "AR-Receipt", "AR-Receipt"])
            scenario = random.choices(
                ["exact_match", "timing_mismatch", "amount_discrepancy", "gl_only", "bank_only", "duplicate"],
                weights=[55, 15, 10, 8, 7, 5]
            )[0]

            if scenario == "exact_match":
                gl_records.append({
                    "gl_date": tx_date.strftime("%Y-%m-%d"),
                    "reference": ref,
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name,
                    "type": tx_type,
                    "gl_amount": amount,
                    "description": f"{tx_type} - {vendor_name}"
                })
                bank_records.append({
                    "bank_date": tx_date.strftime("%Y-%m-%d"),
                    "reference": ref,
                    "bank_amount": amount,
                    "description": f"{tx_type} {vendor_name}",
                    "bank_ref": f"BK{random.randint(100000,999999)}"
                })

            elif scenario == "timing_mismatch":
                offset = random.choice([1, 2, 3])
                gl_records.append({
                    "gl_date": tx_date.strftime("%Y-%m-%d"),
                    "reference": ref,
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name,
                    "type": tx_type,
                    "gl_amount": amount,
                    "description": f"{tx_type} - {vendor_name}"
                })
                bank_records.append({
                    "bank_date": (tx_date + timedelta(days=offset)).strftime("%Y-%m-%d"),
                    "reference": ref,
                    "bank_amount": amount,
                    "description": f"{tx_type} {vendor_name}",
                    "bank_ref": f"BK{random.randint(100000,999999)}"
                })

            elif scenario == "amount_discrepancy":
                variance = round(random.uniform(0.01, 50.00), 2)
                if random.random() > 0.5:
                    bank_amt = amount + variance
                else:
                    bank_amt = amount - variance
                gl_records.append({
                    "gl_date": tx_date.strftime("%Y-%m-%d"),
                    "reference": ref,
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name,
                    "type": tx_type,
                    "gl_amount": amount,
                    "description": f"{tx_type} - {vendor_name}"
                })
                bank_records.append({
                    "bank_date": tx_date.strftime("%Y-%m-%d"),
                    "reference": ref,
                    "bank_amount": round(bank_amt, 2),
                    "description": f"{tx_type} {vendor_name}",
                    "bank_ref": f"BK{random.randint(100000,999999)}"
                })

            elif scenario == "gl_only":
                gl_records.append({
                    "gl_date": tx_date.strftime("%Y-%m-%d"),
                    "reference": ref,
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name,
                    "type": tx_type,
                    "gl_amount": amount,
                    "description": f"{tx_type} - {vendor_name}"
                })

            elif scenario == "bank_only":
                bank_records.append({
                    "bank_date": tx_date.strftime("%Y-%m-%d"),
                    "reference": ref,
                    "bank_amount": amount,
                    "description": f"{tx_type} {vendor_name}",
                    "bank_ref": f"BK{random.randint(100000,999999)}"
                })

            elif scenario == "duplicate":
                gl_records.append({
                    "gl_date": tx_date.strftime("%Y-%m-%d"),
                    "reference": ref,
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name,
                    "type": tx_type,
                    "gl_amount": amount,
                    "description": f"{tx_type} - {vendor_name}"
                })
                for i in range(2):
                    bank_records.append({
                        "bank_date": (tx_date + timedelta(days=i)).strftime("%Y-%m-%d"),
                        "reference": ref,
                        "bank_amount": amount,
                        "description": f"{tx_type} {vendor_name}",
                        "bank_ref": f"BK{random.randint(100000,999999)}"
                    })

    gl_df = pd.DataFrame(gl_records)
    bank_df = pd.DataFrame(bank_records)
    gl_df.to_csv("data/gl_export.csv", index=False)
    bank_df.to_csv("data/bank_statement.csv", index=False)
    print(f"Generated {len(gl_df)} GL records -> data/gl_export.csv")
    print(f"Generated {len(bank_df)} Bank records -> data/bank_statement.csv")

if __name__ == "__main__":
    generate_data()
