import threading
from PIL import Image, ImageDraw
import pystray

def create_tray_icon_image():
    """Generates a stylish 64x64 icon for the system tray using PIL."""
    image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Outer rounded rectangle
    draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill='#1E1E2E', outline='#313244', width=2)
    
    # Database cylinder / Backup symbol
    draw.ellipse([16, 12, 48, 24], fill='#89B4FA', outline='#B4BEFE', width=1)
    draw.rectangle([16, 18, 48, 34], fill='#89B4FA')
    draw.ellipse([16, 28, 48, 40], fill='#74C7EC', outline='#B4BEFE', width=1)
    draw.rectangle([16, 34, 48, 50], fill='#74C7EC')
    draw.ellipse([16, 44, 48, 56], fill='#89A1FA', outline='#B4BEFE', width=1)
    
    return image

class SystemTrayApp:
    def __init__(self, on_show_window, on_trigger_manual, on_exit_app):
        self.on_show_window = on_show_window
        self.on_trigger_manual = on_trigger_manual
        self.on_exit_app = on_exit_app
        self.icon = None

    def run_in_thread(self):
        icon_image = create_tray_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Open Main Window", self._on_show),
            pystray.MenuItem("Trigger Backup Now", self._on_trigger),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Application", self._on_exit)
        )
        self.icon = pystray.Icon("HDiffBackupHelper", icon_image, "HDiff SQL Backup Manager", menu)
        thread = threading.Thread(target=self.icon.run, daemon=True)
        thread.start()

    def stop(self):
        if self.icon:
            self.icon.stop()

    def _on_show(self, icon, item):
        if self.on_show_window:
            self.on_show_window()

    def _on_trigger(self, icon, item):
        if self.on_trigger_manual:
            self.on_trigger_manual()

    def _on_exit(self, icon, item):
        if self.icon:
            self.icon.stop()
        if self.on_exit_app:
            self.on_exit_app()
