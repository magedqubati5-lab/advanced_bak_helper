import os
import ftplib
from sync.base_sync import CloudSyncProvider

class FTPProvider(CloudSyncProvider):
    def __init__(self, host, port, user, passwd, remote_dir="/backups"):
        self.host = host
        self.port = int(port) if port else 21
        self.user = user
        self.passwd = passwd
        self.remote_dir = remote_dir or "/backups"

    def _connect(self):
        ftp = ftplib.FTP()
        ftp.connect(self.host, self.port, timeout=15)
        if self.user:
            ftp.login(self.user, self.passwd)
        else:
            ftp.login()
        
        try:
            ftp.cwd(self.remote_dir)
        except ftplib.error_perm:
            dirs = [d for d in self.remote_dir.split('/') if d]
            current = ""
            for d in dirs:
                current += "/" + d
                try:
                    ftp.cwd(current)
                except ftplib.error_perm:
                    ftp.mkd(current)
                    ftp.cwd(current)
        return ftp

    def test_connection(self) -> tuple[bool, str]:
        try:
            ftp = self._connect()
            ftp.quit()
            return True, "FTP connection established successfully."
        except Exception as e:
            return False, f"FTP connection failed: {e}"

    def upload_file(self, local_path: str, remote_name: str) -> bool:
        if not os.path.exists(local_path):
            return False
        try:
            ftp = self._connect()
            with open(local_path, 'rb') as f:
                ftp.storbinary(f'STOR {remote_name}', f)
            ftp.quit()
            return True
        except Exception as e:
            print(f"FTP upload error: {e}")
            return False

    def download_file(self, remote_name: str, local_path: str) -> bool:
        try:
            ftp = self._connect()
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as f:
                ftp.retrbinary(f'RETR {remote_name}', f.write)
            ftp.quit()
            return True
        except Exception as e:
            print(f"FTP download error: {e}")
            return False

    def list_files(self) -> list[str]:
        try:
            ftp = self._connect()
            files = []
            ftp.retrlines('NLST', files.append)
            ftp.quit()
            return files
        except Exception as e:
            print(f"FTP list error: {e}")
            return []
