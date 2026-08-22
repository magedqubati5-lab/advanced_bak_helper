import os
import subprocess
import zipfile
import json
import shutil
import tempfile
import threading
from hasher import calculate_md5

class HDiffEngine:
    def __init__(self, config):
        self.config = config
        self._cancel_requested = False

    def request_cancel(self):
        """Signals the running process to stop gracefully."""
        self._cancel_requested = True

    def reset_cancel(self):
        self._cancel_requested = False

    def is_cancel_requested(self):
        return self._cancel_requested

    def get_ref_dir(self, output_dir):
        ref_dir = os.path.join(output_dir, ".ref")
        os.makedirs(ref_dir, exist_ok=True)
        return ref_dir

    def get_manifest_path(self, output_dir):
        return os.path.join(self.get_ref_dir(output_dir), "manifest.json")

    def load_manifest(self, output_dir):
        manifest_path = self.get_manifest_path(output_dir)
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading manifest: {e}")
        return {
            "references": [],
            "processed_files": {},
            "active_ref": None,
            "current_chain_count": 0
        }

    def save_manifest(self, output_dir, manifest):
        manifest_path = self.get_manifest_path(output_dir)
        try:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving manifest: {e}")

    def scan_unprocessed_files(self, input_dir, output_dir):
        """
        Scans input_dir and output_dir to return a sorted list of unprocessed files.
        Files are sorted by modification time (oldest first).
        """
        if not os.path.exists(input_dir) or not os.path.exists(output_dir):
            return []

        manifest = self.load_manifest(output_dir)
        processed_map = manifest.get("processed_files", {})

        input_files = []
        for entry in os.listdir(input_dir):
            full_path = os.path.join(input_dir, entry)
            if os.path.isfile(full_path) and not entry.startswith('.'):
                input_files.append(full_path)

        input_files.sort(key=lambda x: os.path.getmtime(x))

        unprocessed = []
        for file_path in input_files:
            filename = os.path.basename(file_path)
            if filename in processed_map:
                continue
            unprocessed.append(file_path)

        return unprocessed

    def materialize_reference(self, target_ref_tag, output_dir, work_dir, log_callback=None):
        """
        Reconstructs a reference raw file on the fly inside work_dir using only:
        - The baseline [HASH]-ref001.zip
        - The chain of differential patches [HASH]-refXXX-refYYY.hdiff
        Leaves NO large uncompressed files permanently in .ref/!
        """
        hpatchz_path = self.config.get("hpatchz_path")
        if not os.path.exists(hpatchz_path):
            raise FileNotFoundError(f"HPatchZ executable not found at: {hpatchz_path}")

        ref_dir = self.get_ref_dir(output_dir)
        manifest = self.load_manifest(output_dir)
        references = manifest.get("references", [])

        if not references:
            raise FileNotFoundError("No reference files recorded in manifest.")

        # Find target reference index in list
        target_idx = -1
        for i, ref in enumerate(references):
            if ref.get("ref_tag") == target_ref_tag:
                target_idx = i
                break

        if target_idx == -1:
            raise ValueError(f"Reference tag '{target_ref_tag}' not found in manifest references.")

        # 1. Extract baseline ref001
        base_ref = references[0]
        base_zip_path = os.path.join(ref_dir, base_ref["ref_file"])
        if not os.path.exists(base_zip_path):
            raise FileNotFoundError(f"Base reference zip not found: {base_zip_path}")

        current_raw_path = os.path.join(work_dir, "ref_base.raw")
        with zipfile.ZipFile(base_zip_path, 'r') as z:
            extracted_names = z.namelist()
            if not extracted_names:
                raise ValueError("Base reference zip is empty.")
            with z.open(extracted_names[0]) as src, open(current_raw_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)

        if target_idx == 0:
            return current_raw_path

        # 2. Sequentially apply patches along the chain: ref001 -> ref002 -> ... -> target_idx
        for step in range(1, target_idx + 1):
            next_ref = references[step]
            diff_file_name = next_ref["ref_file"]  # e.g. [HASH]-ref001-ref002.hdiff
            diff_path = os.path.join(ref_dir, diff_file_name)

            if not os.path.exists(diff_path):
                raise FileNotFoundError(f"Reference patch not found along chain: {diff_path}")

            next_raw_path = os.path.join(work_dir, f"ref_step_{step}.raw")
            if log_callback:
                log_callback(f"Materializing reference chain step: {next_ref['ref_tag']} via {diff_file_name}...")

            cmd = [hpatchz_path, current_raw_path, diff_path, next_raw_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Error executing hpatchz for reference chain: {result.stderr}")

            # Remove previous step raw to save disk space
            if os.path.exists(current_raw_path):
                os.remove(current_raw_path)

            current_raw_path = next_raw_path

        return current_raw_path

    def process_backups(self, input_dir, output_dir, log_callback=None, progress_callback=None, check_cancel=None):
        """
        Processes unprocessed backup files in input_dir using hdiffz.
        Ensures .ref/ only holds the initial .zip and subsequent slim .hdiff patches.
        """
        self.reset_cancel()
        hdiffz_path = self.config.get("hdiffz_path")
        if not os.path.exists(hdiffz_path):
            raise FileNotFoundError(f"Executable hdiffz not found at: {hdiffz_path}")

        unprocessed = self.scan_unprocessed_files(input_dir, output_dir)
        if not unprocessed:
            if log_callback:
                log_callback("No unprocessed files found in input directory.")
            return 0

        ref_dir = self.get_ref_dir(output_dir)
        manifest = self.load_manifest(output_dir)
        
        max_size_bytes = self.config.get("max_file_size_mb", 500) * 1024 * 1024
        max_chain = self.config.get("max_chain_length", 10)

        processed_count = 0
        total_files = len(unprocessed)

        for idx, file_path in enumerate(unprocessed):
            # Check for cancellation
            if self._cancel_requested or (check_cancel and check_cancel()):
                if log_callback:
                    log_callback("Processing halted: Operation was stopped by user.")
                break

            filename = os.path.basename(file_path)
            if log_callback:
                log_callback(f"Processing file ({idx+1}/{total_files}): {filename}")

            file_hash = calculate_md5(file_path)

            references = manifest.get("references", [])
            active_ref = manifest.get("active_ref")
            chain_count = manifest.get("current_chain_count", 0)

            need_new_ref = False
            if not references or not active_ref:
                need_new_ref = True
                if log_callback:
                    log_callback("No prior reference found. Creating initial baseline reference (ref001.zip)...")
            else:
                last_processed_info = manifest.get("last_processed_file_info", {})
                is_ref = last_processed_info.get("is_reference", False)
                last_output_size = last_processed_info.get("size", 0)
                
                # Size threshold applies strictly to processed differential .hdiff files in output_dir
                size_exceeded = (not is_ref) and (last_output_size > max_size_bytes)
                chain_exceeded = chain_count >= max_chain

                if size_exceeded or chain_exceeded:
                    need_new_ref = True
                    if log_callback:
                        reason = "Last processed differential file exceeded size threshold" if size_exceeded else "Maximum chain length reached"
                        log_callback(f"Promoting to new reference (ref{len(references)+1:03d}) because: {reason}")

            if need_new_ref:
                ref_num = len(references) + 1
                ref_tag = f"ref{ref_num:03d}"

                if ref_num == 1:
                    # Initial baseline: compressed into [HASH]-ref001.zip inside .ref/
                    zip_ref_name = f"{file_hash}-{ref_tag}.zip"
                    zip_ref_path = os.path.join(ref_dir, zip_ref_name)
                    with zipfile.ZipFile(zip_ref_path, 'w', zipfile.ZIP_DEFLATED) as z:
                        z.write(file_path, arcname=filename)

                    ref_info = {
                        "ref_tag": ref_tag,
                        "hash": file_hash,
                        "ref_file": zip_ref_name,
                        "original_filename": filename,
                        "is_base_zip": True
                    }
                    if log_callback:
                        log_callback(f"Base reference saved to .ref/{zip_ref_name}")
                else:
                    # Subsequent reference: create slim delta patch [HASH]-ref001-ref002.hdiff inside .ref/
                    prev_ref_tag = references[-1]["ref_tag"]
                    diff_ref_name = f"{file_hash}-{prev_ref_tag}-{ref_tag}.hdiff"
                    diff_ref_path = os.path.join(ref_dir, diff_ref_name)

                    with tempfile.TemporaryDirectory() as tmp_work:
                        if log_callback:
                            log_callback(f"Materializing previous reference {prev_ref_tag} to compute slim reference delta...")
                        prev_raw_path = self.materialize_reference(prev_ref_tag, output_dir, tmp_work, log_callback)
                        
                        cmd = [hdiffz_path, "-c-zstd", prev_raw_path, file_path, diff_ref_path]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode != 0:
                            raise RuntimeError(f"Error creating reference diff: {result.stderr}")

                    ref_info = {
                        "ref_tag": ref_tag,
                        "hash": file_hash,
                        "ref_file": diff_ref_name,
                        "original_filename": filename,
                        "is_base_zip": False,
                        "parent_ref": prev_ref_tag
                    }
                    if log_callback:
                        log_callback(f"Slim reference delta saved to .ref/{diff_ref_name}")

                references.append(ref_info)
                active_ref = ref_info
                chain_count = 0

                manifest["references"] = references
                manifest["active_ref"] = active_ref
                manifest["current_chain_count"] = chain_count
                manifest["processed_files"][filename] = {
                    "hash": file_hash,
                    "ref_tag": ref_tag,
                    "is_reference": True,
                    "output_file": ref_info["ref_file"]
                }
                manifest["last_processed_file_info"] = {
                    "filename": ref_info["ref_file"],
                    "size": os.path.getsize(os.path.join(ref_dir, ref_info["ref_file"])),
                    "is_reference": True
                }
                self.save_manifest(output_dir, manifest)

            else:
                # Normal differential processing stored directly in output_dir/
                ref_tag = active_ref["ref_tag"]
                output_hdiff_name = f"{filename}.{file_hash}.{ref_tag}.hdiff"
                output_hdiff_path = os.path.join(output_dir, output_hdiff_name)

                with tempfile.TemporaryDirectory() as tmp_work:
                    if log_callback:
                        log_callback(f"Materializing active reference {ref_tag} for differential compression...")
                    ref_raw_path = self.materialize_reference(ref_tag, output_dir, tmp_work, log_callback)

                    if log_callback:
                        log_callback(f"Running hdiffz differential against {ref_tag}...")

                    cmd = [hdiffz_path, "-c-zstd", ref_raw_path, file_path, output_hdiff_path]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise RuntimeError(f"Error running hdiffz: {result.stderr}")

                hdiff_size = os.path.getsize(output_hdiff_path)
                chain_count += 1

                manifest["current_chain_count"] = chain_count
                manifest["processed_files"][filename] = {
                    "hash": file_hash,
                    "ref_tag": ref_tag,
                    "is_reference": False,
                    "output_file": output_hdiff_name
                }
                manifest["last_processed_file_info"] = {
                    "filename": output_hdiff_name,
                    "size": hdiff_size,
                    "is_reference": False
                }
                self.save_manifest(output_dir, manifest)

                if log_callback:
                    log_callback(f"Successfully processed: {output_hdiff_name} ({hdiff_size / (1024*1024):.2f} MB)")

            processed_count += 1
            if progress_callback:
                active_tag = manifest.get("active_ref", {}).get("ref_tag", "None") if manifest.get("active_ref") else "None"
                total_processed = len(manifest.get("processed_files", {}))
                remaining_pending = total_files - (idx + 1)
                stats = {
                    "processed_in_run": processed_count,
                    "total_processed": total_processed,
                    "remaining_pending": remaining_pending,
                    "active_ref_tag": active_tag,
                    "total_files": total_files,
                    "current_file": filename
                }
                try:
                    progress_callback((idx + 1) / total_files, stats)
                except TypeError:
                    progress_callback((idx + 1) / total_files)

        return processed_count
