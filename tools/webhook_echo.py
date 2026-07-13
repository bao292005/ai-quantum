"""
tools/webhook_echo.py

Local echo server dùng để test luồng gửi webhook alert (Epic 5) khi chưa
có client thật để nhận payload RED/YELLOW.

Chỉ dùng thư viện chuẩn (http.server) — không thêm dependency mới.

Cách chạy:
    python -m tools.webhook_echo listen http://localhost:9000/hook
    # hoặc chạy trực tiếp file (mặc định listen http://localhost:9000/hook)
    python tools/webhook_echo.py

Server sẽ:
    - Lắng nghe HTTP POST tại host:port bất kỳ path nào (path được log ra,
      nhưng không dùng để routing — mọi request POST đều được nhận).
    - In ra stdout: method, một số header tối thiểu (Content-Type,
      Content-Length, User-Agent) và body đã parse JSON (pretty-print).
    - Luôn trả về HTTP 200 với body {"status": "ok"}.

Lưu ý: server này KHÔNG có auth/TLS — chỉ dùng cho dev cục bộ. Không
dùng để nhận payload nhạy cảm hoặc chạy trên môi trường production.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9000

# Các header "tối thiểu" cần in ra theo AC4.
HEADERS_TO_LOG = ("Content-Type", "Content-Length", "User-Agent")


class WebhookEchoHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def do_POST(self) -> None:
        self._handle_request(method="POST")

    def do_GET(self) -> None:
        self._handle_request(method="GET")

    def _handle_request(self, method: str) -> None:
        content_length = int(self.headers.get("Content-Length", 0) or 0)
        raw_body = self.rfile.read(content_length) if content_length else b""

        parsed_body = None
        parse_error = None
        if raw_body:
            try:
                parsed_body = json.loads(raw_body)
            except json.JSONDecodeError as exc:
                parse_error = str(exc)

        self._print_request(method=method, raw_body=raw_body,
                             parsed_body=parsed_body, parse_error=parse_error)

        response_payload = json.dumps({"status": "ok"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_payload)))
        self.end_headers()
        self.wfile.write(response_payload)

    def _print_request(self, *, method: str, raw_body: bytes,
                        parsed_body, parse_error) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        print(f"\n=== [{ts}] {method} {self.path} ===")

        print("-- headers (tối thiểu) --")
        for header_name in HEADERS_TO_LOG:
            value = self.headers.get(header_name)
            if value is not None:
                print(f"{header_name}: {value}")

        print("-- body --")
        if parsed_body is not None:
            print(json.dumps(parsed_body, indent=2, ensure_ascii=False))
        elif parse_error:
            print(f"(khong parse duoc JSON: {parse_error})")
            print(raw_body.decode("utf-8", errors="replace"))
        else:
            print("(empty body)")
        sys.stdout.flush()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m tools.webhook_echo",
        description="Local echo server nhận webhook test payload.",
    )
    subparsers = parser.add_subparsers(dest="command")

    listen_parser = subparsers.add_parser(
        "listen", help="Chạy server lắng nghe tại URL chỉ định."
    )
    listen_parser.add_argument(
        "url",
        nargs="?",
        default=f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/hook",
        help="URL để lắng nghe, vd: http://localhost:9000/hook "
             "(mặc định: http://localhost:9000/hook)",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    url = getattr(args, "url", None) or f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/hook"
    parsed = urlparse(url)
    host = parsed.hostname or DEFAULT_HOST
    port = parsed.port or DEFAULT_PORT
    path = parsed.path or "/"

    server = HTTPServer((host, port), WebhookEchoHandler)
    print(f"[webhook_echo] listening on http://{host}:{port}{path}")
    print("[webhook_echo] Ctrl+C de dung.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[webhook_echo] stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()