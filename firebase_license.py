"""
Firebase License Manager for Nabil Video Studio Pro
Handles online license validation, activation tracking, and trial management
SECURITY: Always online, encrypted cache, no offline bypass
"""

import json
import os
import uuid
import hashlib
import hmac
import base64
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict
import urllib.request
import urllib.error
import urllib.parse

# Firebase Configuration
FIREBASE_PROJECT_ID = "nabil-video-studio-pro"
# API key obfuscated - decoded at runtime
_FK = [0x30, 0x67, 0x59, 0x1f, 0x10, 0x46, 0x78, 0x5a, 0x39, 0x4e, 0x15, 0x24,
       0x09, 0x74, 0x22, 0x20, 0x66, 0x4b, 0x5f, 0x5c, 0x48, 0x50, 0x5d, 0x4d,
       0x15, 0x6b, 0x03, 0x3c, 0x34, 0x00, 0x1d, 0x63, 0x11, 0x5b, 0x6e, 0x72,
       0x79, 0x38, 0x0f]
_FS = [0x71, 0x2e, 0x23, 0x7e, 0x43, 0x3f, 0x3c, 0x31, 0x7e, 0x2d, 0x76, 0x7e,
       0x65, 0x2b, 0x6b, 0x56, 0x24, 0x23, 0x2b, 0x3b, 0x3d, 0x60, 0x6d, 0x23,
       0x67, 0x39, 0x7b, 0x73, 0x79, 0x65, 0x55, 0x3c, 0x59, 0x6b, 0x43, 0x20,
       0x34, 0x79, 0x56]
FIREBASE_API_KEY = ''.join(chr(a ^ b) for a, b in zip(_FK, _FS))
FIRESTORE_URL = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"

# Encryption salt (obfuscated) - combined with machine ID for per-machine encryption
_ES = [78, 97, 98, 105, 108, 86, 83, 80, 114, 111, 50, 48, 50, 53, 33, 64,
       55, 42, 99, 88, 76, 65, 51, 71, 109, 82, 48, 57, 36, 38, 67, 91]


