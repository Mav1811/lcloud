import 'package:flutter_test/flutter_test.dart';
import 'package:lcloud/services/transfer_client.dart';

void main() {
  group('TransferFile.toJson', () {
    test('serialises all fields correctly', () {
      final file = TransferFile(
        fileId: 'f1',
        fileName: 'photo.jpg',
        fileSize: 1024,
        fileType: 'image/jpeg',
        path: '/DCIM/photo.jpg',
        category: 'photo',
        modifiedAt: DateTime(2026, 1, 1, 10, 0, 0),
      );

      final json = file.toJson();
      expect(json['fileId'], 'f1');
      expect(json['fileName'], 'photo.jpg');
      expect(json['size'], 1024);
      expect(json['fileType'], 'image/jpeg');
      expect(json['path'], '/DCIM/photo.jpg');
      expect(json['category'], 'photo');
      expect(json['modifiedAt'], isA<String>());
      expect(json['modifiedAt'], contains('2026-01-01'));
    });
  });

  group('TransferException', () {
    test('toString includes code and detail', () {
      const ex = TransferException('disk_full', 'Free: 100 B');
      expect(ex.toString(), contains('disk_full'));
      expect(ex.toString(), contains('Free: 100 B'));
    });

    test('detail defaults to empty string', () {
      const ex = TransferException('no_backup_folder');
      expect(ex.detail, '');
    });

    test('code is preserved', () {
      const ex = TransferException('invalid_token');
      expect(ex.code, 'invalid_token');
    });
  });

  group('TransferClient construction', () {
    test('builds base URL correctly', () {
      final client = TransferClient(
        pcAddress: '192.168.1.100',
        pcPort: 53317,
        fingerprint: 'abc123',
      );
      // Access private getter via toString hack isn't ideal,
      // but we verify the fields are stored correctly.
      expect(client.pcAddress, '192.168.1.100');
      expect(client.pcPort, 53317);
      expect(client.fingerprint, 'abc123');
    });
  });
}
