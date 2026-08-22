from abc import ABC, abstractmethod

class CloudSyncProvider(ABC):
    """
    Abstract Base Class for modular cloud storage providers (FTP, Google Drive, Amazon S3, etc.)
    """

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Tests provider connection. Returns (success, message)."""
        pass

    @abstractmethod
    def upload_file(self, local_path: str, remote_name: str) -> bool:
        """Uploads a local file to cloud storage."""
        pass

    @abstractmethod
    def download_file(self, remote_name: str, local_path: str) -> bool:
        """Downloads a remote file from cloud storage to local path."""
        pass

    @abstractmethod
    def list_files(self) -> list[str]:
        """Returns list of remote file names."""
        pass
