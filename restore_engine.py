import os
import sys
import subprocess
import zipfile
import re
import tempfile
from hasher import calculate_md5, verify_md5
from hdiff_engine import HDiffEngine

SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

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
                "md5": match.group(2),
                "ref_tag": match.group(3)
            }
        return None

    def list_restorable_backups(self, output_dir):
        """
        Scans output_dir and .ref/ to return structured metadata about all restorable backups.
        Supports sorting and filtering in the UI table.
        """
        if not os.path.exists(output_dir):
            return []

        backups = []
        ref_dir = os.path.join(output_dir, ".ref")
        manifest_path = os.path.join(ref_dir, "manifest.json")
        manifest = {}

        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
            except Exception:
                pass

        processed_map = manifest.get("processed_files", {})

        # 1. Check baseline zip in .ref/
        if os.path.exists(ref_dir):
            for f in os.listdir(ref_dir):
                if f.endswith(".zip") and "-ref" in f:
                    full_p = os.path.join(ref_dir, f)
                    size = os.path.getsize(full_p)
                    mtime = os.path.getmtime(full_p)
                    # Extract tag (e.g. ref001)
                    tag_match = re.search(r"-(ref\d{3})\.zip$", f)
                    ref_tag = tag_match.group(1) if tag_match else "ref001"
                    
                    # Original name lookup from manifest or zip inspection
                    orig_name = "Base Reference Archive"
                    for orig, p_info in processed_map.items():
                        if p_info.get("output_file") == f:
                            orig_name = orig
                            break

                    backups.append({
                        "filename": f,
                        "file_path": full_p,
                        "original_filename": orig_name,
                        "ref_tag": ref_tag,
                        "type": "Base Reference (.zip)",
                        "size_bytes": size,
                        "size_formatted": f"{size / (1024*1024):.2f} MB",
                        "mtime": mtime,
                        "is_zip_base": True
                    })

        # 2. Check differential patches in output_dir
        for f in os.listdir(output_dir):
            if f.endswith(".hdiff"):
                full_p = os.path.join(output_dir, f)
                info = self.parse_hdiff_filename(full_p)
                if info:
                    size = os.path.getsize(full_p)
                    mtime = os.path.getmtime(full_p)
                    backups.append({
                        "filename": f,
                        "file_path": full_p,
                        "original_filename": info["original_filename"],
                        "ref_tag": info["ref_tag"],
                        "type": f"Differential Delta ({info['ref_tag']})",
                        "size_bytes": size,
                        "size_formatted": f"{size / (1024*1024):.2f} MB",
                        "mtime": mtime,
                        "is_zip_base": False,
                        "md5": info["md5"]
                    })

        return backups

    def restore_file(self, target_file_path, output_dir, destination_dir, log_callback=None):
        """
        Reconstructs the original backup file at destination_dir.
        If target is a baseline .zip, extracts directly.
        If target is an .hdiff, materializes its reference and applies hpatchz.
        Performs 100% MD5 integrity check at the end.
        """
        hpatchz_path = self.config.get("hpatchz_path")
        if not os.path.exists(hpatchz_path):
            raise FileNotFoundError(f"Executable hpatchz not found at: {hpatchz_path}")

        if not os.path.exists(target_file_path):
            raise FileNotFoundError(f"Target backup file not found: {target_file_path}")

        os.makedirs(destination_dir, exist_ok=True)
        filename = os.path.basename(target_file_path)

        # Case 1: Target file is the baseline ZIP archive in .ref/
        if target_file_path.endswith(".zip"):
            if log_callback:
                log_callback(f"Extracting baseline reference ZIP: {filename}...")
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
            # Note: -f forces overwrite, CREATE_NO_WINDOW suppresses console window popup
            cmd = [hpatchz_path, "-f", raw_ref_path, target_file_path, destination_file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
            if result.returncode != 0:
                err_msg = (result.stderr or result.stdout or "Unknown hpatchz error").strip()
                raise RuntimeError(f"Error running hpatchz: {err_msg}")

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
                "actual_md5": actual_md5,
                "expected_md5": expected_md5,
                "md5_matched": md5_matched,
                "message": status_msg
            }
