import sys
import os

def attach_parent_console():
    """
    On Windows, attaches to the parent console when compiled with PyInstaller
    so that CLI outputs print directly to CMD/PowerShell.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            # ATTACH_PARENT_PROCESS = (DWORD)-1
            if ctypes.windll.kernel32.AttachConsole(-1):
                # Redirect standard streams to attached console
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                sys.stdin = open("CONIN$", "r", encoding="utf-8")
        except Exception:
            pass

def main():
    args = sys.argv[1:]

    # List of recognized CLI commands and help flags
    cli_commands = {"scan", "process", "list", "restore", "sync", "daemon", "config"}
    help_flags = {"-h", "--help", "-v", "--version"}

    is_cli_invocation = False
    if args:
        first_arg = args[0].lower()
        if first_arg in cli_commands or any(flag in args for flag in help_flags):
            is_cli_invocation = True

    if is_cli_invocation:
        attach_parent_console()
        from cli import main as cli_main
        sys.exit(cli_main())
    else:
        start_in_tray = any(arg in args for arg in ("--tray", "--minimized", "--start-in-tray"))
        from ui.app import MainApplication
        app = MainApplication(start_in_tray=start_in_tray)
        app.mainloop()

if __name__ == "__main__":
    main()
