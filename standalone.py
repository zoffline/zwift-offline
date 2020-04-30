#!/usr/bin/env python

import os
import signal
import sys
import threading
from datetime import datetime
if sys.version_info[0] > 2:
    import socketserver
    from http.server import SimpleHTTPRequestHandler
else:
    import SocketServer as socketserver
    from SimpleHTTPServer import SimpleHTTPRequestHandler

import zwift_offline

if getattr(sys, 'frozen', False):
    # If we're running as a pyinstaller bundle
    CDN_DIR = "%s/cdn" % sys._MEIPASS
    STORAGE_DIR = "%s/storage" % os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
    CDN_DIR = "%s/cdn" % SCRIPT_DIR
    STORAGE_DIR = "%s/storage" % SCRIPT_DIR

PROXYPASS_FILE = "%s/cdn-proxy.txt" % STORAGE_DIR
MAP_OVERRIDE = None

def sigint_handler(num, frame):
    httpd.shutdown()
    httpd.server_close()
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)


class CDNHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = SimpleHTTPRequestHandler.translate_path(self, path)
        relpath = os.path.relpath(path, os.getcwd())
        fullpath = os.path.join(CDN_DIR, relpath)
        return fullpath

    def do_GET(self):
        global MAP_OVERRIDE
        path_end = self.path.rsplit('/', 1)[1]
        if path_end in [ 'INNSBRUCK', 'LONDON', 'NEWYORK', 'RICHMOND', 'WATOPIA', 'YORKSHIRE' ]:
            MAP_OVERRIDE = path_end
            self.send_response(302)
            self.send_header('Location', 'https://secure.zwift.com/ride')
            self.end_headers()
            return
        if MAP_OVERRIDE and self.path == '/gameassets/MapSchedule_v2.xml':
            self.send_response(200)
            self.send_header('Content-type', 'text/xml')
            self.end_headers()
            self.wfile.write('<MapSchedule><appointments><appointment map="%s" start="%s"/></appointments><VERSION>1</VERSION></MapSchedule>' % (MAP_OVERRIDE, datetime.now().strftime("%Y-%m-%dT00:01-04")))
            MAP_OVERRIDE = None
            return
        elif self.path == '/gameassets/MapSchedule_v2.xml' and os.path.exists(PROXYPASS_FILE):
            # PROXYPASS_FILE existence indicates we know what we're doing and
            # we can try to obtain the official map schedule. This can only work
            # if we're running on a different machine than the Zwift client.
            try:
                import urllib3
                http = urllib3.PoolManager()
                r = http.request('GET', 'http://cdn.zwift.com/gameassets/MapSchedule_v2.xml')
                self.send_response(200)
                self.send_header('Content-type', 'text/xml')
                self.end_headers()
                self.wfile.write(r.data)
                return
            except:
                pass  # fallthrough to return zoffline version

        SimpleHTTPRequestHandler.do_GET(self)

socketserver.ThreadingTCPServer.allow_reuse_address = True
httpd = socketserver.ThreadingTCPServer(('', 80), CDNHandler)
zoffline_thread = threading.Thread(target=httpd.serve_forever)
zoffline_thread.daemon = True
zoffline_thread.start()

zwift_offline.run_standalone()
