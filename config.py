import os
import json
import shutil
import sys

CONFIG_FILE = "settings.json"

def resolve_binary(binary_base_name):
    """
    Finds binary in bin/, system PATH, or default location across Windows, Linux, and macOS.
    Official releases are available at: https://github.com/sisong/HDiffPatch/releases
    """
    exe_name = f"{binary_base_name}.exe" if sys.platform == "win32" else binary_base_name
    
    # 1. Check inside local bin/ directory
    local_bin = os.path.abspath(os.path.join("bin", exe_name))
    if os.path.exists(local_bin):
        return local_bin

    # 2. Check without .exe in local bin/
    local_bin_no_ext = os.path.abspath(os.path.join("bin", binary_base_name))
    if os.path.exists(local_bin_no_ext):
        return local_bin_no_ext

    # 3. Check system PATH
    which_path = shutil.which(binary_base_name) or shutil.which(exe_name)
    if which_path:
        return os.path.abspath(which_path)

    return local_bin

DEFAULT_CONFIG = {
    "input_dir": "",
    "output_dir": "",
    "hdiffz_path": resolve_binary("hdiffz"),
    "hpatchz_path": resolve_binary("hpatchz"),
    "max_file_size_mb": 500,
    "max_chain_length": 10,
    "schedule_interval_min": 60,
    "auto_schedule_enabled": False,
    "encryption_password": "",
    "local_sync_folder_path": "",
    "rsa_private_key_path": os.path.abspath(os.path.join("keys", "private_key.pem")),
    "rsa_public_key_path": os.path.abspath(os.path.join("keys", "public_key.pem")),
    "cloud_provider": "local_folder",
    "ftp_host": "",
    "ftp_port": 21,
    "ftp_user": "",
    "ftp_pass": "",
    "ftp_remote_dir": "/backups",
    "gdrive_credentials_json": "",
    "gdrive_folder_id": ""
}

class AppConfig:
    def __init__(self, config_path=CONFIG_FILE):
        self.config_path = config_path
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception as e:
                print(f"Error loading config file: {e}")

    def save(self):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving config file: {e}")

    def get(self, key, default=None):
        val = self.data.get(key, default)
        # If looking for hdiffz/hpatchz and path doesn't exist, try auto-resolving
        if key in ("hdiffz_path", "hpatchz_path") and (not val or not os.path.exists(val)):
            bname = "hdiffz" if "hdiffz" in key else "hpatchz"
            resolved = resolve_binary(bname)
            if os.path.exists(resolved):
                return resolved
        return val

    def set(self, key, value):
        self.data[key] = value
        self.save()
