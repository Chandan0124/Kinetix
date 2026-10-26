# Kinetix ⚡
### High-Speed Phone-to-PC Delta Mirror & Recovery System

**Kinetix** is a high-performance Android backup and restoration workstation engineered for Android 10, 11, 12, 13, 14, 15, 16, and 17+ (HyperOS, OneUI, Pixel OS, OxygenOS). It combines sub-second delta indexing with high-throughput concurrent ADB streaming, real-time speedometer telemetry, and 1:1 directory tree preservation.

---

## Key Features

- **⚡ Sub-Second Delta Indexing:** Scans tens of thousands of files across Android storage in under 1.5 seconds using optimized batched Linux `stat` routines.
- **🔄 Smart Delta Restore:** Pre-scans phone destination folders to skip already identical files byte-for-byte, saving gigabytes of unnecessary USB transfers and flash wear.
- **📊 Pre-Flight Analysis & Comparison:** Live diff comparison before syncing or restoring, displaying exact file counts, sizes, and estimated time saved.
- **📈 Real-Time Telemetry Dashboard:** Speedometer arc gauge with live MB/s readouts, peak speed tracking, rolling file ticker, and ETA countdown.
- **📁 1:1 Directory Structure Preservation:** Pushes restored files directly back to standard Android paths (`/sdcard/DCIM/Camera`, `/sdcard/Music/SpotFlac`, `/sdcard/Android/media/com.whatsapp/WhatsApp/`, etc.).
- **🎵 Automatic MediaScanner Integration:** Triggers Android's `MediaProvider` broadcast upon restore completion so your Music player and Gallery reflect new media immediately without restarting.
- **🛡️ Atomic Writes & Integrity Checks:** Uses atomic `.hyperpart` file staging, strict size validation, and POSIX modification timestamp preservation.
- **🎨 Windows 11 Fluent 2 Dark UI:** Modern responsive dark dashboard designed with translucent glass panels, colored icon outlines, and live status radar.

---

## System Requirements

- **OS:** Windows 10 / 11 (64-bit)
- **Python:** Python 3.10 or higher
- **Android Device:** Android 10 or later with **USB Debugging** enabled in Developer Options
- **Connection:** High-speed USB Cable (Type-C USB 3.0/3.2 recommended) or 5GHz Wi-Fi ADB

---

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/Chandan0124/Kinetix.git
cd Kinetix
```

### 2. Launch with 1-Click Batch Script
Simply double-click:
```cmd
run_app.bat
```
*The batch launcher automatically checks Python, installs missing dependencies, and opens the Kinetix application in your default browser.*

### Alternatively (Manual Launch)
```bash
pip install -r requirements.txt
python app.py
```
Open your browser at: `http://localhost:8000`

---

## Architecture Overview

```
Kinetix/
├── app.py                     # FastAPI REST API + WebSocket live telemetry streaming
├── desktop_app.py             # Optional native desktop window wrapper (PyWebView)
├── run_app.bat                # 1-Click Windows execution launcher
├── requirements.txt           # Python dependencies (FastAPI, Uvicorn, WebSockets)
├── core/
│   ├── adb_manager.py         # Low-level ADB process wrapper & device discovery
│   ├── config.py              # Category schema & global settings
│   ├── delta_engine.py        # Intelligent two-way diff comparison engine
│   ├── indexer.py             # Sub-second remote (Android) & local (PC) file indexers
│   ├── path_sanitizer.py      # Windows NTFS filename & path sanitizer
│   ├── snapshot_inspector.py  # Fast PC backup snapshot inspector & category extractor
│   ├── sms_exporter.py        # SMS & Call logs exporter (JSON/XML/HTML)
│   └── transfer_engine.py     # Concurrent multithreaded push/pull transfer engine
├── web/
│   ├── index.html             # Windows 11 Fluent 2 Dark dashboard
│   ├── styles.css             # Glassmorphic UI theme & telemetry styling
│   └── app.js                 # Frontend orchestration, telemetry hooks & WebSocket client
└── tests/                     # Comprehensive unit test suite
```

---

## License

MIT License. Designed and engineered for high-performance mobile data synchronization.
