import 'dart:io';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/restore_session.dart';
import '../services/discovery.dart';
import '../services/restore_client.dart';
import '../widgets/progress_card.dart';

const Color _bgColor = Color(0xFF1a1a2e);
const Color _cardColor = Color(0xFF16213e);
const Color _accentColor = Color(0xFF4f46e5);
const Color _textSecondary = Color(0xFF94a3b8);

enum _Phase { listing, restoring, done }

/// Full restore UI — browse sessions, pick files, restore to original location.
class RestoreScreen extends StatefulWidget {
  const RestoreScreen({super.key, required this.pc});

  final DiscoveredPC pc;

  @override
  State<RestoreScreen> createState() => _RestoreScreenState();
}

class _RestoreScreenState extends State<RestoreScreen> {
  late final RestoreClient _client;

  _Phase _phase = _Phase.listing;
  List<RestoreSession> _sessions = [];
  bool _loading = true;
  String? _error;

  // Category filter — null means "all"
  String? _category;

  // Expandable session rows
  final Set<String> _expanded = {};
  final Map<String, List<RestoreFile>> _filesBySession = {};
  final Map<String, Map<String, String>> _tokensBySession = {};

  // File selection (fileId)
  final Set<String> _selected = {};

  // Restore progress
  String _currentFile = '';
  int _currentIndex = 0;
  int _totalToRestore = 0;
  int _bytesTransferred = 0;
  int _totalBytes = 0;

  // End-of-restore results
  int _restoredCount = 0;
  int _skippedCount = 0;
  final List<RestoreFile> _failedFiles = [];

  // Missing folder decisions: folderPath → 'create' | 'fallback'
  final Map<String, String> _folderDecisions = {};

  @override
  void initState() {
    super.initState();
    _client = RestoreClient(
      pcAddress: widget.pc.address,
      pcPort: widget.pc.port,
      fingerprint: widget.pc.fingerprint,
    );
    _loadSessions();
  }

  // ---------------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------------

