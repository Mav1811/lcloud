/// Records the outcome of a completed backup session.
class BackupSession {
  const BackupSession({
    required this.startedAt,
    required this.completedAt,
    required this.filesSaved,
    required this.bytesTransferred,
    required this.errors,
  });

  final DateTime startedAt;
  final DateTime completedAt;
  final int filesSaved;
  final int bytesTransferred;
  final List<String> errors;

  bool get hadErrors => errors.isNotEmpty;

  /// Human-readable size string (e.g. "12.4 MB")
  String get sizeLabel {
    final mb = bytesTransferred / (1024 * 1024);
    if (mb < 1) return '${(bytesTransferred / 1024).toStringAsFixed(0)} KB';
    return '${mb.toStringAsFixed(1)} MB';
  }

  Map<String, dynamic> toJson() => {
        'started_at': startedAt.toIso8601String(),
        'completed_at': completedAt.toIso8601String(),
        'files_saved': filesSaved,
        'bytes_transferred': bytesTransferred,
        'errors': errors,
      };
}
