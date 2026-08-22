import os
import shutil
from sync.base_sync import CloudSyncProvider

class LocalFolderSyncProvider(CloudSyncProvider):
    """
    Provider for syncing with Google Drive for Desktop (G:\\My Drive),
    OneDrive, Dropbox, or any Network Share/External Drive.
    Requires ZERO API keys or cloud console setup!
    """
    def __init__(self, target_folder_path=""):
        self.target_folder_path = target_folder_path

    def test_connection(self) -> tuple[bool, str]:
        if not self.target_folder_path:
            return False, "Target sync folder path is not set."
        if not os.path.exists(self.target_folder_path):
            try:
                os.makedirs(self.target_folder_path, exist_ok=True)
                return True, f"Folder created and accessible: {self.target_folder_path}"
            except Exception as e:
                return False, f"Cannot access target folder: {e}"
        if not os.access(self.target_folder_path, os.W_OK):
            return False, f"Folder is not writable: {self.target_folder_path}"
        return True, f"Target folder is ready and writable: {self.target_folder_path}"

    def upload_file(self, local_path: str, remote_name: str) -> bool:
        if not os.path.exists(local_path):
            return False
        try:
            os.makedirs(self.target_folder_path, exist_ok=True)
            dest_path = os.path.join(self.target_folder_path, remote_name)
            shutil.copy2(local_path, dest_path)
            return True
        except Exception as e:
            print(f"[LocalFolderSyncProvider] upload error: {e}")
            return False

    def download_file(self, remote_name: str, local_path: str) -> bool:
        try:
            src_path = os.path.join(self.target_folder_path, remote_name)
            if not os.path.exists(src_path):
                return False
            os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
            shutil.copy2(src_path, local_path)
            return True
        except Exception as e:
            print(f"[LocalFolderSyncProvider] download error: {e}")
            return False

    def list_files(self) -> list[str]:
        if not self.target_folder_path or not os.path.exists(self.target_folder_path):
            return []
        try:
            return [f for f in os.listdir(self.target_folder_path) if os.path.isfile(os.path.join(self.target_folder_path, f))]
        except Exception as e:
            print(f"[LocalFolderSyncProvider] list error: {e}")
            return []
