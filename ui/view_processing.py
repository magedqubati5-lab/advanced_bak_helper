import os
import threading
import customtkinter as ctk

class ProcessingView(ctk.CTkFrame):
    def __init__(self, parent, config, hdiff_engine, scheduler, sync_manager):
        super().__init__(parent, corner_radius=10)
        self.config = config
        self.hdiff_engine = hdiff_engine
        self.scheduler = scheduler
        self.sync_manager = sync_manager
        self.is_processing = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_cards()
        self._build_actions_and_logs()

    def _build_header(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        title = ctk.CTkLabel(header_frame, text="📊 Backup Dashboard & Differential Engine", font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(side="left", padx=10)

    def _build_cards(self):
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.card_pending = self._create_card(cards_frame, 0, "Pending Files", "0", "#E0A96D")
        self.card_processed = self._create_card(cards_frame, 1, "Processed Files", "0", "#A8DADC")
        self.card_ref = self._create_card(cards_frame, 2, "Active Reference", "None", "#457B9D")
        self.card_schedule = self._create_card(cards_frame, 3, "Schedule Daemon", "Stopped", "#E63946")

    def _create_card(self, parent, col, title, value, color):
        card = ctk.CTkFrame(parent, corner_radius=8, fg_color="#1E1E2E", border_width=1, border_color="#313244")
        card.grid(row=0, column=col, padx=5, pady=5, sticky="ew")

        lbl_title = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12), text_color="#A6ADC8")
        lbl_title.pack(pady=(10, 2))

        lbl_val = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=16, weight="bold"), text_color=color)
        lbl_val.pack(pady=(0, 10))

        return lbl_val

    def _build_actions_and_logs(self):
        body_frame = ctk.CTkFrame(self, fg_color="transparent")
        body_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        body_frame.grid_columnconfigure(0, weight=1)
        body_frame.grid_rowconfigure(1, weight=1)

        # Action Buttons
        btn_frame = ctk.CTkFrame(body_frame, fg_color="transparent")
        btn_frame.grid(row=0, column=0, pady=(0, 10), sticky="ew")

        self.btn_scan = ctk.CTkButton(btn_frame, text="🔍 Scan Directories", command=self.refresh_stats, fg_color="#313244", hover_color="#45475A")
        self.btn_scan.pack(side="left", padx=5)

        self.btn_process = ctk.CTkButton(btn_frame, text="⚡ Start Differential Backup", command=self.start_processing_thread, fg_color="#89B4FA", text_color="#11111B", hover_color="#B4BEFE", font=ctk.CTkFont(weight="bold"))
        self.btn_process.pack(side="left", padx=5)

        self.btn_stop = ctk.CTkButton(btn_frame, text="🛑 Stop Processing", command=self.stop_processing, fg_color="#F38BA8", text_color="#11111B", hover_color="#EBA0AC", state="disabled")
        self.btn_stop.pack(side="left", padx=5)

        self.btn_schedule_toggle = ctk.CTkButton(btn_frame, text="⏱️ Enable Periodic Daemon", command=self.toggle_schedule, fg_color="#A6E3A1", text_color="#11111B", hover_color="#94E2D5")
        self.btn_schedule_toggle.pack(side="right", padx=5)

        # Progress bar & Logs
        logs_frame = ctk.CTkFrame(body_frame, corner_radius=8, fg_color="#181825", border_width=1, border_color="#313244")
        logs_frame.grid(row=1, column=0, sticky="nsew")
        logs_frame.grid_columnconfigure(0, weight=1)
        logs_frame.grid_rowconfigure(1, weight=1)

        self.progress_bar = ctk.CTkProgressBar(logs_frame, orientation="horizontal", mode="determinate")
        self.progress_bar.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="ew")
        self.progress_bar.set(0)

        self.log_textbox = ctk.CTkTextbox(logs_frame, font=ctk.CTkFont(family="Consolas", size=12), fg_color="#11111B", text_color="#CDD6F4")
        self.log_textbox.grid(row=1, column=0, padx=15, pady=(5, 15), sticky="nsew")

    def log(self, message):
        def _do_log():
            self.log_textbox.insert("end", f"{message}\n")
            self.log_textbox.see("end")
        self.after(0, _do_log)

    def refresh_stats(self):
        input_dir = self.config.get("input_dir")
        output_dir = self.config.get("output_dir")

        if not input_dir or not output_dir or not os.path.exists(input_dir) or not os.path.exists(output_dir):
            self.card_pending.configure(text="Not Configured")
            self.log("Notice: Please configure valid Input and Output directories in Settings.")
            return

        unprocessed = self.hdiff_engine.scan_unprocessed_files(input_dir, output_dir)
        manifest = self.hdiff_engine.load_manifest(output_dir)

        processed_count = len(manifest.get("processed_files", {}))
        active_ref = manifest.get("active_ref")
        ref_text = active_ref.get("ref_tag", "None") if active_ref else "None"

        def _update():
            self.card_pending.configure(text=str(len(unprocessed)))
            self.card_processed.configure(text=str(processed_count))
            self.card_ref.configure(text=ref_text)

            sched_text = "Running" if self.scheduler.is_running() else "Stopped"
            sched_color = "#A6E3A1" if self.scheduler.is_running() else "#E63946"
            self.card_schedule.configure(text=sched_text, text_color=sched_color)

        self.after(0, _update)
        self.log(f"Directory scan completed: {len(unprocessed)} pending file(s), {processed_count} processed backup(s).")

    def start_processing_thread(self):
        input_dir = self.config.get("input_dir")
        output_dir = self.config.get("output_dir")

        if not input_dir or not output_dir:
            self.log("Error: Input and Output directories must be set in Settings before processing.")
            return

        # Pre-scan and update pending count immediately before launching worker
        unprocessed = self.hdiff_engine.scan_unprocessed_files(input_dir, output_dir)
        manifest = self.hdiff_engine.load_manifest(output_dir)
        self.card_pending.configure(text=str(len(unprocessed)))
        self.card_processed.configure(text=str(len(manifest.get("processed_files", {}))))
        
        self.is_processing = True
        self.btn_process.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.progress_bar.set(0)

        def worker():
            try:
                def prog(fraction, stats=None):
                    def update_ui():
                        self.progress_bar.set(fraction)
                        if stats:
                            self.card_pending.configure(text=str(stats.get("remaining_pending", 0)))
                            self.card_processed.configure(text=str(stats.get("total_processed", 0)))
                            active_tag = stats.get("active_ref_tag")
                            if active_tag and active_tag != "None":
                                self.card_ref.configure(text=active_tag)
                    self.after(0, update_ui)

                count = self.hdiff_engine.process_backups(
                    input_dir=input_dir,
                    output_dir=output_dir,
                    log_callback=self.log,
                    progress_callback=prog
                )
                self.log(f"Differential backup operation finished. Total processed in this run: {count}")
            except Exception as e:
                self.log(f"Processing error: {e}")
            finally:
                def finalize_ui():
                    self.is_processing = False
                    self.btn_process.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
                    self.refresh_stats()
                self.after(0, finalize_ui)

        threading.Thread(target=worker, daemon=True).start()

    def stop_processing(self):
        if self.is_processing:
            self.log("Stopping processing... waiting for current file to finalize safely.")
            self.hdiff_engine.request_cancel()
            self.btn_stop.configure(state="disabled")

    def toggle_schedule(self):
        if self.scheduler.is_running():
            self.scheduler.stop()
            self.btn_schedule_toggle.configure(text="⏱️ Enable Periodic Daemon", fg_color="#A6E3A1")
        else:
            self.scheduler.start()
            self.btn_schedule_toggle.configure(text="⏸️ Stop Periodic Daemon", fg_color="#F38BA8")
        self.refresh_stats()
