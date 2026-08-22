import os
import customtkinter as ctk
from tkinter import filedialog, messagebox

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, config):
        super().__init__(parent, corner_radius=10)
        self.config = config

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_form()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        title = ctk.CTkLabel(header, text="⚙️ System Configuration & Preferences", font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(side="left", padx=10)

    def _build_form(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        scroll.grid_columnconfigure(1, weight=1)

        row = 0

        # Section 1: Paths
        self._add_section_header(scroll, "1. Directory Paths & Executable Binaries", row)
        row += 1

        self.entry_input = self._add_path_row(scroll, "Input Directory:", self.config.get("input_dir"), row, is_dir=True)
        row += 1
        self.entry_output = self._add_path_row(scroll, "Output Directory:", self.config.get("output_dir"), row, is_dir=True)
        row += 1
        self.entry_hdiffz = self._add_path_row(scroll, "hdiffz Binary Path:", self.config.get("hdiffz_path"), row, is_dir=False)
        row += 1
        self.entry_hpatchz = self._add_path_row(scroll, "hpatchz Binary Path:", self.config.get("hpatchz_path"), row, is_dir=False)
        row += 1

        # Section 2: Thresholds & Timing
        self._add_section_header(scroll, "2. Processing Thresholds & Schedule Daemon", row)
        row += 1

        self.entry_max_size = self._add_input_row(scroll, "Max Acceptable Output Size (MB):", str(self.config.get("max_file_size_mb", 500)), row)
        row += 1
        self.entry_max_chain = self._add_input_row(scroll, "Max Chain Length (Deltas):", str(self.config.get("max_chain_length", 10)), row)
        row += 1
        self.entry_interval = self._add_input_row(scroll, "Periodic Schedule Interval (Min):", str(self.config.get("schedule_interval_min", 60)), row)
        row += 1

        # Section 3: Security & Encryption
        self._add_section_header(scroll, "3. Encryption & Digital Signature Keys", row)
        row += 1

        self.entry_password = self._add_input_row(scroll, "Encryption Password:", self.config.get("encryption_password", ""), row, show="*")
        row += 1

        # Section 4: Easiest Method - Google Drive Desktop / Synced Folder
        self._add_section_header(scroll, "4. Google Drive Desktop / Synced Folder (Easiest Method - Zero Setup)", row)
        row += 1

        self.entry_sync_folder = self._add_path_row(scroll, "Drive / Cloud Sync Folder Path:", self.config.get("local_sync_folder_path", "G:/My Drive/Backups"), row, is_dir=True)
        row += 1

        # Section 5: FTP Account
        self._add_section_header(scroll, "5. FTP Cloud Storage Credentials", row)
        row += 1

        self.entry_ftp_host = self._add_input_row(scroll, "FTP Host:", self.config.get("ftp_host", ""), row)
        row += 1
        self.entry_ftp_port = self._add_input_row(scroll, "FTP Port:", str(self.config.get("ftp_port", 21)), row)
        row += 1
        self.entry_ftp_user = self._add_input_row(scroll, "FTP Username:", self.config.get("ftp_user", ""), row)
        row += 1
        self.entry_ftp_pass = self._add_input_row(scroll, "FTP Password:", self.config.get("ftp_pass", ""), row, show="*")
        row += 1
        self.entry_ftp_dir = self._add_input_row(scroll, "Remote Directory:", self.config.get("ftp_remote_dir", "/backups"), row)
        row += 1

        # Section 6: Google Drive API (Service Account)
        self._add_section_header(scroll, "6. Google Drive API (Advanced / Service Account)", row)
        row += 1

        self.entry_gdrive_json = self._add_path_row(scroll, "Service Account JSON Key:", self.config.get("gdrive_credentials_json", ""), row, is_dir=False, filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")])
        row += 1
        self.entry_gdrive_folder = self._add_input_row(scroll, "Target Drive Folder ID:", self.config.get("gdrive_folder_id", ""), row)
        row += 1

        # Save Button
        btn_save = ctk.CTkButton(scroll, text="💾 Save Configuration", command=self.save_settings, fg_color="#89B4FA", text_color="#11111B", font=ctk.CTkFont(weight="bold"), height=45)
        btn_save.grid(row=row, column=0, columnspan=3, pady=20, sticky="ew")

    def _add_section_header(self, parent, title, row):
        lbl = ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color="#89B4FA")
        lbl.grid(row=row, column=0, columnspan=3, sticky="w", pady=(15, 5))

    def _add_input_row(self, parent, label_text, default_val, row, show=None):
        ctk.CTkLabel(parent, text=label_text).grid(row=row, column=0, padx=10, pady=5, sticky="w")
        entry = ctk.CTkEntry(parent, show=show) if show else ctk.CTkEntry(parent)
        entry.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
        entry.insert(0, default_val or "")
        return entry

    def _add_path_row(self, parent, label_text, default_val, row, is_dir=True, filetypes=None):
        ctk.CTkLabel(parent, text=label_text).grid(row=row, column=0, padx=10, pady=5, sticky="w")
        entry = ctk.CTkEntry(parent)
        entry.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
        entry.insert(0, default_val or "")

        def browse():
            if is_dir:
                res = filedialog.askdirectory(title=label_text)
            else:
                ft = filetypes if filetypes else [("Executables", "*.exe"), ("All Files", "*.*")]
                res = filedialog.askopenfilename(title=label_text, filetypes=ft)
            if res:
                entry.delete(0, "end")
                entry.insert(0, res)

        btn = ctk.CTkButton(parent, text="Browse...", width=90, command=browse, fg_color="#313244")
        btn.grid(row=row, column=2, padx=10, pady=5)
        return entry

    def save_settings(self):
        try:
            self.config.set("input_dir", self.entry_input.get().strip())
            self.config.set("output_dir", self.entry_output.get().strip())
            self.config.set("hdiffz_path", self.entry_hdiffz.get().strip())
            self.config.set("hpatchz_path", self.entry_hpatchz.get().strip())
            self.config.set("max_file_size_mb", int(self.entry_max_size.get().strip() or 500))
            self.config.set("max_chain_length", int(self.entry_max_chain.get().strip() or 10))
            self.config.set("schedule_interval_min", int(self.entry_interval.get().strip() or 60))
            self.config.set("encryption_password", self.entry_password.get().strip())
            self.config.set("local_sync_folder_path", self.entry_sync_folder.get().strip())
            self.config.set("ftp_host", self.entry_ftp_host.get().strip())
            self.config.set("ftp_port", int(self.entry_ftp_port.get().strip() or 21))
            self.config.set("ftp_user", self.entry_ftp_user.get().strip())
            self.config.set("ftp_pass", self.entry_ftp_pass.get().strip())
            self.config.set("ftp_remote_dir", self.entry_ftp_dir.get().strip())
            self.config.set("gdrive_credentials_json", self.entry_gdrive_json.get().strip())
            self.config.set("gdrive_folder_id", self.entry_gdrive_folder.get().strip())

            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
