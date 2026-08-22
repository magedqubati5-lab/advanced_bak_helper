import sys

def main():
    args = sys.argv[1:]
    start_in_tray = any(arg in args for arg in ("--tray", "--minimized", "--start-in-tray"))

    # If CLI subcommands like `scan`, `process`, `restore`, `daemon` are passed, route to CLI
    cli_commands = {"scan", "process", "list", "restore", "sync", "daemon", "config"}
    if args and any(arg in cli_commands for arg in args):
        from cli import main as cli_main
        sys.exit(cli_main())
    else:
        from ui.app import MainApplication
        app = MainApplication(start_in_tray=start_in_tray)
        app.mainloop()

if __name__ == "__main__":
    main()
