import time
import threading

class PeriodicScheduler:
    def __init__(self, config, hdiff_engine, sync_manager=None, log_callback=None):
        self.config = config
        self.hdiff_engine = hdiff_engine
        self.sync_manager = sync_manager
        self.log_callback = log_callback
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if self.log_callback:
            self.log_callback(f"Periodic backup scheduler started (Interval: every {self.config.get('schedule_interval_min', 60)} minutes).")

    def stop(self):
        self._running = False
        if self.log_callback:
            self.log_callback("Periodic backup scheduler stopped.")

    def is_running(self):
        return self._running

    def _run_loop(self):
        while self._running:
            try:
                input_dir = self.config.get("input_dir")
                output_dir = self.config.get("output_dir")

                if input_dir and output_dir:
                    if self.log_callback:
                        self.log_callback("Running scheduled periodic input directory check...")
                    count = self.hdiff_engine.process_backups(
                        input_dir=input_dir,
                        output_dir=output_dir,
                        log_callback=self.log_callback
                    )
                    if count > 0 and self.config.get("auto_cloud_sync", False) and self.sync_manager:
                        if self.log_callback:
                            self.log_callback("Auto-syncing newly processed backups to cloud...")

            except Exception as e:
                if self.log_callback:
                    self.log_callback(f"Scheduler loop error: {e}")

            interval_sec = max(10, self.config.get("schedule_interval_min", 60) * 60)
            elapsed = 0
            while self._running and elapsed < interval_sec:
                time.sleep(1)
                elapsed += 1
