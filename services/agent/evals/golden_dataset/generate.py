#!/usr/bin/env python3
"""Generate all golden test cases as JSON files."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).parent

CASES = [
    # ── Clean matches ──────────────────────────────────────────────────────────
    {
        "name": "clean_exact_match",
        "description": "Single transaction matches single invoice exactly",
        "input_csv": "date,amount,description,account\n2024-01-15,1500.00,Acme Corp,checking",
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": [],
    },
    {
        "name": "clean_multi_match",
        "description": "3 clean matches no ambiguity",
        "input_csv": (
            "date,amount,description,account\n"
            "2024-01-15,1500.00,Acme Corp,checking\n"
            "2024-01-16,2200.00,Beta Solutions,checking\n"
            "2024-01-17,800.00,Gamma Inc,checking"
        ),
        "expected_matches": ["acme_corp_inv_001", "beta_solutions_inv_001", "gamma_inv_001"],
        "expected_escalations": [],
    },
    # ── Fuzzy vendor matches ───────────────────────────────────────────────────
    {
        "name": "fuzzy_vendor_llc_stripped",
        "description": "Invoice has LLC suffix, transaction doesn't",
        "input_csv": "date,amount,description,account\n2024-01-15,1500.00,Acme,checking",
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": [],
    },
    {
        "name": "fuzzy_vendor_typo",
        "description": "Slight typo in vendor name (Acme -> Akme)",
        "input_csv": "date,amount,description,account\n2024-01-15,1500.00,Akme Corp,checking",
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": [],
    },
    {
        "name": "fuzzy_vendor_abbreviation",
        "description": "Abbreviated vendor in transaction",
        "input_csv": "date,amount,description,account\n2024-01-16,2200.00,Beta Sol,checking",
        "expected_matches": ["beta_solutions_inv_001"],
        "expected_escalations": [],
    },
    {
        "name": "fuzzy_vendor_case_insensitive",
        "description": "Vendor in all caps",
        "input_csv": "date,amount,description,account\n2024-01-17,800.00,GAMMA INC,checking",
        "expected_matches": ["gamma_inv_001"],
        "expected_escalations": [],
    },
    # ── Amount edge cases ──────────────────────────────────────────────────────
    {
        "name": "amount_off_by_cent",
        "description": "Amount differs by 1 cent — should escalate",
        "input_csv": "date,amount,description,account\n2024-01-15,1499.99,Acme Corp,checking",
        "expected_matches": [],
        "expected_escalations": ["acme_corp_txn"],
    },
    {
        "name": "amount_off_by_dollar",
        "description": "Amount differs by $1 — should escalate",
        "input_csv": "date,amount,description,account\n2024-01-15,1501.00,Acme Corp,checking",
        "expected_matches": [],
        "expected_escalations": ["acme_corp_txn"],
    },
    {
        "name": "amount_with_dollar_sign",
        "description": "CSV has dollar sign in amount",
        "input_csv": "date,amount,description,account\n2024-01-15,$1500.00,Acme Corp,checking",
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": [],
    },
    {
        "name": "amount_with_comma",
        "description": "CSV has comma-formatted amount",
        "input_csv": 'date,amount,description,account\n2024-01-15,"1,500.00",Acme Corp,checking',
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": [],
    },
    # ── Date edge cases ────────────────────────────────────────────────────────
    {
        "name": "date_within_window",
        "description": "Transaction date 5 days after invoice — within 7-day window",
        "input_csv": "date,amount,description,account\n2024-01-20,1500.00,Acme Corp,checking",
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": [],
    },
    {
        "name": "date_out_of_window",
        "description": "Transaction date 10 days after invoice — outside 7-day window",
        "input_csv": "date,amount,description,account\n2024-01-25,1500.00,Acme Corp,checking",
        "expected_matches": [],
        "expected_escalations": ["acme_txn_late"],
    },
    {
        "name": "date_before_invoice",
        "description": "Transaction date 3 days before invoice — within window",
        "input_csv": "date,amount,description,account\n2024-01-12,1500.00,Acme Corp,checking",
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": [],
    },
    # ── Duplicate invoice prevention ───────────────────────────────────────────
    {
        "name": "duplicate_invoice_prevention",
        "description": "Two transactions match same invoice — second must escalate",
        "input_csv": (
            "date,amount,description,account\n"
            "2024-01-15,1500.00,Acme Corp,checking\n"
            "2024-01-15,1500.00,Acme Corp,savings"
        ),
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": ["duplicate_acme_txn"],
    },
    {
        "name": "duplicate_row_in_csv",
        "description": "Exact duplicate row in CSV",
        "input_csv": (
            "date,amount,description,account\n"
            "2024-01-15,1500.00,Acme Corp,checking\n"
            "2024-01-15,1500.00,Acme Corp,checking"
        ),
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": ["duplicate_row"],
    },
    # ── No-match cases ─────────────────────────────────────────────────────────
    {
        "name": "no_match_unknown_vendor",
        "description": "Vendor with no invoice in DB",
        "input_csv": "date,amount,description,account\n2024-01-15,999.00,Unknown Vendor XYZ,checking",
        "expected_matches": [],
        "expected_escalations": ["unknown_vendor_txn"],
    },
    {
        "name": "no_match_all_invoices_matched",
        "description": "All open invoices already matched in prior run",
        "input_csv": "date,amount,description,account\n2024-02-15,1500.00,Acme Corp,checking",
        "expected_matches": [],
        "expected_escalations": ["acme_already_matched_txn"],
    },
    # ── Malformed CSV ──────────────────────────────────────────────────────────
    {
        "name": "malformed_row_invalid_date",
        "description": "One row has invalid date, rest valid",
        "input_csv": (
            "date,amount,description,account\n"
            "not-a-date,1500.00,Acme Corp,checking\n"
            "2024-01-16,2200.00,Beta Solutions,checking"
        ),
        "expected_matches": ["beta_solutions_inv_001"],
        "expected_escalations": [],
    },
    {
        "name": "malformed_row_missing_field",
        "description": "Row missing description field",
        "input_csv": (
            "date,amount,description,account\n"
            "2024-01-15,,Acme Corp,checking\n"
            "2024-01-16,2200.00,Beta Solutions,checking"
        ),
        "expected_matches": ["beta_solutions_inv_001"],
        "expected_escalations": [],
    },
    {
        "name": "malformed_row_zero_amount",
        "description": "Row has zero amount — invalid",
        "input_csv": (
            "date,amount,description,account\n"
            "2024-01-15,0.00,Acme Corp,checking\n"
            "2024-01-16,2200.00,Beta Solutions,checking"
        ),
        "expected_matches": ["beta_solutions_inv_001"],
        "expected_escalations": [],
    },
    {
        "name": "malformed_csv_wrong_columns",
        "description": "CSV missing required 'account' column",
        "input_csv": "date,amount,description\n2024-01-15,1500.00,Acme Corp",
        "expected_matches": [],
        "expected_escalations": [],
    },
    # ── Partial match / ambiguous ──────────────────────────────────────────────
    {
        "name": "partial_match_multiple_candidates",
        "description": "Transaction matches 2 invoices by vendor, different amounts",
        "input_csv": "date,amount,description,account\n2024-01-15,1500.00,Acme Corp,checking",
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": [],
    },
    {
        "name": "low_confidence_escalation",
        "description": "LLM returns confidence 0.6, must escalate",
        "input_csv": "date,amount,description,account\n2024-01-15,1234.56,Ambiguous Vendor,checking",
        "expected_matches": [],
        "expected_escalations": ["ambiguous_txn"],
    },
    # ── Large batch ────────────────────────────────────────────────────────────
    {
        "name": "batch_10_transactions",
        "description": "10 transactions, 8 match, 2 escalate",
        "input_csv": "\n".join(
            ["date,amount,description,account"]
            + [f"2024-01-{15+i:02d},1000.00,Vendor{i:02d},checking" for i in range(10)]
        ),
        "expected_matches": [f"vendor_{i:02d}_inv" for i in range(8)],
        "expected_escalations": ["vendor_08_txn", "vendor_09_txn"],
    },
    # ── Negative amounts ───────────────────────────────────────────────────────
    {
        "name": "negative_amount_refund",
        "description": "Negative amount (refund) — should escalate",
        "input_csv": "date,amount,description,account\n2024-01-15,-500.00,Acme Corp Refund,checking",
        "expected_matches": [],
        "expected_escalations": ["refund_txn"],
    },
    # ── Date format variants ───────────────────────────────────────────────────
    {
        "name": "date_format_mm_dd_yyyy",
        "description": "Date in MM/DD/YYYY format",
        "input_csv": "date,amount,description,account\n01/15/2024,1500.00,Acme Corp,checking",
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": [],
    },
    {
        "name": "date_format_dd_mon_yyyy",
        "description": "Date in '15 Jan 2024' format",
        "input_csv": "date,amount,description,account\n15 Jan 2024,1500.00,Acme Corp,checking",
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": [],
    },
    # ── Mixed run (realistic) ─────────────────────────────────────────────────
    {
        "name": "realistic_mixed_batch",
        "description": "12 transactions: clean/fuzzy/no-match/malformed",
        "input_csv": (
            "date,amount,description,account\n"
            "2024-01-15,1500.00,Acme Corp,checking\n"
            "2024-01-16,2200.00,Beta Solutions LLC,checking\n"
            "2024-01-17,800.00,GAMMA INC,checking\n"
            "2024-01-18,3500.00,Delta Consulting,checking\n"
            "2024-01-19,450.00,Epsilon Services,checking\n"
            "2024-01-20,1200.00,Zeta Corp,checking\n"
            "2024-01-21,5000.00,Unknown BigCo,checking\n"
            "2024-01-22,750.00,Theta Ltd,checking\n"
            "invalid-date,900.00,Iota Corp,checking\n"
            "2024-01-24,0.00,Empty Amount Co,checking\n"
            "2024-01-25,320.00,Kappa Industries,checking\n"
            "2024-01-26,1800.00,Lambda Group,checking"
        ),
        "expected_matches": [
            "acme_corp_inv_001",
            "beta_solutions_inv_001",
            "gamma_inv_001",
            "delta_inv_001",
            "epsilon_inv_001",
            "zeta_inv_001",
            "theta_inv_001",
        ],
        "expected_escalations": ["unknown_bigco_txn", "kappa_txn", "lambda_txn"],
    },
    # ── Idempotency ────────────────────────────────────────────────────────────
    {
        "name": "idempotent_rerun",
        "description": "Running same CSV twice should not double-post ledger entries",
        "input_csv": "date,amount,description,account\n2024-01-15,1500.00,Acme Corp,checking",
        "expected_matches": ["acme_corp_inv_001"],
        "expected_escalations": [],
    },
    # ── Unicode / special chars ────────────────────────────────────────────────
    {
        "name": "unicode_vendor_name",
        "description": "Vendor name with unicode characters",
        "input_csv": "date,amount,description,account\n2024-01-15,900.00,Müller & Co,checking",
        "expected_matches": [],
        "expected_escalations": ["unicode_txn"],
    },
    {
        "name": "vendor_with_ampersand",
        "description": "Vendor name with & symbol",
        "input_csv": "date,amount,description,account\n2024-01-16,2200.00,Beta & Solutions,checking",
        "expected_matches": ["beta_solutions_inv_001"],
        "expected_escalations": [],
    },
]


def main() -> None:
    for case in CASES:
        out_path = OUT / f"{case['name']}.json"
        with open(out_path, "w") as f:
            json.dump(case, f, indent=2)
        print(f"wrote {out_path.name}")
    print(f"\n{len(CASES)} golden cases generated.")


if __name__ == "__main__":
    main()
