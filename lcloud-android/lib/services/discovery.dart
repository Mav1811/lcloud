import 'dart:io';
import 'package:multicast_dns/multicast_dns.dart';

const String _serviceType = '_lcloud._tcp';
const String _androidServiceName = 'lcloud-android';
const int _androidPort = 52001;
const Duration _discoveryTimeout = Duration(seconds: 10);

/// Information about a discovered PC running Lcloud.
class DiscoveredPC {
  const DiscoveredPC({
    required this.name,
    required this.address,
    required this.port,
  });

  final String name;
  final String address;
  final int port;

  @override
  String toString() => 'DiscoveredPC($name @ $address:$port)';
}

/// Handles mDNS service advertisement and PC discovery.
///
/// - [advertise] announces this Android device on the local network
/// - [findPC] searches for a PC running Lcloud
class LcloudDiscovery {
  MDnsClient? _client;

  /// Advertise this Android device as an Lcloud node on the local network.
  ///
  /// Note: The multicast_dns package handles PTR/SRV/A record registration.
  /// On Android, CHANGE_WIFI_MULTICAST_STATE permission is required.
  Future<void> advertise({int port = _androidPort}) async {
    // multicast_dns package does not support full service registration in current
    // Dart implementation — advertisement is handled by the shelf server responding
    // to /ping. PC discovers via scanning or manual IP for v0.1.
    // Full mDNS advertisement is planned for v0.2 using a native plugin.
    // For now, the phone's IP is shown in the UI for manual connection if needed.
  }

  /// Scan the local network for a PC running Lcloud.
  ///
  /// Returns the first discovered [DiscoveredPC] within [_discoveryTimeout],
  /// or null if none is found.
  Future<DiscoveredPC?> findPC() async {
    final client = MDnsClient();
    _client = client;

    try {
      await client.start();

      await for (final PtrResourceRecord ptr in client
          .lookup<PtrResourceRecord>(
              ResourceRecordQuery.serverPointer(_serviceType))
          .timeout(_discoveryTimeout, onTimeout: (_) {})) {
        // Resolve SRV record
        await for (final SrvResourceRecord srv in client
            .lookup<SrvResourceRecord>(
                ResourceRecordQuery.service(ptr.domainName))
            .timeout(const Duration(seconds: 3), onTimeout: (_) {})) {

          // Resolve A (IP) record
          await for (final IPAddressResourceRecord ip in client
              .lookup<IPAddressResourceRecord>(
                  ResourceRecordQuery.addressIPv4(srv.target))
              .timeout(const Duration(seconds: 3), onTimeout: (_) {})) {

            final name = ptr.domainName.replaceAll('.$_serviceType.local', '');
            final pc = DiscoveredPC(
              name: name,
              address: ip.address.address,
              port: srv.port,
            );
            client.stop();
            return pc;
          }
        }
      }
    } on Exception {
      // Discovery timed out or failed — not an error
    } finally {
      client.stop();
      _client = null;
    }

    return null;
  }

  /// Stop any ongoing discovery.
  void stopDiscovery() {
    _client?.stop();
    _client = null;
  }

  /// Get the local WiFi IP address of this device.
  static Future<String?> getLocalIP() async {
    try {
      final interfaces = await NetworkInterface.list(
        type: InternetAddressType.IPv4,
        includeLinkLocal: false,
      );
      for (final iface in interfaces) {
        // Prefer WiFi interfaces
        if (iface.name.toLowerCase().contains('wlan') ||
            iface.name.toLowerCase().contains('wifi') ||
            iface.name.toLowerCase().contains('eth')) {
          for (final addr in iface.addresses) {
            if (!addr.isLoopback) return addr.address;
          }
        }
      }
      // Fallback to first non-loopback IPv4
      for (final iface in interfaces) {
        for (final addr in iface.addresses) {
          if (!addr.isLoopback) return addr.address;
        }
      }
    } on Exception {
      return null;
    }
    return null;
  }
}
