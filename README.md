# HDiff Backup Pro - SQL Server Differential Backup Manager

A high-performance, compressed differential backup management system powered by **HDiffPatch** (`hdiffz` and `hpatchz`). Engineered specifically for binary backup files such as Microsoft SQL Server (`.bak`) dumps that exhibit high structural similarity across successive cycles.

Features a modern **CustomTkinter** dark-mode GUI, Windows System Tray integration, AES-256 encryption with RSA-2048 dual-key signing for cloud synchronization (Google Drive Desktop / Synced Folders, FTP, and Google Drive API), a full **CLI interface**, and on-the-fly slim reference chaining.

---

## ⚙️ Binary Executables (`hdiffz` & `hpatchz` Setup)

The core differential compression and decompression engines require the official compiled binaries of `hdiffz` and `hpatchz`.

### 📥 Sourcing Binaries from GitHub Releases:
You can obtain precompiled official release binaries directly from the **[HDiffPatch Official GitHub Releases Page](https://github.com/sisong/HDiffPatch/releases)**.

| Operating System | GitHub Release Package | Target Binary Names | Recommended Location |
| :--- | :--- | :--- | :--- |
| **Windows (x64)** | `hdiffpatch_vX.X.X_bin_windows64.zip` | `hdiffz.exe`, `hpatchz.exe` | Place inside `./bin/` or add to system `PATH` |
| **Linux (x64)** | `hdiffpatch_vX.X.X_bin_linux64.zip` | `hdiffz`, `hpatchz` | Place inside `./bin/` or `/usr/local/bin/` |
| **macOS (x64/ARM)** | `hdiffpatch_vX.X.X_bin_macos.zip` | `hdiffz`, `hpatchz` | Place inside `./bin/` or `/usr/local/bin/` |

> [!TIP]
> **Resolution Priority in the App**:
> The application automatically discovers the binaries in this order:
> 1. Custom path configured in **Settings** (`settings.json`).
> 2. Local project `./bin/` folder (`bin/hdiffz.exe`, `bin/hpatchz.exe` or `bin/hdiffz`, `bin/hpatchz`).
> 3. Global System **`PATH`** environment variable (e.g. `C:\Windows\System32`, `/usr/local/bin`, `/usr/bin`).

---

## 🌟 Key Features

- **Extreme Compression via HDiffPatch**: Uses binary differential deltas (`hdiffz -c-zstd`) to produce ultra-compact `.hdiff` backup files (often reducing multi-gigabyte daily backups by 90%+).
- **Slim Reference Chaining (`.ref/`)**:
  - The initial reference baseline is compressed as `[HASH]-ref001.zip`.
  - Subsequent references (`ref002`, `ref003`, etc.) are stored exclusively as slim delta patches (`[HASH]-ref001-ref002.hdiff`).
  - No large uncompressed files are kept permanently in `.ref/`. References are materialized on the fly during patching and restoration.
- **Differential File Output Naming**:
  - Processed `.hdiff` files are placed directly in the `output` directory:
    `[original_name].[MD5].[active_ref].hdiff` (e.g. `AdventureWorks.bak.a1b2c3d4e5f6...ref001.hdiff`).
- **Dynamic Reference Promotion Thresholds**:
  - Automatically promotes to a new reference when the latest differential patch exceeds the **Max File Size Limit** (MB) or when the chain reaches the **Max Chain Length** (e.g., 10 deltas).
  - The size threshold applies strictly to processed differential files, never to baseline `.ref/` archives.
- **Interactive Restore Center with 100% MD5 Verification**:
  - Searchable, sortable table of all restorable backups.
  - Automatically reconstructs any target backup through its reference chain using `hpatchz`.
  - Performs post-restoration chunked MD5 calculation and validates integrity against the recorded hash.
- **AES-256 Encryption & RSA-2048 Digital Signing**:
  - Pre-upload encryption using AES-256 (Fernet with PBKDF2 key derivation).
  - Dual-key asymmetric signing using RSA-2048 (PSS with SHA-256).
  - Tamper detection on download: alerts user upon digital signature mismatch with option to proceed with valid password.
- **Zero-Setup Cloud Synchronization**:
  - **GDrive Desktop / Synced Folders (Easiest)**: Zero API setup. Point directly to `G:\My Drive\Backups`, OneDrive, Dropbox, or a network share. Files are automatically encrypted & signed locally and synced to the cloud.
  - **FTP / FTPS Server**: Direct file transfer to standard FTP servers.
  - **Google Drive API**: Headless authentication using Service Account JSON keys.
- **Modern GUI & Background System Tray**:
  - CustomTkinter dark theme interface.
  - Runs minimized in the system tray beside the system clock with autostart support.
- **Full-Featured CLI**:
  - Complete command-line interface for automation, server scripts, and CI/CD pipelines.

---

## 📁 System Architecture & Reference Chain Design

```
output_backups/
├── .ref/                                        # Reference Baseline Chain
│   ├── [HASH]-ref001.zip                        # Initial base reference (compressed)
│   ├── [HASH]-ref001-ref002.hdiff               # Slim delta from ref001 to ref002
│   ├── [HASH]-ref002-ref003.hdiff               # Slim delta from ref002 to ref003
│   └── manifest.json                            # State & chain ledger
│
├── DB_2026-08-01.bak.[MD5].ref001.hdiff         # Differential delta against ref001
├── DB_2026-08-02.bak.[MD5].ref001.hdiff         # Differential delta against ref001
└── DB_2026-08-03.bak.[MD5].ref002.hdiff         # Differential delta against ref002
```

---

## 🚀 Installation & Requirements

### 1. Requirements
- Python 3.10+ (Tested on Python 3.13)
- Windows / Linux / macOS

### 2. Dependencies
Install required Python libraries:
```bash
pip install customtkinter pillow pystray cryptography
```

The official Windows x64 binaries for `hdiffz.exe` and `hpatchz.exe` (v5.1.3) are included in the `bin/` directory. For Linux or macOS, download the respective archive from [HDiffPatch Releases](https://github.com/sisong/HDiffPatch/releases) and place `hdiffz` and `hpatchz` into `./bin/` (or your system `PATH`).

---

## 🖥️ Graphical User Interface (GUI)

Launch the GUI by running:
```bash
python main.py
```

### GUI Tabs:
1. **📊 Processing**:
   - Status summary cards (Pending, Processed, Active Reference, Scheduler status) updating in real time.
   - "Scan Directories" button to check folders.
   - "Start Differential Backup" button with real-time progress bar.
   - "Stop Processing" button to cancel running operations gracefully at any time.
   - "Enable/Stop Periodic Daemon" toggle.
2. **🔄 Restore**:
   - Searchable and sortable table of all available backups.
   - Filter by name, ref tag, or MD5 hash.
   - Sort by Newest, Oldest, Name, Size, or Ref Tag.
   - Choose destination folder on restore.
   - Real-time integrity validation badge (✅ 100% MD5 Matched).
3. **☁️ Cloud Sync**:
   - Select provider (GDrive Desktop Synced Folder, FTP, or Google Drive API).
   - Test remote connection / sync folder.
   - Encrypt, sign, and upload output backups.
   - Download, verify signature, and decrypt backups.
4. **⚙️ Settings**:
   - Configure input and output paths.
   - Set max differential patch size (MB) and max chain length.
   - Configure scheduler interval (minutes).
   - Set encryption password and cloud credentials.

---

## 💻 Command Line Interface (CLI)

Use `cli.py` (or `main.py <command>`) to perform all actions from the terminal:

### 1. Scan Input Directory
```bash
python cli.py scan
python cli.py scan --input "C:/sql_backups" --output "C:/compressed_out"
```

### 2. Execute Differential Backup
```bash
python cli.py process
python cli.py process --max-size 500 --max-chain 10
```

### 3. List Restorable Backups
```bash
python cli.py list
```

### 4. Restore a Backup
```bash
python cli.py restore --file "output_backups/MyDB.bak.a1b2c3d4...ref001.hdiff" --dest "C:/restored_db"
```

### 5. Cloud Synchronization
```bash
# Upload and encrypt output files
python cli.py sync upload

# Download and verify remote file
python cli.py sync download --file "MyDB.bak.enc" --dest "C:/restored"
```

### 6. Run Scheduler Daemon in Console
```bash
python cli.py daemon --interval 30
```

### 7. Manage Configuration
```bash
# Show configuration
python cli.py config --show

# Set configuration keys
python cli.py config --set input_dir="C:/sql_backups" output_dir="C:/compressed_out"
```

---

## ⏰ Auto-Start on System Boot (Running in Background / System Tray)

You can configure the application to automatically start when your computer boots up or when you log in, running quietly in the system tray beside the system clock.

### 🪟 Windows Configuration

#### Method 1: Windows Startup Folder (Easiest)
1. Press `Win + R`, type `shell:startup`, and press **Enter**.
2. Right-click inside the folder, select **New > Shortcut**.
3. In the location field, enter:
   ```cmd
   pythonw.exe "C:\path\to\advanced_bak_helper\main.py" --tray
   ```
   *(Note: `pythonw.exe` runs Python in background mode without opening an empty black command prompt window).*
4. Set the "Start in" property of the shortcut to `C:\path\to\advanced_bak_helper`.
5. Click **Finish**.

#### Method 2: Windows Task Scheduler (Recommended for Servers)
1. Open **Task Scheduler** (`taskschd.msc`).
2. Click **Create Task...**
3. On the **General** tab:
   - Name: `HDiff Backup Daemon`
   - Check: `Run with highest privileges`
4. On the **Triggers** tab:
   - New Trigger: `At log on` (or `At startup`).
5. On the **Actions** tab:
   - Action: `Start a program`
   - Program/script: `pythonw.exe`
   - Add arguments: `"C:\path\to\advanced_bak_helper\main.py" --tray`
   - Start in: `C:\path\to\advanced_bak_helper`
6. Click **OK**.

---

### 🐧 Linux Configuration (Ubuntu / Debian / RHEL / Arch)

#### Method 1: Systemd User Service (Recommended)
1. Create the systemd user service directory:
   ```bash
   mkdir -p ~/.config/systemd/user
   ```
2. Create `~/.config/systemd/user/hdiff-backup.service`:
   ```ini
   [Unit]
   Description=HDiff SQL Server Backup Daemon
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/home/username/advanced_bak_helper
   ExecStart=/usr/bin/python3 cli.py daemon --interval 60
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=default.target
   ```
3. Enable and start the service:
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable --now hdiff-backup.service
   ```

#### Method 2: Desktop Autostart (GUI Tray Mode)
Create `~/.config/autostart/hdiff-backup.desktop`:
```ini
[Desktop Entry]
Type=Application
Name=HDiff Backup Pro
Exec=python3 /home/username/advanced_bak_helper/main.py --tray
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
```

---

### 🍎 macOS Configuration

#### Method 1: Launchd User Agent (Recommended)
1. Create `~/Library/LaunchAgents/com.hdiff.backup.plist`:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.hdiff.backup</string>
       <key>ProgramArguments</key>
       <array>
           <string>/usr/local/bin/python3</string>
           <string>/Users/username/advanced_bak_helper/main.py</string>
           <string>--tray</string>
       </array>
       <key>WorkingDirectory</key>
       <string>/Users/username/advanced_bak_helper</string>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
   </dict>
   </plist>
   ```
2. Load the agent:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.hdiff.backup.plist
   ```

---

## 🔒 Security Model

- **Symmetric Encryption**: AES-256 (Fernet) with dynamic 16-byte random salt per file and PBKDF2-HMAC-SHA256 (100,000 iterations).
- **Asymmetric Signature**: RSA-2048 with PSS padding (SHA-256 digest).
- **Integrity Validation**: Post-decompression MD5 verification guarantees bit-by-bit restoration fidelity.

---

## 🧪 Automated Testing

Run the automated test suite:
```bash
python test_system.py
```
Validates the full cycle: differential compression, slim reference chaining, decompression, MD5 matching, AES-256 encryption, RSA digital signing, and signature rejection upon tampering.
