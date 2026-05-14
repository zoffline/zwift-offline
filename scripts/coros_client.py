#!/usr/bin/env python3

"""
COROS API client for zoffline.
Handles login, OSS credential acquisition, S3 upload, and activity registration.
"""

import hashlib
import json
import os
import sys
import urllib3
import certifi
from io import BytesIO

# Import boto3 for S3 uploads
try:
    import boto3
    from boto3.s3.transfer import TransferConfig
except ImportError:
    boto3 = None

urllib3.disable_warnings()


# COROS Region Configuration
REGION_CONFIG = {
    1: {  # International
        'teamapi': 'https://teamapi.coros.com',
        'bucket': 'coros-s3',
        'service': 'aws',
        'oss_endpoint': 'https://s3.eu-central-1.amazonaws.com',
    },
    2: {  # China
        'teamapi': 'https://teamcnapi.coros.com',
        'bucket': 'coros-oss',
        'service': 'aliyun',
        'oss_endpoint': 'https://oss-cn-beijing.aliyuncs.com',
    },
    3: {  # Europe
        'teamapi': 'https://teameuapi.coros.com',
        'bucket': 'eu-coros',
        'service': 'aws',
        'oss_endpoint': 'https://s3.eu-central-1.amazonaws.com',
    },
}


def _decode_sts_credentials(credentials):
    """Decode STS credentials from COROS API response."""
    salt = "9y78gpoERW4lBNYL"
    encoded_cred = credentials.replace(salt, '')
    decoded = base64.b64decode(encoded_cred).decode('utf-8')
    return json.loads(decoded)


