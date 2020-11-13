#!/usr/bin/env python

import os
import signal
import struct
import sys
import threading
import time
import csv
import requests
from collections import deque
from datetime import datetime
from shutil import copyfile
if sys.version_info[0] > 2:
    import socketserver
    from http.server import SimpleHTTPRequestHandler
else:
    import SocketServer as socketserver
    from SimpleHTTPServer import SimpleHTTPRequestHandler

import zwift_offline
import protobuf.udp_node_msgs_pb2 as udp_node_msgs_pb2
import protobuf.tcp_node_msgs_pb2 as tcp_node_msgs_pb2
import protobuf.profile_pb2 as profile_pb2

if getattr(sys, 'frozen', False):
    # If we're running as a pyinstaller bundle
    CDN_DIR = "%s/cdn" % sys._MEIPASS
    STORAGE_DIR = "%s/storage" % os.path.dirname(sys.executable)
    START_LINES_FILE = '%s/start_lines.csv' % STORAGE_DIR
    if not os.path.isfile(START_LINES_FILE):
        copyfile('%s/start_lines.csv' % sys._MEIPASS, START_LINES_FILE)
else:
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
    CDN_DIR = "%s/cdn" % SCRIPT_DIR
    STORAGE_DIR = "%s/storage" % SCRIPT_DIR
    START_LINES_FILE = '%s/start_lines.csv' % SCRIPT_DIR

PROXYPASS_FILE = "%s/cdn-proxy.txt" % STORAGE_DIR
SERVER_IP_FILE = "%s/server-ip.txt" % STORAGE_DIR
MAP_OVERRIDE = deque(maxlen=16)

ghost_update_freq = 3
pacer_update_freq = 1
last_pp_updates = {}
global_ghosts = {}
ghosts_enabled = {}
online = {}
player_update_queue = {}
global_pace_partners = {}

def road_id(state):
    return (state.f20 & 0xff00) >> 8

def is_forward(state):
    return (state.f19 & 4) != 0

def get_course(state):
    return (state.f19 & 0xff0000) >> 16

def boolean(s):
    if s.lower() in ['true', 'yes', '1']: return True
    if s.lower() in ['false', 'no', '0']: return False
    return None

def save_ghost(name, player_id):
    global global_ghosts
    if not player_id in global_ghosts.keys(): return
    ghosts = global_ghosts[player_id]
    if len(ghosts.rec.states) > 0:
        folder = '%s/%s/ghosts/%s/%s' % (STORAGE_DIR, player_id, get_course(ghosts.rec.states[0]), road_id(ghosts.rec.states[0]))
        if not is_forward(ghosts.rec.states[0]): folder += '/reverse'
        try:
            if not os.path.isdir(folder):
                os.makedirs(folder)
        except:
            return
        f = '%s/%s-%s.bin' % (folder, zwift_offline.get_utc_date_time().strftime("%Y-%m-%d-%H-%M-%S"), name)
        with open(f, 'wb') as fd:
            fd.write(ghosts.rec.SerializeToString())

def organize_ghosts(player_id):
    # organize ghosts in course/road_id directory structure
    # previously they were saved directly in player_id/ghosts
    folder = '%s/%s/ghosts' % (STORAGE_DIR, player_id)
    if not os.path.isdir(folder): return
    for f in os.listdir(folder):
        if f.endswith('.bin'):
            file = os.path.join(folder, f)
            with open(file, 'rb') as fd:
                g = udp_node_msgs_pb2.Ghost()
                g.ParseFromString(fd.read())
                dest = '%s/%s/%s' % (folder, get_course(g.states[0]), road_id(g.states[0]))
                if not is_forward(g.states[0]): dest += '/reverse'
                try:
                    if not os.path.isdir(dest):
                        os.makedirs(dest)
                except:
                    return
            os.rename(file, os.path.join(dest, f))

