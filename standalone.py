#!/usr/bin/env python

import os
import signal
import SocketServer
import sys
import threading
from datetime import datetime
from SimpleHTTPServer import SimpleHTTPRequestHandler

import zwift_offline

if getattr(sys, 'frozen', False):
    # If we're running as a pyinstaller bundle
    CDN_DIR = "%s/cdn" % sys._MEIPASS
else:
    CDN_DIR = "%s/cdn" % os.path.dirname(os.path.realpath(__file__))

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
        print self.path
        path_end = self.path.rsplit('/', 1)[1]
        if path_end in [ 'INNSBRUCK', 'LONDON', 'NEWYORK', 'RICHMOND', 'WATOPIA' ]:
            MAP_OVERRIDE = path_end
            self.send_response(302)
            self.send_header('Location', 'https://secure.zwift.com/ride')
            self.end_headers()
            return
        if MAP_OVERRIDE and self.path == '/gameassets/MapSchedule_v2.xml':
            print "Overrode map schedule with %s" % MAP_OVERRIDE
            self.send_response(200)
            self.send_header('Content-type', 'text/xml')
            self.end_headers()
            self.wfile.write('<MapSchedule><appointments><appointment map="%s" start="%s"/></appointments><VERSION>1</VERSION></MapSchedule>' % (MAP_OVERRIDE, datetime.now().strftime("%Y-%m-%dT00:01-04")))
            MAP_OVERRIDE = None
            return
        SimpleHTTPRequestHandler.do_GET(self)

SocketServer.ThreadingTCPServer.allow_reuse_address = True
httpd = SocketServer.ThreadingTCPServer(('', 80), CDNHandler)
zoffline_thread = threading.Thread(target=httpd.serve_forever)
zoffline_thread.daemon = True
zoffline_thread.start()

zwift_offline.run_standalone()
