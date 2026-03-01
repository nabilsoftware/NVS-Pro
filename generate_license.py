"""
License Key Generator for Nabil Video Studio Pro
=================================================
Run this to generate license keys for customers.

Usage:
    python generate_license.py <email> <plan_type> [days] [customer_name]

Plan types: trial, starter, pro, enterprise

Examples:
    python generate_license.py customer@email.com trial
    python generate_license.py customer@email.com starter "John Doe"
    python generate_license.py customer@email.com pro "John Doe"
    python generate_license.py customer@email.com pro 30 "John Doe"
    python generate_license.py customer@email.com pro 90 "John Doe"
    python generate_license.py customer@email.com enterprise "Company Inc"

Pro with days = subscription (expires after X days)
Pro without days = lifetime (never expires)
"""

import hashlib
import json
import uuid
import sys
from datetime import datetime

SECRET_KEY = "cf1cab0218ded811ba9960834e933d9a7a46285a5ae055bf4c901b71d96d3c63"

# Plan definitions - single source of truth
PLANS = {
    "trial": {
        "prefix": "T",
        "price": "FREE",
        "price_paid": 0,
        "max_machines": 1,
        "max_channels": 1,
        "is_trial": True,
        "trial_days": 7,
        "license_type": "trial",
        "description": "7 days, 1 channel, 1 machine"
    },
    "starter": {
        "prefix": "S",
        "price": "$500",
        "price_paid": 500,
        "max_machines": 1,
        "max_channels": 3,
        "is_trial": False,
        "license_type": "lifetime",
        "description": "Lifetime, 3 channels, 1 machine"
    },
    "pro": {
        "prefix": "P",
        "price": "$1,000",
        "price_paid": 1000,
        "max_machines": 1,
        "is_trial": False,
        "license_type": "lifetime",
        "description": "Lifetime, unlimited channels, 1 machine"
    },
    "enterprise": {
        "prefix": "E",
        "price": "$5,000",
        "price_paid": 5000,
        "max_machines": 999,
        "is_trial": False,
        "license_type": "lifetime",
        "description": "Lifetime, unlimited channels, unlimited machines"
    }
}


def generate_license_key(customer_email: str, plan_type: str) -> str:
    """Generate a license key for a customer"""
    prefix = PLANS[plan_type]["prefix"]

    email_hash = hashlib.md5(customer_email.lower().encode()).hexdigest()[:5].upper()
    random_part = str(uuid.uuid4().hex)[:5].upper()

    data_to_sign = f"{prefix}{email_hash}{random_part}"
    signature_data = f"{data_to_sign}|{SECRET_KEY}"
    signature = hashlib.sha256(signature_data.encode()).hexdigest()[:5].upper()

    full_key = prefix + email_hash + random_part + signature
    license_key = "-".join([full_key[i:i+4] for i in range(0, 16, 4)])

    return license_key


def get_firebase_doc(email: str, plan_type: str, customer_name: str = "",
                     subscription_days: int = 0, price_paid: int = None) -> dict:
    """Build the complete Firebase document with all required fields"""
    plan = PLANS[plan_type]
    today = datetime.now().strftime("%Y-%m-%d")

    doc = {
        "customer_email": email.lower(),
        "customer_name": customer_name,
        "valid": True,
        "plan_type": plan_type,
        "is_trial": plan["is_trial"],
        "max_machines": plan["max_machines"],
        "price_paid": price_paid if price_paid is not None else plan["price_paid"],
        "purchase_date": today,
        "activations": [],
    }

    # If subscription_days is set, it's a time-limited plan
    if subscription_days > 0:
        doc["license_type"] = "subscription"
        doc["subscription_days"] = subscription_days
    else:
        doc["license_type"] = plan["license_type"]

    if plan["is_trial"]:
        doc["trial_days"] = plan["trial_days"]

    if "max_channels" in plan:
        doc["max_channels"] = plan["max_channels"]

    return doc


def print_firebase_fields(doc: dict):
    """Print Firebase fields with types clearly marked"""
    for key, value in doc.items():
        if isinstance(value, bool):
            print(f"    {key:<20} {str(value).lower():<20} (boolean)")
        elif isinstance(value, int):
            print(f"    {key:<20} {value:<20} (number)")
        elif isinstance(value, list):
            print(f"    {key:<20} {'[]':<20} (array)")
        else:
            print(f"    {key:<20} \"{value}\"{'':.<{18 - len(str(value))}} (string)")


