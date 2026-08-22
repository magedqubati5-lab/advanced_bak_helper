import hashlib
import os

def calculate_md5(file_path, chunk_size=65536, progress_callback=None):
    """
    Calculates MD5 checksum for a file using chunked reading to handle large .bak files cleanly.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found for MD5 calculation: {file_path}")
    
    md5_hash = hashlib.md5()
    total_size = os.path.getsize(file_path)
    processed = 0

    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            md5_hash.update(chunk)
            processed += len(chunk)
            if progress_callback and total_size > 0:
                progress_callback(processed / total_size)

    return md5_hash.hexdigest().lower()

def verify_md5(file_path, expected_md5):
    """
    Verifies that the file matches the expected MD5 string.
    """
    if not expected_md5:
        return False
    actual_md5 = calculate_md5(file_path)
    return actual_md5.strip().lower() == expected_md5.strip().lower()
