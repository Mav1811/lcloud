import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/backup_file.dart';
import '../models/backup_session.dart';
import '../services/discovery.dart';
import '../services/file_scanner.dart';
import '../services/http_server.dart';
import '../widgets/progress_card.dart';
import '../widgets/status_card.dart' as sc;
import 'settings_screen.dart';

const Color _bgColor = Color(0xFF1a1a2e);
const Color _cardColor = Color(0xFF16213e);
const Color _accentColor = Color(0xFF4f46e5);
const Color _textSecondary = Color(0xFF94a3b8);

const String _pcPortKey = 'pc_port';
const int _defaultPcPort = 52000;

/// Main backup screen.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  sc.ConnectionState _connectionState = sc.ConnectionState.searching;
  String? _pcName;
  String? _pcAddress;
  int _pcPort = _defaultPcPort;

  List<BackupFile> _filesToBackup = [];
  bool _scanning = false;
  bool _backingUp = false;

  // Progress
  String _currentFile = '';
  int _currentIndex = 0;
  int _totalFiles = 0;
  int _bytesTransferred = 0;
  int _totalBytes = 0;

  // History
  final List<BackupSession> _sessions = [];

  final LcloudDiscovery _discovery = LcloudDiscovery();
  final LcloudHttpServer _fileServer = LcloudHttpServer();
  final FileScanner _scanner = FileScanner();

  @override
  void initState() {
    super.initState();
    _loadPort();
    _startDiscovery();
    _scanFiles();
  }

  @override
  void dispose() {
    _discovery.stopDiscovery();
    _fileServer.stop();
    super.dispose();
  }

  // ---------------------------------------------------------------------------
  // Initialization
  // ---------------------------------------------------------------------------

  Future<void> _loadPort() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() => _pcPort = prefs.getInt(_pcPortKey) ?? _defaultPcPort);
  }

  Future<void> _startDiscovery() async {
    setState(() => _connectionState = sc.ConnectionState.searching);
    final pc = await _discovery.findPC();
    if (pc != null && mounted) {
      setState(() {
        _pcAddress = pc.address;
        _pcPort = pc.port;
        _pcName = pc.name;
        _connectionState = sc.ConnectionState.found;
      });
    }
  }

  Future<void> _scanFiles() async {
    setState(() => _scanning = true);
    try {
      final files = await _scanner.scanAll();
      if (mounted) {
        setState(() {
          _filesToBackup = files;
          _scanning = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _scanning = false);
    }
  }

  // ---------------------------------------------------------------------------
  // Backup flow
  // ---------------------------------------------------------------------------

  Future<void> _startBackup() async {
    if (_pcAddress == null) {
      _showSnack('No PC connected. Make sure PC app is running on the same WiFi.');
      return;
    }
    if (_filesToBackup.isEmpty) {
      _showSnack('No files found to back up.');
      return;
    }

    setState(() {
      _backingUp = true;
      _connectionState = sc.ConnectionState.backingUp;
      _totalFiles = _filesToBackup.length;
      _totalBytes = _filesToBackup.fold(0, (sum, f) => sum + f.sizeBytes);
      _currentIndex = 0;
      _bytesTransferred = 0;
    });

    final startedAt = DateTime.now();

    try {
      // Start the local file server
      await _fileServer.start(_filesToBackup);

      final localIp = await LcloudDiscovery.getLocalIP();
      if (localIp == null) throw Exception('Could not determine local IP address.');

      // Announce to PC
      final announceUrl = 'http://$_pcAddress:$_pcPort/announce';
      final payload = {
        'server_port': LcloudHttpServer.defaultPort,
        'device_ip': localIp,
        'files': _filesToBackup.map((f) => f.toJson()).toList(),
      };

      final response = await http
          .post(
            Uri.parse(announceUrl),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 507) {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        final freeMb = ((body['free_bytes'] as int? ?? 0) / (1024 * 1024)).round();
        final needMb = ((body['needed_bytes'] as int? ?? 0) / (1024 * 1024)).round();
        throw Exception(
          'PC storage is full.\nFree: ${freeMb} MB  ·  Needed: ${needMb} MB\n'
          'Free up space on your PC and try again.',
        );
      }
      if (response.statusCode == 503) {
        throw Exception('PC has no backup folder set.\nOpen Lcloud on your PC and choose a backup folder.');
      }
      if (response.statusCode != 200) {
        throw Exception('PC rejected backup (${response.statusCode}): ${response.body}');
      }

      // PC is now downloading files from our server
      // Poll progress by watching bytesServed
      int filesConfirmed = 0;
      while (_fileServer.isRunning && filesConfirmed < _filesToBackup.length) {
        await Future<void>.delayed(const Duration(milliseconds: 500));
        final served = _fileServer.bytesServed;
        // Estimate files transferred by bytes
        filesConfirmed = (_totalBytes > 0)
            ? ((served / _totalBytes) * _filesToBackup.length).round()
            : 0;

        final currentFileIndex = filesConfirmed.clamp(0, _filesToBackup.length);
        final currentFileName = currentFileIndex < _filesToBackup.length
            ? _filesToBackup[currentFileIndex].name
            : 'Finishing...';

        if (mounted) {
          setState(() {
            _currentIndex = currentFileIndex;
            _currentFile = currentFileName;
            _bytesTransferred = served;
          });
        }

        if (served >= _totalBytes) break;
      }

      await _fileServer.stop();

      final session = BackupSession(
        startedAt: startedAt,
        completedAt: DateTime.now(),
        filesSaved: _filesToBackup.length,
        bytesTransferred: _fileServer.bytesServed,
        errors: [],
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
    } catch (e) {
      await _fileServer.stop();
      if (mounted) {
        setState(() {
          _connectionState = sc.ConnectionState.error;
          _backingUp = false;
        });
        _showSnack('Backup failed: $e');
      }
    }
  }

  void _showDeletePrompt(BackupSession session) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('Backup Complete', style: TextStyle(color: Colors.white)),
        content: Text(
          '${session.filesSaved} files (${session.sizeLabel}) backed up successfully.\n\n'
          'Do you want to delete the backed-up files from your phone to free space?',
          style: const TextStyle(color: _textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Keep on Phone', style: TextStyle(color: _textSecondary)),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              _showSnack('Delete feature coming in v0.3');
            },
            style: ElevatedButton.styleFrom(backgroundColor: _accentColor),
            child: const Text('Delete from Phone', style: TextStyle(color: Colors.white)),
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
          style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold),
        ),
        backgroundColor: _bgColor,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings, color: Colors.white),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute<void>(builder: (_) => const SettingsScreen()),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: _backingUp ? null : _startDiscovery,
          ),
        ],
      ),
      body: Column(
        children: [
          // Status
          sc.StatusCard(
            state: _connectionState,
            pcName: _pcName,
            subtitle: _pcAddress != null ? 'IP: $_pcAddress' : null,
          ),

          // Stats row
          _statsRow(),

          // Progress (only during backup)
          if (_backingUp)
            ProgressCard(
              currentFile: _currentFile,
              currentIndex: _currentIndex,
              totalFiles: _totalFiles,
              bytesTransferred: _bytesTransferred,
              totalBytes: _totalBytes,
            ),

          // Backup Now button
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton(
                onPressed: (_backingUp || _connectionState == sc.ConnectionState.searching)
                    ? null
                    : _startBackup,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _accentColor,
                  disabledBackgroundColor: Colors.white10,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                child: Text(
                  _backingUp ? 'Backing up...' : 'Backup Now',
                  style: const TextStyle(
                      fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white),
                ),
              ),
            ),
          ),

          // History
          Expanded(child: _historyList()),
        ],
      ),
    );
  }

  Widget _statsRow() {
    final totalSize = _filesToBackup.fold<int>(0, (s, f) => s + f.sizeBytes);
    final sizeMb = totalSize / (1024 * 1024);
    final lastBackup = _sessions.isNotEmpty
        ? DateFormat('MMM d').format(_sessions.first.completedAt)
        : 'Never';

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _statItem(
            _scanning ? '...' : '${_filesToBackup.length}',
            'Files found',
          ),
          _divider(),
          _statItem(
            _scanning ? '...' : '${sizeMb.toStringAsFixed(1)} MB',
            'Total size',
          ),
          _divider(),
          _statItem(lastBackup, 'Last backup'),
        ],
      ),
    );
  }

  Widget _statItem(String value, String label) {
    return Column(
      children: [
        Text(value,
            style: const TextStyle(
                color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700)),
        const SizedBox(height: 2),
        Text(label,
            style: const TextStyle(color: _textSecondary, fontSize: 11)),
      ],
    );
  }

  Widget _divider() => Container(
        height: 30,
        width: 1,
        color: Colors.white12,
      );

  Widget _historyList() {
    if (_sessions.isEmpty) {
      return const Center(
        child: Text(
          'No backups yet.\nTap "Backup Now" to start.',
          textAlign: TextAlign.center,
          style: TextStyle(color: _textSecondary, fontSize: 14, height: 1.6),
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
        final session = _sessions[idx - 1];
        return _sessionTile(session);
      },
    );
  }

  Widget _sessionTile(BackupSession session) {
    final date = DateFormat('MMM d, HH:mm').format(session.completedAt);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.check_circle, color: Color(0xFF22c55e), size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(date,
                    style: const TextStyle(color: Colors.white, fontSize: 13)),
                Text(
                  '${session.filesSaved} files · ${session.sizeLabel}',
                  style: const TextStyle(color: _textSecondary, fontSize: 12),
                ),
              ],
            ),
          ),
          if (session.hadErrors)
            Text(
              '${session.errors.length} error',
              style: const TextStyle(color: Color(0xFFf59e0b), fontSize: 11),
            ),
        ],
      ),
    );
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: _cardColor,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}
