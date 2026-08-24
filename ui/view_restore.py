import os
import threading
import datetime
import customtkinter as ctk
from tkinter import filedialog, messagebox

class RestoreView(ctk.CTkFrame):
    def __init__(self, parent, config, restore_engine):
        super().__init__(parent, corner_radius=10)
        self.config = config
        self.restore_engine = restore_engine
        self.all_backups = []
        self.filtered_backups = []
        self.selected_backup = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_search_and_table()
        self._build_restore_status_panel()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(header, text="🔄 Restore & Decompression Center", font=ctk.CTkFont(size=20, weight="bold"))
        title.grid(row=0, column=0, sticky="w")

        btn_refresh = ctk.CTkButton(header, text="🔄 Refresh Backups List", width=140, command=self.load_backups, fg_color="#313244", hover_color="#45475A")
        btn_refresh.grid(row=0, column=1, sticky="e")

    def _build_search_and_table(self):
        main_card = ctk.CTkFrame(self, corner_radius=8, fg_color="#1E1E2E", border_width=1, border_color="#313244")
        main_card.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        main_card.grid_columnconfigure(0, weight=1)
        main_card.grid_rowconfigure(1, weight=1)

        # Filter & Sort Bar
        filter_bar = ctk.CTkFrame(main_card, fg_color="transparent")
        filter_bar.grid(row=0, column=0, padx=15, pady=10, sticky="ew")
        filter_bar.grid_columnconfigure(0, weight=1)

        self.entry_search = ctk.CTkEntry(filter_bar, placeholder_text="🔍 Search backups by filename, reference tag, or MD5 hash...")
        self.entry_search.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.entry_search.bind("<KeyRelease>", lambda e: self.apply_filter_and_sort())

        self.combo_sort = ctk.CTkComboBox(
            filter_bar,
            values=["Sort: Newest First", "Sort: Oldest First", "Sort: Name (A-Z)", "Sort: Size (Largest)", "Sort: Ref Tag"],
            command=lambda v: self.apply_filter_and_sort(),
            width=180
        )
        self.combo_sort.grid(row=0, column=1, sticky="e")
        self.combo_sort.set("Sort: Newest First")

        # Scrollable Backups List Container
        self.scroll_table = ctk.CTkScrollableFrame(main_card, fg_color="#181825", height=240)
        self.scroll_table.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")
        self.scroll_table.grid_columnconfigure(0, weight=1)

    def _build_restore_status_panel(self):
        status_panel = ctk.CTkFrame(self, corner_radius=8, fg_color="#181825", border_width=1, border_color="#313244")
        status_panel.grid(row=2, column=0, padx=20, pady=(5, 20), sticky="nsew")
        status_panel.grid_columnconfigure(0, weight=1)
        status_panel.grid_rowconfigure(2, weight=1)

        # Header with selected file and button
        top_bar = ctk.CTkFrame(status_panel, fg_color="transparent")
        top_bar.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="ew")
        top_bar.grid_columnconfigure(0, weight=1)

        self.lbl_selected = ctk.CTkLabel(top_bar, text="Selected: None (Select a backup above to restore)", font=ctk.CTkFont(size=13, weight="bold"), text_color="#A6ADC8")
        self.lbl_selected.grid(row=0, column=0, sticky="w")

        self.btn_restore_selected = ctk.CTkButton(
            top_bar,
            text="⚡ Restore Selected Backup...",
            command=self._on_restore_selected_clicked,
            fg_color="#89B4FA",
            text_color="#11111B",
            font=ctk.CTkFont(weight="bold"),
            state="disabled"
        )
        self.btn_restore_selected.grid(row=0, column=1, sticky="e")

        self.lbl_integrity_badge = ctk.CTkLabel(status_panel, text="Ready for restoration", font=ctk.CTkFont(size=12, weight="bold"), text_color="#A6ADC8")
        self.lbl_integrity_badge.grid(row=1, column=0, padx=15, pady=(2, 5), sticky="w")

        self.progress_bar = ctk.CTkProgressBar(status_panel, orientation="horizontal", mode="indeterminate")
        self.progress_bar.grid(row=2, column=0, padx=15, pady=2, sticky="ew")
        self.progress_bar.set(0)

        self.log_textbox = ctk.CTkTextbox(status_panel, font=ctk.CTkFont(family="Consolas", size=12), fg_color="#11111B", text_color="#CDD6F4", height=100)
        self.log_textbox.grid(row=3, column=0, padx=15, pady=(5, 15), sticky="nsew")

    def log(self, message):
        self.log_textbox.insert("end", f"{message}\n")
        self.log_textbox.see("end")

    def load_backups(self):
        output_dir = self.config.get("output_dir")
        if not output_dir or not os.path.exists(output_dir):
            self.log("Please configure a valid Output Directory in Settings first.")
            return

        self.all_backups = self.restore_engine.list_restorable_backups(output_dir)
        self.apply_filter_and_sort()
        self.log(f"Found {len(self.all_backups)} restorable backup archives.")

    def apply_filter_and_sort(self):
        query = self.entry_search.get().strip().lower()
        sort_mode = self.combo_sort.get()

        # 1. Filter
        filtered = []
        for b in self.all_backups:
            fname = b.get("file_name", b.get("filename", ""))
            oname = b.get("original_filename", "")
            rtag = b.get("ref_tag", "")
            md5_str = b.get("md5", "")

            if not query or (
                query in fname.lower() or
                query in oname.lower() or
                query in rtag.lower() or
                query in md5_str.lower()
            ):
                filtered.append(b)

        # 2. Sort
        if "Newest" in sort_mode:
            filtered.sort(key=lambda x: x.get("modified_time", x.get("mtime", 0)), reverse=True)
        elif "Oldest" in sort_mode:
            filtered.sort(key=lambda x: x.get("modified_time", x.get("mtime", 0)), reverse=False)
        elif "Name" in sort_mode:
            filtered.sort(key=lambda x: x.get("original_filename", "").lower())
        elif "Size" in sort_mode:
            filtered.sort(key=lambda x: x.get("size_bytes", 0), reverse=True)
        elif "Ref Tag" in sort_mode:
            filtered.sort(key=lambda x: x.get("ref_tag", ""))

        self.filtered_backups = filtered
        self._render_table_rows()

    def _render_table_rows(self):
        # Clear previous rows
        for widget in self.scroll_table.winfo_children():
            widget.destroy()

        if not self.filtered_backups:
            empty_lbl = ctk.CTkLabel(self.scroll_table, text="No restorable backup files match the current search or folder.", text_color="#A6ADC8")
            empty_lbl.pack(pady=30)
            return

        for idx, item in enumerate(self.filtered_backups):
            row_frame = ctk.CTkFrame(self.scroll_table, corner_radius=6, fg_color="#1E1E2E" if idx % 2 == 0 else "#252739")
            row_frame.pack(fill="x", padx=5, pady=3)
            row_frame.grid_columnconfigure(1, weight=1)

            # Left badge: Ref Tag
            tag_color = "#89B4FA" if item.get("type", "").startswith("Differential") else "#A6E3A1"
            tag_badge = ctk.CTkLabel(row_frame, text=f" {item.get('ref_tag', 'ref001')} ", font=ctk.CTkFont(size=11, weight="bold"), fg_color=tag_color, text_color="#11111B", corner_radius=4)
            tag_badge.grid(row=0, column=0, padx=10, pady=8)

            # Center Details
            details_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            details_frame.grid(row=0, column=1, padx=5, pady=4, sticky="w")

            orig_name = item.get("original_filename", item.get("filename", "Unknown"))
            lbl_name = ctk.CTkLabel(details_frame, text=orig_name, font=ctk.CTkFont(size=13, weight="bold"), text_color="#CDD6F4")
            lbl_name.pack(anchor="w")

            mtime = item.get("modified_time", item.get("mtime", 0))
            date_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S") if mtime else ""
            md5_short = f"MD5: {item['md5'][:10]}..." if item.get('md5') else ""
            lbl_sub = ctk.CTkLabel(details_frame, text=f"{item.get('type', '')} • {item.get('size_formatted', '')} • {date_str} • {md5_short}", font=ctk.CTkFont(size=11), text_color="#A6ADC8")
            lbl_sub.pack(anchor="w")

            # Right Select / Restore Button
            btn_choose = ctk.CTkButton(
                row_frame,
                text="Select",
                width=80,
                command=lambda b=item: self._select_backup(b),
                fg_color="#313244",
                hover_color="#45475A"
            )
            btn_choose.grid(row=0, column=2, padx=10, pady=8)

    def _select_backup(self, backup_item):
        self.selected_backup = backup_item
        orig_name = backup_item.get("original_filename", backup_item.get("filename", "Unknown"))
        ref_tag = backup_item.get("ref_tag", "")
        size_fmt = backup_item.get("size_formatted", "")
        fname = backup_item.get("file_name", backup_item.get("filename", ""))
        self.lbl_selected.configure(text=f"Selected: {orig_name} ({ref_tag} • {size_fmt})", text_color="#89B4FA")
        self.btn_restore_selected.configure(state="normal")
        self.log(f"Selected backup for restore: {fname}")

    def _on_restore_selected_clicked(self):
        if not self.selected_backup:
            messagebox.showwarning("Notice", "Please select a backup from the list first.")
            return

        dest_dir = filedialog.askdirectory(title="Choose Destination Folder to Save Restored .bak File")
        if not dest_dir:
            return  # User cancelled folder picker

        output_dir = self.config.get("output_dir")
        target_file = self.selected_backup.get("full_path", self.selected_backup.get("file_path", ""))

        self.btn_restore_selected.configure(state="disabled")
        self.progress_bar.start()
        self.lbl_integrity_badge.configure(text="Restoring and reconstructing backup through reference chain...", text_color="#89B4FA")

        def worker():
            try:
                res = self.restore_engine.restore_file(
                    target_file_path=target_file,
                    output_dir=output_dir,
                    destination_dir=dest_dir,
                    log_callback=self.log
                )
                if res.get("md5_matched"):
                    self.lbl_integrity_badge.configure(text=f"✅ Restoration Verified 100% (MD5 Matched): {res['restored_path']}", text_color="#A6E3A1")
                    messagebox.showinfo("Restoration Successful", f"Backup restored successfully!\n\nFile: {res['restored_path']}\nMD5 Integrity: MATCHED (100%)")
                else:
                    self.lbl_integrity_badge.configure(text="⚠️ Restored with MD5 Mismatch Warning!", text_color="#F38BA8")
                    messagebox.showwarning("Integrity Warning", "The file was restored, but its MD5 checksum did not match the recorded hash!")
            except Exception as e:
                self.log(f"Restoration error: {e}")
                self.lbl_integrity_badge.configure(text=f"❌ Restoration failed: {e}", text_color="#F38BA8")
                messagebox.showerror("Restoration Error", str(e))
            finally:
                self.progress_bar.stop()
                self.progress_bar.set(0)
                self.btn_restore_selected.configure(state="normal")

        threading.Thread(target=worker, daemon=True).start()
