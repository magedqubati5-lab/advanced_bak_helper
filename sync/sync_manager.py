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

    def has_valid_credentials(self) -> tuple[bool, str]:
        """
        Checks if sufficient configuration and credentials are set to perform cloud sync.
        Returns (True, ProviderDescription) if ready, or (False, MissingReason).
        """
        password = self.config.get("encryption_password", "").strip()
        if not password:
            return False, "Encryption password is not set in Settings"

        provider_type = self.config.get("cloud_provider", "local_folder").lower()

        if provider_type in ("local_folder", "gdrive_desktop", "onedrive", "dropbox"):
            folder = self.config.get("local_sync_folder_path", "").strip()
            if not folder:
                return False, "Local / Drive sync folder path is not configured"
            return True, f"Local / Drive Sync Folder ({folder})"

        elif provider_type == "ftp":
            host = self.config.get("ftp_host", "").strip()
            user = self.config.get("ftp_user", "").strip()
            if not host:
                return False, "FTP Host is not configured"
            return True, f"FTP Server ({host})"

        elif provider_type in ("gdrive", "gdrive_api"):
            creds_json = self.config.get("gdrive_credentials_json", "").strip()
            if not creds_json:
                return False, "Google Drive Service Account JSON key is not set"
            if not os.path.exists(creds_json):
                return False, f"Google Drive credentials file not found: {creds_json}"
            return True, "Google Drive API"

        return False, f"Unsupported provider: {provider_type}"

    def get_provider(self):
        provider_type = self.config.get("cloud_provider", "local_folder").lower()
        if provider_type == "ftp":
            return FTPProvider(
                host=self.config.get("ftp_host"),
                port=self.config.get("ftp_port", 21),
                user=self.config.get("ftp_user"),
                passwd=self.config.get("ftp_pass"),
                remote_dir=self.config.get("ftp_remote_dir")
            )
        elif provider_type in ("gdrive", "gdrive_api"):
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

    def upload_encrypted_and_signed(self, local_file_path, remote_rel_name=None, log_callback=None):
        """
        Encrypts a local file with AES-256, signs it with RSA private key, and uploads both to cloud.
        Preserves relative folder structure (including .ref/ files).
        """
        password = self.config.get("encryption_password")
        priv_key = self.config.get("rsa_private_key_path")
        pub_key = self.config.get("rsa_public_key_path")

        if not password:
            raise ValueError("Please set the encryption password in Settings first.")

        CryptoEngine.generate_rsa_keypair(priv_key, pub_key)
        provider = self.get_provider()
        
        rel_name = remote_rel_name if remote_rel_name else os.path.basename(local_file_path)
        rel_name = rel_name.replace('\\', '/')
        display_name = rel_name

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_enc_path = os.path.join(tmp_dir, "payload.enc")
            tmp_sig_path = os.path.join(tmp_dir, "payload.enc.sig")

            if log_callback:
                log_callback(f"Encrypting file with AES-256: {display_name}...")
            CryptoEngine.encrypt_file(local_file_path, tmp_enc_path, password)

            if log_callback:
                log_callback(f"Signing encrypted file with RSA private key...")
            CryptoEngine.sign_file(tmp_enc_path, priv_key, tmp_sig_path)

            remote_enc_name = f"{rel_name}.enc"
            remote_sig_name = f"{rel_name}.enc.sig"

            if log_callback:
                log_callback(f"Uploading {display_name} (encrypted + signature) to cloud / sync folder...")
            
            u1 = provider.upload_file(tmp_enc_path, remote_enc_name)
            u2 = provider.upload_file(tmp_sig_path, remote_sig_name)

            if u1 and u2:
                if log_callback:
                    log_callback(f"Upload completed successfully for {display_name}.")
                return True
            else:
                raise RuntimeError(f"Failed to upload encrypted file or signature for {display_name}.")

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
            tmp_enc = os.path.join(tmp_dir, "temp_download.enc")
            tmp_sig = os.path.join(tmp_dir, "temp_download.enc.sig")

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
                    raise PermissionError(f"Operation cancelled due to invalid digital signature on {remote_file_enc}.")

            if log_callback:
                log_callback(f"Decrypting payload -> {dest_local_path}...")
            
            os.makedirs(os.path.dirname(os.path.abspath(dest_local_path)), exist_ok=True)
            CryptoEngine.decrypt_file(tmp_enc, dest_local_path, password)

            if log_callback:
                log_callback(f"Decrypted successfully: {dest_local_path}")
            return True

    def sync_all_upload(self, output_dir, force_overwrite=False, log_callback=None):
        """
        Scans output_dir AND .ref/ directory, encrypts, signs, and uploads all backup files and manifest.
        Skips files that already exist on the remote destination unless force_overwrite is True.
        """
        if not output_dir or not os.path.exists(output_dir):
            raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

        can_sync, reason = self.has_valid_credentials()
        if not can_sync:
            raise ValueError(f"Cannot perform cloud sync: {reason}")

        provider = self.get_provider()

        # 1. Fetch remote files list to skip existing backups
        existing_remote_files = set()
        try:
            raw_list = provider.list_files()
            existing_remote_files = set(f.replace('\\', '/') for f in raw_list)
        except Exception as e:
            if log_callback:
                log_callback(f"Notice: Could not list remote files ({e}). Proceeding...")

        files_to_sync = []
        for root, dirs, files in os.walk(output_dir):
            for f in files:
                if f.endswith(".enc") or f.endswith(".sig"):
                    continue
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, output_dir).replace('\\', '/')
                files_to_sync.append((full_path, rel_path))

        if not files_to_sync:
            if log_callback:
                log_callback("No files or references found in output directory to sync.")
            return 0

        if log_callback:
            log_callback(f"Starting cloud sync upload: {len(files_to_sync)} item(s) to verify (including .ref/ directory)...")

        uploaded_count = 0
        skipped_count = 0

        for full_p, rel_p in files_to_sync:
            rel_name = rel_p.replace('\\', '/')
            remote_enc_name = f"{rel_name}.enc"
            remote_sig_name = f"{rel_name}.enc.sig"

            # Check if file already exists in cloud
            # Immutable backup payloads (.hdiff, .zip) are skipped if already present
            is_immutable = not rel_name.endswith("manifest.json")
            if not force_overwrite and is_immutable:
                if remote_enc_name in existing_remote_files and remote_sig_name in existing_remote_files:
                    skipped_count += 1
                    if log_callback:
                        log_callback(f"Skipping already existing cloud file: {rel_name}")
                    continue

            self.upload_encrypted_and_signed(full_p, remote_rel_name=rel_p, log_callback=log_callback)
            uploaded_count += 1
            existing_remote_files.add(remote_enc_name)
            existing_remote_files.add(remote_sig_name)

        if log_callback:
            log_callback(f"Cloud sync upload finished successfully. Uploaded: {uploaded_count}, Skipped (already in cloud): {skipped_count}.")
        return uploaded_count

    def sync_all_download(self, output_dir, log_callback=None, signature_mismatch_callback=None):
        """
        Discovers all remote encrypted files (.enc), downloads, validates signatures, and restores to output_dir and .ref/.
        """
        provider = self.get_provider()
        remote_files = provider.list_files()
        enc_files = [f for f in remote_files if f.endswith(".enc")]

        if not enc_files:
            if log_callback:
                log_callback("No encrypted files (.enc) found in cloud storage.")
            return 0

        if log_callback:
            log_callback(f"Discovered {len(enc_files)} remote encrypted backup item(s). Starting download and restore...")

        downloaded_count = 0
        for remote_enc in enc_files:
            rel_dest = remote_enc[:-4]  # Remove .enc extension
            dest_full_path = os.path.join(output_dir, rel_dest)
            self.download_verify_and_decrypt(
                remote_file_enc=remote_enc,
                dest_local_path=dest_full_path,
                log_callback=log_callback,
                signature_mismatch_callback=signature_mismatch_callback
            )
            downloaded_count += 1

        if log_callback:
            log_callback(f"Cloud sync download complete! Restored {downloaded_count} item(s) to {output_dir}.")
        return downloaded_count
