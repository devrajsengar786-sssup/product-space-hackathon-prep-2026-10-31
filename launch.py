"""Start the local environment check, reusing a running Streamlit server."""
from pathlib import Path
import argparse
import socket
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener
import webbrowser

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8501'
HTTP = build_opener(ProxyHandler({}))


def healthy():
    try:
        with HTTP.open(URL + '/_stcore/health', timeout=1) as response:
            return response.status == 200 and response.read(64) == b'ok'
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if healthy():
        print('A Streamlit server is already running at ' + URL)
        if not args.no_browser:
            webbrowser.open(URL)
        return 0

    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', 8501))
        except OSError:
            print('Port 8501 is occupied. Close the other app using it, then try again.')
            return 1

    with (ROOT / 'server.log').open('a', encoding='utf-8') as log:
        process = subprocess.Popen(
            [sys.executable, '-m', 'streamlit', 'run', str(ROOT / 'app.py'),
             '--server.address=127.0.0.1', '--server.port=8501',
             '--server.headless=true', '--browser.gatherUsageStats=false'],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(60):
                if process.poll() is not None:
                    print('Startup failed. See server.log in this folder for details.')
                    return 1
                if healthy():
                    print('App ready: ' + URL + '\nKeep this window open. Press Ctrl+C to stop.')
                    if not args.no_browser:
                        webbrowser.open(URL)
                    process.wait()
                    return 0
                time.sleep(0.5)
            print('Startup timed out. See server.log in this folder for details.')
            return 1
        except KeyboardInterrupt:
            return 0
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)


if __name__ == '__main__':
    raise SystemExit(main())
