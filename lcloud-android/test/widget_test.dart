// Smoke test — verifies the app widget tree builds without crashing.
import 'package:flutter_test/flutter_test.dart';
import 'package:lcloud/services/transfer_client.dart';

void main() {
  // Full widget smoke test requires platform channels (permissions, multicast lock)
  // which are not available in the test environment. Unit tests in
  // test/services/ cover the core logic instead.

  test('TransferFile serialises to JSON', () {
    final file = TransferFile(
      fileId: 'smoke-1',
      fileName: 'test.jpg',
      fileSize: 512,
      fileType: 'image/jpeg',
      path: '/test/test.jpg',
      category: 'photo',
      modifiedAt: DateTime(2026, 4, 22),
    );
    final json = file.toJson();
    expect(json['fileId'], 'smoke-1');
    expect(json['size'], 512);
  });
}