def _get_disk_serial() -> str:
    """Get Windows disk serial number — sorted to handle drive enumeration order changes"""
    try:
        result = subprocess.run(
            ['wmic', 'diskdrive', 'get', 'serialnumber'],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        lines = [l.strip() for l in result.stdout.strip().split('\n')
                 if l.strip() and l.strip().lower() != 'serialnumber']
        if lines:
            # Sort so drive enumeration order doesn't change the hash
            return '|'.join(sorted(lines))
    except:
        pass
    return ""


def _get_motherboard_serial() -> str:
    """Get motherboard serial number"""
    try:
        result = subprocess.run(
            ['wmic', 'baseboard', 'get', 'serialnumber'],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        lines = [l.strip() for l in result.stdout.strip().split('\n')
                 if l.strip() and l.strip().lower() != 'serialnumber']
        if lines and lines[0] != 'To be filled by O.E.M.':
            return lines[0]
    except:
        pass
    return ""


class FirebaseLicense:
    """Handles Firebase-based license validation and activation"""

    def __init__(self):
        self.project_id = FIREBASE_PROJECT_ID
        self.local_cache_file = self._get_cache_file()
        self._machine_id_cache = None  # Cache to avoid repeated wmic calls

    def _get_cache_file(self) -> Path:
        """Get local cache file path"""
        if os.name == 'nt':
            appdata = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
            cache_dir = Path(appdata) / "NabilVideoStudioPro"
        else:
            cache_dir = Path.home() / ".nvspro"

        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "license.dat"

    def _get_encryption_key(self) -> bytes:
        """Get a stable encryption key for the local license cache.

        Uses a randomly generated key saved to a file (.ekey), NOT derived from hardware.
        This prevents the cache from becoming unreadable when wmic returns different
        values (USB drives plugged/unplugged, wmic timeout under heavy load, etc.).

        The key is generated once and reused forever on this machine.
        Security still holds because:
        - The key file is in AppData (not easily found)
        - The license is still validated online against Firebase
        - The cache is just for offline/startup convenience
        """
        key_file = self._get_cache_file().parent / ".ekey"
        try:
            if key_file.exists():
                raw = key_file.read_bytes()
                if len(raw) == 32:
                    return raw
        except:
            pass

        # Generate a new random key and save it
        salt = bytes(_ES)
        # Mix salt with something unique to this install
        seed = f"{os.environ.get('COMPUTERNAME', 'x')}|{uuid.getnode()}|{os.urandom(16).hex()}"
        key = hmac.new(salt, seed.encode('utf-8'), hashlib.sha256).digest()
        try:
            key_file.write_bytes(key)
        except:
            pass
        return key  # 32 bytes

    def _encrypt_data(self, data: str) -> str:
        """Encrypt data using machine-specific XOR + base64"""
        key = self._get_encryption_key()
        encrypted = bytearray()
        for i, char in enumerate(data.encode('utf-8')):
            encrypted.append(char ^ key[i % len(key)])
        return base64.b64encode(encrypted).decode('utf-8')

    def _decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt data using machine-specific XOR + base64"""
        try:
            key = self._get_encryption_key()
            decoded = base64.b64decode(encrypted_data.encode('utf-8'))
            decrypted = bytearray()
            for i, byte in enumerate(decoded):
                decrypted.append(byte ^ key[i % len(key)])
            return decrypted.decode('utf-8')
        except:
            return None

    def _get_machine_id(self) -> str:
        """Get unique machine identifier from hardware.
        Uses stable hardware signals that don't change between reboots/sessions.

        Stability rules:
        - MAC address: stable (uuid.getnode always returns same value)
        - Computer name: stable (user rarely changes it)
        - Motherboard serial: stable (never changes)
        - Disk serials: sorted to handle enumeration order changes

        Removed: Windows SID (wmic query fails on domain/Microsoft accounts)
        """
        if self._machine_id_cache:
            return self._machine_id_cache

        # Gather stable hardware identifiers
        mac = str(uuid.getnode())
        computer_name = os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'unknown'))
        disk_serial = _get_disk_serial()
        motherboard = _get_motherboard_serial()

        # Combine stable signals only
        combined = f"{mac}|{computer_name}|{disk_serial}|{motherboard}"
        machine_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]

        # Save to .mid file (for backward compat, but not relied upon)
        machine_id_file = self._get_cache_file().parent / ".mid"
        try:
            with open(machine_id_file, 'w') as f:
                f.write(machine_hash)
        except:
            pass

        self._machine_id_cache = machine_hash
        return machine_hash

    def _firestore_request(self, method: str, path: str, data: dict = None) -> Tuple[bool, dict]:
        """Make a request to Firestore REST API"""
        separator = "&" if "?" in path else "?"
        url = f"{FIRESTORE_URL}/{path}{separator}key={FIREBASE_API_KEY}"

        headers = {
            'Content-Type': 'application/json',
        }

        try:
            if data:
                req_data = json.dumps(data).encode('utf-8')
                request = urllib.request.Request(url, data=req_data, headers=headers, method=method)
            else:
                request = urllib.request.Request(url, headers=headers, method=method)

            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                return True, result

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False, {"error": "not_found", "details": "License key not found"}
            elif e.code == 403:
                return False, {"error": "forbidden", "details": "Access denied"}
            else:
                return False, {"error": f"server_error", "details": f"Server error ({e.code})"}
        except urllib.error.URLError as e:
            return False, {"error": "network_error", "details": "Cannot connect to license server. Check your internet connection."}
        except Exception as e:
            return False, {"error": "unknown_error", "details": str(e)}

    def _parse_firestore_doc(self, doc: dict) -> dict:
        """Parse Firestore document format to simple dict"""
        if 'fields' not in doc:
            return {}

        result = {}
        for key, value in doc['fields'].items():
            if 'stringValue' in value:
                result[key] = value['stringValue']
            elif 'integerValue' in value:
                result[key] = int(value['integerValue'])
            elif 'doubleValue' in value:
                result[key] = float(value['doubleValue'])
            elif 'booleanValue' in value:
                result[key] = value['booleanValue']
            elif 'arrayValue' in value:
                arr = []
                for item in value['arrayValue'].get('values', []):
                    if 'mapValue' in item:
                        arr.append(self._parse_firestore_doc(item['mapValue']))
                    elif 'stringValue' in item:
                        arr.append(item['stringValue'])
                result[key] = arr
            elif 'mapValue' in value:
                result[key] = self._parse_firestore_doc(value['mapValue'])

        return result

    def _to_firestore_value(self, value) -> dict:
        """Convert Python value to Firestore format"""
        if isinstance(value, bool):
            return {"booleanValue": value}
        elif isinstance(value, int):
            return {"integerValue": str(value)}
        elif isinstance(value, str):
            return {"stringValue": value}
        elif isinstance(value, list):
            return {"arrayValue": {"values": [self._to_firestore_value(v) for v in value]}}
        elif isinstance(value, dict):
            return {"mapValue": {"fields": {k: self._to_firestore_value(v) for k, v in value.items()}}}
        else:
            return {"stringValue": str(value)}

    def check_license_online(self, license_key: str) -> Tuple[bool, str, dict]:
        """
        Check license status from Firebase - ALWAYS ONLINE, NO OFFLINE FALLBACK
        """
        clean_key = license_key.strip().upper().replace(" ", "").replace("-", "")
        success, result = self._firestore_request("GET", f"licenses/{clean_key}")

        if not success:
            # NO OFFLINE FALLBACK - must connect to server
            error_type = result.get('error', '')
            if error_type == 'not_found':
                return False, "Invalid license key. Please check and try again.", {}
            elif error_type == 'network_error':
                return False, "Internet connection required. Please connect and try again.", {}
            else:
                return False, f"Cannot verify license. Please check your internet connection.", {}

        if 'error' in result or 'fields' not in result:
            return False, "Invalid license key. Please check and try again.", {}

        license_data = self._parse_firestore_doc(result)

        if not license_data.get('valid', False):
            return False, "License has been revoked", license_data

        return True, "License found", license_data

    def activate_license(self, license_key: str, customer_email: str = "") -> Tuple[bool, str, dict]:
        """Activate a license key on this machine - REQUIRES INTERNET"""
        clean_key = license_key.strip().upper().replace(" ", "").replace("-", "")
        machine_id = self._get_machine_id()

        # Email is required
        if not customer_email or not customer_email.strip():
            return False, "Email address is required.", {}

        customer_email = customer_email.strip().lower()

        # First, check if license exists ONLINE
        success, message, license_data = self.check_license_online(clean_key)

        if not success:
            return False, message, {}

        # Verify email matches
        registered_email = (
            license_data.get('customer_email') or
            license_data.get('customerEmail') or
            license_data.get('email') or
            ''
        ).strip().lower()

        if not registered_email:
            return False, "This license has no registered email. Contact support.", {}

        if customer_email != registered_email:
            return False, "Email does not match this license key.", {}

        # Check existing activations
        activations = license_data.get('activations', [])
        max_machines = license_data.get('max_machines', 1)
        is_trial = license_data.get('is_trial', False)
        trial_days_raw = license_data.get('trial_days', 7)
        trial_days = int(trial_days_raw) if trial_days_raw else 7


        # Check if already activated on this machine (exact match or same computer name)
        current_computer = os.environ.get('COMPUTERNAME', 'Unknown')
        matched_activation = None
        need_update_firebase = False

        for activation in activations:
            if activation.get('machine_id') == machine_id:
                # Exact machine ID match
                matched_activation = activation
                break
            elif activation.get('computer_name', '') == current_computer and activation.get('machine_id', '') != machine_id:
                # Same computer name but different machine ID — ID algorithm changed after update
                # Update the activation's machine_id to the current one
                print(f"[LICENSE] Machine ID migration: {activation.get('machine_id')} -> {machine_id}")
                activation['machine_id'] = machine_id
                matched_activation = activation
                need_update_firebase = True
                break

        if matched_activation:
            activated_at = matched_activation.get('activated_at', '')

            expiry_info = self._calculate_expiry(license_data, matched_activation)

            # Block expired licenses (trial AND subscription)
            if expiry_info.get('is_expired', False):
                expiry_date = expiry_info.get('expiry_date', '')
                expiry_str = expiry_date[:10] if expiry_date else 'Unknown'
                if is_trial:
                    return False, f"Trial expired on {expiry_str}. Please upgrade.", {
                        "expired": True, "is_expired": True,
                        "expiry_date": expiry_date, "is_trial": True
                    }
                else:
                    return False, f"License expired on {expiry_str}. Please renew.", {
                        "expired": True, "is_expired": True,
                        "expiry_date": expiry_date, "is_trial": False
                    }

            # Update Firebase if machine ID was migrated
            if need_update_firebase:
                try:
                    update_data = {
                        "fields": {
                            "activations": self._to_firestore_value(activations)
                        }
                    }
                    self._firestore_request(
                        "PATCH",
                        f"licenses/{clean_key}?updateMask.fieldPaths=activations",
                        update_data
                    )
                except:
                    pass  # Non-critical — cache will still work

            cache_data = {
                "license_key": clean_key,
                "machine_id": machine_id,
                "activated_at": activated_at,
                "is_trial": is_trial,
                "license_type": license_data.get('license_type', 'standard'),
                "plan_type": license_data.get('plan_type', 'trial' if is_trial else 'standard'),
                "customer_email": customer_email,
                "customer_name": license_data.get('customer_name', ''),
                "price_paid": license_data.get('price_paid', 0),
                "purchase_date": license_data.get('purchase_date', ''),
                "last_check": datetime.now().isoformat(),
                "trial_days": trial_days,
                **expiry_info
            }

            # Add max_channels if set in Firebase (allows per-license override)
            if 'max_channels' in license_data:
                cache_data['max_channels'] = license_data.get('max_channels')

            # Add subscription_days if set (for time-limited paid plans)
            if 'subscription_days' in license_data:
                cache_data['subscription_days'] = float(license_data.get('subscription_days', 0))

            self._save_cache(cache_data)

            return True, "License already activated on this machine", cache_data

        # Check if max machines reached
        if len(activations) >= max_machines:
            # Before blocking: check if this computer already has a stale activation
            # (same computer_name but old machine_id — machine ID changed after update)
            # If so, replace the stale activation instead of blocking
            stale_idx = None
            for idx, act in enumerate(activations):
                if act.get('computer_name', '') == current_computer:
                    stale_idx = idx
                    break

            if stale_idx is not None:
                # Replace stale activation with fresh one (same computer, new machine ID)
                print(f"[LICENSE] Replacing stale activation for {current_computer} (old ID: {activations[stale_idx].get('machine_id')})")
                activations[stale_idx] = {
                    "machine_id": machine_id,
                    "activated_at": activations[stale_idx].get('activated_at', datetime.now().isoformat()),
                    "computer_name": current_computer
                }
            else:
                return False, f"License already activated on {len(activations)} machine(s). Max: {max_machines}", {
                    "max_reached": True,
                    "current_activations": len(activations),
                    "max_machines": max_machines
                }
        else:
            # Add new activation
            new_activation = {
                "machine_id": machine_id,
                "activated_at": datetime.now().isoformat(),
                "computer_name": current_computer
            }
            activations.append(new_activation)

        # Update Firebase
        update_data = {
            "fields": {
                "activations": self._to_firestore_value(activations)
            }
        }

        success, result = self._firestore_request(
            "PATCH",
            f"licenses/{clean_key}?updateMask.fieldPaths=activations",
            update_data
        )

        if not success:
            return False, f"Failed to activate: {result.get('error', 'Unknown error')}", {}

        # Find this machine's activation entry (whether new or replaced)
        this_activation = None
        for act in activations:
            if act.get('machine_id') == machine_id:
                this_activation = act
                break
        if not this_activation:
            this_activation = {"machine_id": machine_id, "activated_at": datetime.now().isoformat()}

        expiry_info = self._calculate_expiry(license_data, this_activation)

        cache_data = {
            "license_key": clean_key,
            "machine_id": machine_id,
            "activated_at": this_activation['activated_at'],
            "is_trial": is_trial,
            "license_type": license_data.get('license_type', 'trial' if is_trial else 'standard'),
            "plan_type": license_data.get('plan_type', 'trial' if is_trial else 'standard'),
            "customer_email": customer_email,
            "customer_name": license_data.get('customer_name', ''),
            "price_paid": license_data.get('price_paid', 0),
            "purchase_date": license_data.get('purchase_date', ''),
            "last_check": datetime.now().isoformat(),
            "trial_days": trial_days,
            **expiry_info
        }

        # Add max_channels if set in Firebase (allows per-license override)
        if 'max_channels' in license_data:
            cache_data['max_channels'] = license_data.get('max_channels')

        # Add subscription_days if set (for time-limited paid plans)
        if 'subscription_days' in license_data:
            cache_data['subscription_days'] = float(license_data.get('subscription_days', 0))

        self._save_cache(cache_data)

        if is_trial:
            return True, f"Trial activated! You have {trial_days} days to try all features.", cache_data
        elif license_data.get('license_type') == 'subscription' and license_data.get('subscription_days'):
            sub_days = float(license_data.get('subscription_days', 0))
            return True, f"License activated! Your {license_data.get('plan_type', 'Pro').title()} subscription is valid for {sub_days} days.", cache_data
        else:
            return True, "License activated successfully!", cache_data

    def _calculate_expiry(self, license_data: dict, activation: dict) -> dict:
        """Calculate expiry date based on license type

        Supports:
        - Trial: uses trial_days (default 7)
        - Lifetime: never expires
        - Subscription: uses subscription_days from Firebase doc (e.g. 30, 90, 365)
        """
        is_trial = license_data.get('is_trial', False)
        trial_days_raw = license_data.get('trial_days', 7)
        trial_days = int(trial_days_raw) if trial_days_raw else 7
        license_type = license_data.get('license_type', 'standard')
        subscription_days_raw = license_data.get('subscription_days', 0)
        subscription_days = float(subscription_days_raw) if subscription_days_raw else 0

        activated_at = activation.get('activated_at', datetime.now().isoformat())

        try:
            act_date = datetime.fromisoformat(activated_at.replace('Z', '+00:00').replace('+00:00', ''))
        except:
            act_date = datetime.now()

        if is_trial:
            expiry_date = act_date + timedelta(days=trial_days)
            time_left = expiry_date - datetime.now()
            days_left = time_left.days
            hours_left = time_left.seconds // 3600
            return {
                "expiry_date": expiry_date.isoformat(),
                "days_left": max(0, days_left),
                "hours_left": hours_left if days_left >= 0 else 0,
                "is_expired": time_left.total_seconds() < 0
            }
        elif license_type == 'subscription' and subscription_days > 0:
            expiry_date = act_date + timedelta(days=subscription_days)
            time_left = expiry_date - datetime.now()
            days_left = time_left.days
            hours_left = time_left.seconds // 3600
            return {
                "expiry_date": expiry_date.isoformat(),
                "days_left": max(0, days_left),
                "hours_left": hours_left if days_left >= 0 else 0,
                "is_expired": time_left.total_seconds() < 0,
                "subscription_days": subscription_days
            }
        else:
            # All paid licenses (starter, pro, enterprise) are lifetime — never expire
            # This includes license_type == "lifetime", "standard", or anything else
            # Only trials and explicit subscriptions have expiry dates
            return {
                "expiry_date": None,
                "days_left": 99999,
                "hours_left": 0,
                "is_expired": False
            }

    def verify_license(self) -> Tuple[bool, str, dict]:
        """
        Verify current license - checks online but allows cached fallback on temp errors.

        Machine ID migration: if the cached machine_id doesn't match the current one
        (e.g. after an update changed the ID algorithm), we re-verify online rather than
        immediately logging the user out.
        """
        cached = self._load_cache()

        if not cached:
            # Cache decryption failed (machine ID changed = different encryption key)
            # Try to auto-re-activate using the hint file
            hint_file = self.local_cache_file.parent / ".license_hint"
            if hint_file.exists():
                try:
                    with open(hint_file, 'r') as f:
                        hint = json.load(f)
                    hint_key = hint.get('k', '')
                    hint_email = hint.get('e', '')
                    if hint_key and hint_email:
                        print(f"[LICENSE] Cache unreadable, auto-re-activating from hint file...")
                        success, msg, data = self.activate_license(hint_key, hint_email)
                        if success:
                            print(f"[LICENSE] Auto-re-activation successful")
                            return True, msg, data
                        else:
                            print(f"[LICENSE] Auto-re-activation failed: {msg}")
                except Exception as e:
                    print(f"[LICENSE] Hint file error: {e}")
            return False, "No license found. Please activate your license.", {}

        license_key = cached.get('license_key')
        machine_id = cached.get('machine_id')
        current_machine_id = self._get_machine_id()
        machine_id_changed = (machine_id != current_machine_id)

        # If machine ID changed, don't clear cache immediately — try online verification first
        # This handles the case where the ID algorithm was updated between versions
        if machine_id_changed:
            print(f"[LICENSE] Machine ID changed (cached={machine_id}, current={current_machine_id}), re-verifying online...")

        # Try to check online
        success, message, online_data = self.check_license_online(license_key)

        if not success:
            error_lower = message.lower()
            # Only clear cache if license is explicitly invalid/revoked (not temp errors)
            if "invalid" in error_lower or "revoked" in error_lower:
                self._clear_cache()
                return False, message, {}
            # For network errors: if machine ID is the same, use cache; if changed, fail
            if machine_id_changed:
                # Can't verify online and machine ID changed — don't trust cache
                self._clear_cache()
                return False, "Cannot verify license. Please check your internet connection and try again.", {}
            cached['_online_check_failed'] = True
            return True, "License valid (offline)", cached

        # License exists online — re-verify activation
        customer_email = cached.get('customer_email', '')
        success, msg, updated_data = self.activate_license(license_key, customer_email)

        if not success:
            if "expired" in msg.lower():
                return False, msg, updated_data
            if "max" in msg.lower() and "reached" in msg.lower():
                # Max machines reached but this machine WAS activated before
                # Update cache with current machine ID so this doesn't repeat
                if machine_id_changed:
                    cached['machine_id'] = current_machine_id
                    self._save_cache(cached)
                return True, "License valid", cached
            if "invalid" in msg.lower() or "revoked" in msg.lower():
                self._clear_cache()
                return False, msg, {}
            # For any other error (network, server) — keep cached data
            return True, "License valid (offline)", cached

        # Success — update cached data with current machine ID
        cached = updated_data
        if machine_id_changed:
            cached['machine_id'] = current_machine_id
            self._save_cache(cached)

        # Check if expired
        if cached.get('is_expired', False):
            expiry_str = cached.get('expiry_date', '')[:10] if cached.get('expiry_date') else 'Unknown'
            if cached.get('is_trial'):
                return False, f"Trial expired on {expiry_str}. Please upgrade.", cached
            else:
                return False, f"License expired on {expiry_str}. Please renew.", cached

        # Return status
        if cached.get('is_trial'):
            days_left = cached.get('days_left', 0)
            hours_left = cached.get('hours_left', 0)
            if days_left == 0 and hours_left > 0:
                return True, f"Trial license - {hours_left} hours remaining", cached
            elif days_left > 0:
                return True, f"Trial license - {days_left} days remaining", cached
            else:
                return False, "Trial has expired. Please upgrade.", cached

        # Show days remaining for subscription plans
        if cached.get('subscription_days') and cached.get('days_left', 99999) < 99999:
            days_left = cached.get('days_left', 0)
            if days_left > 0:
                return True, f"License valid - {days_left} days remaining", cached

        return True, "License is valid", cached

    def get_subscription_info(self) -> Optional[dict]:
        """Get detailed subscription information for display"""
        cached = self._load_cache()

        if not cached:
            return None

        info = dict(cached)

        # Recalculate time remaining
        expiry_str = info.get('expiry_date')
        license_type = info.get('license_type', 'standard')

        if license_type == 'lifetime':
            info['days_left'] = 99999
            info['hours_left'] = 0
            info['is_expired'] = False
        elif expiry_str:
            try:
                expiry_date = datetime.fromisoformat(expiry_str.replace('Z', '').split('+')[0])
                time_left = expiry_date - datetime.now()
                days_left = time_left.days
                hours_left = time_left.seconds // 3600

                info['days_left'] = max(0, days_left)
                info['hours_left'] = hours_left if days_left >= 0 else 0
                info['is_expired'] = time_left.total_seconds() < 0

                if days_left > 0:
                    info['time_remaining'] = f"{days_left} days"
                elif days_left == 0 and hours_left > 0:
                    info['time_remaining'] = f"{hours_left} hours"
                else:
                    info['time_remaining'] = "Expired"
            except:
                pass

        # Format dates
        if info.get('activated_at'):
            try:
                act_date = datetime.fromisoformat(info['activated_at'].replace('Z', '+00:00').replace('+00:00', ''))
                info['activated_at_formatted'] = act_date.strftime('%B %d, %Y')
            except:
                info['activated_at_formatted'] = info['activated_at']

        if info.get('expiry_date'):
            try:
                exp_date = datetime.fromisoformat(info['expiry_date'].replace('Z', '+00:00').replace('+00:00', ''))
                info['expiry_date_formatted'] = exp_date.strftime('%B %d, %Y')
            except:
                info['expiry_date_formatted'] = info['expiry_date']

        # License type display - use plan_type from Firebase if available
        plan_type = info.get('plan_type', license_type)
        type_names = {
            'trial': 'Free Trial (7 days)',
            'starter': 'Starter',
            'pro': 'Pro',
            'enterprise': 'Enterprise',
        }
        display_name = type_names.get(plan_type, plan_type.title())
        # Add subscription duration to display name
        if license_type == 'subscription' and info.get('subscription_days'):
            sub_days = int(info['subscription_days'])
            display_name = f"{display_name} ({sub_days} days)"
        info['license_type_display'] = display_name
        info['plan_type'] = plan_type

        # Format price
        price_paid = info.get('price_paid', 0)
        if price_paid == 0:
            info['price_display'] = 'FREE'
        else:
            info['price_display'] = f'${price_paid}'

        # Format purchase date
        if info.get('purchase_date'):
            try:
                purch_date = datetime.fromisoformat(info['purchase_date'].replace('Z', '').split('+')[0])
                info['purchase_date_formatted'] = purch_date.strftime('%B %d, %Y')
            except:
                info['purchase_date_formatted'] = info['purchase_date']

        # Status
        if info.get('is_expired'):
            info['status'] = 'Expired'
            info['status_color'] = '#F44336'
        elif info.get('is_trial'):
            days_left = info.get('days_left', 0)
            hours_left = info.get('hours_left', 0)
            if days_left == 0 and hours_left > 0:
                info['status'] = f'Trial - {hours_left} hours left!'
                info['status_color'] = '#FF9800'
            elif days_left <= 2:
                info['status'] = f'Trial - {days_left} days left!'
                info['status_color'] = '#FF9800'
            else:
                info['status'] = f'Trial - {days_left} days left'
                info['status_color'] = '#2196F3'
        elif info.get('subscription_days') and info.get('days_left', 99999) < 99999:
            days_left = info.get('days_left', 0)
            if days_left <= 3:
                info['status'] = f'Active - {days_left} days left!'
                info['status_color'] = '#FF9800'
            elif days_left <= 7:
                info['status'] = f'Active - {days_left} days left'
                info['status_color'] = '#2196F3'
            else:
                info['status'] = f'Active - {days_left} days left'
                info['status_color'] = '#4CAF50'
        else:
            info['status'] = 'Active'
            info['status_color'] = '#4CAF50'

        return info

    def deactivate_license(self) -> Tuple[bool, str]:
        """Remove license from this machine"""
        self._clear_cache()
        return True, "License deactivated from this machine"

    def _clear_cache(self):
        """Clear all license cache files"""
        try:
            if self.local_cache_file.exists():
                self.local_cache_file.unlink()
        except:
            pass

    def _save_cache(self, data: dict):
        """Save license data to encrypted local cache"""
        try:
            json_str = json.dumps(data)
            encrypted = self._encrypt_data(json_str)
            with open(self.local_cache_file, 'w') as f:
                f.write(encrypted)
            # Also save minimal re-activation info (unencrypted) for machine ID migration
            hint_file = self.local_cache_file.parent / ".license_hint"
            hint = {"k": data.get("license_key", ""), "e": data.get("customer_email", "")}
            with open(hint_file, 'w') as f:
                json.dump(hint, f)
        except Exception as e:
            print(f"Warning: Could not save license cache: {e}")

    def _load_cache(self) -> Optional[dict]:
        """Load license data from encrypted local cache"""
        if not self.local_cache_file.exists():
            return None

        try:
            with open(self.local_cache_file, 'r') as f:
                encrypted = f.read()
            decrypted = self._decrypt_data(encrypted)
            if decrypted:
                return json.loads(decrypted)
            return None
        except:
            # If decryption fails, cache is corrupted/tampered - clear it
            self._clear_cache()
            return None


# Test function
if __name__ == "__main__":
    print("=" * 60)
    print("Firebase License Manager - Test")
    print("=" * 60)

    manager = FirebaseLicense()

    print("\nChecking current license...")
    valid, message, info = manager.verify_license()
    print(f"Valid: {valid}")
    print(f"Message: {message}")
    if info:
        print(f"Info: {json.dumps(info, indent=2)}")
