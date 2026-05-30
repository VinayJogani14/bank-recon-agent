#!/usr/bin/env python3
"""
Seed the database with 200 invoices and 250 bank transactions.
80% of transactions match invoices, 10% partial, 10% no-match.
"""

from __future__ import annotations

import random
import re
import uuid
from datetime import date, timedelta

from faker import Faker

from agent.db import get_client

fake = Faker()
random.seed(42)

VENDORS = [
    ("Acme Corporation LLC", "acme corporation"),
    ("Beta Solutions Inc", "beta solutions"),
    ("Gamma Industries", "gamma industries"),
    ("Delta Consulting Group", "delta consulting group"),
    ("Epsilon Services Co", "epsilon services"),
    ("Zeta Technologies", "zeta technologies"),
    ("Eta Logistics Ltd", "eta logistics"),
    ("Theta Analytics", "theta analytics"),
    ("Iota Software", "iota software"),
    ("Kappa Marketing", "kappa marketing"),
    ("Lambda Cloud Services", "lambda cloud services"),
    ("Mu Design Studio", "mu design studio"),
    ("Nu Research Labs", "nu research labs"),
    ("Xi Data Corp", "xi data corp"),
    ("Omicron Printing", "omicron printing"),
    ("Pi Financial Services", "pi financial services"),
    ("Rho Security Inc", "rho security"),
    ("Sigma Staffing", "sigma staffing"),
    ("Tau Engineering", "tau engineering"),
    ("Upsilon Media", "upsilon media"),
]

# Realistic amount buckets (cents)
AMOUNT_BUCKETS = [
    50000,
    75000,
    100000,
    125000,
    150000,
    175000,
    200000,
    250000,
    300000,
    350000,
    400000,
    500000,
    750000,
    1000000,
]

START_DATE = date(2024, 1, 1)


def random_date(start: date, days: int) -> date:
    return start + timedelta(days=random.randint(0, days))


def normalize(vendor: str) -> str:
    s = vendor.lower().strip()
    s = re.sub(r"\b(llc|inc|corp|co|ltd|group|holdings)\b\.?$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def seed_invoices(db: object) -> list[dict]:
    invoices = []
    for i in range(200):
        vendor_name, vendor_norm = VENDORS[i % len(VENDORS)]
        amount = random.choice(AMOUNT_BUCKETS) + random.randint(0, 9900)
        issued = random_date(START_DATE, 80)
        invoices.append(
            {
                "id": str(uuid.uuid4()),
                "vendor": vendor_name,
                "normalized_vendor": vendor_norm,
                "amount_cents": amount,
                "issued_date": str(issued),
                "due_date": str(issued + timedelta(days=30)),
                "status": "open",
            }
        )

    db.table("invoices").insert(invoices).execute()  # type: ignore[attr-defined]
    print(f"  inserted {len(invoices)} invoices")
    return invoices


def seed_transactions(db: object, invoices: list[dict]) -> None:
    transactions = []
    used_invoice_ids: set[str] = set()

    def make_txn(inv: dict, jitter_amount: int = 0, date_offset: int = 0) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "run_id": None,
            "date": str(date.fromisoformat(inv["issued_date"]) + timedelta(days=date_offset)),
            "amount_cents": inv["amount_cents"] + jitter_amount,
            "description": inv["vendor"],
            "normalized_merchant": inv["normalized_vendor"],
            "account": random.choice(["checking", "savings", "operating"]),
            "raw_row": {"seeded": True},
        }

    available = [inv for inv in invoices if inv["id"] not in used_invoice_ids]

    # 80% clean matches (200 txns)
    clean_count = 200
    for inv in random.sample(available, clean_count):
        used_invoice_ids.add(inv["id"])
        transactions.append(make_txn(inv, jitter_amount=0, date_offset=random.randint(0, 3)))

    # 10% partial matches (25 txns) — amount off by a small amount
    available = [inv for inv in invoices if inv["id"] not in used_invoice_ids]
    for inv in random.sample(available, 25):
        jitter = random.choice([1, -1, 100, -100, 50])
        transactions.append(make_txn(inv, jitter_amount=jitter, date_offset=random.randint(0, 5)))

    # 10% no match (25 txns) — completely unknown vendors
    for i in range(25):
        transactions.append(
            {
                "id": str(uuid.uuid4()),
                "run_id": None,
                "date": str(random_date(START_DATE, 90)),
                "amount_cents": random.choice(AMOUNT_BUCKETS),
                "description": f"Unknown Vendor {fake.company()}",
                "normalized_merchant": f"unknown vendor {i}",
                "account": "checking",
                "raw_row": {"seeded": True, "no_match": True},
            }
        )

    random.shuffle(transactions)

    # Insert in batches of 50
    batch_size = 50
    for i in range(0, len(transactions), batch_size):
        db.table("bank_transactions").insert(transactions[i : i + batch_size]).execute()  # type: ignore[attr-defined]

    print(f"  inserted {len(transactions)} bank transactions")


def main() -> None:
    print("Seeding database...")
    db = get_client()
    print("  connected to Supabase")

    invoices = seed_invoices(db)
    seed_transactions(db, invoices)
    print("Done.")


if __name__ == "__main__":
    main()
