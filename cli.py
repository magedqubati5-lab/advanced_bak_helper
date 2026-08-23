import sys
import os
import argparse
import time
from config import AppConfig
from hdiff_engine import HDiffEngine
from restore_engine import RestoreEngine
from sync.sync_manager import SyncManager
from scheduler import PeriodicScheduler

def print_banner():
    print("""
===========================================================
  HDiff Backup Pro - SQL Server Differential Backup Tool
===========================================================
""")

def cmd_scan(args, config, hdiff_engine):
    input_dir = args.input or config.get("input_dir")
    output_dir = args.output or config.get("output_dir")

    if not input_dir or not output_dir or not os.path.exists(input_dir) or not os.path.exists(output_dir):
        print("[ERROR] Input and Output directories must exist. Configure them in Settings or pass --input and --output.")
        return 1

    print(f"Scanning Input Dir : {input_dir}")
    print(f"Scanning Output Dir: {output_dir}\n")

    unprocessed = hdiff_engine.scan_unprocessed_files(input_dir, output_dir)
    manifest = hdiff_engine.load_manifest(output_dir)
    processed = manifest.get("processed_files", {})
    active_ref = manifest.get("active_ref", {})

    print(f"Active Reference : {active_ref.get('ref_tag', 'None')} ({active_ref.get('ref_file', 'None')})")
    print(f"Processed Backups: {len(processed)}")
    print(f"Pending Files    : {len(unprocessed)}\n")

    if unprocessed:
        print("--- Pending Unprocessed Files ---")
        for i, f in enumerate(unprocessed, 1):
            st = os.stat(f)
            size_mb = st.st_size / (1024 * 1024)
            print(f"  [{i}] {os.path.basename(f)} ({size_mb:.2f} MB)")
    else:
        print("[INFO] All files in input directory have already been processed.")
    return 0

def cmd_process(args, config, hdiff_engine):
    input_dir = args.input or config.get("input_dir")
    output_dir = args.output or config.get("output_dir")

    if args.max_size:
        config.set("max_file_size_mb", args.max_size)
    if args.max_chain:
        config.set("max_chain_length", args.max_chain)

    if not input_dir or not output_dir:
        print("[ERROR] Input and Output directories must be specified.")
        return 1

    print(f"Starting differential backup processing...")
    print(f"Input : {input_dir}")
    print(f"Output: {output_dir}")
    print(f"Max Diff Size Threshold : {config.get('max_file_size_mb')} MB")
    print(f"Max Delta Chain Length  : {config.get('max_chain_length')}\n")

    count = hdiff_engine.process_backups(
        input_dir=input_dir,
        output_dir=output_dir,
        log_callback=lambda msg: print(f"[*] {msg}")
    )

    print(f"\n[SUCCESS] Differential backup complete! Processed {count} file(s).")
    return 0

def cmd_list(args, config, restore_engine):
    output_dir = args.output or config.get("output_dir")
    if not output_dir or not os.path.exists(output_dir):
        print("[ERROR] Valid Output directory required.")
        return 1

    backups = restore_engine.list_restorable_backups(output_dir)
    print(f"Found {len(backups)} restorable backup archives in {output_dir}:\n")
    print(f"{'IDX':<4} {'REF':<8} {'TYPE':<25} {'SIZE':<12} {'NAME'}")
    print("-" * 75)
    for i, b in enumerate(backups, 1):
        print(f"{i:<4} {b['ref_tag']:<8} {b['type']:<25} {b['size_formatted']:<12} {b['original_filename']}")
    return 0

def cmd_restore(args, config, restore_engine):
    output_dir = args.output or config.get("output_dir")
    target_file = args.file
    dest_dir = args.dest

    if not target_file or not os.path.exists(target_file):
        print(f"[ERROR] Target file not found: {target_file}")
        return 1
    if not dest_dir:
        print("[ERROR] Destination directory (--dest) is required.")
        return 1

    print(f"Restoring backup archive: {target_file}")
    print(f"Destination folder      : {dest_dir}\n")

    res = restore_engine.restore_file(
        target_file_path=target_file,
        output_dir=output_dir,
        destination_dir=dest_dir,
        log_callback=lambda msg: print(f"[*] {msg}")
    )

    if res.get("md5_matched"):
        print(f"\n[SUCCESS] {res['message']}")
        print(f"Restored file path : {res['restored_path']}")
        print(f"MD5 Integrity Check: MATCHED ({res['actual_md5']})")
        return 0
    else:
        print(f"\n[WARNING] {res['message']}")
        return 2

