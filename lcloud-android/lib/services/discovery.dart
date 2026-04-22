/// Lcloud Android — Device Discovery (Multicast UDP)
///
/// Listens for the PC's multicast broadcast on 224.0.0.167:53317.
/// Uses the native platform channel (MainActivity.kt) to acquire a
/// WifiManager.MulticastLock before joining the multicast group — required
/// on Android to receive multicast packets from the WiFi chip.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';

const String _multicastGroup = '224.0.0.167';
const int _multicastPort = 53317;
const _channel = MethodChannel('com.lcloud.lcloud/multicast');

/// A PC running Lcloud that is broadcasting its presence.
class DiscoveredPC {
  const DiscoveredPC({
    required this.name,
    required this.address,
    required this.port,
    required this.fingerprint,
  });

  final String name;
  final String address;
  final int port;
  final String fingerprint;

  @override
  String toString() => 'DiscoveredPC($name @ $address:$port)';
}

/// Listens for PC broadcasts on the local multicast group.
///
/// Usage:
///   final discovery = LcloudDiscovery();
///   discovery.startListening(onFound: (pc) { ... });
///   // later:
///   discovery.stopDiscovery();
class LcloudDiscovery {
  RawDatagramSocket? _socket;
  bool _running = false;

  /// Start listening for PC broadcasts.
  ///
  /// [onFound] fires each time a valid broadcast is parsed — it may fire
  /// multiple times for the same PC (once per 2-second interval).
  /// Deduplicate by [DiscoveredPC.address] in the caller if needed.
  Future<void> startListening({
    required void Function(DiscoveredPC pc) onFound,
  }) async {
    _running = true;

    // Acquire WiFi multicast lock — required on Android to receive multicast.
    // On error (e.g. emulator), we continue without it — best effort.
    try {
      await _channel.invokeMethod<void>('acquireLock');
    } catch (_) {}

    try {
      _socket = await RawDatagramSocket.bind(
        InternetAddress.anyIPv4,
        _multicastPort,
        reuseAddress: true,
      );
      _socket!.joinMulticast(InternetAddress(_multicastGroup));

      await for (final event in _socket!) {
        if (!_running) break;
        if (event != RawSocketEvent.read) continue;

        final datagram = _socket!.receive();
        if (datagram == null) continue;

        try {
          final text = utf8.decode(datagram.data);
          final map = jsonDecode(text) as Map<String, dynamic>;

          if (map['protocol'] != 'https') continue;

          final pc = DiscoveredPC(
            name: (map['alias'] as String?) ?? 'Lcloud PC',
            address: datagram.address.address,
            port: (map['port'] as int?) ?? _multicastPort,
            fingerprint: (map['fingerprint'] as String?) ?? '',
          );
          onFound(pc);
        } catch (_) {
          // Malformed packet — ignore silently
        }
      }
    } finally {
      try {
        await _channel.invokeMethod<void>('releaseLock');
      } catch (_) {}
    }
  }

  /// Stop listening and release the multicast lock.
  void stopDiscovery() {
    _running = false;
    _socket?.close();
    _socket = null;
  }

  /// Returns the device's local WiFi IP (first non-loopback IPv4 address).
  static Future<String?> getLocalIP() async {
    try {
      final interfaces = await NetworkInterface.list(
        type: InternetAddressType.IPv4,
        includeLinkLocal: false,
      );
      for (final iface in interfaces) {
        for (final addr in iface.addresses) {
          if (!addr.isLoopback) return addr.address;
        }
      }
    } catch (_) {}
    return null;
  }
}
