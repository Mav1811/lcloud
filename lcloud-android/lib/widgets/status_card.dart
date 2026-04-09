import 'package:flutter/material.dart';

/// Color palette — matches the PC app
const Color _bgColor = Color(0xFF1a1a2e);
const Color _cardColor = Color(0xFF16213e);
const Color _accentColor = Color(0xFF4f46e5);
const Color _successColor = Color(0xFF22c55e);
const Color _warningColor = Color(0xFFf59e0b);
const Color _textSecondary = Color(0xFF94a3b8);

/// Connection states for [StatusCard]
enum ConnectionState {
  searching,
  found,
  backingUp,
  complete,
  error,
}

extension ConnectionStateLabel on ConnectionState {
  String get label {
    switch (this) {
      case ConnectionState.searching:
        return 'Searching for PC on WiFi...';
      case ConnectionState.found:
        return 'PC Found';
      case ConnectionState.backingUp:
        return 'Backing up...';
      case ConnectionState.complete:
        return 'Backup complete';
      case ConnectionState.error:
        return 'Connection error';
    }
  }

  Color get color {
    switch (this) {
      case ConnectionState.searching:
        return _textSecondary;
      case ConnectionState.found:
        return _successColor;
      case ConnectionState.backingUp:
        return _accentColor;
      case ConnectionState.complete:
        return _successColor;
      case ConnectionState.error:
        return const Color(0xFFef4444);
    }
  }

  IconData get icon {
    switch (this) {
      case ConnectionState.searching:
        return Icons.wifi_find;
      case ConnectionState.found:
        return Icons.computer;
      case ConnectionState.backingUp:
        return Icons.cloud_upload;
      case ConnectionState.complete:
        return Icons.check_circle;
      case ConnectionState.error:
        return Icons.error_outline;
    }
  }
}

/// Displays the current PC connection status.
class StatusCard extends StatelessWidget {
  const StatusCard({
    super.key,
    required this.state,
    this.pcName,
    this.subtitle,
  });

  final ConnectionState state;
  final String? pcName;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    final label = pcName != null && state == ConnectionState.found
        ? 'PC Found: $pcName'
        : state.label;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: state.color.withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(state.icon, color: state.color, size: 24),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    color: state.color,
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 3),
                  Text(
                    subtitle!,
                    style: const TextStyle(
                      color: _textSecondary,
                      fontSize: 12,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (state == ConnectionState.searching)
            const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: _textSecondary,
              ),
            ),
        ],
      ),
    );
  }
}
