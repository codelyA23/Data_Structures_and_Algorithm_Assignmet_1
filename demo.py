import argparse
import json
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from demo_engine import batch_demo, evaluate_demo


APP_DIRECTORY = Path(__file__).resolve().parent


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIRECTORY / "ui"), **kwargs)

    def log_message(self, format, *args):
        pass

    def respond(self, value, status=200):
        content = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/health":
            self.respond({"ready": True})
        elif path == "/main.py":
            content = (APP_DIRECTORY / "main.py").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
        else:
            super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ("/api/evaluate", "/api/batch"):
            self.respond({"error": "Unknown operation."}, 404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 4_000_000:
                raise ValueError("The request must be smaller than 4 MB.")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict) or not isinstance(payload.get("input"), str):
                raise ValueError("Provide expression or file content as text.")
            text = payload["input"]
            if path == "/api/evaluate" and len(text) > 10000:
                raise ValueError("Use an expression of up to 10,000 characters.")
            result = evaluate_demo(text) if path == "/api/evaluate" else batch_demo(text)
            self.respond(result)
        except (ValueError, UnicodeError) as error:
            self.respond({"error": str(error)}, 400)
        except Exception:
            self.respond({"error": "The calculation could not be completed. Try a smaller input."}, 500)


def main():
    parser = argparse.ArgumentParser(description="Run the Stack Lab browser demo on your laptop.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), DemoHandler)
    except OSError as error:
        print(f"Could not start the demo: {error}")
        print("Try a different port: python3 demo.py --port 8001")
        return 1
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Stack Lab is running at {url}", flush=True)
    print("Keep this window open. Press Ctrl+C to stop.", flush=True)
    if not args.no_browser:
        timer = threading.Timer(0.5, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStack Lab stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
