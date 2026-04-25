/// Data classes for the restore feature.
///
/// RestoreSession  — summary from GET /restore/sessions
/// RestoreFile     — one file entry from GET /restore/files
/// RestoreFileListing — full response from GET /restore/files

/// Summary of one backup session (shown in the session list).
class RestoreSession {
  const RestoreSession({
    required this.sessionId,
    required this.startedAt,
    required this.completedAt,
    required this.deviceAlias,
    required this.fileCount,
    required this.totalBytes,
  });

  final String sessionId;
  final DateTime startedAt;
  final DateTime completedAt;
  final String deviceAlias;
  final int fileCount;
  final int totalBytes;

  factory RestoreSession.fromJson(Map<String, dynamic> json) => RestoreSession(
        sessionId:   json['sessionId'] as String,
        startedAt:   DateTime.parse(json['startedAt'] as String),
        completedAt: DateTime.parse(json['completedAt'] as String),
        deviceAlias: json['deviceAlias'] as String? ?? 'Unknown',
        fileCount:   json['fileCount'] as int,
        totalBytes:  json['totalBytes'] as int,
      );

  /// Human-readable size (e.g. "12.4 MB" or "512 KB").
  String get sizeLabel {
    final mb = totalBytes / (1024 * 1024);
    if (mb >= 1) return '${mb.toStringAsFixed(1)} MB';
    return '${(totalBytes / 1024).toStringAsFixed(0)} KB';
  }
}

/// One file entry within a restore session.
class RestoreFile {
  const RestoreFile({
    required this.fileId,
    required this.fileName,
    required this.originalPath,
    required this.category,
    required this.sizeBytes,
    required this.modifiedAt,
    required this.available,
  });

  final String fileId;
  final String fileName;

  /// Absolute path where the file lived on the phone before backup.
  final String originalPath;

  final String category;
  final int sizeBytes;
  final DateTime modifiedAt;

  /// False when the backed-up copy is missing from PC disk.
  final bool available;

  factory RestoreFile.fromJson(Map<String, dynamic> json) => RestoreFile(
        fileId:       json['fileId'] as String,
        fileName:     json['fileName'] as String,
        originalPath: json['originalPath'] as String,
        category:     json['category'] as String? ?? 'other',
        sizeBytes:    json['sizeBytes'] as int,
        modifiedAt:   DateTime.parse(json['modifiedAt'] as String),
        available:    json['available'] as bool? ?? true,
      );

  String get sizeLabel {
    final kb = sizeBytes / 1024;
    if (kb >= 1024) return '${(kb / 1024).toStringAsFixed(1)} MB';
    return '${kb.toStringAsFixed(0)} KB';
  }
}

/// Full response from GET /restore/files — files + one-time tokens.
class RestoreFileListing {
  const RestoreFileListing({
    required this.sessionId,
    required this.files,
    required this.tokens,
  });

  final String sessionId;
  final List<RestoreFile> files;
  final Map<String, String> tokens; // fileId → one-time token

  factory RestoreFileListing.fromJson(Map<String, dynamic> json) =>
      RestoreFileListing(
        sessionId: json['sessionId'] as String,
        files: (json['files'] as List<dynamic>)
            .map((f) => RestoreFile.fromJson(f as Map<String, dynamic>))
            .toList(),
        tokens: (json['tokens'] as Map<String, dynamic>)
            .map((k, v) => MapEntry(k, v as String)),
      );
}
