"""
License Manager for Nabil Video Studio Pro
Handles license key generation, validation, and activation
Now with Firebase integration for online validation!
"""

import hashlib
import json
import uuid
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

# Try to import Firebase license manager
try:
    from firebase_license import FirebaseLicense
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    FirebaseLicense = None


class LicenseManager:
    """Manages license keys and activation"""

    def __init__(self, license_file: str = None):
        # Use AppData for user data (writable location)
        if license_file is None:
            appdata_dir = self._get_user_data_dir()
            appdata_dir.mkdir(parents=True, exist_ok=True)
            license_file = appdata_dir / "license.dat"

        self.license_file = Path(license_file)
        self.secret_key = "cf1cab0218ded811ba9960834e933d9a7a46285a5ae055bf4c901b71d96d3c63"

        # Initialize Firebase license manager
        self.firebase = None
        if FIREBASE_AVAILABLE:
            try:
                self.firebase = FirebaseLicense()
            except Exception as e:
                print(f"Firebase init warning: {e}")

    def _get_user_data_dir(self) -> Path:
        """Get the user data directory (AppData on Windows)"""
        if os.name == 'nt':  # Windows
            appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
            return Path(appdata) / "NabilVideoStudioPro"
        else:  # Linux/Mac
            return Path.home() / ".nvspro"

    def generate_license_key(self, customer_email: str, license_type: str = "starter",
                            days_valid: int = 365) -> str:
        """
        Generate a license key for a customer with embedded verification

        Args:
            customer_email: Customer's email address
            license_type: Type of license (trial, starter, pro, enterprise)
            days_valid: Number of days the license is valid

        Returns:
            License key in format: TXXX-XXXX-XXXX-XXXX (T = type prefix)
        """
        # License type prefix (first character encodes the type)
        type_prefix = {
            "trial": "T",
            "starter": "S",
            "pro": "P",
            "enterprise": "E"
        }
        prefix = type_prefix.get(license_type.lower(), "S")

        # Create email hash (first 5 chars of email hash)
        email_hash = hashlib.md5(customer_email.lower().encode()).hexdigest()[:5].upper()

        # Generate random component (5 chars)
        random_part = str(uuid.uuid4().hex)[:5].upper()

        # Create data to sign (WITHOUT date, to avoid reconstruction issues)
        data_to_sign = f"{prefix}{email_hash}{random_part}"

        # Generate signature/checksum (5 chars) using secret key
        signature_data = f"{data_to_sign}|{self.secret_key}"
        signature = hashlib.sha256(signature_data.encode()).hexdigest()[:5].upper()

        # Build key: [Prefix:1][Email:5][Random:5][Signature:5]
        # Total: 16 chars
        full_key = prefix + email_hash + random_part + signature

        # Format as TXXX-XXXX-XXXX-XXXX
        license_key = "-".join([full_key[i:i+4] for i in range(0, 16, 4)])

        return license_key

    def get_license_type_from_key(self, license_key: str) -> Tuple[str, int]:
        """
        Extract license type from key prefix

        Args:
            license_key: The license key

        Returns:
            (license_type, days_valid)
        """
        # Remove spaces and dashes
        clean_key = license_key.strip().upper().replace(" ", "").replace("-", "")

        if len(clean_key) < 1:
            return "standard", 365

        # Get prefix (first character)
        prefix = clean_key[0]

        # Map prefix to license type
        prefix_map = {
            "T": ("trial", 7),
            "S": ("starter", 36500),
            "P": ("pro", 36500),
            "E": ("enterprise", 36500)
        }

        return prefix_map.get(prefix, ("standard", 365))

    def validate_license_key(self, license_key: str, customer_email: str = None) -> Tuple[bool, str]:
        """
        Validate if a license key is properly formatted and legitimately generated

        Args:
            license_key: The license key to validate
            customer_email: Customer's email (optional, for stronger validation)

        Returns:
            (is_valid, message)
        """
        # Remove spaces and convert to uppercase
        license_key = license_key.strip().upper().replace(" ", "")

        # Check format: XXXX-XXXX-XXXX-XXXX
        if len(license_key) != 19:  # 16 chars + 3 dashes
            return False, "Invalid license key format"

        parts = license_key.split("-")
        if len(parts) != 4:
            return False, "Invalid license key format"

        # Remove dashes
        clean_key = license_key.replace("-", "")

        if len(clean_key) != 16:
            return False, "Invalid license key format"

        # Extract components: [Prefix:1][Email:5][Random:5][Signature:5]
        prefix = clean_key[0]
        email_hash = clean_key[1:6]
        random_part = clean_key[6:11]
        signature = clean_key[11:16]

        # Validate prefix
        if prefix not in "TSPE":
            return False, "Invalid license type prefix"

        # Verify signature (checksum)
        data_to_sign = f"{prefix}{email_hash}{random_part}"
        signature_data = f"{data_to_sign}|{self.secret_key}"
        expected_signature = hashlib.sha256(signature_data.encode()).hexdigest()[:5].upper()

        if signature != expected_signature:
            return False, "Invalid license key - authentication failed"

        # Optional: Verify email hash if email provided
        if customer_email:
            expected_email_hash = hashlib.md5(customer_email.lower().encode()).hexdigest()[:5].upper()
            if email_hash != expected_email_hash:
                return False, "License key does not match this email address"

        return True, "License key is valid and authentic"

    def activate_license(self, license_key: str, customer_email: str,
                         license_type: str = "standard", days_valid: int = 365) -> Tuple[bool, str]:
        """
        Activate a license key and save to local file
        Uses Firebase for online validation if available

        Args:
            license_key: The license key to activate
            customer_email: Customer's email for validation
            license_type: Type of license (trial, standard, professional, lifetime)
            days_valid: Number of days the license is valid

        Returns:
            (success, message)
        """
        # Firebase validation required - no local fallback
        if not self.firebase:
            return False, "License server not available. Please check your internet connection."

        success, message, firebase_data = self.firebase.activate_license(license_key, customer_email)

        if success:
            # Firebase handles encrypted cache - don't save plain JSON
            return True, message

        else:
            # Firebase rejected - return error (no fallback!)
            return False, message

    def check_license(self) -> Tuple[bool, str, dict]:
        """
        Check if the application has a valid license
        ALWAYS uses Firebase - no offline fallback

        Returns:
            (is_licensed, message, license_info)
        """
        # Firebase verification required
        if not self.firebase:
            return False, "License server not available. Please check your internet connection.", {}

        valid, message, firebase_info = self.firebase.verify_license()

        if valid:
            return True, message, firebase_info
        else:
            return False, message, firebase_info

    def get_subscription_info(self) -> Optional[dict]:
        """Get detailed subscription info for display in UI"""
        if self.firebase:
            return self.firebase.get_subscription_info()
        return None

    def deactivate_license(self) -> bool:
        """Deactivate and remove license"""
        if self.firebase:
            self.firebase.deactivate_license()
        return True

    def get_license_info(self) -> Optional[dict]:
        """Get current license information - uses Firebase"""
        if self.firebase:
            return self.firebase.get_subscription_info()
        return None

    def get_max_channels(self) -> int:
        """
        Get max channels allowed based on license tier

        Pricing tiers:
        - starter ($500): 1 user, 3 channels
        - pro ($1000): 1 user, unlimited channels
        - enterprise ($5000): unlimited users, unlimited channels

        Firebase can override with 'max_channels' field in license doc
        """
        info = self.get_subscription_info()
        if not info:
            return 1  # No license = 1 channel only

        # Check if Firebase has explicit max_channels set
        if 'max_channels' in info:
            return int(info.get('max_channels', 1))

        # Otherwise use plan_type to determine limits
        plan_type = info.get('plan_type', 'starter').lower()

        tier_limits = {
            'trial': 1,          # FREE - 7 days, 1 channel
            'starter': 3,        # $500 - 1 user, 3 channels
            'pro': 9999,         # $1,000 - 1 user, unlimited channels
            'enterprise': 9999,  # $5,000 - unlimited users, unlimited channels
        }

        return tier_limits.get(plan_type, 3)

    def get_tier(self) -> str:
        """Get current license tier"""
        info = self.get_subscription_info()
        if info:
            return info.get('plan_type', info.get('tier', 'starter'))
        return 'starter'

    def can_add_channel(self, current_count: int) -> Tuple[bool, str]:
        """
        Check if user can add another channel

        Args:
            current_count: Current number of channels

        Returns:
            (can_add, message)
        """
        max_channels = self.get_max_channels()

        if current_count >= max_channels:
            tier = self.get_tier()
            if tier == 'starter':
                return False, f"Starter plan allows 3 channels. Upgrade to Pro ($1000) for unlimited channels."
            return False, f"Your {tier.title()} plan allows {max_channels} channel(s). Upgrade to add more."

        return True, ""

    def _get_license_type_info(self, plan_type: str) -> dict:
        """Get information about a license/plan type"""
        plan_types = {
            "trial": {
                "duration": "7 days",
                "price": "FREE",
                "price_paid": 0,
                "max_machines": 1,
                "max_channels": 1,
                "is_trial": True,
                "license_type": "trial",
                "use_case": "Free trial - 1 channel, all features"
            },
            "starter": {
                "duration": "Lifetime",
                "price": "$500",
                "price_paid": 500,
                "max_machines": 1,
                "max_channels": 3,
                "is_trial": False,
                "license_type": "lifetime",
                "use_case": "1 user, 3 channels - Perfect for small creators"
            },
            "pro": {
                "duration": "Lifetime",
                "price": "$1,000",
                "price_paid": 1000,
                "max_machines": 1,
                "max_channels": None,  # Unlimited
                "is_trial": False,
                "license_type": "lifetime",
                "use_case": "1 user, unlimited channels - For serious creators"
            },
            "enterprise": {
                "duration": "Lifetime",
                "price": "$5,000",
                "price_paid": 5000,
                "max_machines": 999,
                "max_channels": None,  # Unlimited
                "is_trial": False,
                "license_type": "lifetime",
                "use_case": "Unlimited users & channels - For agencies & teams"
            }
        }
        return plan_types.get(plan_type.lower(), plan_types["starter"])

    def _get_machine_id(self) -> str:
        """Get unique machine identifier"""
        # Use MAC address as machine ID
        mac = uuid.getnode()
        return str(mac)


