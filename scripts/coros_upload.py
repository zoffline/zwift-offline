#!/usr/bin/env python3

"""
COROS activity upload script for zoffline.
This script is called by activity_uploads() in zwift_offline.py after an activity is saved.
"""

import logging
import os
import sys

logger = logging.getLogger('zoffline')


def coros_upload(player_id, activity):
    """
    Upload activity to COROS.

    Args:
        player_id: int - player's ID
        activity: activity_pb2.Activity - the activity to upload

    Returns:
        bool - True if upload succeeded or was skipped, False on error
    """
    credentials_file = 'storage/%s/coros_credentials.bin' % player_id

    if not os.path.exists(credentials_file):
        logger.debug("COROS credentials not found, skipping upload")
        return True

    try:
        email, password = decrypt_credentials(credentials_file)
        if not email or not password:
            logger.warning("COROS credentials file exists but is empty")
            return True

        from scripts.coros_client import CorosClient, CorosError, CorosLoginError

        client = CorosClient(email, password)
        client.login()

        fit_data = activity.fit
        file_name = activity.fit_filename or "activity.fit"

        success = client.upload_fit_file(fit_data, file_name)

        if success:
            logger.info("COROS upload succeeded for player %s activity %s", player_id, activity.id)
        else:
            logger.warning("COROS upload returned failure for player %s activity %s", player_id, activity.id)

        return success

    except CorosLoginError as e:
        logger.warning("COROS login failed for player %s: %s", player_id, e)
        return True
    except CorosError as e:
        logger.warning("COROS upload failed for player %s: %s", player_id, e)
        return False
    except Exception as e:
        logger.warning("COROS upload error for player %s: %s", player_id, e)
        return False


def decrypt_credentials(file):
    """Decrypt credentials from AES encrypted file. Uses credentials_key from zwift_offline module."""
    cred = ('', '')
    if os.path.isfile(file):
        try:
            from zwift_offline import credentials_key
            with open(file, 'rb') as f:
                from Crypto.Cipher import AES
                cipher_suite = AES.new(credentials_key, AES.MODE_CFB, iv=f.read(16))
                lines = cipher_suite.decrypt(f.read()).decode('UTF-8').splitlines()
                cred = (lines[0], lines[1])
        except Exception as e:
            logger.warning("Failed to decrypt COROS credentials: %s", e)
    return cred