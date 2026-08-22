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

        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.restored_dir, exist_ok=True)

        self.config = AppConfig(os.path.join(self.test_dir, "test_settings.json"))
        self.config.set("input_dir", self.input_dir)
        self.config.set("output_dir", self.output_dir)
        self.config.set("hdiffz_path", os.path.abspath("bin/hdiffz.exe"))
        self.config.set("hpatchz_path", os.path.abspath("bin/hpatchz.exe"))
        self.config.set("max_file_size_mb", 500)
        self.config.set("max_chain_length", 2)  # Trigger ref002 after 2 diffs!
        self.config.set("encryption_password", "SecretPass123!")

        self.hdiff_engine = HDiffEngine(self.config)
        self.restore_engine = RestoreEngine(self.config)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_differential_slim_chain_and_restore_cycle(self):
        print("\n--- [Test 1] Slim Delta Reference Chaining & Restoration ---")
        
        base_content = b"SQL_SERVER_DATA_BLOCK_HEADER_" * 50000  # ~1.5 MB
        
        # Day 1: Becomes baseline ref001.zip
        f1 = os.path.join(self.input_dir, "db_2026_08_01.bak")
        with open(f1, "wb") as f:
            f.write(base_content + b"DAY1")

        # Day 2: Diff against ref001 (chain count = 1)
        f2 = os.path.join(self.input_dir, "db_2026_08_02.bak")
        with open(f2, "wb") as f:
            f.write(base_content + b"DAY2_MODIFIED")

        # Day 3: Diff against ref001 (chain count = 2 -> reaches max_chain=2)
        f3 = os.path.join(self.input_dir, "db_2026_08_03.bak")
        with open(f3, "wb") as f:
            f.write(base_content + b"DAY3_MODIFIED_FURTHER")

        # Day 4: Must promote to ref002 (stored as slim [HASH]-ref001-ref002.hdiff)
        f4 = os.path.join(self.input_dir, "db_2026_08_04.bak")
        with open(f4, "wb") as f:
            f.write(base_content + b"DAY4_NEW_BASELINE")

        # Day 5: Diff against ref002
        f5 = os.path.join(self.input_dir, "db_2026_08_05.bak")
        with open(f5, "wb") as f:
            f.write(base_content + b"DAY5_DIFF_AGAINST_REF002")

        md5_f5 = calculate_md5(f5)

        count = self.hdiff_engine.process_backups(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            log_callback=print
        )
        self.assertEqual(count, 5)

        # Verify .ref/ contents: Must contain ref001.zip and slim ref001-ref002.hdiff
        ref_dir = os.path.join(self.output_dir, ".ref")
        ref_files = os.listdir(ref_dir)
        print(f"Files in .ref/ directory: {ref_files}")

        self.assertTrue(any(f.endswith("-ref001.zip") for f in ref_files))
        self.assertTrue(any("-ref001-ref002.hdiff" in f for f in ref_files))
        # Ensure NO large .raw files permanently exist in .ref/
        self.assertFalse(any(f.endswith(".raw") for f in ref_files))

        # Verify processed files in output_dir: Should contain .hdiff files
        out_files = [f for f in os.listdir(self.output_dir) if f.endswith(".hdiff")]
        self.assertGreaterEqual(len(out_files), 3)

        # Restore Day 5 (which depends on ref002 materialized via ref001.zip + ref001-ref002.hdiff)
        day5_hdiff = [f for f in out_files if "db_2026_08_05" in f][0]
        res = self.restore_engine.restore_file(
            target_file_path=os.path.join(self.output_dir, day5_hdiff),
            output_dir=self.output_dir,
            destination_dir=self.restored_dir,
            log_callback=print
        )

        self.assertTrue(res["success"])
        self.assertTrue(res["md5_matched"])
        self.assertEqual(res["actual_md5"], md5_f5)
        print("[SUCCESS] Restored Day 5 backup through multi-step reference chain with 100% MD5 match!")

    def test_crypto_and_digital_signature(self):
        print("\n--- [Test 2] Encryption & RSA Digital Signature ---")
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
        print("\n--- [Test 3] CLI Interface Execution ---")
        # Test CLI config show
        res = subprocess.run(["python", "cli.py", "config", "--show"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Current System Configuration:", res.stdout)
        print("[SUCCESS] CLI command 'config --show' executed successfully!")

if __name__ == "__main__":
    unittest.main()