def load_ghosts(player_id, state, ghosts):
    folder = '%s/%s/ghosts/%s/%s' % (STORAGE_DIR, player_id, get_course(state), road_id(state))
    if not is_forward(state): folder += '/reverse'
    if not os.path.isdir(folder): return
    s = list()
    for f in os.listdir(folder):
        if f.endswith('.bin'):
            with open(os.path.join(folder, f), 'rb') as fd:
                g = ghosts.play.ghosts.add()
                g.ParseFromString(fd.read())
                s.append(g.states[0].roadTime)
    ghosts.start_road = road_id(state)
    ghosts.start_rt = 0
    if os.path.isfile(START_LINES_FILE):
        with open(START_LINES_FILE, 'r') as fd:
            sl = [tuple(line) for line in csv.reader(fd)]
            rt = [t for t in sl if t[0] == str(get_course(state)) and t[1] == str(road_id(state)) and (boolean(t[2]) == is_forward(state) or not t[2])]
            if rt:
                ghosts.start_road = int(rt[0][3])
                ghosts.start_rt = int(rt[0][4])
    if not ghosts.start_rt:
        s.append(state.roadTime)
        if is_forward(state): ghosts.start_rt = max(s)
        else: ghosts.start_rt = min(s)
    for g in ghosts.play.ghosts:
        try:
            while road_id(g.states[0]) != ghosts.start_road:
                del g.states[0]
            if is_forward(g.states[0]):
                while not (g.states[0].roadTime <= ghosts.start_rt <= g.states[1].roadTime):
                    del g.states[0]
            else:
                while not (g.states[0].roadTime >= ghosts.start_rt >= g.states[1].roadTime):
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

hostname = 'cdn.zwift.com'

def merge_two_dicts(x, y):
    z = x.copy()
    z.update(y)
    return z

def set_header():
    headers = {
        'Host': hostname
    }
    return headers

class CDNHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = SimpleHTTPRequestHandler.translate_path(self, path)
        relpath = os.path.relpath(path, os.getcwd())
        fullpath = os.path.join(CDN_DIR, relpath)
        return fullpath

    def do_GET(self):
        path_end = self.path.split('/')[-1]
        if path_end in ['FRANCE', 'INNSBRUCK', 'LONDON', 'NEWYORK', 'PARIS', 'RICHMOND', 'WATOPIA', 'YORKSHIRE']:
            # We have no identifying information when Zwift makes MapSchedule request except for the client's IP.
            MAP_OVERRIDE.append((self.client_address[0], path_end))
            self.send_response(302)
            self.send_header('Cookie', self.headers.get('Cookie') + "; map=%s" % path_end)
            self.send_header('Location', 'https://secure.zwift.com/ride')
            self.end_headers()
            return
        if self.path == '/gameassets/MapSchedule_v2.xml':
            # Check if client requested the map be overridden
            for override in MAP_OVERRIDE:
                if override[0] == self.client_address[0]:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/xml')
                    self.end_headers()
                    output = '<MapSchedule><appointments><appointment map="%s" start="%s"/></appointments><VERSION>1</VERSION></MapSchedule>' % (override[1], datetime.now().strftime("%Y-%m-%dT00:01-04"))
                    self.wfile.write(output.encode())
                    MAP_OVERRIDE.remove(override)
                    return
        exceptions = ['Launcher_ver_cur.xml', 'LauncherMac_ver_cur.xml',
                      'Zwift_ver_cur.xml', 'ZwiftMac_ver_cur.xml',
                      'ZwiftAndroid_ver_cur.xml', 'Zwift_StreamingFiles_ver_cur.xml']
        if os.path.exists(PROXYPASS_FILE) and self.path.startswith('/gameassets/') and not path_end in exceptions:
            # PROXYPASS_FILE existence indicates we know what we're doing and
            # we can try to obtain the official map schedule and update files.
            # This can only work if we're running on a different machine than the Zwift client.
            sent = False
            try:
                url = 'http://{}{}'.format(hostname, self.path)
                req_header = self.parse_headers()
                resp = requests.get(url, headers=merge_two_dicts(req_header, set_header()), verify=False)
                sent = True
                self.send_response(resp.status_code)
                self.send_resp_headers(resp)
                self.wfile.write(resp.content)
                return
            finally:
                if not sent:
                    self.send_error(404, 'error trying to proxy')

        SimpleHTTPRequestHandler.do_GET(self)

    def parse_headers(self):
        req_header = {}
        for line in self.headers:
            line_parts = [o.strip() for o in line.split(':', 1)]
            if len(line_parts) == 2:
                req_header[line_parts[0]] = line_parts[1]
        return req_header

    def send_resp_headers(self, resp):
        respheaders = resp.headers
        for key in respheaders:
            if key not in ['Content-Encoding', 'Transfer-Encoding', 'content-encoding', 'transfer-encoding', 'content-length', 'Content-Length']:
                self.send_header(key, respheaders[key])
        self.send_header('Content-Length', len(resp.content))
        self.end_headers()

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

        player_id = hello.player_id
        msg = tcp_node_msgs_pb2.RecurringTCPResponse()
        msg.player_id = player_id
        msg.f3 = 0
        msg.f11 = 1
        payload = msg.SerializeToString()

        last_alive_check = int(zwift_offline.get_utc_time())
        while True:
            #Check every 5 seconds for new updates
            tcpthreadevent.wait(timeout=5)
            try:
                message = udp_node_msgs_pb2.ServerToClient()
                message.f1 = 1
                message.player_id = player_id
                message.world_time = zwift_offline.world_time()

                #PlayerUpdate
                if player_id in player_update_queue and len(player_update_queue[player_id]) > 0 and player_id in online:
                    added_player_updates = list()
                    for player_update_proto in player_update_queue[player_id]:
                        player_update = message.updates.add()
                        player_update.ParseFromString(player_update_proto)

                        #Send if 10 updates has already been added and start a new message
                        if len(message.updates) > 9:
                            message_payload = message.SerializeToString()
                            self.request.sendall(struct.pack('!h', len(message_payload)))
                            self.request.sendall(message_payload)
                            
                            message = udp_node_msgs_pb2.ServerToClient()
                            message.f1 = 1
                            message.player_id = player_id
                            message.world_time = zwift_offline.world_time()

                        added_player_updates.append(player_update_proto)
                    for player_update_proto in added_player_updates:
                        player_update_queue[player_id].remove(player_update_proto)

                t = int(zwift_offline.get_utc_time())

                #Check if any updates are added and should be sent to client, otherwise just keep alive every 25 seconds
                if len(message.updates) > 0:
                    last_alive_check = t
                    message_payload = message.SerializeToString()
                    self.request.sendall(struct.pack('!h', len(message_payload)))
                    self.request.sendall(message_payload)
                elif last_alive_check < t - 25:
                    last_alive_check = t
                    self.request.sendall(struct.pack('!h', len(payload)))
                    self.request.sendall(payload)
            except Exception as e:
                print('Exception TCP: %s' % e)
                break

