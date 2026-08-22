import os
import threading
import customtkinter as ctk
from tkinter import messagebox

PROVIDER_MAP = {
    "GDrive Desktop (Synced Folder)": "local_folder",
    "FTP Server": "ftp",
    "GDrive API (Service Account)": "gdrive"
}
REVERSE_MAP = {v: k for k, v in PROVIDER_MAP.items()}

class CloudSyncView(ctk.CTkFrame):
    def __init__(self, parent, config, sync_manager):
        super().__init__(parent, corner_radius=10)
        self.config = config
        self.sync_manager = sync_manager

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_controls()
        self._build_actions_and_logs()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        title = ctk.CTkLabel(header, text="☁️ Encrypted Cloud Sync & Dual-Key Verification", font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(side="left", padx=10)

    def _build_controls(self):
        controls = ctk.CTkFrame(self, corner_radius=8, fg_color="#1E1E2E", border_width=1, border_color="#313244")
        controls.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        controls.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(controls, text="Storage Provider:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        provider_names = list(PROVIDER_MAP.keys())
        self.combo_provider = ctk.CTkComboBox(controls, values=provider_names, command=self._on_provider_change, width=240)
        self.combo_provider.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        curr_code = self.config.get("cloud_provider", "local_folder")
        curr_display = REVERSE_MAP.get(curr_code, "GDrive Desktop (Synced Folder)")
        self.combo_provider.set(curr_display)

        self.btn_test = ctk.CTkButton(controls, text="🔌 Test Connection / Folder", command=self._test_connection, fg_color="#313244", hover_color="#45475A")
        self.btn_test.grid(row=0, column=2, padx=10, pady=10, sticky="w")

    def _build_actions_and_logs(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        body.grid_columnconfigure((0, 1), weight=1)
        body.grid_rowconfigure(1, weight=1)

        # Upload Column (Local -> Cloud)
        up_card = ctk.CTkFrame(body, corner_radius=8, fg_color="#181825", border_width=1, border_color="#313244")
        up_card.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        ctk.CTkLabel(up_card, text="⬆️ Auto / Manual Upload (Local ➔ Cloud)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#89B4FA").pack(pady=10)
        self.btn_upload_all = ctk.CTkButton(up_card, text="Encrypt, Sign & Upload Output Backups", command=self._start_upload_thread, fg_color="#89B4FA", text_color="#11111B", font=ctk.CTkFont(weight="bold"))
        self.btn_upload_all.pack(pady=(0, 10), padx=10, fill="x")

        # Download Column (Cloud -> Local)
        dn_card = ctk.CTkFrame(body, corner_radius=8, fg_color="#181825", border_width=1, border_color="#313244")
        dn_card.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkLabel(dn_card, text="⬇️ Manual Download & Verify (Cloud ➔ Local)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#A6E3A1").pack(pady=10)
        self.btn_list_remote = ctk.CTkButton(dn_card, text="Download, Verify Signature & Decrypt", command=self._start_download_thread, fg_color="#A6E3A1", text_color="#11111B", font=ctk.CTkFont(weight="bold"))
        self.btn_list_remote.pack(pady=(0, 10), padx=10, fill="x")

        # Logs box
        logs_frame = ctk.CTkFrame(body, corner_radius=8, fg_color="#11111B", border_width=1, border_color="#313244")
        logs_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=10, sticky="nsew")
        logs_frame.grid_columnconfigure(0, weight=1)
        logs_frame.grid_rowconfigure(0, weight=1)

        self.log_textbox = ctk.CTkTextbox(logs_frame, font=ctk.CTkFont(family="Consolas", size=12), fg_color="#11111B", text_color="#CDD6F4")
        self.log_textbox.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    def log(self, message):
        def _do():
            self.log_textbox.insert("end", f"{message}\n")
            self.log_textbox.see("end")
        self.after(0, _do)

    def _on_provider_change(self, value):
        code = PROVIDER_MAP.get(value, "local_folder")
        self.config.set("cloud_provider", code)
        self.log(f"Cloud sync provider set to: {value} ({code})")

    def _test_connection(self):
        def worker():
            try:
                provider = self.sync_manager.get_provider()
                success, msg = provider.test_connection()
                if success:
                    self.log(f"✅ {msg}")
                    messagebox.showinfo("Connection Test", msg)
                else:
                    self.log(f"❌ {msg}")
                    messagebox.showerror("Connection Error", msg)
            except Exception as e:
                self.log(f"❌ Error: {e}")
                messagebox.showerror("Error", str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _start_upload_thread(self):
        output_dir = self.config.get("output_dir")
        if not output_dir or not os.path.exists(output_dir):
            messagebox.showerror("Error", "Please configure a valid Output Directory in Settings first.")
            return

        def worker():
            try:
                files_to_upload = []
                for root, dirs, files in os.walk(output_dir):
                    for f in files:
                        if not f.endswith(".enc") and not f.endswith(".sig") and f != "manifest.json":
                            files_to_upload.append(os.path.join(root, f))

                if not files_to_upload:
                    self.log("No processed backup files found to upload.")
                    return

                for file_path in files_to_upload:
                    self.log(f"Uploading file: {os.path.basename(file_path)}...")
                    self.sync_manager.upload_encrypted_and_signed(file_path, log_callback=self.log)

                self.log("All backups encrypted, signed, and uploaded successfully.")
            except Exception as e:
                self.log(f"Upload error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _start_download_thread(self):
        def worker():
            try:
                provider = self.sync_manager.get_provider()
                remote_files = provider.list_files()
                enc_files = [f for f in remote_files if f.endswith(".enc")]

                if not enc_files:
                    self.log("No encrypted files (.enc) found in cloud storage.")
                    return

                target_enc = enc_files[0]
                dest_local = os.path.join(self.config.get("output_dir", "./output_backups"), target_enc.replace(".enc", ""))

                def on_mismatch(filename):
                    return messagebox.askyesno(
                        "Digital Signature Warning",
                        f"WARNING: The RSA digital signature for ({filename}) is INVALID or missing!\n\nDo you want to ignore this warning and proceed with decryption using your password?",
                        icon="warning"
                    )

                self.sync_manager.download_verify_and_decrypt(
                    remote_file_enc=target_enc,
                    dest_local_path=dest_local,
                    log_callback=self.log,
                    signature_mismatch_callback=on_mismatch
                )
            except Exception as e:
                self.log(f"Download error: {e}")

        threading.Thread(target=worker, daemon=True).start()
