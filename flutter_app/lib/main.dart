import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';

/// Shell that hosts the calendar served by the local FastAPI backend.
/// Change [serverUrl] to the machine running `uvicorn` (127.0.0.1 on desktop,
/// the PC's LAN IP on a phone/tablet).
const serverUrl = 'http://127.0.0.1:8000';

void main() => runApp(const CalendarApp());

class CalendarApp extends StatelessWidget {
  const CalendarApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'PhD MNH Calendar',
        theme: ThemeData(colorSchemeSeed: const Color(0xFFB8892B)),
        home: Scaffold(
          body: SafeArea(
            child: InAppWebView(initialUrlRequest: URLRequest(url: WebUri(serverUrl))),
          ),
        ),
      );
}
