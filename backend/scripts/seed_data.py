import uuid
import random
from datetime import datetime, timedelta
import os
import sys

# Add the 'app' directory to the path so we can import models and database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models import Transaction, Incident, Diagnosis, RecoveryAction, Outcome, AuditLog

# Seed for absolute reproducibility during the demo
random.seed(42)

# Constants
START_DATE = datetime.now() - timedelta(days=10, hours=16)
GENERAL_ISSUERS = ["HDFC", "SBI", "ICICI", "Axis", "Kotak", "Yes Bank", "PNB", "BOB", "IDFC", "IndusInd", "Union Bank", "Canara", "HSBC", "Citi", "Standard Chartered"]
PAYMENT_METHODS = ["card", "upi", "netbanking"]
CARD_NETWORKS = ["Visa", "Mastercard", "RuPay"]
ROUTING_PARTNERS = ["Router_Alpha", "Router_Beta"]

# Typical decline reasons
NORMAL_DECLINES = [
    ("insufficient_funds", "Customer account has insufficient funds"),
    ("invalid_pin", "Incorrect PIN entered"),
    ("limit_exceeded", "Transaction exceeds daily limit"),
    ("do_not_honor", "Issuer declined without specific reason"),
    ("try_again_later", "Temporary system rate limit")
]

def generate_transaction(timestamp, segment_override=None, force_fail=False, specific_decline=None, force_success=False):
    if force_fail:
        is_success = False
    elif force_success:
        is_success = True
    else:
        is_success = (random.random() < 0.93)
    
    if segment_override:
        issuer, method, bin_prefix = segment_override
    else:
        issuer = random.choice(GENERAL_ISSUERS)
        method = random.choice(PAYMENT_METHODS)
        bin_prefix = str(random.randint(400000, 599999)) if method == "card" else None

    network = random.choice(CARD_NETWORKS) if method == "card" else None
    
    decline_code = None
    decline_reason = None
    if not is_success:
        if specific_decline:
            decline_code, decline_reason = specific_decline
        else:
            decline_code, decline_reason = random.choice(NORMAL_DECLINES)

    return Transaction(
        id=f"txn_{uuid.uuid4().hex[:12]}",
        merchant_id="merchant_demo_01",
        amount=round(random.uniform(500, 5000), 2),
        timestamp=timestamp,
        payment_method=method,
        issuer=issuer,
        card_network=network,
        decline_code=decline_code,
        decline_reason=decline_reason,
        retry_count=random.randint(0, 1) if not is_success else 0,
        customer_id=f"cust_{random.randint(1000, 9999)}",
        routing_partner=random.choice(ROUTING_PARTNERS),
        success=is_success
    )

