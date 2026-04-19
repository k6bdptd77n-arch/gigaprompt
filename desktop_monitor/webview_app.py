#!/usr/bin/env python3
"""
Super Memory — native WebView entry-point.

Boots Flask + WebSocket in background threads, then opens a native pywebview
window. Falls back to opening the system browser if pywebview is missing.
"""

import sys
import threading
import time

from desktop_monitor.app import UI_TOKEN, start_flask, start_websocket_server


URL = f'http://127.0.0.1:5000/?token={UI_TOKEN}'


def _start_servers():
    threading.Thread(target=start_websocket_server, daemon=True).start()
    threading.Thread(target=start_flask, daemon=True).start()
    time.sleep(1.5)


def main():
    _start_servers()
    print(f'Super Memory ready at {URL}')

    try:
        import webview
    except ImportError:
        import webbrowser
        print('pywebview not installed — opening in system browser.')
        print('Install with: pip install pywebview')
        webbrowser.open(URL)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return

    webview.create_window(
        'Super Memory',
        URL,
        width=1400,
        height=900,
        min_size=(1000, 640),
    )
    webview.start()


if __name__ == '__main__':
    sys.exit(main() or 0)
