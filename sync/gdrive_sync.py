import os
import json
import time
import base64
import urllib.request
import urllib.parse
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from sync.base_sync import CloudSyncProvider

class GDriveProvider(CloudSyncProvider):
    def __init__(self, credentials_json="", folder_id=""):
        self.credentials_json = credentials_json
        self.folder_id = folder_id
        self._access_token = None
        self._token_expiry = 0

    def _get_access_token(self):
        """
        Obtains a Google OAuth2 access token using the Service Account JSON key.
        Uses pure-python cryptography (RSA RS256) and standard urllib.
        """
        now = int(time.time())
        if self._access_token and now < self._token_expiry - 60:
            return self._access_token

        if not self.credentials_json or not os.path.exists(self.credentials_json):
            raise FileNotFoundError("Google Drive Service Account JSON key file not found or not configured.")

        with open(self.credentials_json, 'r', encoding='utf-8') as f:
            sa_data = json.load(f)

        client_email = sa_data.get("client_email")
        private_key_pem = sa_data.get("private_key")
        token_uri = sa_data.get("token_uri", "https://oauth2.googleapis.com/token")

        if not client_email or not private_key_pem:
            raise ValueError("Invalid Service Account JSON key: Missing client_email or private_key.")

        # 1. Build JWT Header and Claim Set
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {
            "iss": client_email,
            "scope": "https://www.googleapis.com/auth/drive",
            "aud": token_uri,
            "exp": now + 3600,
            "iat": now
        }

        def b64url(b_data):
            return base64.urlsafe_b64encode(b_data).decode('utf-8').rstrip('=')

        header_b64 = b64url(json.dumps(header).encode('utf-8'))
        payload_b64 = b64url(json.dumps(payload).encode('utf-8'))
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')

        # 2. Sign JWT using Service Account Private Key
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None
        )

        signature = private_key.sign(
            signing_input,
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        jwt_assertion = f"{header_b64}.{payload_b64}.{b64url(signature)}"

        # 3. Exchange JWT for Access Token
        post_data = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt_assertion
        }).encode('utf-8')

        req = urllib.request.Request(token_uri, data=post_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            token_resp = json.loads(resp.read().decode('utf-8'))
            self._access_token = token_resp["access_token"]
            self._token_expiry = now + token_resp.get("expires_in", 3600)
            return self._access_token

    def test_connection(self) -> tuple[bool, str]:
        try:
            token = self._get_access_token()
            req = urllib.request.Request(
                "https://www.googleapis.com/drive/v3/about?fields=user",
                headers={"Authorization": f"Bearer {token}"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                user_email = data.get("user", {}).get("emailAddress", "Authenticated")
                return True, f"Google Drive connected successfully (Service Account: {user_email})."
        except Exception as e:
            return False, f"Google Drive connection failed: {e}"

    def list_files(self) -> list[str]:
        try:
            token = self._get_access_token()
            query = "trashed=false"
            if self.folder_id:
                query += f" and '{self.folder_id}' in parents"

            url = f"https://www.googleapis.com/drive/v3/files?q={urllib.parse.quote(query)}&fields=files(id,name)"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return [f["name"] for f in data.get("files", [])]
        except Exception as e:
            print(f"[GDriveProvider] list_files error: {e}")
            return []

    def upload_file(self, local_path: str, remote_name: str) -> bool:
        if not os.path.exists(local_path):
            return False
        try:
            token = self._get_access_token()
            metadata = {"name": remote_name}
            if self.folder_id:
                metadata["parents"] = [self.folder_id]

            boundary = "-------314159265358979323846"
            delimiter = f"\r\n--{boundary}\r\n"
            close_delim = f"\r\n--{boundary}--\r\n"

            with open(local_path, "rb") as f:
                file_bytes = f.read()

            body = (
                delimiter +
                "Content-Type: application/json; charset=UTF-8\r\n\r\n" +
                json.dumps(metadata) +
                delimiter +
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode('utf-8') + file_bytes + close_delim.encode('utf-8')

            url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": f"multipart/related; boundary={boundary}"
                }
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status in (200, 201)
        except Exception as e:
            print(f"[GDriveProvider] upload error: {e}")
            return False

    def download_file(self, remote_name: str, local_path: str) -> bool:
        try:
            token = self._get_access_token()
            query = f"name='{remote_name}' and trashed=false"
            if self.folder_id:
                query += f" and '{self.folder_id}' in parents"

            url = f"https://www.googleapis.com/drive/v3/files?q={urllib.parse.quote(query)}&fields=files(id,name)"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                files = data.get("files", [])
                if not files:
                    raise FileNotFoundError(f"Remote file '{remote_name}' not found on Google Drive.")
                file_id = files[0]["id"]

            download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
            d_req = urllib.request.Request(download_url, headers={"Authorization": f"Bearer {token}"})
            os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
            with urllib.request.urlopen(d_req, timeout=60) as d_resp, open(local_path, "wb") as f_out:
                f_out.write(d_resp.read())
            return True
        except Exception as e:
            print(f"[GDriveProvider] download error: {e}")
            return False
