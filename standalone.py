#!/usr/bin/env python

import os
import signal
import sys
import threading
import time
from datetime import datetime
if sys.version_info[0] > 2:
    import socketserver
    from http.server import SimpleHTTPRequestHandler
else:
    import SocketServer as socketserver
    from SimpleHTTPServer import SimpleHTTPRequestHandler

import zwift_offline
import protobuf.messages_pb2 as messages_pb2

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
    tcpthreadevent.set()
    tcpserver.shutdown()
    tcpserver.server_close()
    udpserver.shutdown()
    udpserver.server_close()
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
            output = '<MapSchedule><appointments><appointment map="%s" start="%s"/></appointments><VERSION>1</VERSION></MapSchedule>' % (MAP_OVERRIDE, datetime.now().strftime("%Y-%m-%dT00:01-04"))
            self.wfile.write(output.encode())
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

class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.data = self.request.recv(1024)
        # send packet containing UDP server (127.0.0.1)
        # it contains player_id (1000) but apparently client doesn't bother, works for other profiles
        self.request.sendall(bytearray.fromhex('007010e8071800c2012e0a12080110061a093132372e302e302e3120ce170a12080010001a093132372e302e302e3120ce17100a181e2003ca01370a18080110061a12080110061a093132372e302e302e3120ce170a18080010001a12080010001a093132372e302e302e3120ce1710ce17'))
        while True:
            tcpthreadevent.wait(timeout=25)
            try:
                self.request.sendall(bytearray.fromhex('000710e80718005801'))
            except:
                break

class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        socket = self.request[1]
        message = messages_pb2.ServerToClient()
        message.f1 = 1
        message.player_id = 1000
        message.world_time = int(time.time()-1414016075)*1000
        message.seqno = 1
        message.f5 = 1
        message.f11 = 1
        message.num_msgs = 1
        message.msgnum = 1
        socket.sendto(message.SerializeToString(), self.client_address)

socketserver.ThreadingTCPServer.allow_reuse_address = True
httpd = socketserver.ThreadingTCPServer(('', 80), CDNHandler)
zoffline_thread = threading.Thread(target=httpd.serve_forever)
zoffline_thread.daemon = True
zoffline_thread.start()

tcpthreadevent = threading.Event()
tcpserver = socketserver.ThreadingTCPServer(('', 3023), TCPHandler)
tcpserver_thread = threading.Thread(target=tcpserver.serve_forever)
tcpserver_thread.daemon = True
tcpserver_thread.start()

socketserver.ThreadingUDPServer.allow_reuse_address = True
udpserver = socketserver.ThreadingUDPServer(('', 3022), UDPHandler)
udpserver_thread = threading.Thread(target=udpserver.serve_forever)
udpserver_thread.daemon = True
udpserver_thread.start()

zwift_offline.run_standalone()
