#!/usr/bin/env python

import os
import signal
import struct
import sys
import threading
import time
import csv
from datetime import datetime
if sys.version_info[0] > 2:
    import socketserver
    from http.server import SimpleHTTPRequestHandler
    from urllib.parse import unquote
else:
    import SocketServer as socketserver
    from SimpleHTTPServer import SimpleHTTPRequestHandler
    from urllib2 import unquote

import zwift_offline
import protobuf.udp_node_msgs_pb2 as udp_node_msgs_pb2
import protobuf.tcp_node_msgs_pb2 as tcp_node_msgs_pb2

if getattr(sys, 'frozen', False):
    # If we're running as a pyinstaller bundle
    CDN_DIR = "%s/cdn" % sys._MEIPASS
    STORAGE_DIR = "%s/storage" % os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
    CDN_DIR = "%s/cdn" % SCRIPT_DIR
    STORAGE_DIR = "%s/storage" % SCRIPT_DIR

PROXYPASS_FILE = "%s/cdn-proxy.txt" % STORAGE_DIR
SERVER_IP_FILE = "%s/server-ip.txt" % STORAGE_DIR
MAP_OVERRIDE = None

ENABLEGHOSTS_FILE = "%s/enable_ghosts.txt" % STORAGE_DIR
enable_ghosts = os.path.exists(ENABLEGHOSTS_FILE)
rec = udp_node_msgs_pb2.Ghost()
play = udp_node_msgs_pb2.Ghosts()
seqno = 1
last_rec = 0
last_play = 0
play_count = 0
last_rt = 0
ghosts_loaded = False
ghosts_started = False
start_road = 0
start_rt = 0
update_freq = 3

def roadID(state):
    return (state.f20 & 0xff00) >> 8

def isForward(state):
    return (state.f19 & 4) != 0

def course(state):
    return (state.f19 & 0xff0000) >> 16

def boolean(s):
    if s.lower() in ['true', 'yes', '1']: return True
    if s.lower() in ['false', 'no', '0']: return False
    return None

def saveGhost(name):
    if not rec.player_id: return
    folder = '%s/%s/ghosts/%s/%s' % (STORAGE_DIR, rec.player_id, course(rec.states[0]), roadID(rec.states[0]))
    if not isForward(rec.states[0]): folder += '/reverse'
    try:
        if not os.path.isdir(folder):
            os.makedirs(folder)
    except:
        return
    f = '%s/%s-%s.bin' % (folder, time.strftime("%Y-%m-%d-%H-%M-%S"), unquote(name))
    with open(f, 'wb') as fd:
        fd.write(rec.SerializeToString())

def organizeGhosts(folder):
    # organize ghosts in course/roadID directory structure
    # previously they were saved directly in player_id/ghosts
    for f in os.listdir(folder):
        if f.endswith('.bin'):
            file = os.path.join(folder, f)
            with open(file, 'rb') as fd:
                g = udp_node_msgs_pb2.Ghost()
                g.ParseFromString(fd.read())
                dest = '%s/%s/%s' % (folder, course(g.states[0]), roadID(g.states[0]))
                if not isForward(g.states[0]): dest += '/reverse'
                try:
                    if not os.path.isdir(dest):
                        os.makedirs(dest)
                except:
                    return
            os.rename(file, os.path.join(dest, f))

def loadGhosts(player_id, state):
    global play
    global start_road
    global start_rt
    if not player_id: return
    folder = '%s/%s/ghosts/%s/%s' % (STORAGE_DIR, player_id, course(state), roadID(state))
    if not isForward(state): folder += '/reverse'
    if not os.path.isdir(folder): return
    s = list()
    for f in os.listdir(folder):
        if f.endswith('.bin'):
            with open(os.path.join(folder, f), 'rb') as fd:
                g = play.ghosts.add()
                g.ParseFromString(fd.read())
                s.append(g.states[0].roadTime)
    start_road = roadID(state)
    start_rt = 0
    sl_file = '%s/start_lines.csv' % STORAGE_DIR
    if os.path.isfile(sl_file):
        with open(sl_file, 'r') as fd:
            sl = [tuple(line) for line in csv.reader(fd)]
            rt = [t for t in sl if t[0] == str(course(state)) and t[1] == str(roadID(state)) and (boolean(t[2]) == isForward(state) or not t[2])]
            if rt:
                start_road = int(rt[0][3])
                start_rt = int(rt[0][4])
    if not start_rt:
        s.append(state.roadTime)
        if isForward(state): start_rt = max(s)
        else: start_rt = min(s)
    for g in play.ghosts:
        try:
            while roadID(g.states[0]) != start_road:
                del g.states[0]
            if isForward(g.states[0]):
                while not (g.states[0].roadTime <= start_rt <= g.states[1].roadTime):
                    del g.states[0]
            else:
                while not (g.states[0].roadTime >= start_rt >= g.states[1].roadTime):
                    del g.states[0]
        except IndexError:
            pass


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
        if path_end in ['FRANCE', 'INNSBRUCK', 'LONDON', 'NEWYORK', 'PARIS', 'RICHMOND', 'WATOPIA', 'YORKSHIRE']:
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
        if path_end.startswith('saveghost?'):
            self.send_response(200)
            self.end_headers()
            saveGhost(path_end[10:])
            return

        SimpleHTTPRequestHandler.do_GET(self)