# ============================================================================
# LICENSE KEY GENERATOR TOOL (For you to generate keys for customers)
# ============================================================================

def generate_keys_for_customers():
    """
    Tool for generating license keys for customers
    Run this script separately to generate keys
    """
    from datetime import datetime

    print("=" * 60)
    print("Nabil Video Studio Pro - LICENSE KEY GENERATOR")
    print("=" * 60)

    manager = LicenseManager()

    while True:
        print("\n" + "=" * 60)
        customer_email = input("Customer Email (or 'quit' to exit): ").strip()

        if customer_email.lower() == 'quit':
            break

        if not customer_email or "@" not in customer_email:
            print("  ! Invalid email. Must contain @")
            continue

        customer_name = input("Customer Name (optional): ").strip()

        print("\nPlans:")
        print("  1. Trial      - FREE  (7 days, 1 channel, 1 machine)")
        print("  2. Starter    - $500  (lifetime, 3 channels, 1 machine)")
        print("  3. Pro        - $1000 (lifetime, unlimited channels, 1 machine)")
        print("  4. Enterprise - $5000 (lifetime, unlimited channels, unlimited machines)")

        choice = input("\nSelect plan (1-4): ").strip()
        plan_map = {"1": "trial", "2": "starter", "3": "pro", "4": "enterprise"}
        plan_type = plan_map.get(choice)

        if not plan_type:
            print("  ! Invalid choice")
            continue

        # For Pro and Starter: ask if lifetime or limited days
        subscription_days = 0
        custom_price = None
        if plan_type in ("pro", "starter"):
            print(f"\n  Duration for {plan_type.upper()} plan:")
            print(f"    1. Lifetime (forever)")
            print(f"    2. Limited days (subscription)")
            dur_choice = input("  Select (1-2): ").strip()

            if dur_choice == "2":
                days_input = input("  How many days? ").strip()
                if days_input.isdigit() and int(days_input) > 0:
                    subscription_days = int(days_input)
                    price_input = input("  Price paid (or Enter to skip): $").strip()
                    if price_input.isdigit():
                        custom_price = int(price_input)
                else:
                    print("  ! Invalid number of days")
                    continue

        # Generate key
        license_key = manager.generate_license_key(customer_email, plan_type)
        clean_key = license_key.replace("-", "")
        plan_info = manager._get_license_type_info(plan_type)
        today = datetime.now().strftime("%Y-%m-%d")

        # Build Firebase document
        firebase_doc = {
            "customer_email": customer_email.lower(),
            "customer_name": customer_name,
            "valid": True,
            "plan_type": plan_type,
            "is_trial": plan_info["is_trial"],
            "max_machines": plan_info["max_machines"],
            "price_paid": custom_price if custom_price is not None else plan_info["price_paid"],
            "purchase_date": today,
            "activations": [],
        }

        # Set license_type and subscription_days
        if subscription_days > 0:
            firebase_doc["license_type"] = "subscription"
            firebase_doc["subscription_days"] = subscription_days
        else:
            firebase_doc["license_type"] = plan_info["license_type"]

        if plan_info["is_trial"]:
            firebase_doc["trial_days"] = 7
        if plan_info["max_channels"] is not None:
            firebase_doc["max_channels"] = plan_info["max_channels"]

        # Display results
        print("\n" + "=" * 60)
        print(f"  LICENSE KEY:  {license_key}")
        if subscription_days > 0:
            print(f"  Plan:         {plan_type.upper()} ({subscription_days} days subscription)")
        else:
            print(f"  Plan:         {plan_type.upper()} ({plan_info['price']})")
        print(f"  Email:        {customer_email.lower()}")
        if customer_name:
            print(f"  Name:         {customer_name}")
        if custom_price is not None:
            print(f"  Price:        ${custom_price}")
        print("=" * 60)

        # Firebase instructions
        print("\n  FIREBASE: Add this document to Firestore")
        print("-" * 60)
        print(f"  Collection:   licenses")
        print(f"  Document ID:  {clean_key}")
        print()
        print("  Fields to add:")
        print()
        for key, value in firebase_doc.items():
            if isinstance(value, bool):
                print(f"    {key}  =  {str(value).lower()}  (boolean)")
            elif isinstance(value, int):
                print(f"    {key}  =  {value}  (number)")
            elif isinstance(value, list):
                print(f"    {key}  =  []  (array)")
            else:
                print(f"    {key}  =  \"{value}\"  (string)")
        print()
        print("-" * 60)
        print("  Steps:")
        print("  1. Firebase Console > Firestore > 'licenses' collection")
        print(f"  2. Add document with ID: {clean_key}")
        print("  3. Add ALL the fields above (types matter!)")
        print(f"  4. Send LICENSE KEY to customer: {license_key}")
        print("=" * 60)


if __name__ == "__main__":
    generate_keys_for_customers()
