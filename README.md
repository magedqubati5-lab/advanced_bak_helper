# HDiff Backup Pro - SQL Server Differential Backup Manager

A high-performance, compressed differential backup management system powered by **HDiffPatch** (`hdiffz` and `hpatchz`). Engineered specifically for binary backup files such as Microsoft SQL Server (`.bak`) dumps that exhibit high structural similarity across successive cycles.

Features a modern **CustomTkinter** dark-mode GUI, Windows System Tray integration with dynamic status icons, AES-256 encryption with RSA-2048 dual-key signing for cloud synchronization (Google Drive Desktop / Synced Folders, FTP, and Google Drive API), a full **CLI interface**, and on-the-fly slim reference chaining.

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
- **Slim Reference Chaining (`.ref/`) & Depth Limiting**:
  - The initial reference baseline is compressed as `[HASH]-ref001.zip`.
  - Subsequent references (`ref002`, `ref003`, etc.) are stored as slim delta patches (`[HASH]-ref001-ref002.hdiff`).
  - **Reference Chain Depth Limiting**: `max_chain_length` caps the maximum hop distance from baseline to any reference.
  - **Configurable Chain Reset Strategies**:
    1. **Direct Root Delta (Default)**: When max depth is reached (e.g., at `ref010`), `ref011` is derived directly from root `ref001` (`ref001-ref011.hdiff`), resetting depth to 1.
    2. **Standalone Base ZIP Option**: Optionally create a new standalone baseline ZIP archive (e.g., `ref011.zip`), starting a completely independent reference branch.
- **Differential File Output Naming**:
  - Processed `.hdiff` files are placed directly in the `output` directory:
    `[original_name].[MD5].[active_ref].hdiff` (e.g. `AdventureWorks.bak.a1b2c3d4e5f6...ref001.hdiff`).
- **Interactive Restore Center with 100% MD5 Verification**:
  - Searchable, sortable table of all restorable backups.
  - Automatically reconstructs any target backup through its reference chain using `hpatchz`.
  - Performs post-restoration chunked MD5 calculation and validates integrity against the recorded hash.
- **AES-256 Encryption & RSA-2048 Digital Signing**:
  - Pre-upload encryption using AES-256 (Fernet with PBKDF2 key derivation).
  - Dual-key asymmetric signing using RSA-2048 (PSS with SHA-256).
  - Full synchronization of both `output/` backups and `.ref/` chain archives.
  - Smart skipping: only uploads new files and latest manifest without redundant re-uploads.
- **Zero-Setup Cloud Synchronization**:
  - **GDrive Desktop / Synced Folders (Easiest)**: Zero API setup. Point directly to `G:\My Drive\Backups`, OneDrive, Dropbox, or a network share.
  - **FTP / FTPS Server**: Direct file transfer to standard FTP servers with nested path support.
  - **Google Drive API**: Headless authentication using Service Account JSON keys.
- **Background System Tray & Status Indicators**:
  - **Double-click** the tray icon to restore the main window.
  - **Dynamic Status Colors**: 🟢 Full Green mask when periodic daemon is running; 🔴 Full Red mask when stopped.
  - **Hover Tooltips**: Live scheduler status displayed on mouse hover.
  - Silent background execution (`subprocess.CREATE_NO_WINDOW`) with zero CMD window flashes.
- **Unified Binary / Dual GUI & CLI Support**:
  - `main.py` seamlessly executes both the GUI/Tray and all CLI subcommands (`scan`, `process`, `restore`, `sync`, `daemon`, `config`).
  - Supports compilation to a standalone `.exe` using PyInstaller.

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
   - "Enable/Stop Periodic Daemon" toggle with live button state synchronization.
2. **🔄 Restore**:
   - Searchable and sortable table of all available backups.
   - Filter by name, ref tag, or MD5 hash.
   - Sort by Newest, Oldest, Name, Size, or Ref Tag.
   - Choose destination folder on restore.
   - Real-time integrity validation badge (✅ 100% MD5 Matched).
3. **☁️ Cloud Sync**:
   - Select provider (GDrive Desktop Synced Folder, FTP, or Google Drive API).
   - Test remote connection / sync folder.
   - Encrypt, sign, and upload output backups (including `.ref/` and manifest).
   - Download, verify signatures, and decrypt backups.
4. **⚙️ Settings**:
   - Configure input and output paths.
   - Set max differential patch size (MB) and max chain depth limit.
   - Toggle Standalone Base ZIP reset strategy.
   - Configure scheduler interval (minutes) and auto-start switch.
   - Toggle automatic cloud sync after scheduled backups.
   - Set encryption password and cloud credentials.

---

## 💻 Command Line Interface (CLI)

Use `main.py <command>` (or `cli.py <command>`) to perform all actions directly from the terminal:

### 1. Scan Input Directory
```bash
python main.py scan
python main.py scan --input "C:/sql_backups" --output "C:/compressed_out"
```

### 2. Execute Differential Backup
```bash
python main.py process
python main.py process --max-size 500 --max-chain 10
```

### 3. List Restorable Backups
```bash
python main.py list
```

### 4. Restore a Backup
```bash
python main.py restore --file "output_backups/MyDB.bak.a1b2c3d4...ref001.hdiff" --dest "C:/restored_db"
```

### 5. Cloud Synchronization
```bash
# Upload and encrypt output files and .ref/ directory (skips already existing files)
python main.py sync upload

# Download and verify remote files
python main.py sync download
```

### 6. Run Scheduler Daemon in Console
```bash
python main.py daemon --interval 30
```

### 7. Manage Configuration
```bash
# Show configuration
python main.py config --show

# Set configuration keys
python main.py config --set input_dir="C:/sql_backups" output_dir="C:/compressed_out" auto_schedule_enabled=true
```

---

## 📦 Building Executable with PyInstaller (Unified Single EXE)

You can package the entire application into a standalone executable (`.exe`) that works seamlessly in **both GUI/Tray and CLI modes**:

### 1. Install PyInstaller
```bash
pip install pyinstaller
```

### 2. Build the Executable
Run the following build command in PowerShell / Terminal:
```bash
pyinstaller --noconfirm --onedir --windowed `
    --name "HDiffBackupPro" `
    --add-data "bin;bin" `
    --add-data "assets;assets" `
    --icon "assets/app_icon.jpg" `
    main.py
```
*(Or use `--onefile` if you prefer a single `.exe` file).*

### 3. Running the Compiled Executable:
- **GUI Mode**: Double-click `HDiffBackupPro.exe` (or run without arguments).
- **Tray Mode**: `HDiffBackupPro.exe --tray` (runs minimized in system tray).
- **CLI Mode**: Run directly in CMD or PowerShell:
  ```cmd
  HDiffBackupPro.exe scan
  HDiffBackupPro.exe process
  HDiffBackupPro.exe list
  HDiffBackupPro.exe restore --file "output/db.bak...hdiff" --dest "C:/restored"
  HDiffBackupPro.exe sync upload
  HDiffBackupPro.exe config --show
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
   *(Or point to `HDiffBackupPro.exe --tray` if using the compiled executable).*
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
   - Program/script: `pythonw.exe` (or `HDiffBackupPro.exe`)
   - Add arguments: `"C:\path\to\advanced_bak_helper\main.py" --tray` (or `--tray`)
   - Start in: `C:\path\to\advanced_bak_helper`
6. Click **OK**.

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
Validates the full cycle: differential compression, reference chain depth limiting, standalone base ZIP reset, decompression, MD5 matching, full `.ref` cloud sync, smart skipping of existing cloud files, AES-256 encryption, RSA digital signing, and signature rejection upon tampering.
