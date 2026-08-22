import os
import shutil
import tempfile
from sync.ftp_sync import FTPProvider
from sync.gdrive_sync import GDriveProvider
from sync.local_folder_sync import LocalFolderSyncProvider
from crypto_engine import CryptoEngine

class SyncManager:
    def __init__(self, config):
        self.config = config

    def get_provider(self):
        provider_type = self.config.get("cloud_provider", "ftp").lower()
        if provider_type == "ftp":
            return FTPProvider(
                host=self.config.get("ftp_host"),
                port=self.config.get("ftp_port", 21),
                user=self.config.get("ftp_user"),
                passwd=self.config.get("ftp_pass"),
                remote_dir=self.config.get("ftp_remote_dir")
            )
        elif provider_type == "gdrive":
            return GDriveProvider(
                credentials_json=self.config.get("gdrive_credentials_json"),
                folder_id=self.config.get("gdrive_folder_id")
            )
        elif provider_type in ("local_folder", "gdrive_desktop", "onedrive", "dropbox"):
            return LocalFolderSyncProvider(
                target_folder_path=self.config.get("local_sync_folder_path", "")
            )
        else:
            raise ValueError(f"Unsupported cloud sync provider: {provider_type}")

    def upload_encrypted_and_signed(self, local_file_path, log_callback=None):
        """
        Encrypts a local file with AES-256, signs it with RSA private key, and uploads both to cloud.
        """
        password = self.config.get("encryption_password")
        priv_key = self.config.get("rsa_private_key_path")
        pub_key = self.config.get("rsa_public_key_path")

        if not password:
            raise ValueError("Please set the encryption password in Settings first.")

        CryptoEngine.generate_rsa_keypair(priv_key, pub_key)
        provider = self.get_provider()
        filename = os.path.basename(local_file_path)

        with tempfile.TemporaryDirectory() as tmp_dir:
            enc_path = os.path.join(tmp_dir, f"{filename}.enc")
            sig_path = os.path.join(tmp_dir, f"{filename}.enc.sig")

            if log_callback:
                log_callback(f"Encrypting file with AES-256: {filename}...")
            CryptoEngine.encrypt_file(local_file_path, enc_path, password)

            if log_callback:
                log_callback("Signing encrypted file with RSA private key...")
            CryptoEngine.sign_file(enc_path, priv_key, sig_path)

            if log_callback:
                log_callback("Uploading encrypted payload and signature to cloud / sync folder...")
            
            u1 = provider.upload_file(enc_path, f"{filename}.enc")
            u2 = provider.upload_file(sig_path, f"{filename}.enc.sig")

            if u1 and u2:
                if log_callback:
                    log_callback(f"Upload completed successfully for {filename}.")
                return True
            else:
                raise RuntimeError("Failed to upload encrypted file or signature to cloud provider.")

    def download_verify_and_decrypt(self, remote_file_enc, dest_local_path, log_callback=None, signature_mismatch_callback=None):
        """
        Downloads encrypted file and signature, verifies RSA signature, prompts user if invalid, and decrypts.
        """
        password = self.config.get("encryption_password")
        pub_key = self.config.get("rsa_public_key_path")

        if not password:
            raise ValueError("Please set the encryption password in Settings to decrypt files.")

        provider = self.get_provider()
        remote_sig_name = f"{remote_file_enc}.sig"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_enc = os.path.join(tmp_dir, remote_file_enc)
            tmp_sig = os.path.join(tmp_dir, remote_sig_name)

            if log_callback:
                log_callback(f"Downloading encrypted backup and digital signature: {remote_file_enc}...")

            d1 = provider.download_file(remote_file_enc, tmp_enc)
            d2 = provider.download_file(remote_sig_name, tmp_sig)

            if not d1:
                raise RuntimeError(f"Failed to download remote file: {remote_file_enc}")

            sig_valid = False
            if d2 and os.path.exists(pub_key):
                sig_valid = CryptoEngine.verify_signature(tmp_enc, tmp_sig, pub_key)

            if log_callback:
                status_str = "VALID & VERIFIED" if sig_valid else "INVALID / TAMPERED / MISSING"
                log_callback(f"RSA Digital Signature Status: {status_str}")

            if not sig_valid:
                proceed = False
                if signature_mismatch_callback:
                    proceed = signature_mismatch_callback(remote_file_enc)
                if not proceed:
                    raise PermissionError("Operation cancelled due to invalid digital signature.")

            if log_callback:
                log_callback("Decrypting payload using encryption password...")
            
            os.makedirs(os.path.dirname(dest_local_path), exist_ok=True)
            CryptoEngine.decrypt_file(tmp_enc, dest_local_path, password)

            if log_callback:
                log_callback(f"Decryption and download completed successfully -> {dest_local_path}")
            return True
