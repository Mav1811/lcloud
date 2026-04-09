import 'dart:io';
import 'dart:convert';
import 'package:shelf/shelf.dart';
import 'package:shelf/shelf_io.dart' as shelf_io;
import 'package:shelf_router/shelf_router.dart';
import '../models/backup_file.dart';

/// HTTP server that runs on the phone and serves files to the PC.
///
/// The PC connects to this server to download files during backup.
/// Port: 52001 (default)
class LcloudHttpServer {
  static const int defaultPort = 52001;
  static const String _appVersion = '0.1.0';

  HttpServer? _server;
  List<BackupFile> _files = [];
  int _bytesServed = 0;

  int get bytesServed => _bytesServed;

  /// Start the file server with the given list of files.
  Future<void> start(List<BackupFile> files, {int port = defaultPort}) async {
    _files = files;
    _bytesServed = 0;

    final router = Router()
      ..get('/ping', _ping)
      ..get('/files', _listFiles)
      ..get('/file/<encodedPath>', _serveFile);

    final handler = const Pipeline()
        .addMiddleware(logRequests())
        .addHandler(router.call);

    _server = await shelf_io.serve(handler, InternetAddress.anyIPv4, port);
  }

  /// Stop the server cleanly.
  Future<void> stop() async {
    await _server?.close(force: true);
    _server = null;
  }

  bool get isRunning => _server != null;

  // ---------------------------------------------------------------------------
  // Route handlers
  // ---------------------------------------------------------------------------

  Response _ping(Request request) {
    return Response.ok(
      jsonEncode({
        'status': 'ok',
        'device': 'android',
        'version': _appVersion,
      }),
      headers: {'content-type': 'application/json'},
    );
  }

  Response _listFiles(Request request) {
    final fileList = _files.map((f) => f.toJson()).toList();
    return Response.ok(
      jsonEncode({'files': fileList, 'total': fileList.length}),
      headers: {'content-type': 'application/json'},
    );
  }

  Future<Response> _serveFile(Request request, String encodedPath) async {
    final filePath = Uri.decodeComponent(encodedPath);
    final file = File(filePath);

    if (!await file.exists()) {
      return Response.notFound(
        jsonEncode({'error': 'File not found: $filePath'}),
        headers: {'content-type': 'application/json'},
      );
    }

    try {
      final stat = await file.stat();
      final stream = file.openRead().map((chunk) {
        _bytesServed += chunk.length;
        return chunk;
      });

      return Response.ok(
        stream,
        headers: {
          'content-type': 'application/octet-stream',
          'content-length': stat.size.toString(),
          'x-file-name': Uri.encodeFull(file.uri.pathSegments.last),
        },
      );
    } on FileSystemException catch (e) {
      return Response.internalServerError(
        body: jsonEncode({'error': e.message}),
        headers: {'content-type': 'application/json'},
      );
    }
  }
}
