import 'dart:collection';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

/// Configure with --dart-define=SERVER_URL=http://192.168.1.10:8000
/// Use the backend computer's LAN address on a phone/tablet, not 127.0.0.1.
const serverUrl = String.fromEnvironment(
  'SERVER_URL',
  defaultValue: 'http://127.0.0.1:8000',
);
const secureStorage = FlutterSecureStorage();

void main() => runApp(const CalendarApp());

class CalendarApp extends StatelessWidget {
  const CalendarApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'PhD MNH Academic Calendar',
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFFB8892B),
          ),
          useMaterial3: true,
        ),
        home: const AuthGate(),
      );
}

class Api {
  static Map<String, String> headers(String token) => {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      };

  static Future<dynamic> get(String token, String path) async {
    final response = await http.get(
      Uri.parse('$serverUrl$path'),
      headers: headers(token),
    );
    return _decode(response);
  }

  static Future<dynamic> post(String token, String path) async {
    final response = await http.post(
      Uri.parse('$serverUrl$path'),
      headers: headers(token),
      body: jsonEncode(<String, dynamic>{}),
    );
    return _decode(response);
  }

  static dynamic _decode(http.Response response) {
    dynamic value;
    try {
      value = jsonDecode(response.body);
    } catch (_) {
      value = <String, dynamic>{};
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = value is Map ? value['detail'] : null;
      throw Exception(detail ?? 'Server request failed (${response.statusCode}).');
    }
    return value;
  }
}

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  String? _token;
  bool _checking = true;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    final token = await secureStorage.read(key: 'staff_token');
    if (token != null && token.isNotEmpty) {
      try {
        await Api.get(token, '/api/comms/whoami');
        if (mounted) setState(() => _token = token);
      } catch (_) {
        await secureStorage.delete(key: 'staff_token');
      }
    }
    if (_token == null) {
      // Outside production the backend accepts a tokenless local session and
      // reports dev=true, so the mobile shell can skip its sign-in screen too.
      try {
        final who = await Api.get('', '/api/comms/whoami');
        if (who is Map && who['dev'] == true && mounted) setState(() => _token = '');
      } catch (_) {}
    }
    if (mounted) setState(() => _checking = false);
  }

  Future<void> _signedIn(String token) async {
    await secureStorage.write(key: 'staff_token', value: token);
    if (mounted) setState(() => _token = token);
  }

  Future<void> _signedOut() async {
    await secureStorage.delete(key: 'staff_token');
    if (mounted) setState(() => _token = null);
  }

  @override
  Widget build(BuildContext context) {
    if (_checking) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_token == null) return LoginScreen(onSignedIn: _signedIn);
    return HomeScreen(token: _token!, onSignOut: _signedOut);
  }
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.onSignedIn});
  final ValueChanged<String> onSignedIn;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _token = TextEditingController();
  bool _busy = false;
  String? _error;

  Future<void> _login() async {
    final token = _token.text.trim();
    if (token.isEmpty) {
      setState(() => _error = 'Enter your staff access token.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await Api.get(token, '/api/comms/whoami');
      widget.onSignedIn(token);
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    _token.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 460),
            child: Padding(
              padding: const EdgeInsets.all(28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Icon(Icons.school, size: 54),
                  const SizedBox(height: 16),
                  Text(
                    'PhD MNH Academic Calendar',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Sign in using the staff token issued by the programme administrator.',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 22),
                  TextField(
                    controller: _token,
                    obscureText: true,
                    decoration: const InputDecoration(
                      labelText: 'Staff access token',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _login(),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 10),
                    Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  ],
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: _busy ? null : _login,
                    child: _busy
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Sign in'),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Server: $serverUrl',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
        ),
      );
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.token, required this.onSignOut});
  final String token;
  final VoidCallback onSignOut;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _loading = true;
  String? _error;
  String _name = '';
  String _role = '';
  List<Map<String, dynamic>> _events = [];
  List<Map<String, dynamic>> _notices = [];
  bool get _studentPortal => _role == 'student' || _role == 'class_rep';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final who = await Api.get(widget.token, '/api/comms/whoami') as Map;
      _name = (who['name'] ?? '').toString();
      _role = (who['role'] ?? '').toString();
      if (_studentPortal) {
        final data = await Api.get(widget.token, '/api/comms/student/agenda') as Map;
        _name = (data['person']?['name'] ?? _name).toString();
        _events = List<Map<String, dynamic>>.from(data['events'] ?? const []);
        _notices = List<Map<String, dynamic>>.from(data['notices'] ?? const []);
      } else {
        final data = await Api.get(widget.token, '/api/bootstrap') as Map;
        _events = List<Map<String, dynamic>>.from(data['events'] ?? const []);
        _events.sort((a, b) => '${a['date']} ${a['start'] ?? ''}'.compareTo('${b['date']} ${b['start'] ?? ''}'));
        _notices = [];
      }
    } catch (e) {
      _error = e.toString().replaceFirst('Exception: ', '');
      if (_error!.contains('401')) widget.onSignOut();
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _acknowledge(dynamic id) async {
    try {
      await Api.post(widget.token, '/api/comms/student/ack/$id');
      await _load();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Acknowledgement recorded. This is not an attendance record.')),
      );
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString().replaceFirst('Exception: ', ''))),
      );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('PhD MNH Calendar'),
          actions: [
            IconButton(tooltip: 'Refresh', onPressed: _load, icon: const Icon(Icons.refresh)),
            IconButton(tooltip: 'Full calendar', onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => FullCalendarScreen(token: widget.token)),
            ), icon: const Icon(Icons.calendar_month)),
            IconButton(tooltip: 'Sign out', onPressed: widget.onSignOut, icon: const Icon(Icons.logout)),
          ],
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? _MessagePanel(message: _error!, onRetry: _load)
                : RefreshIndicator(
                    onRefresh: _load,
                    child: ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        Text('Welcome, $_name', style: Theme.of(context).textTheme.headlineSmall),
                        Text(_role.replaceAll('_', ' ').toUpperCase()),
                        const SizedBox(height: 16),
                        Text(_studentPortal ? 'My academic schedule' : 'Academic calendar',
                            style: Theme.of(context).textTheme.titleLarge),
                        if (_events.isEmpty)
                          const Padding(
                            padding: EdgeInsets.symmetric(vertical: 24),
                            child: Text('No activities are currently assigned or scheduled.'),
                          ),
                        ..._events.map(_eventCard),
                        if (_studentPortal) ...[
                          const SizedBox(height: 18),
                          Text('Academic notices', style: Theme.of(context).textTheme.titleLarge),
                          if (_notices.isEmpty) const Text('No notices.'),
                          ..._notices.map((n) => Card(
                                child: ListTile(
                                  leading: const Icon(Icons.notifications_active_outlined),
                                  title: Text((n['text'] ?? '').toString()),
                                  subtitle: Text((n['ts'] ?? '').toString()),
                                ),
                              )),
                        ],
                      ],
                    ),
                  ),
      );

  Widget _eventCard(Map<String, dynamic> event) {
    final acknowledged = event['acknowledged'] == true;
    final time = event['start'] == null || event['start'].toString().isEmpty
        ? 'Time not confirmed'
        : '${event['start']}–${event['end']}';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text((event['title'] ?? '').toString(),
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16)),
            const SizedBox(height: 6),
            Text('${event['date'] ?? ''} · $time'),
            if ((event['venue'] ?? '').toString().isNotEmpty) Text('Venue: ${event['venue']}'),
            if (_studentPortal) ...[
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: acknowledged
                    ? const Chip(label: Text('Acknowledged'))
                    : OutlinedButton.icon(
                        onPressed: () => _acknowledge(event['id']),
                        icon: const Icon(Icons.done),
                        label: const Text('Acknowledge'),
                      ),
              ),
              const Text('Acknowledgement confirms you have seen the notice; it does not record attendance.',
                  style: TextStyle(fontSize: 11)),
            ],
          ],
        ),
      ),
    );
  }
}

class FullCalendarScreen extends StatelessWidget {
  const FullCalendarScreen({super.key, required this.token});
  final String token;

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Full calendar and editor')),
        body: InAppWebView(
          initialUrlRequest: URLRequest(url: WebUri(serverUrl)),
          initialUserScripts: UnmodifiableListView<UserScript>([
            UserScript(
              source: 'sessionStorage.setItem("ctoken", ${jsonEncode(token)});',
              injectionTime: UserScriptInjectionTime.AT_DOCUMENT_START,
            ),
          ]),
          initialSettings: InAppWebViewSettings(
            javaScriptEnabled: true,
            useShouldOverrideUrlLoading: true,
            mediaPlaybackRequiresUserGesture: false,
          ),
        ),
      );
}

class _MessagePanel extends StatelessWidget {
  const _MessagePanel({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off, size: 48),
              const SizedBox(height: 12),
              Text(message, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
}
