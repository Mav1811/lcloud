# Lcloud — Feature Roadmap

## What Makes Lcloud Different

LocalSend, Syncthing, Droid Transfer — they all do file transfer.  
**Lcloud does automatic backup with intelligence.**

| Feature | Lcloud | LocalSend | PhotoSync | Immich |
|---------|--------|-----------|-----------|--------|
| Smart priority (WhatsApp first) | ✅ v0.3 | ❌ | ❌ | ❌ |
| Auto-trigger at low storage | ✅ v0.3 | ❌ | ❌ | ❌ |
| Restore files to original location | ✅ v0.3 | ❌ | ❌ | Partial |
| Secure HTTPS transfer (cert trust) | ✅ v0.2 | ✅ | ✅ | ✅ |
| Organized folders (date/type) | ✅ v0.1 | ❌ | ✅ | ✅ |
| No internet / no cloud | ✅ | ✅ | ✅ | ✅ |
| Open source | ✅ v0.5 | ✅ | ❌ | ✅ |
| Encryption at rest | v0.4 | ❌ | ❌ | ❌ |
| iOS support | Future | ✅ | ✅ | ✅ |
| Free forever | ✅ | ✅ | ❌ (paid auto) | ✅ |

---

## Version Plan

### v0.1 — Prototype ✅ DONE
End-to-end working backup. mDNS discovery (replaced in v0.2). Manual backup only.

### v0.2 — Secure Transport ✅ DONE
Replaced broken mDNS + HTTP pull with LocalSend-inspired multicast UDP + HTTPS push.  
Self-signed cert with fingerprint trust. Real streaming progress. No more Zeroconf.

### v0.3 — Core Features ✅ DONE

**Restore (shipped 2026-04-25):**
- Browse backed-up sessions on phone
- Select files by category/session
- Restore to exact original phone location
- Handles missing folders, skips existing files

**Still to build (pushed to v0.4+):**
- Priority engine (WhatsApp → Photos → Videos → Docs → Other)
- Storage threshold trigger (phone < 15% free → auto-backup starts)
- "Delete after backup" — actually execute the delete
- Duplicate detection (SHA-256 hash — skip already-backed-up files)
- Resume interrupted backups

### v0.4 — Security
- AES-256-GCM encryption for files at rest on PC
- Password protection (PBKDF2 key derivation)
- *(TLS in-transit is already in v0.2)*

### v0.5 — Open Source Release
- Windows background service (auto-start with Windows)
- Full settings screen (port, threshold %, theme)
- Toast notifications on backup complete
- GitHub public release with proper README
- Android APK in GitHub releases

---

## Future (Post v0.5)
- iOS support (Flutter makes this feasible without rewriting)
- Scheduled automatic backups (time-based)
- Selective backup (choose specific folders to include/exclude)
- Multiple PC targets
- NAS / network folder as destination