class GhostsVariables:
    loaded = False
    started = False
    rec = None
    play = None
    last_rec = 0
    last_play = 0
    play_count = 0
    last_rt = 0
    start_road = 0
    start_rt = 0

class PacePartnerVariables:
    route = None
    position = 0

def load_pace_partners():
    folder = '%s/pace_partners' % STORAGE_DIR
    if not os.path.isdir(folder): return
    for (root, dirs, files) in os.walk(folder):
        for pp_id in dirs:
            p_id = int(pp_id)
            route = '%s/%s/route.bin' % (folder, pp_id)
            if os.path.isfile(route):
                with open(route, 'rb') as fd:
                    global_pace_partners[p_id] = PacePartnerVariables()
                    pp = global_pace_partners[p_id]
                    pp.route = udp_node_msgs_pb2.Ghost()
                    pp.route.ParseFromString(fd.read())
                    pp.position = 0

def play_pace_partners():
    while True:
        keys = global_pace_partners.keys()
        for pp_id in keys:
            pp = global_pace_partners[pp_id]
            if pp.position < len(pp.route.states) - 1: pp.position += 1
            else: pp.position = 0
            state = pp.route.states[pp.position]
            state.id = pp_id
            state.watchingRiderId = pp_id
            state.worldTime = zwift_offline.world_time()
        ppthreadevent.wait(timeout=pacer_update_freq)

def get_empty_message(player_id):
    message = udp_node_msgs_pb2.ServerToClient()
    message.f1 = 1
    message.player_id = player_id
    message.seqno = 1
    message.f5 = 1
    message.f11 = 1
    message.msgnum = 1
    return message