  Future<void> _loadSessions() async {
    setState(() { _loading = true; _error = null; });
    try {
      final sessions = await _client.getSessions();
      if (mounted) setState(() { _sessions = sessions; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _toggleExpand(String sessionId) async {
    if (_expanded.contains(sessionId)) {
      setState(() => _expanded.remove(sessionId));
      return;
    }
    setState(() => _expanded.add(sessionId));
    if (!_filesBySession.containsKey(sessionId)) {
      await _loadFiles(sessionId);
    }
  }

  Future<void> _loadFiles(String sessionId) async {
    try {
      final listing = await _client.getFiles(sessionId, category: _category);
      if (mounted) {
        setState(() {
          _filesBySession[sessionId] = listing.files;
          _tokensBySession[sessionId] = listing.tokens;
        });
      }
    } catch (e) {
      if (mounted) {
        _showSnack('Could not load files: $e');
      }
    }
  }

  Future<void> _onCategoryChanged(String? category) async {
    setState(() {
      _category = category;
      _filesBySession.clear();
      _tokensBySession.clear();
      _selected.clear();
    });
    for (final sessionId in List.of(_expanded)) {
      await _loadFiles(sessionId);
    }
  }

  // ---------------------------------------------------------------------------
  // Selection
  // ---------------------------------------------------------------------------

  void _toggleFile(String fileId, bool? checked) {
    setState(() {
      if (checked == true) {
        _selected.add(fileId);
      } else {
        _selected.remove(fileId);
      }
    });
  }

  void _selectAll(String sessionId) {
    final files = _filesBySession[sessionId] ?? [];
    final availableIds = files
        .where((f) => f.available)
        .map((f) => f.fileId)
        .toList();
    setState(() {
      final allSelected = availableIds.every(_selected.contains);
      if (allSelected) {
        _selected.removeAll(availableIds);
      } else {
        _selected.addAll(availableIds);
      }
    });
  }

  int get _selectedCount => _selected.length;

  // ---------------------------------------------------------------------------
  // Restore flow
  // ---------------------------------------------------------------------------

  Future<void> _startRestore() async {
    final toRestore = <String, List<RestoreFile>>{};
    for (final entry in _filesBySession.entries) {
      final sessionFiles = entry.value
          .where((f) => _selected.contains(f.fileId) && f.available)
          .toList();
      if (sessionFiles.isNotEmpty) {
        toRestore[entry.key] = sessionFiles;
      }
    }
    if (toRestore.isEmpty) return;

    setState(() {
      _phase = _Phase.restoring;
      _restoredCount = 0;
      _skippedCount = 0;
      _failedFiles.clear();
      _folderDecisions.clear();
      _currentFile = '';
      _currentIndex = 0;
      _totalToRestore = toRestore.values.fold(0, (s, l) => s + l.length);
      _totalBytes = toRestore.values
          .expand((l) => l)
          .fold(0, (s, f) => s + f.sizeBytes);
      _bytesTransferred = 0;
    });

    int index = 0;
    for (final sessionEntry in toRestore.entries) {
      final sessionId = sessionEntry.key;
      final files = sessionEntry.value;

      RestoreFileListing listing;
      try {
        listing = await _client.getFiles(sessionId, category: _category);
      } catch (e) {
        for (final f in files) {
          if (mounted) setState(() => _failedFiles.add(f));
        }
        continue;
      }

      for (final file in files) {
        index++;
        final token = listing.tokens[file.fileId];
        if (token == null) {
          if (mounted) setState(() { _failedFiles.add(file); _currentIndex = index; });
          continue;
        }

        if (mounted) setState(() { _currentFile = file.fileName; _currentIndex = index; });

        final destPath = await _resolveDestination(file);
        if (destPath == null) {
          if (mounted) setState(() => _skippedCount++);
          continue;
        }

        try {
          await _client.downloadFile(
            sessionId: sessionId,
            fileId: file.fileId,
            token: token,
            destPath: destPath,
            onProgress: (bytes) {
              if (mounted) setState(() => _bytesTransferred += bytes);
            },
          );
          if (mounted) setState(() => _restoredCount++);
        } on RestoreException {
          if (mounted) setState(() => _failedFiles.add(file));
        } catch (_) {
          if (mounted) setState(() => _failedFiles.add(file));
        }
      }
    }

    if (mounted) setState(() => _phase = _Phase.done);
  }

  Future<String?> _resolveDestination(RestoreFile file) async {
    final originalPath = file.originalPath;

    if (await File(originalPath).exists()) return null;

    final parentPath = _parentDir(originalPath);
    if (await Directory(parentPath).exists()) return originalPath;

    if (!_folderDecisions.containsKey(parentPath)) {
      if (!mounted) return null;
      final decision = await _showFolderDialog(parentPath, file.category);
      _folderDecisions[parentPath] = decision;
    }

    if (_folderDecisions[parentPath] == 'create') {
      return originalPath;
    } else {
      return '/storage/emulated/0/Lcloud_Restored/${file.category}/${_basename(originalPath)}';
    }
  }

  Future<String> _showFolderDialog(String folderPath, String category) async {
    final result = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text(
          'Folder Missing',
          style: TextStyle(color: Colors.white),
        ),
        content: Text(
          'The original folder does not exist:\n$folderPath\n\n'
          'What should Lcloud do?',
          style: const TextStyle(color: _textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop('fallback'),
            child: const Text(
              'Use Lcloud_Restored/',
              style: TextStyle(color: _textSecondary),
            ),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop('create'),
            style: ElevatedButton.styleFrom(backgroundColor: _accentColor),
            child: const Text(
              'Create Folder',
              style: TextStyle(color: Colors.white),
            ),
          ),
        ],
      ),
    );
    return result ?? 'fallback';
  }

  // ---------------------------------------------------------------------------
  // UI helpers
  // ---------------------------------------------------------------------------

  String _parentDir(String path) {
    final i = path.lastIndexOf('/');
    return i > 0 ? path.substring(0, i) : '/';
  }

  String _basename(String path) {
    final i = path.lastIndexOf('/');
    return i >= 0 ? path.substring(i + 1) : path;
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(message),
      backgroundColor: _cardColor,
      behavior: SnackBarBehavior.floating,
    ));
  }

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: const Text(
          'Restore',
          style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
        ),
        backgroundColor: _bgColor,
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
        actions: [
          if (_phase == _Phase.listing)
            IconButton(
              icon: const Icon(Icons.refresh, color: Colors.white),
              onPressed: _loadSessions,
            ),
        ],
      ),
      body: _phase == _Phase.done
          ? _buildSummary()
          : Column(
              children: [
                if (_phase == _Phase.listing) _buildCategoryTabs(),
                if (_phase == _Phase.restoring)
                  ProgressCard(
                    currentFile: _currentFile,
                    currentIndex: _currentIndex,
                    totalFiles: _totalToRestore,
                    bytesTransferred: _bytesTransferred,
                    totalBytes: _totalBytes,
                  ),
                Expanded(child: _buildBody()),
                if (_phase == _Phase.listing) _buildRestoreButton(),
              ],
            ),
    );
  }

  Widget _buildCategoryTabs() {
    const cats = [
      (null, 'All'),
      ('photo', 'Photos'),
      ('video', 'Videos'),
      ('whatsapp', 'WhatsApp'),
      ('document', 'Documents'),
    ];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: cats.map((c) {
          final selected = _category == c.$1;
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChoiceChip(
              label: Text(c.$2),
              selected: selected,
              onSelected: (_) => _onCategoryChanged(c.$1),
              selectedColor: _accentColor,
              backgroundColor: _cardColor,
              labelStyle: TextStyle(
                color: selected ? Colors.white : _textSecondary,
                fontSize: 13,
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: _accentColor));
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.wifi_off, color: _textSecondary, size: 48),
              const SizedBox(height: 16),
              const Text(
                'Connect to PC first',
                style: TextStyle(color: Colors.white, fontSize: 16),
              ),
              const SizedBox(height: 8),
              ElevatedButton(
                onPressed: _loadSessions,
                style: ElevatedButton.styleFrom(backgroundColor: _accentColor),
                child: const Text('Retry', style: TextStyle(color: Colors.white)),
              ),
            ],
          ),
        ),
      );
    }
    if (_sessions.isEmpty) {
      return const Center(
        child: Text(
          'No backups yet.\nRun a backup first.',
          textAlign: TextAlign.center,
          style: TextStyle(color: _textSecondary, fontSize: 14, height: 1.6),
        ),
      );
    }
    if (_phase == _Phase.restoring) {
      return const Center(
        child: Text(
          'Restoring files...',
          style: TextStyle(color: _textSecondary, fontSize: 14),
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      itemCount: _sessions.length,
      itemBuilder: (_, i) => _buildSessionTile(_sessions[i]),
    );
  }

  Widget _buildSessionTile(RestoreSession session) {
    final expanded = _expanded.contains(session.sessionId);
    final files = _filesBySession[session.sessionId] ?? [];
    final date = DateFormat('MMM d, HH:mm').format(session.completedAt);

    final sessionSelected = files
        .where((f) => f.available && _selected.contains(f.fileId))
        .length;
    final sessionAvailable = files.where((f) => f.available).length;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: () => _toggleExpand(session.sessionId),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(date,
                            style: const TextStyle(color: Colors.white, fontSize: 13)),
                        const SizedBox(height: 2),
                        Text(
                          '${session.fileCount} files · ${session.sizeLabel} · ${session.deviceAlias}',
                          style: const TextStyle(color: _textSecondary, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                  if (expanded && sessionAvailable > 0)
                    TextButton(
                      onPressed: () => _selectAll(session.sessionId),
                      child: Text(
                        sessionSelected == sessionAvailable ? 'Deselect All' : 'Select All',
                        style: const TextStyle(color: _accentColor, fontSize: 12),
                      ),
                    ),
                  Icon(
                    expanded ? Icons.expand_less : Icons.expand_more,
                    color: _textSecondary,
                  ),
                ],
              ),
            ),
          ),
          if (expanded) ...[
            const Divider(height: 1, color: Colors.white10),
            if (files.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Center(
                  child: CircularProgressIndicator(color: _accentColor, strokeWidth: 2),
                ),
              )
            else
              ...files.map((f) => _buildFileTile(session.sessionId, f)),
          ],
        ],
      ),
    );
  }

  Widget _buildFileTile(String sessionId, RestoreFile file) {
    final selected = _selected.contains(file.fileId);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      child: Row(
        children: [
          Icon(_categoryIcon(file.category),
              color: file.available ? _accentColor : _textSecondary, size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  file.fileName,
                  style: TextStyle(
                    color: file.available ? Colors.white : _textSecondary,
                    fontSize: 13,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  file.available ? file.sizeLabel : 'Not found on PC',
                  style: const TextStyle(color: _textSecondary, fontSize: 11),
                ),
              ],
            ),
          ),
          if (file.available)
            Checkbox(
              value: selected,
              onChanged: (v) => _toggleFile(file.fileId, v),
              activeColor: _accentColor,
              side: const BorderSide(color: _textSecondary),
            )
          else
            const SizedBox(width: 24),
        ],
      ),
    );
  }

  IconData _categoryIcon(String category) {
    switch (category) {
      case 'photo':
        return Icons.photo;
      case 'video':
        return Icons.videocam;
      case 'whatsapp':
        return Icons.chat;
      case 'document':
        return Icons.description;
      default:
        return Icons.insert_drive_file;
    }
  }

  Widget _buildRestoreButton() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: SizedBox(
        width: double.infinity,
        height: 52,
        child: ElevatedButton(
          onPressed: _selectedCount == 0 ? null : _startRestore,
          style: ElevatedButton.styleFrom(
            backgroundColor: _accentColor,
            disabledBackgroundColor: Colors.white10,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
          child: Text(
            _selectedCount == 0
                ? 'Select files to restore'
                : 'Restore $_selectedCount file${_selectedCount == 1 ? '' : 's'}',
            style: const TextStyle(
                fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white),
          ),
        ),
      ),
    );
  }

  Widget _buildSummary() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Restore Complete',
            style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 24),
          _summaryRow(Icons.check_circle, const Color(0xFF22c55e),
              '$_restoredCount file${_restoredCount == 1 ? '' : 's'} restored'),
          if (_skippedCount > 0)
            _summaryRow(Icons.skip_next, _textSecondary,
                '$_skippedCount skipped (already on phone)'),
          if (_failedFiles.isNotEmpty)
            _summaryRow(Icons.error, const Color(0xFFf59e0b),
                '${_failedFiles.length} failed'),
          if (_failedFiles.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text('Failed files:',
                style: TextStyle(color: _textSecondary, fontSize: 13)),
            const SizedBox(height: 8),
            ..._failedFiles.map((f) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(
                    f.fileName,
                    style: const TextStyle(color: Colors.white, fontSize: 13),
                  ),
                )),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              height: 48,
              child: OutlinedButton(
                onPressed: () {
                  setState(() {
                    _selected
                      ..clear()
                      ..addAll(_failedFiles.map((f) => f.fileId));
                    _phase = _Phase.listing;
                    _failedFiles.clear();
                  });
                },
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: _accentColor),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('Retry Failed',
                    style: TextStyle(color: _accentColor)),
              ),
            ),
          ],
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton(
              onPressed: () {
                setState(() {
                  _phase = _Phase.listing;
                  _selected.clear();
                });
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: _accentColor,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
              child: const Text('Done',
                  style: TextStyle(color: Colors.white, fontSize: 16)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _summaryRow(IconData icon, Color color, String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 12),
          Text(text, style: const TextStyle(color: Colors.white, fontSize: 15)),
        ],
      ),
    );
  }
}