if __name__ == "__main__":
    print("=" * 60)
    print("  Nabil Video Studio Pro - LICENSE KEY GENERATOR")
    print("=" * 60)

    # Check arguments or ask for input
    customer_name = ""
    subscription_days = 0
    price_paid = None

    if len(sys.argv) >= 3:
        # Command line mode
        email = sys.argv[1]
        plan_type = sys.argv[2].lower()

        # Check if next arg is a number (days) or name
        arg_idx = 3
        if len(sys.argv) > arg_idx and sys.argv[arg_idx].isdigit():
            subscription_days = int(sys.argv[arg_idx])
            arg_idx += 1
        if len(sys.argv) > arg_idx:
            customer_name = " ".join(sys.argv[arg_idx:])
    else:
        # Interactive mode
        print("\n  Plans:")
        print(f"    1. {'trial':<12} {'FREE':<8} (7 days, 1 channel, 1 machine)")
        print(f"    2. {'starter':<12} {'$500':<8} (Lifetime, 3 channels, 1 machine)")
        print(f"    3. {'pro':<12} {'$1,000':<8} (Lifetime, unlimited channels, 1 machine)")
        print(f"    4. {'enterprise':<12} {'$5,000':<8} (Lifetime, unlimited channels, unlimited machines)")
        print()

        email = input("  Customer email: ").strip()
        if not email or "@" not in email:
            print("  Error: Valid email is required")
            sys.exit(1)

        customer_name = input("  Customer name:  ").strip()

        choice = input("  Select plan (1-4): ").strip()
        plan_map = {"1": "trial", "2": "starter", "3": "pro", "4": "enterprise"}
        plan_type = plan_map.get(choice, "")

        if not plan_type:
            print("  Error: Invalid plan choice")
            sys.exit(1)

        # For Pro and Starter: ask if lifetime or limited days
        if plan_type in ("pro", "starter"):
            print()
            print(f"  Duration for {plan_type.upper()} plan:")
            print(f"    1. Lifetime (forever)")
            print(f"    2. Limited days (subscription)")
            dur_choice = input("  Select (1-2): ").strip()

            if dur_choice == "2":
                days_input = input("  How many days? ").strip()
                if days_input.isdigit() and int(days_input) > 0:
                    subscription_days = int(days_input)
                    price_input = input(f"  Price paid (or Enter for custom): $").strip()
                    if price_input.isdigit():
                        price_paid = int(price_input)
                else:
                    print("  Error: Invalid number of days")
                    sys.exit(1)

    if plan_type not in PLANS:
        print(f"\n  Error: Invalid plan type '{plan_type}'")
        print(f"  Valid: {', '.join(PLANS.keys())}")
        sys.exit(1)

    # Generate
    license_key = generate_license_key(email, plan_type)
    clean_key = license_key.replace("-", "")
    plan = PLANS[plan_type]
    firebase_doc = get_firebase_doc(email, plan_type, customer_name,
                                    subscription_days, price_paid)

    # Output
    print()
    print("=" * 60)
    print(f"  LICENSE KEY:  {license_key}")
    if subscription_days > 0:
        print(f"  Plan:         {plan_type.upper()} ({subscription_days} days subscription)")
    else:
        print(f"  Plan:         {plan_type.upper()} ({plan['description']})")
    print(f"  Email:        {email.lower()}")
    if customer_name:
        print(f"  Name:         {customer_name}")
    if price_paid is not None:
        print(f"  Price:        ${price_paid}")
    print("=" * 60)

    # Firebase
    print()
    print("  FIREBASE SETUP")
    print("-" * 60)
    print(f"  Collection:   licenses")
    print(f"  Document ID:  {clean_key}")
    print()
    print("  Fields (add ALL of these):")
    print()
    print_firebase_fields(firebase_doc)
    print()
    print("-" * 60)

    # JSON for easy copy-paste
    print()
    print("  JSON (for import/API):")
    print("-" * 60)
    json_doc = {k: v for k, v in firebase_doc.items()}
    print(json.dumps(json_doc, indent=2))
    print("-" * 60)

    print()
    print("  STEPS:")
    print("  1. Firebase Console > Firestore > 'licenses' collection")
    print(f"  2. Add document with ID: {clean_key}")
    print("  3. Add ALL fields above (check types: boolean/number/string)")
    print(f"  4. Send LICENSE KEY to customer: {license_key}")
    print()
