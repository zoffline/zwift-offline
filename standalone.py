#!/usr/bin/env python

import os
import signal
import SocketServer
import sys
import threading
from SimpleHTTPServer import SimpleHTTPRequestHandler

import zwift_offline

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

def sigint_handler(num, frame):
	httpd.shutdown()
	httpd.server_close()
        sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)


class CDNHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = SimpleHTTPRequestHandler.translate_path(self, path)
        relpath = os.path.relpath(path, os.getcwd())
        fullpath = os.path.join("%s/cdn" % SCRIPT_DIR, relpath)
        return fullpath

SocketServer.ThreadingTCPServer.allow_reuse_address = True
httpd = SocketServer.ThreadingTCPServer(('', 80), CDNHandler)
zoffline_thread = threading.Thread(target=httpd.serve_forever)
zoffline_thread.daemon = True
zoffline_thread.start()

zwift_offline.run_standalone()