class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        socket = self.request[1]
        recv = udp_node_msgs_pb2.ClientToServer()

        try:
            recv.ParseFromString(data[:-4])
        except:
            try:
                recv.ParseFromString(data[3:-4])
            except:
                return

        client_address = self.client_address
        player_id = recv.player_id
        state = recv.state

        nearby_state = state
        if state.watchingRiderId in online.keys():
            nearby_state = online[state.watchingRiderId]
        elif state.watchingRiderId in global_pace_partners.keys():
            pp = global_pace_partners[state.watchingRiderId]
            nearby_state = pp.route.states[pp.position]

        #Add handling of ghosts for player if it's missing
        if not player_id in global_ghosts.keys():
            global_ghosts[player_id] = GhostsVariables()

        ghosts = global_ghosts[player_id]

        #Add pace partner last update for player if it's missing
        if not player_id in last_pp_updates.keys():
            last_pp_updates[player_id] = 0

        last_pp_update = last_pp_updates[player_id]

        if recv.seqno == 1 or ghosts.rec == None:
            ghosts.rec = udp_node_msgs_pb2.Ghost()
            ghosts.play = udp_node_msgs_pb2.Ghosts()
            ghosts.last_rt = 0
            ghosts.play_count = 0
            ghosts.loaded = False
            ghosts.started = False
            ghosts.rec.player_id = player_id
            organize_ghosts(player_id)

        t = int(zwift_offline.get_utc_time())
        ghosts.last_package_time = t

        if player_id in ghosts_enabled and ghosts_enabled[player_id]:
            if not ghosts.loaded and get_course(state):
                ghosts.loaded = True
                load_ghosts(player_id, state, ghosts)
            if state.roadTime and ghosts.last_rt and state.roadTime != ghosts.last_rt:
                if t >= ghosts.last_rec + ghost_update_freq:
                    s = ghosts.rec.states.add()
                    s.CopyFrom(state)
                    ghosts.last_rec = t
                if not ghosts.started and ghosts.play.ghosts and road_id(state) == ghosts.start_road:
                    if is_forward(state):
                        if state.roadTime >= ghosts.start_rt >= ghosts.last_rt:
                            ghosts.started = True
                    else:
                        if state.roadTime <= ghosts.start_rt <= ghosts.last_rt:
                            ghosts.started = True
            ghosts.last_rt = state.roadTime

        keys = online.keys()
        remove_players = list()
        for p_id in keys:
            if zwift_offline.world_time() > online[p_id].worldTime + 10000:
                remove_players.insert(0, p_id)
        for p_id in remove_players:
            online.pop(p_id)
        if state.roadTime:
            online[player_id] = state

        #Remove ghosts entries for inactive players (disconnected?)
        keys = global_ghosts.keys()
        remove_players = list()
        for p_id in keys:
            if global_ghosts[p_id].last_package_time < t - 10:
                remove_players.insert(0, p_id)
        for p_id in remove_players:
            global_ghosts.pop(p_id)

        if ghosts.started and t >= ghosts.last_play + ghost_update_freq:
            message = get_empty_message(player_id)
            active_ghosts = 0
            for g in ghosts.play.ghosts:
                if len(g.states) > ghosts.play_count: active_ghosts += 1
            if active_ghosts:
                message.num_msgs = active_ghosts // 10
                if active_ghosts % 10: message.num_msgs += 1
                ghost_id = 1
                for g in ghosts.play.ghosts:
                    if len(g.states) > ghosts.play_count:
                        if len(message.states) < 10:
                            state = message.states.add()
                            state.CopyFrom(g.states[ghosts.play_count])
                            state.id = player_id + ghost_id * 10000000
                            state.worldTime = zwift_offline.world_time()
                        else:
                            message.world_time = zwift_offline.world_time()
                            socket.sendto(message.SerializeToString(), client_address)
                            message.msgnum += 1
                            del message.states[:]
                            state = message.states.add()
                            state.CopyFrom(g.states[ghosts.play_count])
                            state.id = player_id + ghost_id * 10000000
                            state.worldTime = zwift_offline.world_time()
                    ghost_id += 1
            else: message.num_msgs = 1
            message.world_time = zwift_offline.world_time()
            socket.sendto(message.SerializeToString(), client_address)
            ghosts.play_count += 1
            ghosts.last_play = t
        message = get_empty_message(player_id)
        nearby = list()
        for p_id in online.keys():
            player = online[p_id]
            if player.id != player_id:
                #Check if players are close in world
                if zwift_offline.is_nearby(nearby_state, player):
                    nearby.append(p_id)
        if t >= last_pp_update + pacer_update_freq:
            last_pp_updates[player_id] = t
            for p_id in global_pace_partners.keys():
                pace_partner_variables = global_pace_partners[p_id]
                pace_partner = pace_partner_variables.route.states[pace_partner_variables.position]
                #Check if pacepartner is close to player in world
                if zwift_offline.is_nearby(nearby_state, pace_partner):
                    nearby.append(p_id)
        players = len(nearby)
        message.num_msgs = players // 10
        if players % 10: message.num_msgs += 1
        for p_id in nearby:
            player = None
            if p_id in online.keys():
                player = online[p_id]
            elif p_id in global_pace_partners.keys():
                pace_partner_variables = global_pace_partners[p_id]
                player = pace_partner_variables.route.states[pace_partner_variables.position]
            if player != None:
                if len(message.states) < 10:
                    state = message.states.add()
                    state.CopyFrom(player)
                else:
                    message.world_time = zwift_offline.world_time()
                    socket.sendto(message.SerializeToString(), client_address)
                    message.msgnum += 1
                    del message.states[:]
                    state = message.states.add()
                    state.CopyFrom(player)
        message.world_time = zwift_offline.world_time()
        socket.sendto(message.SerializeToString(), client_address)
  
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

load_pace_partners()
ppthreadevent = threading.Event()
pp = threading.Thread(target=play_pace_partners)
pp.start()

zwift_offline.run_standalone(online, global_pace_partners, ghosts_enabled, save_ghost, player_update_queue)
