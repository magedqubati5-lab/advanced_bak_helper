import sys
import os
import customtkinter as ctk
from tkinter import messagebox

from ui.view_processing import ProcessingView
from ui.view_restore import RestoreView
from ui.view_cloud import CloudSyncView
from ui.view_settings import SettingsView

from config import AppConfig
from hdiff_engine import HDiffEngine
from restore_engine import RestoreEngine
from sync.sync_manager import SyncManager
from scheduler import PeriodicScheduler
from tray_icon import SystemTrayApp

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class MainApplication(ctk.CTk):
    def __init__(self, start_in_tray=False):
        super().__init__()

        self.title("HDiff Backup Pro - SQL Server Differential Backup Manager")
        self.geometry("1100x720")
        self.minsize(950, 620)

        # Core System Components
        self.config = AppConfig()
        self.hdiff_engine = HDiffEngine(self.config)
        self.restore_engine = RestoreEngine(self.config)
        self.sync_manager = SyncManager(self.config)
        self.scheduler = PeriodicScheduler(self.config, self.hdiff_engine, self.sync_manager)

        # System Tray Integration
        self.tray = SystemTrayApp(
            on_show_window=self.show_window,
            on_trigger_manual=self.trigger_manual_processing,
            on_exit_app=self.quit_app
        )
        self.tray.run_in_thread()

        self.protocol("WM_DELETE_WINDOW", self.on_close_window)

        # Build Main UI Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_container()

        # Show Processing View by default
        self.select_tab("processing")

        if start_in_tray:
            self.withdraw()
            self.scheduler.start()
            self.view_processing.refresh_stats()

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#1E1E2E")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(5, weight=1)

        # App Logo & Title
        logo_lbl = ctk.CTkLabel(self.sidebar, text="🛡️ HDiff Backup Pro", font=ctk.CTkFont(size=18, weight="bold"), text_color="#89B4FA")
        logo_lbl.grid(row=0, column=0, padx=20, pady=(25, 30))

        # Nav Buttons
        self.btn_processing = ctk.CTkButton(self.sidebar, text="📊 Processing", font=ctk.CTkFont(size=14), fg_color="transparent", text_color="#CDD6F4", hover_color="#313244", anchor="w", command=lambda: self.select_tab("processing"))
        self.btn_processing.grid(row=1, column=0, padx=15, pady=5, sticky="ew")

        self.btn_restore = ctk.CTkButton(self.sidebar, text="🔄 Restore", font=ctk.CTkFont(size=14), fg_color="transparent", text_color="#CDD6F4", hover_color="#313244", anchor="w", command=lambda: self.select_tab("restore"))
        self.btn_restore.grid(row=2, column=0, padx=15, pady=5, sticky="ew")

        self.btn_cloud = ctk.CTkButton(self.sidebar, text="☁️ Cloud Sync", font=ctk.CTkFont(size=14), fg_color="transparent", text_color="#CDD6F4", hover_color="#313244", anchor="w", command=lambda: self.select_tab("cloud"))
        self.btn_cloud.grid(row=3, column=0, padx=15, pady=5, sticky="ew")

        self.btn_settings = ctk.CTkButton(self.sidebar, text="⚙️ Settings", font=ctk.CTkFont(size=14), fg_color="transparent", text_color="#CDD6F4", hover_color="#313244", anchor="w", command=lambda: self.select_tab("settings"))
        self.btn_settings.grid(row=4, column=0, padx=15, pady=5, sticky="ew")

        # Footer Status
        self.lbl_footer = ctk.CTkLabel(self.sidebar, text="v1.1 | HDiffPatch v5.1.3", font=ctk.CTkFont(size=11), text_color="#A6ADC8")
        self.lbl_footer.grid(row=6, column=0, padx=20, pady=15)

    def _build_container(self):
        self.container = ctk.CTkFrame(self, fg_color="#181825", corner_radius=0)
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        # Initialize Views
        self.view_processing = ProcessingView(self.container, self.config, self.hdiff_engine, self.scheduler, self.sync_manager)
        self.view_restore = RestoreView(self.container, self.config, self.restore_engine)
        self.view_cloud = CloudSyncView(self.container, self.config, self.sync_manager)
        self.view_settings = SettingsView(self.container, self.config)

    def select_tab(self, tab_name):
        self.view_processing.grid_forget()
        self.view_restore.grid_forget()
        self.view_cloud.grid_forget()
        self.view_settings.grid_forget()

        for btn in (self.btn_processing, self.btn_restore, self.btn_cloud, self.btn_settings):
            btn.configure(fg_color="transparent", text_color="#CDD6F4")

        if tab_name == "processing":
            self.view_processing.grid(row=0, column=0, sticky="nsew")
            self.btn_processing.configure(fg_color="#313244", text_color="#89B4FA")
            self.view_processing.refresh_stats()
        elif tab_name == "restore":
            self.view_restore.grid(row=0, column=0, sticky="nsew")
            self.btn_restore.configure(fg_color="#313244", text_color="#89B4FA")
            self.view_restore.load_backups()
        elif tab_name == "cloud":
            self.view_cloud.grid(row=0, column=0, sticky="nsew")
            self.btn_cloud.configure(fg_color="#313244", text_color="#89B4FA")
        elif tab_name == "settings":
            self.view_settings.grid(row=0, column=0, sticky="nsew")
            self.btn_settings.configure(fg_color="#313244", text_color="#89B4FA")

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def trigger_manual_processing(self):
        self.show_window()
        self.select_tab("processing")
        self.view_processing.start_processing_thread()

    def on_close_window(self):
        if self.scheduler.is_running():
            self.withdraw()  # Minimize to system tray silently
        else:
            self.quit_app()

    def quit_app(self):
        self.scheduler.stop()
        self.tray.stop()
        self.destroy()
        sys.exit(0)
