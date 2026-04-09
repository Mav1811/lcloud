import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';

import 'screens/home_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const LcloudApp());
}

/// Root application widget.
class LcloudApp extends StatelessWidget {
  const LcloudApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Lcloud',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF4f46e5),
          surface: Color(0xFF1a1a2e),
        ),
        scaffoldBackgroundColor: const Color(0xFF1a1a2e),
        useMaterial3: true,
      ),
      home: const _PermissionsGate(),
    );
  }
}

/// Requests required permissions before showing the main screen.
class _PermissionsGate extends StatefulWidget {
  const _PermissionsGate();

  @override
  State<_PermissionsGate> createState() => _PermissionsGateState();
}

class _PermissionsGateState extends State<_PermissionsGate> {
  bool _permissionsGranted = false;
  bool _checking = true;
  String _statusMessage = 'Requesting permissions...';

  @override
  void initState() {
    super.initState();
    _requestPermissions();
  }

  Future<void> _requestPermissions() async {
    // Request storage permissions based on Android version
    final statuses = await [
      Permission.storage,
      Permission.photos,
      Permission.videos,
      Permission.audio,
    ].request();

    // For Android 11+ we also need MANAGE_EXTERNAL_STORAGE
    final manageStorage = await Permission.manageExternalStorage.status;
    if (manageStorage.isDenied) {
      await Permission.manageExternalStorage.request();
    }

    final allGranted = statuses.values.every(
      (s) => s.isGranted || s.isLimited,
    );

    final manageGranted = await Permission.manageExternalStorage.isGranted;
    if (mounted) {
      setState(() {
        _permissionsGranted = allGranted || manageGranted;
        _checking = false;
        _statusMessage = _permissionsGranted
            ? 'Permissions granted'
            : 'Some permissions were denied. File scanning may be limited.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_checking) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(color: Color(0xFF4f46e5)),
              SizedBox(height: 20),
              Text('Requesting permissions...', style: TextStyle(color: Colors.white70)),
            ],
          ),
        ),
      );
    }

    if (!_permissionsGranted) {
      return Scaffold(
        body: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.folder_off, size: 64, color: Color(0xFFf59e0b)),
              const SizedBox(height: 24),
              const Text(
                'Storage Permission Needed',
                style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              Text(
                _statusMessage,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Color(0xFF94a3b8)),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: openAppSettings,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF4f46e5),
                  minimumSize: const Size(200, 48),
                ),
                child: const Text('Open Settings', style: TextStyle(color: Colors.white)),
              ),
              const SizedBox(height: 12),
              TextButton(
                onPressed: () => setState(() {
                  _permissionsGranted = true; // Continue with limited access
                }),
                child: const Text('Continue Anyway',
                    style: TextStyle(color: Color(0xFF94a3b8))),
              ),
            ],
          ),
        ),
      );
    }

    return const HomeScreen();
  }
}
