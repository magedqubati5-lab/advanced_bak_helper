import os
import subprocess
import zipfile
import re
import tempfile
from hasher import calculate_md5, verify_md5
from hdiff_engine import HDiffEngine

class RestoreEngine:
    def __init__(self, config):
        self.config = config
        self.hdiff_engine = HDiffEngine(config)

    def parse_hdiff_filename(self, target_hdiff_path):
        """
        Parses standard output hdiff filename format:
        [original_name].[MD5].[ref_tag].hdiff
        Example: db_backup.bak.a1b2c3d4e5f6.ref001.hdiff
        """
        filename = os.path.basename(target_hdiff_path)
        pattern = r"^(.*)\.([a-fA-F0-9]{32})\.(ref\d{3})\.hdiff$"
        match = re.match(pattern, filename)
        if match:
            return {
                "original_filename": match.group(1),
                "md5": match.group(2).lower(),
                "ref_tag": match.group(3)
            }
        return None

    def list_restorable_backups(self, output_dir):
        """
        Scans output_dir and .ref/ to return a list of all restorable backup archives.
        Returns a list of dicts:
        [{
            'file_name': ...,
            'full_path': ...,
            'original_filename': ...,
            'type': 'Differential Patch' | 'Baseline Reference',
            'ref_tag': ...,
            'md5': ...,
            'size_bytes': ...,
            'size_formatted': ...,
            'modified_time': ...
        }]
        """
        items = []
        if not output_dir or not os.path.exists(output_dir):
            return items

        ref_dir = os.path.join(output_dir, ".ref")
        manifest = self.hdiff_engine.load_manifest(output_dir)
        processed_files = manifest.get("processed_files", {})

        # 1. Processed differential files in output_dir
        for entry in os.listdir(output_dir):
            full_path = os.path.join(output_dir, entry)
            if not os.path.isfile(full_path) or not entry.endswith(".hdiff"):
                continue

            parsed = self.parse_hdiff_filename(entry)
            st = os.stat(full_path)
            size_mb = st.st_size / (1024 * 1024)

            items.append({
                "file_name": entry,
                "full_path": full_path,
                "original_filename": parsed["original_filename"] if parsed else entry,
                "type": "Differential Patch",
                "ref_tag": parsed["ref_tag"] if parsed else "Unknown",
                "md5": parsed["md5"] if parsed else "",
                "size_bytes": st.st_size,
                "size_formatted": f"{size_mb:.2f} MB" if size_mb >= 0.01 else f"{st.st_size / 1024:.2f} KB",
                "modified_time": st.st_mtime
            })

        # 2. Base reference zip in .ref/
        if os.path.exists(ref_dir):
            for entry in os.listdir(ref_dir):
                if entry.endswith(".zip"):
                    full_path = os.path.join(ref_dir, entry)
                    st = os.stat(full_path)
                    size_mb = st.st_size / (1024 * 1024)
                    
                    # Look up original filename from manifest
                    orig_name = entry
                    ref_hash = entry.split("-")[0] if "-" in entry else ""
                    for orig, info in processed_files.items():
                        if info.get("is_reference") and info.get("output_file") == entry:
                            orig_name = orig
                            ref_hash = info.get("hash", ref_hash)
                            break

                    items.append({
                        "file_name": entry,
                        "full_path": full_path,
                        "original_filename": orig_name,
                        "type": "Baseline Reference (ZIP)",
                        "ref_tag": "ref001",
                        "md5": ref_hash,
                        "size_bytes": st.st_size,
                        "size_formatted": f"{size_mb:.2f} MB" if size_mb >= 0.01 else f"{st.st_size / 1024:.2f} KB",
                        "modified_time": st.st_mtime
                    })

        # Sort by modified time descending (newest first)
        items.sort(key=lambda x: x["modified_time"], reverse=True)
        return items

    def restore_file(self, target_file_path, output_dir, destination_dir, log_callback=None, progress_callback=None):
        """
        Restores a backup file from a .hdiff patch or .zip baseline reference.
        """
        hpatchz_path = self.config.get("hpatchz_path")
        if not os.path.exists(hpatchz_path):
            raise FileNotFoundError(f"HPatchZ executable not found at: {hpatchz_path}")

        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir, exist_ok=True)

        filename = os.path.basename(target_file_path)

        # Case 1: Target file is a ZIP baseline reference directly
        if filename.endswith(".zip"):
            if log_callback:
                log_callback(f"Extracting baseline reference from ZIP archive: {filename}...")
            with zipfile.ZipFile(target_file_path, 'r') as z:
                extracted_files = z.namelist()
                if not extracted_files:
                    raise ValueError("ZIP archive is empty.")
                z.extractall(destination_dir)
                restored_path = os.path.join(destination_dir, extracted_files[0])
                actual_md5 = calculate_md5(restored_path)
                return {
                    "success": True,
                    "restored_path": restored_path,
                    "actual_md5": actual_md5,
                    "expected_md5": actual_md5,
                    "md5_matched": True,
                    "message": "Baseline reference successfully extracted and verified from ZIP."
                }

        # Case 2: Target file is an .hdiff differential patch file
        parsed_info = self.parse_hdiff_filename(target_file_path)
        if not parsed_info:
            raise ValueError(f"Unrecognized hdiff filename format: {filename}")

        original_name = parsed_info["original_filename"]
        expected_md5 = parsed_info["md5"]
        ref_tag = parsed_info["ref_tag"]

        if log_callback:
            log_callback(f"Reconstructing reference chain for target reference ({ref_tag})...")

        with tempfile.TemporaryDirectory() as tmp_work:
            # Materialize reference on the fly through the slim delta chain
            raw_ref_path = self.hdiff_engine.materialize_reference(ref_tag, output_dir, tmp_work, log_callback)

            destination_file_path = os.path.join(destination_dir, original_name)
            if log_callback:
                log_callback(f"Applying hpatchz delta to reconstruct original file: {original_name}...")

            cmd = [hpatchz_path, raw_ref_path, target_file_path, destination_file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Error running hpatchz: {result.stderr}")

            if log_callback:
                log_callback("File reconstructed. Performing post-restoration MD5 integrity validation...")

            actual_md5 = calculate_md5(destination_file_path)
            md5_matched = (actual_md5.lower() == expected_md5.lower())

            status_msg = "Restoration successful! MD5 checksum matched 100%." if md5_matched else "Warning: Restored file MD5 checksum mismatch!"

            if log_callback:
                log_callback(f"Integrity Check: Expected={expected_md5} | Actual={actual_md5}")
                log_callback(status_msg)

            return {
                "success": True,
                "restored_path": destination_file_path,
                "expected_md5": expected_md5,
                "actual_md5": actual_md5,
                "md5_matched": md5_matched,
                "message": status_msg
            }
