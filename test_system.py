import os
import shutil
import unittest
import subprocess
from config import AppConfig
from hasher import calculate_md5, verify_md5
from hdiff_engine import HDiffEngine
from restore_engine import RestoreEngine
from crypto_engine import CryptoEngine
from sync.sync_manager import SyncManager

class TestBackupSystem(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.abspath("./test_env")
        self.input_dir = os.path.join(self.test_dir, "input")
        self.output_dir = os.path.join(self.test_dir, "output")
        self.restored_dir = os.path.join(self.test_dir, "restored")
        self.cloud_sync_dir = os.path.join(self.test_dir, "cloud_storage")
        self.cloud_dest_dir = os.path.join(self.test_dir, "cloud_restored_output")

        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.restored_dir, exist_ok=True)
        os.makedirs(self.cloud_sync_dir, exist_ok=True)
        os.makedirs(self.cloud_dest_dir, exist_ok=True)

        self.config = AppConfig(os.path.join(self.test_dir, "test_settings.json"))
        self.config.set("input_dir", self.input_dir)
        self.config.set("output_dir", self.output_dir)
        self.config.set("hdiffz_path", os.path.abspath("bin/hdiffz.exe"))
        self.config.set("hpatchz_path", os.path.abspath("bin/hpatchz.exe"))
        self.config.set("max_file_size_mb", 0.001)
        self.config.set("max_chain_length", 2)
        self.config.set("reset_as_standalone_base_zip", False)
        self.config.set("encryption_password", "SecretPass123!")
        self.config.set("cloud_provider", "local_folder")
        self.config.set("local_sync_folder_path", self.cloud_sync_dir)
        self.config.set("auto_cloud_sync", True)

        self.hdiff_engine = HDiffEngine(self.config)
        self.restore_engine = RestoreEngine(self.config)
        self.sync_manager = SyncManager(self.config)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_reference_chain_depth_limiting_and_reset(self):
        print("\n--- [Test 1] Reference Chain Depth Limiting (Root Delta Reset) ---")
        base_content = b"SQL_SERVER_DATA_BLOCK_HEADER_" * 40000

        files = []
        for i in range(1, 10):
            f_path = os.path.join(self.input_dir, f"db_day_{i:02d}.bak")
            distinct_payload = os.urandom(30000)
            with open(f_path, "wb") as f:
                f.write(base_content + distinct_payload)
            files.append(f_path)

        count = self.hdiff_engine.process_backups(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            log_callback=print
        )
        self.assertEqual(count, 9)

        manifest = self.hdiff_engine.load_manifest(self.output_dir)
        references = manifest.get("references", [])
        self.assertEqual(len(references), 5)
        
        ref_map = {r["ref_tag"]: r for r in references}
        self.assertEqual(ref_map["ref001"]["chain_depth"], 0)
        self.assertEqual(ref_map["ref002"]["parent_ref"], "ref001")
        self.assertEqual(ref_map["ref003"]["parent_ref"], "ref002")
        self.assertEqual(ref_map["ref004"]["parent_ref"], "ref001")
        self.assertEqual(ref_map["ref005"]["parent_ref"], "ref004")
        print("[SUCCESS] Verified chain depth limiting and reset to ref001 delta!")

    def test_standalone_base_zip_reset_option(self):
        print("\n--- [Test 2] Standalone Base ZIP Reset Option ---")
        self.config.set("reset_as_standalone_base_zip", True)
        
        base_content = b"SQL_SERVER_DATA_BLOCK_HEADER_" * 40000
        files = []
        for i in range(1, 10):
            f_path = os.path.join(self.input_dir, f"db_day_{i:02d}.bak")
            distinct_payload = os.urandom(30000)
            with open(f_path, "wb") as f:
                f.write(base_content + distinct_payload)
            files.append(f_path)

        count = self.hdiff_engine.process_backups(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            log_callback=print
        )
        self.assertEqual(count, 9)

        manifest = self.hdiff_engine.load_manifest(self.output_dir)
        references = manifest.get("references", [])
        ref_map = {r["ref_tag"]: r for r in references}

        # Check ref004 is a standalone ZIP base!
        self.assertTrue(ref_map["ref004"]["is_base_zip"])
        self.assertTrue(ref_map["ref004"]["ref_file"].endswith(".zip"))
        self.assertIsNone(ref_map["ref004"]["parent_ref"])
        self.assertEqual(ref_map["ref004"]["chain_depth"], 0)
        print("[SUCCESS] Verified ref004 was created as a standalone new ZIP baseline!")

        # Check ref005 chained to ref004
        self.assertEqual(ref_map["ref005"]["parent_ref"], "ref004")
        self.assertEqual(ref_map["ref005"]["chain_depth"], 1)

        # Test restoration of a backup on ref005
        extra_file = os.path.join(self.input_dir, "db_day_10_target.bak")
        with open(files[-1], "rb") as f_in:
            day9_data = f_in.read()
        with open(extra_file, "wb") as f_out:
            f_out.write(day9_data + b"_EXTRA_TARGET")
        md5_target = calculate_md5(extra_file)

        self.config.set("max_file_size_mb", 500)
        self.hdiff_engine.process_backups(self.input_dir, self.output_dir, log_callback=print)

        out_files = [f for f in os.listdir(self.output_dir) if f.endswith(".hdiff")]
        target_hdiff = [f for f in out_files if "db_day_10_target" in f][0]

        res = self.restore_engine.restore_file(
            target_file_path=os.path.join(self.output_dir, target_hdiff),
            output_dir=self.output_dir,
            destination_dir=self.restored_dir,
            log_callback=print
        )

        self.assertTrue(res["success"])
        self.assertTrue(res["md5_matched"])
        self.assertEqual(res["actual_md5"], md5_target)
        print("[SUCCESS] Restored backup derived from standalone ref004.zip with 100% MD5 match!")

    def test_sync_skips_existing_files_and_full_sync(self):
        print("\n--- [Test 3] Cloud Sync (Skipping existing files & Credentials validation) ---")
        can_sync, info = self.sync_manager.has_valid_credentials()
        self.assertTrue(can_sync)
        self.assertIn("Local / Drive Sync Folder", info)

        base_content = b"SQL_SERVER_DATA_CHUNK_" * 30000
        for i in range(1, 4):
            f_path = os.path.join(self.input_dir, f"backup_{i}.bak")
            with open(f_path, "wb") as f:
                f.write(base_content + f"PART_{i}".encode())

        self.hdiff_engine.process_backups(self.input_dir, self.output_dir, log_callback=print)
        
        # First sync upload: Uploads all initial files (3 backups + manifest)
        up_count_1 = self.sync_manager.sync_all_upload(self.output_dir, log_callback=print)
        self.assertGreaterEqual(up_count_1, 3)

        # Second sync upload immediately after: Should SKIP all existing files (Uploaded: 1 for manifest, 0 for backup files!)
        up_count_2 = self.sync_manager.sync_all_upload(self.output_dir, log_callback=print)
        # Manifest is uploaded as latest state, but all other files are skipped!
        self.assertEqual(up_count_2, 1)
        print("[SUCCESS] Verified second sync run successfully skipped all existing backup payloads in cloud!")

        # Download & Restore verification
        down_count = self.sync_manager.sync_all_download(self.cloud_dest_dir, log_callback=print)
        self.assertGreaterEqual(down_count, 3)

        restored_ref_dir = os.path.join(self.cloud_dest_dir, ".ref")
        self.assertTrue(os.path.exists(restored_ref_dir))
        self.assertTrue(os.path.exists(os.path.join(restored_ref_dir, "manifest.json")))
        print("[SUCCESS] Cloud sync download verified and fully restored!")

    def test_crypto_and_digital_signature(self):
        print("\n--- [Test 4] Encryption & RSA Digital Signature ---")
        priv_key = os.path.join(self.test_dir, "priv.pem")
        pub_key = os.path.join(self.test_dir, "pub.pem")

        CryptoEngine.generate_rsa_keypair(priv_key, pub_key)
        sample_file = os.path.join(self.test_dir, "sample.bin")
        with open(sample_file, "wb") as f:
            f.write(b"CONFIDENTIAL_SQL_SERVER_BACKUP_PAYLOAD")

        enc_file = os.path.join(self.test_dir, "sample.bin.enc")
        sig_file = os.path.join(self.test_dir, "sample.bin.enc.sig")

        CryptoEngine.encrypt_file(sample_file, enc_file, "SecretPass123!")
        CryptoEngine.sign_file(enc_file, priv_key, sig_file)

        valid = CryptoEngine.verify_signature(enc_file, sig_file, pub_key)
        self.assertTrue(valid)
        print("[SUCCESS] RSA Digital Signature valid!")

        with open(sig_file, "r+b") as f:
            f.seek(0)
            f.write(b"\x00\x00\x00\x00")

        invalid = CryptoEngine.verify_signature(enc_file, sig_file, pub_key)
        self.assertFalse(invalid)
        print("[SUCCESS] Tampered signature correctly rejected!")

    def test_cli_interface(self):
        print("\n--- [Test 5] CLI Interface Execution ---")
        res = subprocess.run(["python", "cli.py", "config", "--show"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Current System Configuration:", res.stdout)
        print("[SUCCESS] CLI command 'config --show' executed successfully!")

if __name__ == "__main__":
    unittest.main()
