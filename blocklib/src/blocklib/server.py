import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .core import HostsBlocker

DEFAULT_PORT = 8765


class BlockListHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/blocked-domains":
            self.send_response(404)
            self.end_headers()
            return
        blocked = HostsBlocker().blocked_urls
        body = json.dumps({"blocked": sorted(blocked)}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args) -> None:
        pass


def make_server(port: int = DEFAULT_PORT) -> HTTPServer:
    return HTTPServer(("127.0.0.1", port), BlockListHandler)
