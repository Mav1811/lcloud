import 'dart:io';
import '../models/backup_file.dart';

/// Scans the device storage for files to back up.
///
/// Returns files in priority order:
///   1. WhatsApp media (most critical)
///   2. Photos — newest first
///   3. Videos — newest first
///   4. Documents
///   5. Everything else
class FileScanner {
  static const List<String> _photoExtensions = [
    '.jpg', '.jpeg', '.png', '.heic', '.webp', '.gif', '.bmp',
  ];
  static const List<String> _videoExtensions = [
    '.mp4', '.mov', '.avi', '.mkv', '.3gp', '.m4v',
  ];
  static const List<String> _documentExtensions = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.csv', '.odt',
  ];

  static const List<String> _whatsappBasePaths = [
    '/storage/emulated/0/WhatsApp/Media',
    '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Media',
  ];

  static const List<String> _photoPaths = [
    '/storage/emulated/0/DCIM',
    '/storage/emulated/0/Pictures',
  ];

  static const List<String> _documentPaths = [
    '/storage/emulated/0/Documents',
    '/storage/emulated/0/Download',
  ];

  /// Scan all storage and return files in priority order.
  Future<List<BackupFile>> scanAll() async {
    final whatsapp = await scanWhatsApp();
    final photos = await _scanPaths(_photoPaths, 'photo');
    final videos = await _scanPathsForCategory(_photoPaths, 'video');
    final documents = await _scanPaths(_documentPaths, 'document');

    return [...whatsapp, ...photos, ...videos, ...documents];
  }

  /// Scan WhatsApp media folders specifically.
  Future<List<BackupFile>> scanWhatsApp() async {
    final results = <BackupFile>[];
    for (final basePath in _whatsappBasePaths) {
      final dir = Directory(basePath);
      if (!await dir.exists()) continue;

      await for (final entity in dir.list(recursive: true, followLinks: false)) {
        if (entity is! File) continue;
        if (_isSystemFile(entity.path)) continue;

        final stat = await entity.stat();
        results.add(BackupFile(
          path: entity.path,
          name: entity.uri.pathSegments.last,
          sizeBytes: stat.size,
          modifiedAt: stat.modified,
          category: 'whatsapp',
        ));
      }
    }
    // Newest first
    results.sort((a, b) => b.modifiedAt.compareTo(a.modifiedAt));
    return results;
  }

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  Future<List<BackupFile>> _scanPaths(
    List<String> paths,
    String targetCategory,
  ) async {
    final results = <BackupFile>[];
    for (final basePath in paths) {
      final dir = Directory(basePath);
      if (!await dir.exists()) continue;

      await for (final entity in dir.list(recursive: true, followLinks: false)) {
        if (entity is! File) continue;
        if (_isSystemFile(entity.path)) continue;

        final ext = _extension(entity.path);
        final category = _detectCategory(entity.path, ext);
        if (category != targetCategory) continue;

        final stat = await entity.stat();
        results.add(BackupFile(
          path: entity.path,
          name: entity.uri.pathSegments.last,
          sizeBytes: stat.size,
          modifiedAt: stat.modified,
          category: category,
        ));
      }
    }
    results.sort((a, b) => b.modifiedAt.compareTo(a.modifiedAt));
    return results;
  }

  Future<List<BackupFile>> _scanPathsForCategory(
    List<String> paths,
    String targetCategory,
  ) async {
    return _scanPaths(paths, targetCategory);
  }

  String _extension(String path) {
    final lastDot = path.lastIndexOf('.');
    if (lastDot == -1) return '';
    return path.substring(lastDot).toLowerCase();
  }

  String _detectCategory(String path, String ext) {
    final lower = path.toLowerCase();
    if (lower.contains('whatsapp')) return 'whatsapp';
    if (_photoExtensions.contains(ext)) return 'photo';
    if (_videoExtensions.contains(ext)) return 'video';
    if (_documentExtensions.contains(ext)) return 'document';
    return 'other';
  }

  bool _isSystemFile(String path) {
    return path.endsWith('.nomedia') ||
        path.contains('/.thumbnails/') ||
        path.contains('/.cache/');
  }
}