class CorosClient:
    """COROS API client."""

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.req = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
        self.access_token = None
        self.user_id = None
        self.region_id = None
        self._teamapi = None
        self._sts_credentials = None

    @property
    def teamapi(self):
        if self._teamapi:
            return self._teamapi
        return REGION_CONFIG[1]['teamapi']

    @teamapi.setter
    def teamapi(self, value):
        self._teamapi = value

    def login(self):
        """Login to COROS with email and MD5(password)."""
        # Use default international teamapi for login first
        login_url = f"{REGION_CONFIG[1]['teamapi']}/account/login"
        login_data = {
            "account": self.email,
            "pwd": hashlib.md5(self.password.encode()).hexdigest(),
            "accountType": 2,
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "referer": REGION_CONFIG[1]['teamapi'],
            "origin": REGION_CONFIG[1]['teamapi'],
        }

        try:
            response = self.req.request(
                'POST',
                login_url,
                body=json.dumps(login_data).encode('utf-8'),
                headers=headers
            )
            login_response = json.loads(response.data)

            if login_response.get("result") != "0000":
                raise CorosLoginError(login_response.get("message", "Unknown login error"))

            self.access_token = login_response["data"]["accessToken"]
            self.user_id = login_response["data"]["userId"]
            self.region_id = login_response["data"]["regionId"]

            # Set region-specific config
            if self.region_id in REGION_CONFIG:
                self.teamapi = REGION_CONFIG[self.region_id]['teamapi']
            else:
                # Default to international
                self.teamapi = REGION_CONFIG[1]['teamapi']
                self.region_id = 1

        except urllib3.exceptions.HTTPError as e:
            raise CorosLoginError(f"Network error during login: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            raise CorosLoginError(f"Invalid response during login: {e}")

    def _get_sts_token(self):
        """Get OSS temporary credentials from COROS."""
        if self.region_id not in REGION_CONFIG:
            raise CorosError(f"Unsupported region: {self.region_id}")

        region_cfg = REGION_CONFIG[self.region_id]
        app_id = "1660188068672619112"
        sign = "877571111A1EE5316E4B590103D4B5B3"

        sts_url = (
            f"https://faq.coros.com/openapi/oss/sts"
            f"?bucket={region_cfg['bucket']}&service={region_cfg['service']}"
            f"&app_id={app_id}&sign={sign}&v=2"
        )

        try:
            response = self.req.request('GET', sts_url)
            sts_response = json.loads(response.data)

            if sts_response.get("code") != 200:
                raise CorosError(f"Failed to get STS token: code={sts_response.get('code')}")

            self._sts_credentials = sts_response["data"]["credentials"]

        except urllib3.exceptions.HTTPError as e:
            raise CorosError(f"Network error getting STS token: {e}")
        except json.JSONDecodeError as e:
            raise CorosError(f"Invalid STS token response: {e}")

    def _get_s3_client(self):
        """Get S3 client using STS credentials."""
        if boto3 is None:
            raise CorosError("boto3 is required for S3 upload. Install with: pip install boto3")

        if self._sts_credentials is None:
            self._get_sts_token()

        region_cfg = REGION_CONFIG[self.region_id]
        cred = _decode_sts_credentials(self._sts_credentials)

        if region_cfg['service'] == 'aws':
            client = boto3.client(
                "s3",
                aws_access_key_id=cred["AccessKeyId"],
                aws_secret_access_key=cred["SecretAccessKey"],
                aws_session_token=cred["SessionToken"],
                endpoint_url=region_cfg['oss_endpoint'],
            )
        else:
            # Aliyun OSS - use endpoint URL
            client = boto3.client(
                "s3",
                aws_access_key_id=cred["AccessKeyId"],
                aws_secret_access_key=cred["SecretAccessKey"],
                aws_session_token=cred.get("SessionToken", ""),
                endpoint_url=region_cfg['oss_endpoint'],
            )

        return client, region_cfg

    def upload_fit_file(self, fit_data, file_name):
        """
        Upload FIT file to COROS OSS and register activity.

        Args:
            fit_data: bytes - FIT file content
            file_name: str - original file name

        Returns:
            bool - True if upload succeeded
        """
        if self.access_token is None:
            raise CorosError("Not logged in. Call login() first.")

        # Step 1: Get STS credentials
        if self._sts_credentials is None:
            self._get_sts_token()

        region_cfg = REGION_CONFIG[self.region_id]

        # Step 2: Calculate MD5 of FIT data
        file_md5 = hashlib.md5(fit_data).hexdigest()

        # Step 3: Upload to S3
        if region_cfg['service'] == 'aws':
            s3_client, _ = self._get_s3_client()
            bucket = region_cfg['bucket']
            s3_key = f"fit/{self.user_id}/{file_md5}.fit"

            config = TransferConfig(
                multipart_threshold=5 * 1024 * 1024,
                max_concurrency=4,
                multipart_chunksize=5 * 1024 * 1024,
                use_threads=True
            )

            try:
                s3_client.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=fit_data,
                )
            except Exception as e:
                raise CorosError(f"S3 upload failed: {e}")

        else:
            raise CorosError(f"Unsupported service: {region_cfg['service']}")

        # Step 4: Register activity with COROS
        size = len(fit_data)
        oss_object = f"fit/{self.user_id}/{file_md5}.fit"

        upload_url = f"{self.teamapi}/activity/fit/import"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "accesstoken": self.access_token,
        }

        data = {
            "source": 1,
            "timezone": 32,
            "bucket": bucket,
            "md5": file_md5,
            "size": size,
            "object": oss_object,
            "serviceName": region_cfg['service'],
            "oriFileName": file_name
        }

        try:
            response = self.req.request(
                method='POST',
                url=upload_url,
                fields={"jsonParameter": json.dumps(data)},
                headers=headers
            )
            upload_response = json.loads(response.data)

            if upload_response.get("result") == "0000":
                status = upload_response.get("data", {}).get("status")
                if status == 2:
                    return True
                raise CorosError(f"Activity registration failed: status={status}")
            else:
                raise CorosError(f"Activity registration failed: {upload_response.get('message')}")

        except urllib3.exceptions.HTTPError as e:
            raise CorosError(f"Network error during activity registration: {e}")


class CorosError(Exception):
    """COROS API error."""
    pass


class CorosLoginError(CorosError):
    """COROS login error."""
    pass


if __name__ == "__main__":
    # Simple test
    import getpass

    email = input("COROS email: ")
    password = getpass.getpass("COROS password: ")

    client = CorosClient(email, password)
    try:
        client.login()
        print(f"Login successful! user_id={client.user_id}, region_id={client.region_id}")
    except CorosLoginError as e:
        print(f"Login failed: {e}")