class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.data = self.request.recv(1024)
        hello = tcp_node_msgs_pb2.TCPHello()
        try:
            hello.ParseFromString(self.data[3:-4])
        except:
            return
        # send packet containing UDP server (127.0.0.1)
        # (very little investigation done into this packet while creating
        #  protobuf structures hence the excessive "details" usage)
        msg = tcp_node_msgs_pb2.TCPServerInfo()
        msg.player_id = hello.player_id
        msg.f3 = 0
        servers = msg.servers.add()
        if os.path.exists(SERVER_IP_FILE):
            with open(SERVER_IP_FILE, 'r') as f:
                udp_node_ip = f.read().rstrip('\r\n')
        else:
            udp_node_ip = "127.0.0.1"
        details1 = servers.details.add()
        details1.f1 = 1
        details1.f2 = 6
        details1.ip = udp_node_ip
        details1.port = 3022
        details2 = servers.details.add()
        details2.f1 = 0
        details2.f2 = 0
        details2.ip = udp_node_ip
        details2.port = 3022
        servers.f2 = 10
        servers.f3 = 30
        servers.f4 = 3
        other_servers = msg.other_servers.add()
        wdetails1 = other_servers.details_wrapper.add()
        wdetails1.f1 = 1
        wdetails1.f2 = 6
        details3 = wdetails1.details.add()
        details3.CopyFrom(details1)
        wdetails2 = other_servers.details_wrapper.add()
        wdetails2.f1 = 0
        wdetails2.f2 = 0
        details4 = wdetails2.details.add()
        details4.CopyFrom(details2)
        other_servers.port = 3022
        payload = msg.SerializeToString()
        # Send size of payload as 2 bytes
        self.request.sendall(struct.pack('!h', len(payload)))
        self.request.sendall(payload)

        msg = tcp_node_msgs_pb2.RecurringTCPResponse()
        msg.player_id = hello.player_id
        msg.f3 = 0
        msg.f11 = 1
        payload = msg.SerializeToString()
        while True:
            tcpthreadevent.wait(timeout=25)
            try:
                self.request.sendall(struct.pack('!h', len(payload)))
                self.request.sendall(payload)
            except:
                break

class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        global seqno
        global rec
        global play
        global last_rec
        global last_play
        global play_count
        global last_rt
        global ghosts_loaded
        global ghosts_started

        data = self.request[0]
        socket = self.request[1]
        recv = udp_node_msgs_pb2.ClientToServer()
        try:
            recv.ParseFromString(data[:-4])
        except:
            return

        if recv.seqno == 1:
            del rec.states[:]
            del play.ghosts[:]
            seqno = 1
            last_rt = 0
            play_count = 0
            ghosts_loaded = False
            ghosts_started = False
            organizeGhosts('%s/%s/ghosts' % (STORAGE_DIR, recv.player_id))
            rec.player_id = recv.player_id

        t = int(time.time())

        if enable_ghosts:
            if not ghosts_loaded and course(recv.state):
                ghosts_loaded = True
                load = threading.Thread(target=loadGhosts, args=(recv.player_id, recv.state))
                load.start()
            if recv.state.roadTime and recv.state.roadTime != last_rt:
                if t >= last_rec + update_freq:
                    state = rec.states.add()
                    state.CopyFrom(recv.state)
                    last_rec = t
                if not ghosts_started and play.ghosts and roadID(recv.state) == start_road:
                    if isForward(recv.state):
                        if recv.state.roadTime >= start_rt >= last_rt:
                            ghosts_started = True
                    else:
                        if recv.state.roadTime <= start_rt <= last_rt:
                            ghosts_started = True
            last_rt = recv.state.roadTime

        if ghosts_started and t >= last_play + update_freq:
            message = udp_node_msgs_pb2.ServerToClient()
            message.f1 = 1
            message.player_id = recv.player_id
            message.f5 = 1
            message.f11 = 1
            msgnum = 1
            active_ghosts = 0
            for g in play.ghosts:
                if len(g.states) > play_count: active_ghosts += 1
            if active_ghosts:
                message.num_msgs = active_ghosts // 10
                if active_ghosts % 10: message.num_msgs += 1
                ghost_id = 1
                for g in play.ghosts:
                    if len(g.states) > play_count:
                        if len(message.states) < 10:
                            state = message.states.add()
                            state.CopyFrom(g.states[play_count])
                            state.id = ghost_id
                            state.worldTime = zwift_offline.world_time()
                        else:
                            message.world_time = zwift_offline.world_time()
                            message.seqno = seqno
                            message.msgnum = msgnum
                            socket.sendto(message.SerializeToString(), self.client_address)
                            seqno += 1
                            msgnum += 1
                            del message.states[:]
                            state = message.states.add()
                            state.CopyFrom(g.states[play_count])
                            state.id = ghost_id
                            state.worldTime = zwift_offline.world_time()
                    ghost_id += 1
            else: message.num_msgs = 1
            message.world_time = zwift_offline.world_time()
            message.seqno = seqno
            message.msgnum = msgnum
            socket.sendto(message.SerializeToString(), self.client_address)
            seqno += 1
            play_count += 1
            last_play = t
        else:
            message = udp_node_msgs_pb2.ServerToClient()
            message.f1 = 1
            message.player_id = recv.player_id
            message.world_time = zwift_offline.world_time()
            message.seqno = seqno
            message.f5 = 1
            message.f11 = 1
            message.num_msgs = 1
            message.msgnum = 1
            socket.sendto(message.SerializeToString(), self.client_address)
            seqno += 1

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
