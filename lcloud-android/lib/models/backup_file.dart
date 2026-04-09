/// Represents a single file on the phone that can be backed up.
class BackupFile {
  const BackupFile({
    required this.path,
    required this.name,
    required this.sizeBytes,
    required this.modifiedAt,
    required this.category,
    this.isTransferred = false,
  });

  /// Absolute path on the device (e.g. /storage/emulated/0/DCIM/photo.jpg)
  final String path;

  /// Filename only (e.g. photo.jpg)
  final String name;

  /// File size in bytes
  final int sizeBytes;

  /// Last modified timestamp
  final DateTime modifiedAt;

  /// One of: 'whatsapp', 'photo', 'video', 'document', 'other'
  final String category;

  /// True once the file has been successfully sent to the PC
  final bool isTransferred;

  BackupFile copyWith({bool? isTransferred}) {
    return BackupFile(
      path: path,
      name: name,
      sizeBytes: sizeBytes,
      modifiedAt: modifiedAt,
      category: category,
      isTransferred: isTransferred ?? this.isTransferred,
    );
  }

  /// Convert to JSON for the /announce payload sent to the PC.
  Map<String, dynamic> toJson() => {
        'path': path,
        'name': name,
        'size': sizeBytes,
        'modified_at': modifiedAt.toIso8601String(),
        'category': category,
      };

  @override
  String toString() => 'BackupFile($name, ${(sizeBytes / 1024).toStringAsFixed(1)} KB)';
}