def seed_database():
    random.seed(42)
    print("Clearing old data and recreating tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    transactions = []

    # 1. Background Traffic (~120 txns/day for 14 days)
    print("Generating baseline traffic...")
    for day in range(14):
        for _ in range(120):
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            ts = START_DATE + timedelta(days=day, hours=hour, minutes=minute)
            transactions.append(generate_transaction(ts))

    # 2. Bank X / Card / 4521xx Trailing Baseline (~15/day to give detection a history)
    print("Generating Bank X trailing baseline...")
    segment_bank_x = ("Bank X", "card", "452114")
    for day in range(14):
        for _ in range(15):
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            ts = START_DATE + timedelta(days=day, hours=hour, minutes=minute)
            transactions.append(generate_transaction(ts, segment_override=segment_bank_x))

    # 3. THE HERO INCIDENT (Day 10, 14:00 to Day 11, 02:00)
    # Success rate drops to ~58%. Out of failures, 85% are processor_declined.
    print("Injecting Primary Incident (Routing Degradation)...")
    # Shifted to start 6 hours ago (now - 10d - 16h + 10d + 10h = now - 6h)
    incident_start = START_DATE + timedelta(days=10, hours=10)
    for _ in range(210):
        # Compressed to a safe 4-hour window, ending 2 hours before 'now'
        ts = incident_start + timedelta(minutes=random.randint(0, 4 * 60))
        
        is_success_in_incident = random.random() < 0.58
        if is_success_in_incident:
            transactions.append(generate_transaction(ts, segment_override=segment_bank_x, force_success=True))
        else:
            specific_decline = None
            if random.random() < 0.85:
                specific_decline = ("processor_declined", "Routing gateway rejected the BIN path")
            tx = generate_transaction(ts, segment_override=segment_bank_x, force_fail=True, specific_decline=specific_decline)
            if specific_decline:
                tx.routing_partner = "Router_Alpha"
            transactions.append(tx)

    # 4. THE AMBIGUOUS/FAILURE INCIDENT (Now in the same time window)
    print("Injecting Ambiguous Failure Scenario...")
    ambiguous_start = START_DATE + timedelta(days=10, hours=14)
    segment_ambiguous = ("SBI", "upi", None)

    # 4a. Add a trailing baseline for SBI UPI
    for day in range(14):
        for _ in range(10):
            ts = START_DATE + timedelta(days=day, hours=random.randint(0, 23), minutes=random.randint(0, 59))
            transactions.append(generate_transaction(ts, segment_override=segment_ambiguous))

    # 4b. Inject the actual incident with a ~60% failure rate but totally random reasons
    for _ in range(80):
        ts = ambiguous_start + timedelta(minutes=random.randint(0, 119))
        force_fail = random.random() < 0.60
        tx = generate_transaction(ts, segment_override=segment_ambiguous, force_fail=force_fail)
        transactions.append(tx)

    # 5. HIGH-VALUE HUMAN APPROVAL INCIDENT
    # High-confidence routing issue with >₹500k at-risk revenue.
    # Calibrated with 70 processor_declined failures (>₹500k at-risk) and 80 successful txns
    # to yield sample_size > 50 and confidence >= 0.70 without starving Bank X.
    print("Injecting High-Value Human Approval Scenario...")

    incident_start_high_value = START_DATE + timedelta(days=10, hours=12)
    segment_high_value = ("ICICI", "card", "476543")

    # 5a. Healthy trailing baseline for ICICI Card (98% success rate)
    for day in range(14):
        for _ in range(10):
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            ts = START_DATE + timedelta(days=day, hours=hour, minutes=minute)
            is_base_success = random.random() < 0.98
            tx = generate_transaction(
                ts,
                segment_override=segment_high_value,
                force_fail=not is_base_success
            )
            transactions.append(tx)

    # 5b. High-value incident failures:
    # 70 failed transactions × ~₹9,500 each => ~₹660k at-risk revenue (>₹500k).
    for _ in range(70):
        ts = incident_start_high_value + timedelta(
            minutes=random.randint(0, 119)
        )

        tx = generate_transaction(
            ts,
            segment_override=segment_high_value,
            force_fail=True,
            specific_decline=(
                "processor_declined",
                "Routing gateway rejected the BIN path"
            )
        )

        tx.amount = round(random.uniform(8000, 11000), 2)
        tx.routing_partner = "Router_Alpha"
        transactions.append(tx)

    # 5c. High-value incident concurrent traffic:
    # 80 successful transactions to provide sample_size >= 50 and stable detection.
    for _ in range(80):
        ts = incident_start_high_value + timedelta(
            minutes=random.randint(0, 119)
        )

        tx = generate_transaction(
            ts,
            segment_override=segment_high_value,
            force_success=True
        )
        transactions.append(tx)    

    # 👇 YEH WOH LINES HAIN JO DELETE HO GAYI THIN 👇
    print(f"Inserting {len(transactions)} transactions into SQLite...")
    db.add_all(transactions)
    db.commit()
    print("[OK] Seed generation complete! Database is ready.")

if __name__ == "__main__":
    seed_database()