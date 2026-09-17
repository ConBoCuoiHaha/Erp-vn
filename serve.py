"""
Server tĩnh cho app/ — có mật khẩu (HTTP Basic Auth).

Dùng khi mở ra Internet qua tunnel: URL tunnel là công khai, ai đoán/quét được
link là vào được, mà app đang có dữ liệu thật (tên NCC, MST, số tiền).

Chạy:
    python serve.py                  # cổng 5173, user/mật khẩu mặc định bên dưới
    python serve.py 8080             # đổi cổng
    set ERP_USER=sep & set ERP_PASS=... & python serve.py     # đổi tài khoản (cmd)
    $env:ERP_USER='sep'; $env:ERP_PASS='...'; python serve.py # (PowerShell)

Đặt ERP_PASS rỗng để tắt hẳn mật khẩu (chỉ nên dùng khi chạy trong mạng LAN).
"""
import base64
import functools
import http.server
import os
import socket
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
USER = os.environ.get("ERP_USER", "lfood")
PASS = os.environ.get("ERP_PASS", "Lfood@2026")
REALM = "ERP Lifes Food"

_expected = "Basic " + base64.b64encode(f"{USER}:{PASS}".encode()).decode() if PASS else None


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def _denied(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="{REALM}", charset="UTF-8"')
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h3>Cần đăng nhập</h3>".encode("utf-8"))

    def _ok(self):
        if _expected is None:
            return True
        return self.headers.get("Authorization") == _expected

    def do_GET(self):
        if not self._ok():
            return self._denied()
        return super().do_GET()

    def do_HEAD(self):
        if not self._ok():
            return self._denied()
        return super().do_HEAD()

    def end_headers(self):
        # prototype thay đổi liên tục — đừng để trình duyệt cache bản cũ
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"  Thư mục : {ROOT}")
    print(f"  Máy này : http://localhost:{port}")
    print(f"  Mạng LAN: http://{lan_ip()}:{port}")
    print(f"  Đăng nhập: {USER} / {PASS}" if _expected else "  Đăng nhập: TẮT (không mật khẩu)")
    print("  Ctrl+C để dừng.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng.")
