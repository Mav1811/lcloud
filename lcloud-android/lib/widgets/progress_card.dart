import 'package:flutter/material.dart';

const Color _cardColor = Color(0xFF16213e);
const Color _accentColor = Color(0xFF4f46e5);
const Color _textSecondary = Color(0xFF94a3b8);

/// Shows file transfer progress during a backup session.
class ProgressCard extends StatelessWidget {
  const ProgressCard({
    super.key,
    required this.currentFile,
    required this.currentIndex,
    required this.totalFiles,
    required this.bytesTransferred,
    required this.totalBytes,
  });

  final String currentFile;
  final int currentIndex;
  final int totalFiles;
  final int bytesTransferred;
  final int totalBytes;

  double get _progress =>
      totalFiles > 0 ? (currentIndex / totalFiles).clamp(0.0, 1.0) : 0.0;

  String get _sizeLabel {
    final done = bytesTransferred / (1024 * 1024);
    final total = totalBytes / (1024 * 1024);
    if (total < 1) {
      return '${(bytesTransferred / 1024).toStringAsFixed(0)} KB / ${(totalBytes / 1024).toStringAsFixed(0)} KB';
    }
    return '${done.toStringAsFixed(1)} MB / ${total.toStringAsFixed(1)} MB';
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Transferring',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
              Text(
                '$currentIndex / $totalFiles files',
                style: const TextStyle(color: _textSecondary, fontSize: 13),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: _progress,
              minHeight: 8,
              backgroundColor: Colors.white10,
              valueColor: const AlwaysStoppedAnimation<Color>(_accentColor),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            currentFile,
            style: const TextStyle(color: _textSecondary, fontSize: 12),
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 4),
          Text(
            _sizeLabel,
            style: const TextStyle(color: _textSecondary, fontSize: 12),
          ),
        ],
      ),
    );
  }
}
