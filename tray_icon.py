import os
import threading
from PIL import Image, ImageOps, ImageDraw
import pystray

def generate_fallback_icon(is_running: bool):
    """Generates a high-contrast fallback icon if image assets are absent."""
    image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    color = '#10B981' if is_running else '#EF4444'
    draw.rounded_rectangle([4, 4, 60, 60], radius=14, fill='#11111B', outline=color, width=2)
    # Database cylinders
    draw.ellipse([16, 12, 48, 24], fill=color, outline='#FFFFFF', width=1)
    draw.rectangle([16, 18, 48, 34], fill=color)
    draw.ellipse([16, 28, 48, 40], fill=color, outline='#FFFFFF', width=1)
    draw.rectangle([16, 34, 48, 50], fill=color)
    draw.ellipse([16, 44, 48, 56], fill=color, outline='#FFFFFF', width=1)
    return image

def get_status_icon(is_running: bool):
    """
    Creates a full-color masked 64x64 icon:
    - 🟢 Full Emerald Green mask when Running / Active
    - 🔴 Full Crimson Red mask when Stopped / Disabled
    """
    icon_path = os.path.abspath(os.path.join("assets", "app_icon.jpg"))
    if os.path.exists(icon_path):
        try:
            base_gray = Image.open(icon_path).convert('L')
            base_resized = base_gray.resize((64, 64), Image.Resampling.LANCZOS)

            if is_running:
                # Full Green Mask (Active)
                tinted = ImageOps.colorize(
                    base_resized,
                    black='#051A14',
                    mid='#10B981',
                    white='#A7F3D0',
                    midpoint=120
                ).convert('RGBA')
            else:
                # Full Red Mask (Stopped)
                tinted = ImageOps.colorize(
                    base_resized,
                    black='#1A0508',
                    mid='#EF4444',
                    white='#FCA5A5',
                    midpoint=120
                ).convert('RGBA')

            # Rounded corners mask
            mask = Image.new('L', (64, 64), 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle([2, 2, 62, 62], radius=14, fill=255)
            tinted.putalpha(mask)
            return tinted
        except Exception:
            return generate_fallback_icon(is_running)
    else:
        return generate_fallback_icon(is_running)

class SystemTrayApp:
    def __init__(self, on_show_window, on_trigger_manual, on_exit_app):
        self.on_show_window = on_show_window
        self.on_trigger_manual = on_trigger_manual
        self.on_exit_app = on_exit_app
        self.icon = None
        self.is_running_state = False

        self.img_running = get_status_icon(is_running=True)
        self.img_stopped = get_status_icon(is_running=False)

    def run_in_thread(self, initial_running=False):
        self.is_running_state = initial_running
        initial_img = self.img_running if initial_running else self.img_stopped
        initial_title = self._get_tooltip_title(initial_running)

        menu = pystray.Menu(
            # default=True binds double-click on Windows tray to open the window!
            pystray.MenuItem("Open Main Window", self._on_show, default=True),
            pystray.MenuItem("Trigger Backup Now", self._on_trigger),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Application", self._on_exit)
        )
        self.icon = pystray.Icon("HDiffBackupHelper", initial_img, initial_title, menu)
        thread = threading.Thread(target=self.icon.run, daemon=True)
        thread.start()

    def update_status(self, is_running: bool, custom_tooltip: str = None):
        """Updates the tray icon color (Full Green/Red Mask) and hover tooltip in real time."""
        self.is_running_state = is_running
        if self.icon:
            try:
                self.icon.icon = self.img_running if is_running else self.img_stopped
                self.icon.title = custom_tooltip if custom_tooltip else self._get_tooltip_title(is_running)
            except Exception:
                pass

    def _get_tooltip_title(self, is_running: bool):
        if is_running:
            return "HDiff Backup Pro - Scheduler: Running (Active 🟢)"
        else:
            return "HDiff Backup Pro - Scheduler: Stopped (Idle 🔴)"

    def stop(self):
        if self.icon:
            self.icon.stop()

    def _on_show(self, icon=None, item=None):
        if self.on_show_window:
            self.on_show_window()

    def _on_trigger(self, icon=None, item=None):
        if self.on_trigger_manual:
            self.on_trigger_manual()

    def _on_exit(self, icon=None, item=None):
        if self.icon:
            self.icon.stop()
        if self.on_exit_app:
            self.on_exit_app()
