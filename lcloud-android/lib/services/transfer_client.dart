/// Lcloud Android — Transfer Client
///
/// Pushes files to the PC's HTTPS server using the Lcloud v2 protocol.
/// Verifies the PC's self-signed cert by SHA-256 fingerprint (TOFU).
/// Streams files from disk — never loads the entire file into memory.
library;

import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';

/// One file to be transferred.
class TransferFile {
  const TransferFile({
    required this.fileId,
    required this.fileName,
    required this.fileSize,
    required this.fileType,
    required this.path,
    required this.category,
    required this.modifiedAt,
  });

  final String fileId;
  final String fileName;
  final int fileSize;
  final String fileType;
  final String path;
  final String category;
  final DateTime modifiedAt;

  Map<String, dynamic> toJson() => {
        'fileId': fileId,
        'fileName': fileName,
        'size': fileSize,
        'fileType': fileType,
        'path': path,
        'category': category,
        'modifiedAt': modifiedAt.toIso8601String(),
      };
}

/// Thrown when the PC returns a known error code.
class TransferException implements Exception {
  const TransferException(this.code, [this.detail = '']);

  final String code; // 'disk_full' | 'no_backup_folder' | 'upload_failed' | 'invalid_token'
  final String detail;

  @override
  String toString() => 'TransferException($code: $detail)';
}

/// HTTPS client for the Lcloud v2 transfer protocol.
class TransferClient {
  TransferClient({
    required this.pcAddress,
    required this.pcPort,
    required this.fingerprint,
  });

  final String pcAddress;
  final int pcPort;
  final String fingerprint; // SHA-256 hex — trusts the PC's self-signed cert

  String get _base => 'https://$pcAddress:$pcPort/api/lcloud/v2';

  /// Build an HttpClient that trusts the PC cert by fingerprint only.
  HttpClient _client() {
    return HttpClient()
      ..connectionTimeout = const Duration(seconds: 15)
      ..badCertificateCallback = (X509Certificate cert, String host, int port) {
        final fp = sha256.convert(cert.der).toString();
        return fp == fingerprint;
      };
  }

  /// Send file list to PC; receive sessionId + per-file tokens.
  ///
  /// Returns a map: `{'__sessionId__': '...', 'fileId1': 'token1', ...}`
  Future<Map<String, String>> prepareUpload({
    required String deviceAlias,
    required List<TransferFile> files,
  }) async {
    final client = _client();
    try {
      final req = await client
          .postUrl(Uri.parse('$_base/prepare-upload'))
          .timeout(const Duration(seconds: 15));

      final bodyBytes = utf8.encode(jsonEncode({
        'deviceAlias': deviceAlias,
        'files': files.map((f) => f.toJson()).toList(),
      }));
      req.headers
        ..contentType = ContentType.json
        ..contentLength = bodyBytes.length;
      req.add(bodyBytes);

      final resp = await req.close().timeout(const Duration(seconds: 15));
      final respBody = await resp.transform(utf8.decoder).join();
      final data = jsonDecode(respBody) as Map<String, dynamic>;

      switch (resp.statusCode) {
        case 507:
          throw TransferException(
            'disk_full',
            'Free: ${data['free_bytes']} B  Need: ${data['needed_bytes']} B',
          );
        case 503:
          throw const TransferException(
            'no_backup_folder',
            'Open Lcloud on PC and set a backup folder.',
          );
        case 200:
          break;
        default:
          throw TransferException('prepare_failed', 'HTTP ${resp.statusCode}');
      }

      final sessionId = data['sessionId'] as String;
      final tokens = (data['files'] as Map<String, dynamic>)
          .map((k, v) => MapEntry(k, v as String));
      return {'__sessionId__': sessionId, ...tokens};
    } finally {
      client.close();
    }
  }

  /// Stream one file from disk to the PC.
  ///
  /// [onProgress] is called after each chunk with total bytes sent so far.
  Future<void> uploadFile({
    required String sessionId,
    required TransferFile file,
    required String token,
    void Function(int bytesSent)? onProgress,
  }) async {
    final client = _client();
    try {
      final uri = Uri.parse(
        '$_base/upload'
        '?sessionId=${Uri.encodeComponent(sessionId)}'
        '&fileId=${Uri.encodeComponent(file.fileId)}'
        '&token=${Uri.encodeComponent(token)}',
      );

      final req =
          await client.postUrl(uri).timeout(const Duration(seconds: 60));

      req.headers
        ..set(
          'Content-Type',
          file.fileType.isNotEmpty
              ? file.fileType
              : 'application/octet-stream',
        )
        ..contentLength = file.fileSize;

      // Stream file in chunks — never fully loaded into memory
      int sent = 0;
      await for (final chunk in File(file.path).openRead()) {
        req.add(chunk);
        sent += chunk.length;
        onProgress?.call(sent);
      }

      final resp = await req.close().timeout(const Duration(seconds: 60));
      await resp.drain<void>();

      if (resp.statusCode == 401) {
        throw const TransferException('invalid_token');
      }
      if (resp.statusCode != 200) {
        throw TransferException('upload_failed', 'HTTP ${resp.statusCode}');
      }
    } finally {
      client.close();
    }
  }

  /// Cancel the active session (best-effort — errors are swallowed).
  Future<void> cancel(String sessionId) async {
    final client = _client();
    try {
      final req = await client
          .postUrl(Uri.parse(
              '$_base/cancel?sessionId=${Uri.encodeComponent(sessionId)}'))
          .timeout(const Duration(seconds: 5));
      req.headers.contentLength = 0;
      final resp = await req.close().timeout(const Duration(seconds: 5));
      await resp.drain<void>();
    } catch (_) {
      // Best-effort — don't rethrow on cancel
    } finally {
      client.close();
    }
  }
}
