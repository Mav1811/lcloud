import 'dart:io';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/backup_file.dart';
import '../models/backup_session.dart';
import '../services/discovery.dart';
import '../services/file_scanner.dart';
import '../services/transfer_client.dart';
import '../widgets/progress_card.dart';
import '../widgets/status_card.dart' as sc;
import 'restore_screen.dart';
import 'settings_screen.dart';

const Color _bgColor = Color(0xFF1a1a2e);
const Color _cardColor = Color(0xFF16213e);
const Color _accentColor = Color(0xFF4f46e5);
const Color _textSecondary = Color(0xFF94a3b8);

/// Main backup screen.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // Discovery
  sc.ConnectionState _connectionState = sc.ConnectionState.searching;
  DiscoveredPC? _pc;

  // File scan
  List<BackupFile> _filesToBackup = [];
  bool _scanning = false;

  // Backup progress
  bool _backingUp = false;
  String _currentFile = '';
  int _currentIndex = 0;
  int _totalFiles = 0;
  int _bytesTransferred = 0;
  int _totalBytes = 0;

  // History (in-memory for now)
  final List<BackupSession> _sessions = [];

  final LcloudDiscovery _discovery = LcloudDiscovery();
  final FileScanner _scanner = FileScanner();

  @override
  void initState() {
    super.initState();
    _scanFiles();
    _startDiscovery();
  }

  @override
  void dispose() {
    _discovery.stopDiscovery();
    super.dispose();
  }

  // ---------------------------------------------------------------------------
  // Discovery
  // ---------------------------------------------------------------------------

  void _startDiscovery() {
    if (mounted) setState(() => _connectionState = sc.ConnectionState.searching);
    _discovery.startListening(onFound: _onPCFound);
  }

  void _onPCFound(DiscoveredPC pc) {
    if (!mounted) return;
    // Only update state when PC changes (avoids rebuilds every 2 s)
    if (_pc?.address != pc.address || _pc?.fingerprint != pc.fingerprint) {
      setState(() {
        _pc = pc;
        _connectionState = sc.ConnectionState.found;
      });
    }
  }

  // ---------------------------------------------------------------------------
  // File scanning
  // ---------------------------------------------------------------------------

  Future<void> _scanFiles() async {
    setState(() => _scanning = true);
    try {
      final files = await _scanner.scanAll();
      if (mounted) setState(() { _filesToBackup = files; _scanning = false; });
    } catch (_) {
      if (mounted) setState(() => _scanning = false);
    }
  }

  // ---------------------------------------------------------------------------
  // Backup flow
  // ---------------------------------------------------------------------------

  Future<void> _startBackup() async {
    final pc = _pc;
    if (pc == null) {
      _showSnack('No PC found. Make sure Lcloud is running on your PC.');
      return;
    }
    if (_filesToBackup.isEmpty) {
      _showSnack('No files found to back up.');
      return;
    }

    // Build TransferFile list from scanned BackupFiles
    final transferFiles = _filesToBackup.map((f) => TransferFile(
          fileId: f.path.hashCode.toRadixString(16),
          fileName: f.name,
          fileSize: f.sizeBytes,
          fileType: _mimeType(f.name),
          path: f.path,
          category: f.category,
          modifiedAt: f.modifiedAt,
        )).toList();

    final client = TransferClient(
      pcAddress: pc.address,
      pcPort: pc.port,
      fingerprint: pc.fingerprint,
    );

    setState(() {
      _backingUp = true;
      _connectionState = sc.ConnectionState.backingUp;
      _totalFiles = transferFiles.length;
      _totalBytes = transferFiles.fold(0, (s, f) => s + f.fileSize);
      _currentIndex = 0;
      _bytesTransferred = 0;
    });

    final startedAt = DateTime.now();
    String? sessionId;
    final errors = <String>[];

    try {
      // 1. Prepare — send file list, get session + tokens
      final tokens = await client.prepareUpload(
        deviceAlias: Platform.localHostname,
        files: transferFiles,
      );
      sessionId = tokens['__sessionId__']!;

      // 2. Upload each file in priority order
      for (int i = 0; i < transferFiles.length; i++) {
        final file = transferFiles[i];
        final token = tokens[file.fileId];
        if (token == null) {
          errors.add(file.fileName);
          continue;
        }

        if (mounted) {
          setState(() {
            _currentFile = file.fileName;
            _currentIndex = i + 1;
          });
        }

        try {
          // Track bytes from previous files + live progress of current file
          final prevBytes =
              transferFiles.take(i).fold(0, (s, f) => s + f.fileSize);

          await client.uploadFile(
            sessionId: sessionId,
            file: file,
            token: token,
            onProgress: (bytesSent) {
              if (mounted) {
                setState(() => _bytesTransferred = prevBytes + bytesSent);
              }
            },
          );
        } on TransferException catch (e) {
          errors.add(file.fileName);
          if (e.code == 'invalid_token') break; // session broken — stop
        }
      }

      final session = BackupSession(
        startedAt: startedAt,
        completedAt: DateTime.now(),
        filesSaved: transferFiles.length - errors.length,
        bytesTransferred: _bytesTransferred,
        errors: errors,
      );

      if (mounted) {
        setState(() {
          _sessions.insert(0, session);
          if (_sessions.length > 20) _sessions.removeLast();
          _connectionState = sc.ConnectionState.complete;
          _backingUp = false;
        });
        _showDeletePrompt(session);
      }
    } on TransferException catch (e) {
      if (sessionId != null) await client.cancel(sessionId);
      if (mounted) {
        setState(() {
          _connectionState = sc.ConnectionState.error;
          _backingUp = false;
        });
        _showSnack(_friendlyError(e));
      }
    } catch (e) {
      if (sessionId != null) await client.cancel(sessionId);
      if (mounted) {
        setState(() {
          _connectionState = sc.ConnectionState.error;
          _backingUp = false;
        });
        _showSnack('Backup failed: $e');
      }
    }
  }

  String _friendlyError(TransferException e) {
    switch (e.code) {
      case 'disk_full':
        return 'PC storage is full. Free up space and try again.';
      case 'no_backup_folder':
        return 'Open Lcloud on your PC and set a backup folder.';
      case 'invalid_token':
        return 'Connection error. Please try again.';
      default:
        return 'Backup failed (${e.code}). Please try again.';
    }
  }

  String _mimeType(String fileName) {
    final ext = fileName.split('.').last.toLowerCase();
    const types = {
      'jpg': 'image/jpeg',
      'jpeg': 'image/jpeg',
      'png': 'image/png',
      'gif': 'image/gif',
      'heic': 'image/heic',
      'webp': 'image/webp',
      'mp4': 'video/mp4',
      'mov': 'video/quicktime',
      'avi': 'video/x-msvideo',
      'mkv': 'video/x-matroska',
      '3gp': 'video/3gpp',
      'pdf': 'application/pdf',
      'doc': 'application/msword',
      'docx':
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    };
    return types[ext] ?? 'application/octet-stream';
  }

  void _showDeletePrompt(BackupSession session) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('Backup Complete',
            style: TextStyle(color: Colors.white)),
        content: Text(
          '${session.filesSaved} files (${session.sizeLabel}) backed up.\n\n'
          'Delete backed-up files from your phone to free space?',
          style: const TextStyle(color: _textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Keep on Phone',
                style: TextStyle(color: _textSecondary)),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              _showSnack('Delete feature coming in v0.3');
            },
            style:
                ElevatedButton.styleFrom(backgroundColor: _accentColor),
            child: const Text('Delete from Phone',
                style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // UI
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: const Text(
          'Lcloud',
          style: TextStyle(
              color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold),
        ),
        backgroundColor: _bgColor,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings, color: Colors.white),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute<void>(
                  builder: (_) => const SettingsScreen()),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: _backingUp
                ? null
                : () {
                    _discovery.stopDiscovery();
                    setState(() {
                      _connectionState = sc.ConnectionState.searching;
                      _pc = null;
                    });
                    _startDiscovery();
                  },
          ),
        ],
      ),
      body: Column(
        children: [
          sc.StatusCard(
            state: _connectionState,
            pcName: _pc?.name,
            subtitle: null, // no raw IP shown to user
          ),
          _statsRow(),
          if (_backingUp)
            ProgressCard(
              currentFile: _currentFile,
              currentIndex: _currentIndex,
              totalFiles: _totalFiles,
              bytesTransferred: _bytesTransferred,
              totalBytes: _totalBytes,
            ),
          Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton(
                onPressed: (_backingUp || _pc == null) ? null : _startBackup,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _accentColor,
                  disabledBackgroundColor: Colors.white10,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                child: Text(
                  _backingUp ? 'Backing up...' : 'Backup Now',
                  style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: Colors.white),
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: SizedBox(
              width: double.infinity,
              height: 48,
              child: OutlinedButton(
                onPressed: _pc == null
                    ? null
                    : () => Navigator.push(
                          context,
                          MaterialPageRoute<void>(
                            builder: (_) => RestoreScreen(pc: _pc!),
                          ),
                        ),
                style: OutlinedButton.styleFrom(
                  side: BorderSide(
                      color: _pc == null ? Colors.white24 : _accentColor),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                child: Text(
                  'Restore',
                  style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w500,
                      color: _pc == null ? Colors.white24 : _accentColor),
                ),
              ),
            ),
          ),
          Expanded(child: _historyList()),
        ],
      ),
    );
  }

  Widget _statsRow() {
    final totalSize =
        _filesToBackup.fold<int>(0, (s, f) => s + f.sizeBytes);
    final sizeMb = totalSize / (1024 * 1024);
    final lastBackup = _sessions.isNotEmpty
        ? DateFormat('MMM d').format(_sessions.first.completedAt)
        : 'Never';

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding:
          const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _statItem(
              _scanning ? '...' : '${_filesToBackup.length}', 'Files found'),
          _divider(),
          _statItem(
              _scanning ? '...' : '${sizeMb.toStringAsFixed(1)} MB',
              'Total size'),
          _divider(),
          _statItem(lastBackup, 'Last backup'),
        ],
      ),
    );
  }

  Widget _statItem(String value, String label) => Column(
        children: [
          Text(value,
              style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text(label,
              style:
                  const TextStyle(color: _textSecondary, fontSize: 11)),
        ],
      );

  Widget _divider() =>
      Container(height: 30, width: 1, color: Colors.white12);

  Widget _historyList() {
    if (_sessions.isEmpty) {
      return const Center(
        child: Text(
          'No backups yet.\nTap "Backup Now" to start.',
          textAlign: TextAlign.center,
          style: TextStyle(
              color: _textSecondary, fontSize: 14, height: 1.6),
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      itemCount: _sessions.length + 1,
      itemBuilder: (ctx, idx) {
        if (idx == 0) {
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text(
              'Recent Backups',
              style: TextStyle(
                  color: _textSecondary,
                  fontSize: 12,
                  fontWeight: FontWeight.w600),
            ),
          );
        }
        return _sessionTile(_sessions[idx - 1]);
      },
    );
  }

  Widget _sessionTile(BackupSession session) {
    final date = DateFormat('MMM d, HH:mm').format(session.completedAt);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
          color: _cardColor, borderRadius: BorderRadius.circular(12)),
      child: Row(
        children: [
          const Icon(Icons.check_circle,
              color: Color(0xFF22c55e), size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(date,
                    style: const TextStyle(
                        color: Colors.white, fontSize: 13)),
                Text(
                  '${session.filesSaved} files · ${session.sizeLabel}',
                  style: const TextStyle(
                      color: _textSecondary, fontSize: 12),
                ),
              ],
            ),
          ),
          if (session.hadErrors)
            Text(
              '${session.errors.length} error',
              style: const TextStyle(
                  color: Color(0xFFf59e0b), fontSize: 11),
            ),
        ],
      ),
    );
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(message),
      backgroundColor: _cardColor,
      behavior: SnackBarBehavior.floating,
    ));
  }
}
