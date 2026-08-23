import time
import threading

class PeriodicScheduler:
    def __init__(self, config, hdiff_engine, sync_manager=None, log_callback=None, progress_callback=None, on_run_start=None, on_run_end=None, on_status_change=None):
        self.config = config
        self.hdiff_engine = hdiff_engine
        self.sync_manager = sync_manager
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.on_run_start = on_run_start
        self.on_run_end = on_run_end
        self.on_status_change = on_status_change
        self._running = False
        self._thread = None
        self._is_processing_active = False

    def start(self):
        if self._running:
            return
        self._running = True
        self.config.set("auto_schedule_enabled", True)
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if self.on_status_change:
            try:
                self.on_status_change(True)
            except Exception:
                pass
        if self.log_callback:
            self.log_callback(f"Periodic backup scheduler started (Interval: every {self.config.get('schedule_interval_min', 60)} minutes).")

    def stop(self):
        self._running = False
        self.config.set("auto_schedule_enabled", False)
        if self.on_status_change:
            try:
                self.on_status_change(False)
            except Exception:
                pass
        if self.log_callback:
            self.log_callback("Periodic backup scheduler stopped.")

    def is_running(self):
        return self._running

    def is_processing_active(self):
        return self._is_processing_active

    def _run_loop(self):
        while self._running:
            try:
                input_dir = self.config.get("input_dir")
                output_dir = self.config.get("output_dir")

                if input_dir and output_dir:
                    unprocessed = self.hdiff_engine.scan_unprocessed_files(input_dir, output_dir)
                    if unprocessed:
                        self._is_processing_active = True
                        if self.on_run_start:
                            try:
                                self.on_run_start()
                            except Exception:
                                pass

                        if self.log_callback:
                            self.log_callback(f"Scheduled periodic daemon triggered: processing {len(unprocessed)} pending file(s)...")

                        count = self.hdiff_engine.process_backups(
                            input_dir=input_dir,
                            output_dir=output_dir,
                            log_callback=self.log_callback,
                            progress_callback=self.progress_callback
                        )

                        if count > 0 and self.config.get("auto_cloud_sync", False) and self.sync_manager:
                            if self.log_callback:
                                self.log_callback("Auto-syncing newly processed backups to cloud...")
                            try:
                                self.sync_manager.sync_all_upload(output_dir, log_callback=self.log_callback)
                            except Exception as sync_err:
                                if self.log_callback:
                                    self.log_callback(f"Auto-sync error: {sync_err}")

                        self._is_processing_active = False
                        if self.on_run_end:
                            try:
                                self.on_run_end()
                            except Exception:
                                pass

            except Exception as e:
                self._is_processing_active = False
                if self.on_run_end:
                    try:
                        self.on_run_end()
                    except Exception:
                        pass
                if self.log_callback:
                    self.log_callback(f"Scheduler loop error: {e}")

            interval_sec = max(10, self.config.get("schedule_interval_min", 60) * 60)
            elapsed = 0
            while self._running and elapsed < interval_sec:
                time.sleep(1)
                elapsed += 1
