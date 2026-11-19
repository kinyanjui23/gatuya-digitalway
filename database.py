from __future__ import annotations

import sqlite3
from datetime import date, time
from pathlib import Path

import pandas as pd


DB_PATH = Path(__file__).with_name("gatuya_coffee.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize() -> None:
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS farmers (
            id INTEGER PRIMARY KEY,
            share_number TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            national_id TEXT,
            account_number TEXT,
            zone TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY,
            farmer_id INTEGER NOT NULL REFERENCES farmers(id),
            delivery_date TEXT NOT NULL,
            weighed_at TEXT NOT NULL,
            coffee_type TEXT NOT NULL CHECK (coffee_type IN ('Cherry', 'Mbuni')),
            kg REAL NOT NULL CHECK (kg > 0),
            receipt_number TEXT,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (farmer_id, delivery_date)
        );
        CREATE INDEX IF NOT EXISTS idx_deliveries_date ON deliveries(delivery_date);
        CREATE TABLE IF NOT EXISTS delivery_audit (
            id INTEGER PRIMARY KEY,
            delivery_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            before_json TEXT,
            after_json TEXT,
            reason TEXT NOT NULL,
            changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS processing_batches (
            id INTEGER PRIMARY KEY,
            processed_at TEXT NOT NULL,
            input_cherry_kg REAL NOT NULL CHECK (input_cherry_kg > 0),
            pp1_kg REAL NOT NULL DEFAULT 0 CHECK (pp1_kg >= 0),
            pp2_kg REAL NOT NULL DEFAULT 0 CHECK (pp2_kg >= 0),
            third_kg REAL NOT NULL DEFAULT 0 CHECK (third_kg >= 0),
            light_kg REAL NOT NULL DEFAULT 0 CHECK (light_kg >= 0),
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY,
            movement_at TEXT NOT NULL,
            grade TEXT NOT NULL CHECK (grade IN ('PP1', 'PP2', 'Third grade', 'Light', 'Mbuni')),
            direction TEXT NOT NULL CHECK (direction IN ('IN', 'OUT')),
            kg REAL NOT NULL CHECK (kg > 0),
            movement_kind TEXT NOT NULL,
            reference TEXT NOT NULL,
            source_batch_id INTEGER REFERENCES processing_batches(id),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (source_batch_id, grade)
        );
        CREATE INDEX IF NOT EXISTS idx_stock_movements_grade_time ON stock_movements(grade, movement_at);
        CREATE TABLE IF NOT EXISTS laborers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS labor_shifts (
            id INTEGER PRIMARY KEY,
            laborer_id INTEGER NOT NULL REFERENCES laborers(id),
            started_at TEXT NOT NULL,
            ended_at TEXT NOT NULL,
            break_minutes INTEGER NOT NULL DEFAULT 60,
            paid_hours REAL NOT NULL,
            overtime_hours REAL NOT NULL,
            pay_kes REAL NOT NULL,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS meeting_notices (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            meeting_at TEXT NOT NULL,
            location TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS feedback_submissions (
            id INTEGER PRIMARY KEY,
            submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            category TEXT NOT NULL,
            message TEXT NOT NULL,
            contact TEXT
        );
        CREATE TABLE IF NOT EXISTS message_campaigns (
            id INTEGER PRIMARY KEY,
            meeting_id INTEGER REFERENCES meeting_notices(id),
            message TEXT NOT NULL,
            recipient_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            provider_response TEXT,
            attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS agrochemical_products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            product_type TEXT NOT NULL DEFAULT 'Other',
            formulation TEXT NOT NULL DEFAULT 'Other',
            unit TEXT NOT NULL,
            price_per_unit_kes REAL NOT NULL DEFAULT 0 CHECK (price_per_unit_kes >= 0),
            registration_reference TEXT,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS agrochemical_transactions (
            id INTEGER PRIMARY KEY,
            transacted_at TEXT NOT NULL,
            product_id INTEGER REFERENCES agrochemical_products(id),
            farmer_id INTEGER REFERENCES farmers(id),
            transaction_type TEXT NOT NULL CHECK (transaction_type IN ('RECEIPT', 'LOAN', 'REPAYMENT')),
            quantity REAL NOT NULL DEFAULT 0 CHECK (quantity >= 0),
            unit_price_kes REAL NOT NULL DEFAULT 0 CHECK (unit_price_kes >= 0),
            amount_kes REAL NOT NULL DEFAULT 0 CHECK (amount_kes >= 0),
            reference TEXT NOT NULL,
            notes TEXT,
            loan_request_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS agrochemical_loan_requests (
            id INTEGER PRIMARY KEY,
            farmer_id INTEGER NOT NULL REFERENCES farmers(id),
            product_id INTEGER NOT NULL REFERENCES agrochemical_products(id),
            requested_quantity REAL NOT NULL CHECK (requested_quantity > 0),
            farmer_notes TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'ISSUED')),
            manager_notes TEXT,
            requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT,
            issued_transaction_id INTEGER REFERENCES agrochemical_transactions(id),
            UNIQUE (issued_transaction_id)
        );
        """)
        try:
            conn.execute("ALTER TABLE farmers ADD COLUMN phone_number TEXT")
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc).lower():
                raise
        for column, definition in (
            ("product_type", "TEXT NOT NULL DEFAULT 'Other'"),
            ("formulation", "TEXT NOT NULL DEFAULT 'Other'"),
            ("registration_reference", "TEXT"),
        ):
            try:
                conn.execute(f"ALTER TABLE agrochemical_products ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise
        try:
            conn.execute("ALTER TABLE agrochemical_transactions ADD COLUMN loan_request_id INTEGER")
        except sqlite3.OperationalError as exc:
            if "duplicate column" not in str(exc).lower():
                raise


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def save_farmer(share_number: str, name: str, national_id: str | None,
                account_number: str | None, zone: str | None, phone_number: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO farmers (share_number, name, national_id, account_number, zone, phone_number) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (share_number, name, national_id, account_number, zone, phone_number),
        )


def update_farmer_phone(farmer_id: int, phone_number: str | None) -> None:
    with connect() as conn:
        conn.execute("UPDATE farmers SET phone_number=? WHERE id=?", (phone_number, farmer_id))


def save_meeting(title: str, meeting_at: str, location: str, message: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO meeting_notices (title, meeting_at, location, message) VALUES (?, ?, ?, ?)",
            (title.strip(), meeting_at, location.strip(), message.strip()),
        )


def save_feedback(category: str, message: str, contact: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO feedback_submissions (category, message, contact) VALUES (?, ?, ?)",
            (category, message.strip(), contact.strip() if contact else None),
        )


def save_message_campaign(meeting_id: int, message: str, recipient_count: int,
                          status: str, provider_response: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO message_campaigns (meeting_id, message, recipient_count, status, provider_response) "
            "VALUES (?, ?, ?, ?, ?)",
            (meeting_id, message, recipient_count, status, provider_response),
        )


def save_agrochemical_product(name: str, product_type: str, formulation: str, unit: str,
                              price_per_unit_kes: float, registration_reference: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO agrochemical_products (name, product_type, formulation, unit, price_per_unit_kes, registration_reference) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name.strip(), product_type, formulation, unit.strip(), price_per_unit_kes,
             registration_reference.strip() if registration_reference else None),
        )


def seed_common_agrochemicals() -> int:
    """Add sample catalog records; these are not application or spray recommendations."""
    samples = [
        ("COPABELT 50 WP", "Fungicide", "Wettable powder", "kg", "PCPB(CR)0382-P(v)"),
        ("ALTO 100 SL", "Fungicide", "Soluble concentrate", "litre", "PCPB(CR)0203"),
        ("CABRIO EC", "Fungicide", "Emulsifiable concentrate", "litre", "PCPB(CR)0745"),
        ("XENTARI", "Biopesticide / insect control", "Biological product", "pack", "PCPB(CR)0262"),
        ("Demo coffee foliar feed", "Foliar fertilizer", "Liquid", "litre", "Demo item — verify supplier label"),
        ("Demo NPK coffee fertilizer", "Granular fertilizer", "Granules", "kg", "Demo item — verify supplier label"),
        ("Demo micronutrient blend", "Micronutrient fertilizer", "Powder", "kg", "Demo item — verify supplier label"),
        ("Demo liquid soil conditioner", "Soil amendment", "Liquid concentrate", "litre", "Demo item — verify supplier label"),
        ("Demo foliar micronutrient powder", "Foliar fertilizer", "Soluble powder", "kg", "Demo item — verify supplier label"),
    ]
    inserted = 0
    with connect() as conn:
        for name, product_type, formulation, unit, registration in samples:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO agrochemical_products "
                "(name, product_type, formulation, unit, registration_reference) VALUES (?, ?, ?, ?, ?)",
                (name, product_type, formulation, unit, registration),
            )
            inserted += max(cursor.rowcount, 0)
    return inserted


def seed_demo_agrochemical_stock() -> tuple[int, int]:
    """Load clearly fictional starter stock for a prototype walkthrough."""
    from datetime import datetime

    added_products = seed_common_agrochemicals()
    starter_products = (
        ("COPABELT 50 WP", 20), ("ALTO 100 SL", 12), ("CABRIO EC", 8),
        ("XENTARI", 15), ("Demo coffee foliar feed", 25),
        ("Demo NPK coffee fertilizer", 100), ("Demo micronutrient blend", 40),
        ("Demo liquid soil conditioner", 10), ("Demo foliar micronutrient powder", 30),
    )
    stocked_products = 0
    with connect() as conn:
        for name, quantity in starter_products:
            product = conn.execute(
                "SELECT id FROM agrochemical_products WHERE name=? AND active=1", (name,)
            ).fetchone()
            if product is None:
                continue
            has_history = conn.execute(
                "SELECT 1 FROM agrochemical_transactions WHERE product_id=? LIMIT 1",
                (product["id"],),
            ).fetchone()
            if has_history:
                continue
            conn.execute(
                "INSERT INTO agrochemical_transactions "
                "(transacted_at, product_id, transaction_type, quantity, reference, notes) "
                "VALUES (?, ?, 'RECEIPT', ?, 'DEMO-STOCK-STARTER', ?) ",
                (datetime.now().isoformat(sep=" ", timespec="seconds"), product["id"], quantity,
                 "Fictional starter inventory for prototype demonstration; verify physical stock before use."),
            )
            stocked_products += 1
    return added_products, stocked_products


def record_agrochemical_transaction(transacted_at: str, transaction_type: str,
                                   product_id: int | None, farmer_id: int | None,
                                   quantity: float, unit_price_kes: float,
                                   amount_kes: float, reference: str, notes: str | None,
                                   loan_request_id: int | None = None) -> int:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if transaction_type in ("RECEIPT", "LOAN"):
            if product_id is None or quantity <= 0:
                raise ValueError("Select an agrochemical and enter a quantity greater than zero.")
        if transaction_type == "LOAN":
            if farmer_id is None:
                raise ValueError("Select the farmer receiving the agrochemical loan.")
            if loan_request_id is not None:
                request = conn.execute(
                    "SELECT farmer_id, product_id, requested_quantity, status "
                    "FROM agrochemical_loan_requests WHERE id=?", (loan_request_id,)
                ).fetchone()
                if request is None or request["status"] != "APPROVED":
                    raise ValueError("This farmer request is not approved for issue.")
                if int(request["farmer_id"]) != farmer_id or int(request["product_id"]) != product_id:
                    raise ValueError("The selected farmer or product does not match the approved request.")
                if abs(float(request["requested_quantity"]) - quantity) > 1e-6:
                    raise ValueError("Issue the approved quantity exactly. Ask the farmer to submit a new request if it should change.")
            product_balance = conn.execute(
                "SELECT COALESCE(SUM(CASE WHEN transaction_type='RECEIPT' THEN quantity "
                "WHEN transaction_type='LOAN' THEN -quantity ELSE 0 END), 0) "
                "FROM agrochemical_transactions WHERE product_id=?", (product_id,)
            ).fetchone()[0]
            if quantity > float(product_balance):
                raise ValueError(f"Only {float(product_balance):,.2f} units are in stock.")
            amount_kes = quantity * unit_price_kes
        elif transaction_type == "REPAYMENT":
            if farmer_id is None or amount_kes <= 0:
                raise ValueError("Select a farmer and enter a repayment amount greater than zero.")
            balance = conn.execute(
                "SELECT COALESCE(SUM(CASE WHEN transaction_type='LOAN' THEN amount_kes "
                "WHEN transaction_type='REPAYMENT' THEN -amount_kes ELSE 0 END), 0) "
                "FROM agrochemical_transactions WHERE farmer_id=?", (farmer_id,)
            ).fetchone()[0]
            if amount_kes > float(balance):
                raise ValueError(f"Repayment exceeds the farmer's outstanding loan of KES {float(balance):,.2f}.")
            product_id = None
            quantity = 0
            unit_price_kes = 0
        cursor = conn.execute(
            "INSERT INTO agrochemical_transactions (transacted_at, product_id, farmer_id, transaction_type, "
            "quantity, unit_price_kes, amount_kes, reference, notes, loan_request_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (transacted_at, product_id, farmer_id, transaction_type, quantity, unit_price_kes,
             amount_kes, reference.strip(), notes, loan_request_id),
        )
        transaction_id = int(cursor.lastrowid)
        if loan_request_id is not None:
            conn.execute(
                "UPDATE agrochemical_loan_requests SET status='ISSUED', reviewed_at=CURRENT_TIMESTAMP, "
                "issued_transaction_id=? WHERE id=? AND status='APPROVED'",
                (transaction_id, loan_request_id),
            )
        return transaction_id


def create_agrochemical_loan_request(farmer_id: int, product_id: int, quantity: float,
                                     farmer_notes: str | None) -> int:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        physical_balance = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN transaction_type='RECEIPT' THEN quantity "
            "WHEN transaction_type='LOAN' THEN -quantity ELSE 0 END), 0) "
            "FROM agrochemical_transactions WHERE product_id=?", (product_id,)
        ).fetchone()[0]
        reserved = conn.execute(
            "SELECT COALESCE(SUM(requested_quantity), 0) FROM agrochemical_loan_requests "
            "WHERE product_id=? AND status='APPROVED'", (product_id,)
        ).fetchone()[0]
        available = float(physical_balance) - float(reserved)
        if quantity <= 0 or quantity > available:
            raise ValueError(f"Requested quantity must be positive and no more than the {available:,.2f} unreserved units currently in store.")
        pending = conn.execute(
            "SELECT 1 FROM agrochemical_loan_requests WHERE farmer_id=? AND product_id=? AND status='PENDING'",
            (farmer_id, product_id),
        ).fetchone()
        if pending:
            raise ValueError("You already have a pending request for this agrochemical.")
        cursor = conn.execute(
            "INSERT INTO agrochemical_loan_requests (farmer_id, product_id, requested_quantity, farmer_notes) "
            "VALUES (?, ?, ?, ?)",
            (farmer_id, product_id, quantity, farmer_notes),
        )
        return int(cursor.lastrowid)


def decide_agrochemical_loan_request(request_id: int, decision: str, manager_notes: str | None) -> None:
    if decision not in ("APPROVED", "REJECTED"):
        raise ValueError("Decision must be APPROVED or REJECTED.")
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        request = conn.execute(
            "SELECT product_id, requested_quantity, status FROM agrochemical_loan_requests WHERE id=?",
            (request_id,),
        ).fetchone()
        if request is None or request["status"] != "PENDING":
            raise ValueError("This request is no longer pending.")
        if decision == "APPROVED":
            physical_balance = conn.execute(
                "SELECT COALESCE(SUM(CASE WHEN transaction_type='RECEIPT' THEN quantity "
                "WHEN transaction_type='LOAN' THEN -quantity ELSE 0 END), 0) "
                "FROM agrochemical_transactions WHERE product_id=?", (request["product_id"],)
            ).fetchone()[0]
            reserved = conn.execute(
                "SELECT COALESCE(SUM(requested_quantity), 0) FROM agrochemical_loan_requests "
                "WHERE product_id=? AND status='APPROVED'", (request["product_id"],)
            ).fetchone()[0]
            available = float(physical_balance) - float(reserved)
            if float(request["requested_quantity"]) > available:
                raise ValueError(f"Only {available:,.2f} unreserved units remain. Receive more stock or reject the request.")
        cursor = conn.execute(
            "UPDATE agrochemical_loan_requests SET status=?, manager_notes=?, reviewed_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND status='PENDING'",
            (decision, manager_notes, request_id),
        )
        if cursor.rowcount == 0:
            raise ValueError("This request is no longer pending.")


def find_farmer(share_number: str):
    with connect() as conn:
        return conn.execute(
            "SELECT id, share_number, name FROM farmers WHERE share_number = ?",
            (share_number.strip(),),
        ).fetchone()


def seed_demo_data() -> int:
    """Add clearly fictional farmers and historical deliveries for a local demo."""
    demo_farmers = [
        (f"DEMO-{1000 + i}", f"Demo Farmer {i:02d}", f"Demo Zone {chr(65 + (i - 1) % 4)}")
        for i in range(1, 41)
    ]
    from datetime import date, timedelta
    import random

    rng = random.Random(17)
    added = 0
    with connect() as conn:
        for i, (share, name, zone) in enumerate(demo_farmers, start=1):
            conn.execute(
                "INSERT INTO farmers (share_number, name, national_id, account_number, phone_number, zone) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(share_number) DO UPDATE SET "
                "national_id=excluded.national_id, account_number=excluded.account_number, "
                "phone_number=excluded.phone_number, zone=excluded.zone",
                (share, name, f"DEMO-ID-{i:04d}", f"DEMO-ACCT-{i:04d}",
                 f"DEMO-PHONE-{i:04d}", zone),
            )
        farmer_ids = [r[0] for r in conn.execute(
            "SELECT id FROM farmers WHERE share_number LIKE 'DEMO-%' ORDER BY share_number"
        )]
        start = date.today() - timedelta(days=730)
        for day_index in range(730):
            day = start + timedelta(days=day_index)
            # Society delivers Tuesday-Friday. Simulated seasonal harvest follows the society's calendar.
            if day.weekday() not in (1, 2, 3, 4):
                continue
            if day.month in (10, 11):
                chance, low_kg, high_kg, coffee_type = 0.72, 500, 1_300, "Cherry"
            elif day.month in (12, 1):
                chance, low_kg, high_kg, coffee_type = 0.38, 400, 1_100, "Cherry"
            elif day.month == 2:
                chance, low_kg, high_kg, coffee_type = 0.30, 30, 180, "Mbuni"
            else:
                chance, low_kg, high_kg, coffee_type = 0.04, 100, 450, "Cherry"
            for farmer_id in farmer_ids:
                if rng.random() > chance:
                    continue
                exists = conn.execute(
                    "SELECT 1 FROM deliveries WHERE farmer_id=? AND delivery_date=?",
                    (farmer_id, day.isoformat()),
                ).fetchone()
                if exists:
                    continue
                kg = round(rng.uniform(low_kg, high_kg), 1)
                hour = rng.choice([7, 8, 9, 10, 14, 16, 19, 22])
                conn.execute(
                    "INSERT INTO deliveries (farmer_id, delivery_date, weighed_at, coffee_type, kg, receipt_number) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (farmer_id, day.isoformat(), f"{day.isoformat()} {hour:02d}:{rng.randrange(60):02d}:00",
                     coffee_type, kg, f"DEMO-{day:%y%m%d}-{farmer_id}"),
                )
                added += 1
    return added


def correct_delivery(delivery_id: int, farmer_id: int, delivery_date: date, weighed_time: time,
                     coffee_type: str, kg: float, reason: str) -> None:
    import json

    when = f"{delivery_date.isoformat()} {weighed_time.strftime('%H:%M:%S')}"
    with connect() as conn:
        old = conn.execute("SELECT * FROM deliveries WHERE id=?", (delivery_id,)).fetchone()
        if old is None:
            raise ValueError("Delivery no longer exists.")
        before = dict(old)
        try:
            conn.execute(
                "UPDATE deliveries SET farmer_id=?, delivery_date=?, weighed_at=?, coffee_type=?, kg=? "
                "WHERE id=?",
                (farmer_id, delivery_date.isoformat(), when, coffee_type, kg, delivery_id),
            )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc):
                raise ValueError("That farmer already has a delivery on the corrected date.") from exc
            raise
        after = dict(conn.execute("SELECT * FROM deliveries WHERE id=?", (delivery_id,)).fetchone())
        conn.execute(
            "INSERT INTO delivery_audit (delivery_id, action, before_json, after_json, reason) "
            "VALUES (?, 'corrected', ?, ?, ?)",
            (delivery_id, json.dumps(before), json.dumps(after), reason.strip()),
        )


def record_processing(processed_at: str, input_kg: float, pp1: float, pp2: float,
                      third: float, light: float, notes: str | None) -> int:
    output = pp1 + pp2 + third + light
    if output > input_kg:
        raise ValueError("Total graded output cannot exceed the cherry input weight.")
    if output <= 0:
        raise ValueError("Enter at least one non-zero grade quantity.")
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO processing_batches (processed_at, input_cherry_kg, pp1_kg, pp2_kg, third_kg, light_kg, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (processed_at, input_kg, pp1, pp2, third, light, notes),
        )
        batch_id = int(cursor.lastrowid)
        for grade, kg in (("PP1", pp1), ("PP2", pp2), ("Third grade", third), ("Light", light)):
            if kg > 0:
                conn.execute(
                    "INSERT INTO stock_movements (movement_at, grade, direction, kg, movement_kind, reference, source_batch_id, notes) "
                    "VALUES (?, ?, 'IN', ?, 'Washing output', ?, ?, ?)",
                    (processed_at, grade, kg, f"Washing batch #{batch_id}", batch_id, notes),
                )
    return batch_id


def receive_stock(movement_at: str, grade: str, kg: float, reference: str, notes: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO stock_movements (movement_at, grade, direction, kg, movement_kind, reference, notes) "
            "VALUES (?, ?, 'IN', ?, 'Store receipt', ?, ?)",
            (movement_at, grade, kg, reference.strip(), notes),
        )


def dispatch_stock(movement_at: str, grade: str, kg: float, reference: str, notes: str | None) -> float:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN direction='IN' THEN kg ELSE -kg END), 0) "
            "FROM stock_movements WHERE grade=?", (grade,)
        ).fetchone()
        balance = float(row[0])
        if kg > balance:
            raise ValueError(f"Cannot dispatch {kg:,.1f} kg. Only {balance:,.1f} kg of {grade} is in stock.")
        conn.execute(
            "INSERT INTO stock_movements (movement_at, grade, direction, kg, movement_kind, reference, notes) "
            "VALUES (?, ?, 'OUT', ?, 'Dispatch', ?, ?)",
            (movement_at, grade, kg, reference.strip(), notes),
        )
    return balance - kg


def save_laborer(name: str) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO laborers (name) VALUES (?)", (name.strip(),))


def record_labor_shift(laborer_id: int, started_at: str, ended_at: str,
                       break_minutes: int, notes: str | None) -> tuple[float, float, float]:
    from datetime import datetime

    start = datetime.fromisoformat(started_at)
    end = datetime.fromisoformat(ended_at)
    elapsed = (end - start).total_seconds() / 3600
    paid_hours = max(0.0, elapsed - break_minutes / 60)
    overtime = max(0.0, paid_hours - 8.0)
    pay = 400.0 + overtime * 50.0 if paid_hours > 0 else 0.0
    with connect() as conn:
        conn.execute(
            "INSERT INTO labor_shifts (laborer_id, started_at, ended_at, break_minutes, paid_hours, overtime_hours, pay_kes, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (laborer_id, start.isoformat(sep=" "), end.isoformat(sep=" "), break_minutes,
             round(paid_hours, 2), round(overtime, 2), round(pay, 2), notes),
        )
    return round(paid_hours, 2), round(overtime, 2), round(pay, 2)


def seed_demo_labor() -> int:
    """Create a few visibly fictional staff and example regular/overtime shifts."""
    from datetime import date, datetime, timedelta

    examples = [
        ("Demo Labourer 01", 8, 0, 17, 0, "Regular day shift"),
        ("Demo Labourer 02", 8, 0, 19, 0, "Two hours overtime during peak season"),
        ("Demo Labourer 03", 18, 0, 4, 0, "Night cover removal; ends next day"),
    ]
    shift_day = date.today() - timedelta(days=7)
    inserted = 0
    with connect() as conn:
        for name, *_ in examples:
            conn.execute("INSERT OR IGNORE INTO laborers (name) VALUES (?)", (name,))
        people = {r[1]: r[0] for r in conn.execute(
            "SELECT id, name FROM laborers WHERE name LIKE 'Demo Labourer %'"
        )}
        existing = conn.execute(
            "SELECT COUNT(*) FROM labor_shifts WHERE laborer_id IN "
            "(SELECT id FROM laborers WHERE name LIKE 'Demo Labourer %')"
        ).fetchone()[0]
        if existing:
            return 0
        for i, (name, start_hour, start_minute, end_hour, end_minute, note) in enumerate(examples):
            start_date = shift_day + timedelta(days=i)
            end_date = start_date + (timedelta(days=1) if end_hour <= start_hour else timedelta())
            start = datetime.combine(start_date, time(start_hour, start_minute)).isoformat(sep=" ")
            end = datetime.combine(end_date, time(end_hour, end_minute)).isoformat(sep=" ")
            # Each sample includes one simulated hour break.
            elapsed = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 3600
            paid = max(0.0, elapsed - 1)
            overtime = max(0.0, paid - 8)
            conn.execute(
                "INSERT INTO labor_shifts (laborer_id, started_at, ended_at, break_minutes, paid_hours, overtime_hours, pay_kes, notes) "
                "VALUES (?, ?, ?, 60, ?, ?, ?, ?)",
                (people[name], start, end, paid, overtime, 400 + overtime * 50, note),
            )
            inserted += 1
    return inserted


def record_delivery(farmer_id: int, delivery_date: date, weighed_time: time,
                    coffee_type: str, kg: float, receipt_number: str | None) -> int:
    when = f"{delivery_date.isoformat()} {weighed_time.strftime('%H:%M:%S')}"
    with connect() as conn:
        already = conn.execute(
            "SELECT 1 FROM deliveries WHERE farmer_id=? AND delivery_date=?",
            (farmer_id, delivery_date.isoformat()),
        ).fetchone()
        if already:
            raise ValueError("This farmer already has a delivery recorded for that day.")
        try:
            cursor = conn.execute(
                "INSERT INTO deliveries (farmer_id, delivery_date, weighed_at, coffee_type, kg, receipt_number) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (farmer_id, delivery_date.isoformat(), when, coffee_type, kg, receipt_number),
            )
            return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc):
                raise ValueError("This farmer already has a delivery recorded for that day.") from exc
            raise
