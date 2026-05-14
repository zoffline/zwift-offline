#!/usr/bin/env python3

"""
Set COROS credentials for zoffline.
This script encrypts and saves COROS email/password to coros_credentials.bin.
"""

import getpass
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, SCRIPT_DIR)


def set_coros_credentials(player_id):
    """Interactively set COROS credentials for a player."""
    credentials_file = os.path.join(SCRIPT_DIR, "storage", str(player_id), "coros_credentials.bin")

    print("COROS Credentials Setup")
    print("=" * 40)
    print()

    email = input("COROS email: ").strip()
    if not email:
        print("Email cannot be empty")
        return False

    password = getpass.getpass("COROS password: ").strip()
    if not password:
        print("Password cannot be empty")
        return False

    # Confirm password
    password_confirm = getpass.getpass("Confirm password: ").strip()
    if password != password_confirm:
        print("Passwords do not match")
        return False

    try:
        from Crypto.Cipher import AES

        credentials_key_file = os.path.join(SCRIPT_DIR, "storage", "credentials-key.bin")
        if not os.path.exists(credentials_key_file):
            print("Error: credentials-key.bin not found. Run zoffline at least once.")
            return False

        with open(credentials_key_file, 'rb') as f:
            credentials_key = f.read()

        cipher_suite = AES.new(credentials_key, AES.MODE_CFB)
        with open(credentials_file, 'wb') as f:
            f.write(cipher_suite.iv)
            f.write(cipher_suite.encrypt((email + '\n' + password).encode('UTF-8')))

        print()
        print(f"Credentials saved to: {credentials_file}")
        return True

    except Exception as e:
        print(f"Error saving credentials: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Set COROS credentials for zoffline')
    parser.add_argument('player_id', type=int, help='Player ID')
    args = parser.parse_args()

    success = set_coros_credentials(args.player_id)
    sys.exit(0 if success else 1)