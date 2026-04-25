/// Lcloud Android — Restore Client
///
/// HTTPS client for the three restore endpoints.
/// Uses the same fingerprint-based trust as TransferClient.
library;

import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';

import '../models/restore_session.dart';

/// Thrown when the PC returns a known error code during restore.
class RestoreException implements Exception {
  const RestoreException(this.code, [this.detail = '']);

  final String code;
  final String detail;

  @override
  String toString() => 'RestoreException($code: $detail)';
}

/// HTTPS client for all three restore endpoints.
class RestoreClient {
  RestoreClient({
    required this.pcAddress,
    required this.pcPort,
    required this.fingerprint,
  });

  final String pcAddress;
  final int pcPort;
  final String fingerprint;

  String get _base => 'https://$pcAddress:$pcPort/api/lcloud/v2';

  HttpClient _httpClient() => HttpClient()
    ..connectionTimeout = const Duration(seconds: 15)
    ..badCertificateCallback = (X509Certificate cert, String host, int port) =>
        sha256.convert(cert.der).toString() == fingerprint;

  // ------------------------------------------------------------------
  // GET /restore/sessions
  // ------------------------------------------------------------------

  /// Fetch all backup sessions available for restore, newest first.
  ///
  /// Returns an empty list if no backups exist yet (404 from PC).
  Future<List<RestoreSession>> getSessions() async {
    final client = _httpClient();
    try {
      final req = await client
          .getUrl(Uri.parse('$_base/restore/sessions'))
          .timeout(const Duration(seconds: 15));
      final resp = await req.close().timeout(const Duration(seconds: 15));
      if (resp.statusCode == 404) {
        await resp.drain<void>();
        return [];
      }
      if (resp.statusCode != 200) {
        await resp.drain<void>();
        throw RestoreException('sessions_failed', 'HTTP ${resp.statusCode}');
      }
      final body = await resp.transform(utf8.decoder).join();
      final data = jsonDecode(body) as Map<String, dynamic>;
      return (data['sessions'] as List<dynamic>)
          .map((s) => RestoreSession.fromJson(s as Map<String, dynamic>))
          .toList();
    } finally {
      client.close();
    }
  }

  // ------------------------------------------------------------------
  // GET /restore/files?sessionId=X[&category=Y]
  // ------------------------------------------------------------------

  /// Fetch file listing + fresh one-time tokens for a session.
  ///
  /// Pass [category] to filter: 'photo' | 'video' | 'whatsapp' |
  /// 'document' | 'other'. Omit for all files.
  Future<RestoreFileListing> getFiles(
    String sessionId, {
    String? category,
  }) async {
    final client = _httpClient();
    try {
      var url = '$_base/restore/files?sessionId=${Uri.encodeComponent(sessionId)}';
      if (category != null) {
        url += '&category=${Uri.encodeComponent(category)}';
      }
      final req =
          await client.getUrl(Uri.parse(url)).timeout(const Duration(seconds: 15));
      final resp = await req.close().timeout(const Duration(seconds: 15));
      if (resp.statusCode == 404) {
        await resp.drain<void>();
        throw const RestoreException('session_not_found');
      }
      if (resp.statusCode != 200) {
        await resp.drain<void>();
        throw RestoreException('files_failed', 'HTTP ${resp.statusCode}');
      }
      final body = await resp.transform(utf8.decoder).join();
      return RestoreFileListing.fromJson(
          jsonDecode(body) as Map<String, dynamic>);
    } finally {
      client.close();
    }
  }

  // ------------------------------------------------------------------
  // GET /restore/file?sessionId=X&fileId=Y&token=Z
  // ------------------------------------------------------------------

  /// Stream a backed-up file from PC to [destPath] on the phone.
  ///
  /// [onProgress] is called after each chunk with total bytes received.
  /// Throws [RestoreException] on 401 (bad/expired token) or 404.
  Future<void> downloadFile({
    required String sessionId,
    required String fileId,
    required String token,
    required String destPath,
    void Function(int bytesReceived)? onProgress,
  }) async {
    final client = _httpClient();
    try {
      final url = '$_base/restore/file'
          '?sessionId=${Uri.encodeComponent(sessionId)}'
          '&fileId=${Uri.encodeComponent(fileId)}'
          '&token=${Uri.encodeComponent(token)}';

      final req =
          await client.getUrl(Uri.parse(url)).timeout(const Duration(seconds: 60));
      final resp = await req.close().timeout(const Duration(seconds: 60));

      if (resp.statusCode == 401) {
        await resp.drain<void>();
        throw const RestoreException('invalid_token');
      }
      if (resp.statusCode == 404) {
        await resp.drain<void>();
        throw const RestoreException('file_not_found');
      }
      if (resp.statusCode != 200) {
        await resp.drain<void>();
        throw RestoreException('download_failed', 'HTTP ${resp.statusCode}');
      }

      // Create parent directories if needed, then stream to disk
      final dest = File(destPath);
      await dest.parent.create(recursive: true);
      final sink = dest.openWrite();
      int received = 0;
      try {
        await for (final chunk in resp) {
          sink.add(chunk);
          received += chunk.length;
          onProgress?.call(received);
        }
      } finally {
        await sink.close();
      }
    } finally {
      client.close();
    }
  }
}
