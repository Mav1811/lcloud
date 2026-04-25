# Lcloud — User Guide
**Version 0.3** · No cloud · No account · No internet required

---

## What Is Lcloud?

Lcloud backs up your Android phone to your Windows PC over your home WiFi.

- No cables, no accounts, no internet
- Files organized automatically: `Photos/2026/04/`, `WhatsApp/Images/`, etc.
- Restore backed-up files back to your phone at any time
- Completely free and open source

---

## First-Time Setup

### PC App

1. Go to `lcloud-pc/`
2. Double-click `setup.bat` (first time only — installs dependencies)
3. Double-click `run.bat` to start Lcloud
4. Lcloud appears in your **system tray** (bottom-right corner, near the clock)
5. Click the tray icon → **Open Lcloud**
6. Click **Change** to pick your backup folder

You can also just double-click **`Lcloud.exe`** if you downloaded the pre-built binary.

### Android App

Install **`lcloud-android.apk`** on your phone (from the releases section or build from source).

On first launch, grant the storage permission when prompted — Lcloud needs it to read your files.

---

## Running a Backup

1. Make sure your phone and PC are on the **same WiFi network**
2. Start the PC app (or make sure it's already running in the system tray)
3. Open Lcloud on your phone
4. Wait for **"PC Found: [your PC name]"** to appear — usually 2–5 seconds
5. Tap **Backup Now**

Files will stream from your phone to the PC. You'll see progress on both screens.

---

## Restoring Files

1. Open Lcloud on your phone
2. Wait for PC to be found
3. Tap **Restore** (below the Backup Now button)
4. Browse your backup sessions
5. Use the category tabs (Photos / Videos / WhatsApp / Documents) to filter
6. Tap a session to expand it, check the files you want
7. Tap **Restore N files**

**What happens:**
- Files are restored to their exact original location on your phone
- If a file already exists, it is skipped (no overwrite)
- If the original folder is missing, you'll be asked: create it or save to `Lcloud_Restored/` instead

---

## File Organization

Your backup folder looks like this:

```
[Your Backup Folder]/
├── Photos/
│   └── 2026/04/     ← Photos sorted by year and month
├── Videos/
│   └── 2026/04/
├── WhatsApp/
│   ├── Images/
│   ├── Video/
│   ├── Audio/
│   └── Documents/
├── Documents/
│   └── 2026/04/
└── Other/
    └── 2026/04/
```

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| "PC not found" on phone | Phone and PC must be on the same WiFi (not one on 5GHz, one on 2.4GHz bands that are isolated) |
| `setup.bat` fails | Make sure Python 3.12 is installed and added to PATH |
| App won't start | Run `run.bat` from Command Prompt to see error messages |
| Files not visible on Android | Grant "All files access" in phone Settings → Apps → Lcloud → Permissions |
| Restore shows "Not found on PC" | The backed-up file was moved or deleted from the backup folder |

---

## Privacy

- No data ever leaves your home network
- No analytics, no telemetry, no accounts required
- All transfer happens directly between your phone and PC over HTTPS
- Source code: github.com/Mav1811/lcloud

---

## Building from Source

**PC app:**
```bat
cd lcloud-pc
setup.bat       # creates venv, installs deps
run.bat         # start
```

**Android app:**
```bat
cd lcloud-android
flutter run     # build and deploy to connected phone
```

**Run tests:**
```bat
cd lcloud-pc
call venv\Scripts\activate
pytest tests\ -v

cd lcloud-android
flutter test
```

**Build release binaries:**
```bat
build-pc.bat        # → Lcloud.exe (PyInstaller)
build-android.bat   # → lcloud-android.apk
```
