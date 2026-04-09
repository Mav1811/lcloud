# Lcloud — User Guide
**Version 0.1.0** | Open Source | No cloud, no account, no internet required

---

## What Is Lcloud?

Lcloud backs up your Android phone to your Windows PC over your home WiFi.  
- No cables needed  
- No internet or cloud accounts  
- Files are organized automatically (Photos, Videos, WhatsApp, Documents)  
- Completely free and open source  

---

## Before You Start — Install These (One Time Only)

### Step 1: Install Python (for the PC app)

1. Download Python 3.12 from: https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe
2. Run the installer
3. **CRITICAL:** Check the box "Add Python to PATH" at the bottom of the first screen
4. Click "Install Now"

To verify: open Command Prompt and type `python --version` — you should see `Python 3.12.x`

---

### Step 2: Set Up the PC App

1. Open File Explorer, go to `H:\fun\lcloud\lcloud-pc\`
2. Double-click `setup.bat`
3. Wait for it to finish (downloads ~50MB of packages)
4. You should see "Setup complete!" at the end

---

### Step 3: Install Flutter (for building the Android app)

1. Go to `H:\fun\lcloud\tools\`
2. Double-click `install_flutter.bat`
3. Wait — this downloads Flutter SDK (~1GB). This is a one-time step.
4. After it finishes, follow the on-screen instructions to add Flutter to PATH

---

### Step 4: Build the Android App

Once Flutter is installed and in PATH:

1. Open Command Prompt
2. Navigate: `cd H:\fun\lcloud\lcloud-android`
3. Run: `flutter pub get` (downloads Dart packages)
4. Connect your Android phone via USB
5. On your phone: Settings → Developer Options → Enable USB Debugging
6. Run: `flutter run` (builds and installs on your phone)

> **Note:** First build takes 5–10 minutes. Subsequent builds are fast.

---

## Using Lcloud

### On Your PC

1. Double-click `H:\fun\lcloud\lcloud-pc\run.bat`
2. Lcloud appears in your **system tray** (bottom-right corner, near the clock)
3. Click the tray icon → "Open Lcloud" to see the main window
4. First time: click **"Change"** to select your backup folder

### On Your Phone

1. Open the Lcloud app
2. The app will scan your files and search for your PC on WiFi
3. When it says **"PC Found: [your PC name]"** — you're connected
4. Tap **"Backup Now"** to start

### Automatic Backup
(Coming in v0.2) — When your phone storage drops below 15%, backup starts automatically.

---

## File Organization

Your files are organized like this on the PC:

```
[Your Backup Folder]/
├── Photos/2025/04/   ← Photos by year and month
├── Videos/2025/04/
├── WhatsApp/Images/  ← WhatsApp media (images, video, audio, docs)
├── Documents/2025/
└── Other/2025/
```

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| "PC not found" on phone | Make sure phone and PC are on the same WiFi network |
| setup.bat fails with Python error | Make sure Python is installed and "Add to PATH" was checked |
| App won't start | Run `run.bat` from Command Prompt to see error messages |
| Files not found on Android | Grant "All files access" permission in phone settings → Apps → Lcloud |
| Flutter build fails | Run `flutter doctor` and fix any issues it reports |

---

## Privacy

- No data ever leaves your home network
- No analytics, no telemetry, no accounts
- All file transfer happens directly between your phone and PC
- Source code is fully open at: github.com/lcloud-app/lcloud (coming in v0.5)

---

## Version History

| Version | What's new |
|---------|-----------|
| 0.1.0 | First working prototype: manual backup, file organization, PC/phone connection |
| 0.2.0 | Smart priority, storage trigger, delete-after-backup (coming soon) |
| 0.3.0 | Duplicate detection, resume, backup history |
| 0.4.0 | Encryption |
| 0.5.0 | GitHub open source release |
