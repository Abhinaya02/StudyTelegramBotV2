import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    print(f"Starting health check web server on port {port}...")
    httpd.serve_forever()

def keep_alive():
    t = threading.Thread(target=run_dummy_server)
    t.daemon = True
    t.start()
