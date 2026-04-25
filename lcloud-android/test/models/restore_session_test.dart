import 'package:flutter_test/flutter_test.dart';
import 'package:lcloud/models/restore_session.dart';

void main() {
  group('RestoreSession.fromJson', () {
    test('parses all fields correctly', () {
      final json = {
        'sessionId': 'sess-abc',
        'startedAt': '2026-04-20T10:30:00',
        'completedAt': '2026-04-20T10:45:00',
        'deviceAlias': 'Pixel 7',
        'fileCount': 42,
        'totalBytes': 5242880,
      };
      final s = RestoreSession.fromJson(json);
      expect(s.sessionId, 'sess-abc');
      expect(s.deviceAlias, 'Pixel 7');
      expect(s.fileCount, 42);
      expect(s.totalBytes, 5242880);
      expect(s.startedAt, isA<DateTime>());
      expect(s.completedAt, isA<DateTime>());
    });

    test('deviceAlias defaults to Unknown when missing', () {
      final json = {
        'sessionId': 's1',
        'startedAt': '2026-04-20T10:30:00',
        'completedAt': '2026-04-20T10:45:00',
        'fileCount': 0,
        'totalBytes': 0,
      };
      final s = RestoreSession.fromJson(json);
      expect(s.deviceAlias, 'Unknown');
    });

    test('sizeLabel returns MB for large sizes', () {
      final json = {
        'sessionId': 's1', 'startedAt': '2026-04-20T10:30:00',
        'completedAt': '2026-04-20T10:45:00',
        'deviceAlias': 'Phone', 'fileCount': 1,
        'totalBytes': 5242880, // 5 MB
      };
      final s = RestoreSession.fromJson(json);
      expect(s.sizeLabel, contains('MB'));
    });

    test('sizeLabel returns KB for small sizes', () {
      final json = {
        'sessionId': 's1', 'startedAt': '2026-04-20T10:30:00',
        'completedAt': '2026-04-20T10:45:00',
        'deviceAlias': 'Phone', 'fileCount': 1,
        'totalBytes': 512,
      };
      final s = RestoreSession.fromJson(json);
      expect(s.sizeLabel, contains('KB'));
    });
  });

  group('RestoreFile.fromJson', () {
    test('parses all fields correctly', () {
      final json = {
        'fileId': 'f1',
        'fileName': 'photo.jpg',
        'originalPath': '/storage/emulated/0/DCIM/Camera/photo.jpg',
        'category': 'photo',
        'sizeBytes': 3145728,
        'modifiedAt': '2026-04-19T14:22:00',
        'available': true,
      };
      final f = RestoreFile.fromJson(json);
      expect(f.fileId, 'f1');
      expect(f.fileName, 'photo.jpg');
      expect(f.originalPath, '/storage/emulated/0/DCIM/Camera/photo.jpg');
      expect(f.category, 'photo');
      expect(f.sizeBytes, 3145728);
      expect(f.available, isTrue);
    });

    test('available defaults to true when field missing', () {
      final json = {
        'fileId': 'f2', 'fileName': 'doc.pdf',
        'originalPath': '/docs/doc.pdf', 'category': 'document',
        'sizeBytes': 500, 'modifiedAt': '2026-04-19T14:22:00',
      };
      final f = RestoreFile.fromJson(json);
      expect(f.available, isTrue);
    });

    test('sizeLabel formats KB correctly', () {
      final json = {
        'fileId': 'f3', 'fileName': 'small.txt',
        'originalPath': '/small.txt', 'category': 'document',
        'sizeBytes': 2048, 'modifiedAt': '2026-04-19T14:22:00',
        'available': true,
      };
      final f = RestoreFile.fromJson(json);
      expect(f.sizeLabel, contains('KB'));
    });
  });

  group('RestoreFileListing.fromJson', () {
    test('parses session id, files list, and tokens map', () {
      final json = {
        'sessionId': 'sess-1',
        'files': [
          {
            'fileId': 'f1', 'fileName': 'photo.jpg',
            'originalPath': '/DCIM/photo.jpg', 'category': 'photo',
            'sizeBytes': 100, 'modifiedAt': '2026-04-19T10:00:00',
            'available': true,
          }
        ],
        'tokens': {'f1': 'token-abc'},
      };
      final listing = RestoreFileListing.fromJson(json);
      expect(listing.sessionId, 'sess-1');
      expect(listing.files, hasLength(1));
      expect(listing.tokens['f1'], 'token-abc');
    });
  });
}