def cmd_sync(args, config, sync_manager):
    action = args.action
    output_dir = args.output or config.get("output_dir")

    if action == "upload":
        if not output_dir or not os.path.exists(output_dir):
            print("[ERROR] Output directory must exist for upload.")
            return 1
        
        count = sync_manager.sync_all_upload(output_dir, log_callback=lambda msg: print(f"[*] {msg}"))
        print(f"[SUCCESS] Cloud sync upload complete ({count} items synced, including .ref/ and manifest).")

    elif action == "download":
        remote_file = args.file
        if remote_file:
            dest = args.dest or os.path.join(output_dir, remote_file.replace(".enc", ""))
            print(f"Downloading single file {remote_file} -> {dest}...")
            sync_manager.download_verify_and_decrypt(
                remote_file_enc=remote_file,
                dest_local_path=dest,
                log_callback=lambda msg: print(f"[*] {msg}"),
                signature_mismatch_callback=lambda fn: input("Signature mismatch! Proceed anyway? (y/n): ").lower() == 'y'
            )
            print("[SUCCESS] Download and decryption completed.")
        else:
            if not output_dir:
                print("[ERROR] Output directory (--output) required for full sync download.")
                return 1
            count = sync_manager.sync_all_download(
                output_dir=output_dir,
                log_callback=lambda msg: print(f"[*] {msg}"),
                signature_mismatch_callback=lambda fn: input(f"Signature mismatch on {fn}! Proceed anyway? (y/n): ").lower() == 'y'
            )
            print(f"[SUCCESS] Full cloud sync download complete ({count} items restored).")
    return 0

def cmd_daemon(args, config, hdiff_engine, sync_manager):
    interval = args.interval or config.get("schedule_interval_min", 60)
    config.set("schedule_interval_min", interval)

    scheduler = PeriodicScheduler(
        config=config,
        hdiff_engine=hdiff_engine,
        sync_manager=sync_manager,
        log_callback=lambda msg: print(f"[{time.strftime('%X')}] {msg}")
    )
    print(f"Starting CLI Daemon mode (Interval: {interval} minutes). Press Ctrl+C to stop.")
    scheduler.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping daemon...")
        scheduler.stop()
    return 0

def cmd_config(args, config):
    if args.show:
        print("Current System Configuration:")
        for k, v in config.data.items():
            if "pass" in k or "secret" in k:
                v = "******" if v else ""
            print(f"  {k:<25}: {v}")
    elif args.set:
        for pair in args.set:
            if "=" in pair:
                k, v = pair.split("=", 1)
                # Parse integer values if applicable
                if v.isdigit():
                    v = int(v)
                config.set(k.strip(), v)
                print(f"[CONFIG] Updated '{k.strip()}' = {v}")
            else:
                print(f"[ERROR] Invalid format: {pair}. Use KEY=VALUE.")
    return 0

def main():
    parser = argparse.ArgumentParser(description="HDiff Backup Pro - Command Line Interface (CLI)")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Scan command
    p_scan = subparsers.add_parser("scan", help="Scan input directory for pending backups")
    p_scan.add_argument("--input", help="Input directory path")
    p_scan.add_argument("--output", help="Output directory path")

    # Process command
    p_proc = subparsers.add_parser("process", help="Execute differential backup processing")
    p_proc.add_argument("--input", help="Input directory path")
    p_proc.add_argument("--output", help="Output directory path")
    p_proc.add_argument("--max-size", type=int, help="Max differential patch size (MB)")
    p_proc.add_argument("--max-chain", type=int, help="Max differential delta chain length")

    # List command
    p_list = subparsers.add_parser("list", help="List all restorable backups")
    p_list.add_argument("--output", help="Output directory path")

    # Restore command
    p_rest = subparsers.add_parser("restore", help="Restore and verify a backup file")
    p_rest.add_argument("--file", required=True, help="Path to .hdiff or .zip backup archive")
    p_rest.add_argument("--dest", required=True, help="Destination directory for restored file")
    p_rest.add_argument("--output", help="Output directory path (containing .ref/)")

    # Sync command
    p_sync = subparsers.add_parser("sync", help="Cloud synchronization")
    p_sync.add_argument("action", choices=["upload", "download"], help="Upload or download")
    p_sync.add_argument("--file", help="Remote encrypted file name (for download)")
    p_sync.add_argument("--dest", help="Destination path")
    p_sync.add_argument("--output", help="Output directory path")

    # Daemon command
    p_daem = subparsers.add_parser("daemon", help="Run background scheduler in console")
    p_daem.add_argument("--interval", type=int, help="Periodic interval in minutes")

    # Config command
    p_conf = subparsers.add_parser("config", help="View or modify configuration")
    p_conf.add_argument("--show", action="store_true", help="Display all configuration keys")
    p_conf.add_argument("--set", nargs="+", help="Set configuration pairs: KEY=VALUE")

    args = parser.parse_args()

    config = AppConfig()
    hdiff_engine = HDiffEngine(config)
    restore_engine = RestoreEngine(config)
    sync_manager = SyncManager(config)

    if not args.command:
        print_banner()
        parser.print_help()
        return 0

    if args.command == "scan":
        return cmd_scan(args, config, hdiff_engine)
    elif args.command == "process":
        return cmd_process(args, config, hdiff_engine)
    elif args.command == "list":
        return cmd_list(args, config, restore_engine)
    elif args.command == "restore":
        return cmd_restore(args, config, restore_engine)
    elif args.command == "sync":
        return cmd_sync(args, config, sync_manager)
    elif args.command == "daemon":
        return cmd_daemon(args, config, hdiff_engine, sync_manager)
    elif args.command == "config":
        return cmd_config(args, config)

if __name__ == "__main__":
    sys.exit(main())
