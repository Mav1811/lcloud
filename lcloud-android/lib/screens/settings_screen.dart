import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

const Color _bgColor = Color(0xFF1a1a2e);
const Color _cardColor = Color(0xFF16213e);
const Color _accentColor = Color(0xFF4f46e5);
const Color _textSecondary = Color(0xFF94a3b8);

const String _keyThreshold = 'storage_threshold';
const String _keyIncludeWhatsapp = 'include_whatsapp';
const String _keyIncludePhotos = 'include_photos';
const String _keyIncludeVideos = 'include_videos';
const String _keyIncludeDocs = 'include_documents';

/// Settings screen for Lcloud.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  double _threshold = 15.0;
  bool _includeWhatsapp = true;
  bool _includePhotos = true;
  bool _includeVideos = true;
  bool _includeDocs = true;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _threshold = prefs.getDouble(_keyThreshold) ?? 15.0;
      _includeWhatsapp = prefs.getBool(_keyIncludeWhatsapp) ?? true;
      _includePhotos = prefs.getBool(_keyIncludePhotos) ?? true;
      _includeVideos = prefs.getBool(_keyIncludeVideos) ?? true;
      _includeDocs = prefs.getBool(_keyIncludeDocs) ?? true;
      _loading = false;
    });
  }

  Future<void> _saveSettings() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_keyThreshold, _threshold);
    await prefs.setBool(_keyIncludeWhatsapp, _includeWhatsapp);
    await prefs.setBool(_keyIncludePhotos, _includePhotos);
    await prefs.setBool(_keyIncludeVideos, _includeVideos);
    await prefs.setBool(_keyIncludeDocs, _includeDocs);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Settings saved'), backgroundColor: _accentColor),
      );
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: const Text('Settings', style: TextStyle(color: Colors.white)),
        backgroundColor: _bgColor,
        iconTheme: const IconThemeData(color: Colors.white),
        elevation: 0,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: _accentColor))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _sectionHeader('Auto-Backup Trigger'),
                _thresholdCard(),
                const SizedBox(height: 16),
                _sectionHeader('File Types to Include'),
                _toggleCard('WhatsApp Media', Icons.chat, _includeWhatsapp,
                    (v) => setState(() => _includeWhatsapp = v)),
                _toggleCard('Photos', Icons.photo, _includePhotos,
                    (v) => setState(() => _includePhotos = v)),
                _toggleCard('Videos', Icons.videocam, _includeVideos,
                    (v) => setState(() => _includeVideos = v)),
                _toggleCard('Documents', Icons.description, _includeDocs,
                    (v) => setState(() => _includeDocs = v)),
                const SizedBox(height: 16),
                _sectionHeader('About'),
                _aboutCard(),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: _saveSettings,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _accentColor,
                    minimumSize: const Size(double.infinity, 52),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                  child: const Text('Save Settings',
                      style: TextStyle(fontSize: 16, color: Colors.white)),
                ),
              ],
            ),
    );
  }

  Widget _sectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Text(
        title,
        style: const TextStyle(
            color: _textSecondary, fontSize: 12, fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _thresholdCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Auto-backup when storage below',
                  style: TextStyle(color: Colors.white, fontSize: 14)),
              Text('${_threshold.round()}%',
                  style: const TextStyle(color: _accentColor, fontSize: 16, fontWeight: FontWeight.bold)),
            ],
          ),
          Slider(
            value: _threshold,
            min: 5,
            max: 30,
            divisions: 25,
            activeColor: _accentColor,
            inactiveColor: Colors.white12,
            onChanged: (v) => setState(() => _threshold = v),
          ),
          const Text(
            'When your phone storage drops below this percentage, backup will start automatically. (v0.2 feature)',
            style: TextStyle(color: _textSecondary, fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _toggleCard(
      String label, IconData icon, bool value, ValueChanged<bool> onChanged) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(14),
      ),
      child: SwitchListTile(
        title: Text(label, style: const TextStyle(color: Colors.white)),
        secondary: Icon(icon, color: value ? _accentColor : _textSecondary),
        value: value,
        activeColor: _accentColor,
        onChanged: onChanged,
      ),
    );
  }

  Widget _aboutCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(14),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Lcloud v0.1.0',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
          SizedBox(height: 6),
          Text('Open source WiFi backup tool.',
              style: TextStyle(color: _textSecondary, fontSize: 13)),
          SizedBox(height: 4),
          Text('github.com/lcloud-app/lcloud (coming in v0.5)',
              style: TextStyle(color: _textSecondary, fontSize: 12)),
        ],
      ),
    );
  }
}
