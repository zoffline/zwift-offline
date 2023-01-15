#!/usr/bin/env python

import os
import signal
import struct
import sys
import threading
import time
import csv
import math
import random
import itertools
import socketserver
from http.server import SimpleHTTPRequestHandler
from http.cookies import SimpleCookie
from collections import deque
from datetime import datetime, timedelta
from shutil import copyfile
from Crypto.Cipher import AES

import zwift_offline as zo
import udp_node_msgs_pb2
import tcp_node_msgs_pb2
import profile_pb2

if getattr(sys, 'frozen', False):
    # If we're running as a pyinstaller bundle
    SCRIPT_DIR = sys._MEIPASS
    EXE_DIR = os.path.dirname(sys.executable)
    STORAGE_DIR = "%s/storage" % EXE_DIR
    PACE_PARTNERS_DIR = '%s/pace_partners' % EXE_DIR
    START_LINES_FILE = '%s/start_lines.csv' % STORAGE_DIR
    if not os.path.isfile(START_LINES_FILE):
        copyfile('%s/start_lines.csv' % SCRIPT_DIR, START_LINES_FILE)
else:
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
    STORAGE_DIR = "%s/storage" % SCRIPT_DIR
    PACE_PARTNERS_DIR = '%s/pace_partners' % SCRIPT_DIR
    START_LINES_FILE = '%s/start_lines.csv' % SCRIPT_DIR

CDN_DIR = "%s/cdn" % SCRIPT_DIR

PROXYPASS_FILE = "%s/cdn-proxy.txt" % STORAGE_DIR
SERVER_IP_FILE = "%s/server-ip.txt" % STORAGE_DIR
FAKE_DNS_FILE = "%s/fake-dns.txt" % STORAGE_DIR
DISCORD_CONFIG_FILE = "%s/discord.cfg" % STORAGE_DIR
if os.path.isfile(DISCORD_CONFIG_FILE):
    from discord_bot import DiscordThread
    discord = DiscordThread(DISCORD_CONFIG_FILE)
else:
    class DummyDiscord():
        def send_message(self, msg, sender_id=None):
            pass
        def change_presence(self, n):
            pass
    discord = DummyDiscord()

MAP_OVERRIDE = deque(maxlen=16)

ghost_update_freq = 3
pacer_update_freq = 1
last_pp_updates = {}
last_bot_updates = {}
global_ghosts = {}
ghosts_enabled = {}
online = {}
player_update_queue = {}
global_pace_partners = {}
global_bots = {}
global_news = {} #player id to dictionary of peer_player_id->worldTime
global_relay = {}
global_clients = {}
start_time = time.time()

def sigint_handler(num, frame):
    httpd.shutdown()
    httpd.server_close()
    tcpserver.shutdown()
    tcpserver.server_close()
    udpserver.shutdown()
    udpserver.server_close()
    os._exit(0)

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
        if path_end == 'map_override':
            cookies_string = self.headers.get('Cookie')
            cookies = SimpleCookie()
            cookies.load(cookies_string)
            # We have no identifying information when Zwift makes MapSchedule request except for the client's IP.
            MAP_OVERRIDE.append((self.client_address[0], cookies['selected_map'].value))
            self.send_response(302)
            self.send_header('Cookie', cookies_string)
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
                    start = datetime.today() - timedelta(days=1)
                    output = '<MapSchedule><appointments><appointment map="%s" start="%s"/></appointments><VERSION>1</VERSION></MapSchedule>' % (override[1], start.strftime("%Y-%m-%dT00:01-04"))
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
            import requests
            try:
                url = 'http://{}{}'.format(hostname, self.path)
                req_header = self.parse_headers()
                resp = requests.get(url, headers=merge_two_dicts(req_header, set_header()), verify=False)
            except Exception as exc:
                print('Error trying to proxy: %s' % repr(exc))
                self.send_error(404, 'error trying to proxy')
                return
            self.send_response(resp.status_code)
            self.send_resp_headers(resp)
            self.wfile.write(resp.content)
            return

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

class DeviceType:
    Relay = 1
    Zc = 2

class ChannelType:
    UdpClient = 1
    UdpServer = 2
    TcpClient = 3
    TcpServer = 4

class Packet:
    flags = None
    ri = None
    ci = None
    sn = None
    payload = None

class InitializationVector:
    def __init__(self, dt = 0, ct = 0, ci = 0, sn = 0):
        self._dt = struct.pack('!h', dt)
        self._ct = struct.pack('!h', ct)
        self._ci = struct.pack('!h', ci)
        self._sn = struct.pack('!i', sn)
    @property
    def dt(self):
        return self._dt
    @dt.setter
    def dt(self, v):
        self._dt = struct.pack('!h', v)
    @property
    def ct(self):
        return self._ct
    @ct.setter
    def ct(self, v):
        self._ct = struct.pack('!h', v)
    @property
    def ci(self):
        return self._ci
    @ci.setter
    def ci(self, v):
        self._ci = struct.pack('!h', v)
    @property
    def sn(self):
        return self._sn
    @sn.setter
    def sn(self, v):
        self._sn = struct.pack('!i', v)
    @property
    def data(self):
        return bytearray(2) + self._dt + self._ct + self._ci + self._sn

def decode_packet(data, key, iv):
    p = Packet()
    s = 1
    p.flags = data[0]
    if p.flags & 4:
        p.ri = int.from_bytes(data[s:s+4], "big")
        s += 4
    if p.flags & 2:
        p.ci = int.from_bytes(data[s:s+2], "big")
        iv.ci = p.ci
        s += 2
    if p.flags & 1:
        p.sn = int.from_bytes(data[s:s+4], "big")
        iv.sn = p.sn
        s += 4
    aesgcm = AES.new(key, AES.MODE_GCM, iv.data)
    p.payload = aesgcm.decrypt(data[s:])
    return p

def encode_packet(payload, key, iv, ri, ci, sn):
    flags = 0
    header = b''
    if ri is not None:
        flags = flags | 4
        header += struct.pack('!i', ri)
    if ci is not None:
        flags = flags | 2
        header += struct.pack('!h', ci)
    if sn is not None:
        flags = flags | 1
        header += struct.pack('!i', sn)
    aesgcm = AES.new(key, AES.MODE_GCM, iv.data)
    header = struct.pack('b', flags) + header
    aesgcm.update(header)
    ep, tag = aesgcm.encrypt_and_digest(payload)
    return header + ep + tag[:4]

class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.data = self.request.recv(1024)
        ip = self.client_address[0] + str(self.client_address[1])
        if not ip in global_clients.keys():
            relay_id = int.from_bytes(self.data[3:7], "big")
            ENCRYPTION_KEY_FILE = "%s/%s/encryption_key.bin" % (STORAGE_DIR, relay_id)
            if relay_id in global_relay.keys():
                with open(ENCRYPTION_KEY_FILE, 'wb') as f:
                    f.write(global_relay[relay_id].key)
            elif os.path.isfile(ENCRYPTION_KEY_FILE):
                with open(ENCRYPTION_KEY_FILE, 'rb') as f:
                    global_relay[relay_id] = zo.Relay(f.read())
            else:
                print('No encryption key for relay ID %s' % relay_id)
                return
            global_clients[ip] = global_relay[relay_id]
        if int.from_bytes(self.data[0:2], "big") != len(self.data) - 2:
            print("Wrong packet size")
            return
        relay = global_clients[ip]
        iv = InitializationVector(DeviceType.Relay, ChannelType.TcpClient, relay.tcp_ci, 0)
        p = decode_packet(self.data[2:], relay.key, iv)
        if p.ci is not None:
            relay.tcp_ci = p.ci
            relay.tcp_r_sn = 1
            relay.tcp_t_sn = 0
            iv.ci = p.ci
        if len(p.payload) > 1 and p.payload[1] != 0:
            print("TCPHandler hello(0) expected, got %s" % p.payload[1])
            return
        hello = udp_node_msgs_pb2.ClientToServer()
        try:
            hello.ParseFromString(p.payload[2:-8]) #2 bytes: payload length, 1 byte: =0x1 (TcpClient::sendClientToServer) 1 byte: type; payload; 4 bytes: hash
            #type: TcpClient::sayHello(=0x0), TcpClient::sendSubscribeToSegment(=0x1), TcpClient::processSegmentUnsubscription(=0x1)
        except Exception as exc:
            print('TCPHandler ParseFromString exception: %s' % repr(exc))
            return
        # send packet containing UDP server (127.0.0.1)
        msg = udp_node_msgs_pb2.ServerToClient()
        msg.player_id = hello.player_id
        msg.world_time = 0
        if self.request.getpeername()[0] == '127.0.0.1':  # to avoid needing hairpinning
            udp_node_ip = "127.0.0.1"
        elif os.path.exists(SERVER_IP_FILE):
            with open(SERVER_IP_FILE, 'r') as f:
                udp_node_ip = f.read().rstrip('\r\n')
        else:
            udp_node_ip = "127.0.0.1"
        details1 = msg.udp_config.relay_addresses.add()
        details1.lb_realm = udp_node_msgs_pb2.ZofflineConstants.RealmID
        details1.lb_course = 6 # watopia crowd
        details1.ip = udp_node_ip
        details1.port = 3022
        details2 = msg.udp_config.relay_addresses.add()
        details2.lb_realm = 0 #generic load balancing realm
        details2.lb_course = 0 #generic load balancing course
        details2.ip = udp_node_ip
        details2.port = 3022
        msg.udp_config.uc_f2 = 10
        msg.udp_config.uc_f3 = 30
        msg.udp_config.uc_f4 = 3
        wdetails1 = msg.udp_config_vod_1.relay_addresses_vod.add()
        wdetails1.lb_realm = udp_node_msgs_pb2.ZofflineConstants.RealmID
        wdetails1.lb_course = 6 # watopia crowd
        wdetails1.relay_addresses.append(details1)
        wdetails2 = msg.udp_config_vod_1.relay_addresses_vod.add()
        wdetails2.lb_realm = 0  #generic load balancing realm
        wdetails2.lb_course = 0 #generic load balancing course
        wdetails2.relay_addresses.append(details2)
        msg.udp_config_vod_1.port = 3022
        payload = msg.SerializeToString()
        iv.ct = ChannelType.TcpServer
        r = encode_packet(payload, relay.key, iv, None, None, None)
        relay.tcp_t_sn += 1
        self.request.sendall(struct.pack('!h', len(r)) + r)

        player_id = hello.player_id
        self.request.settimeout(1) #make recv non-blocking
        while True:
            self.data = b''
            try:
                self.data = self.request.recv(1024)
                i = 0
                while i < len(self.data):
                    size = int.from_bytes(self.data[i:i+2], "big")
                    packet = self.data[i:i+size+2]
                    iv.ct = ChannelType.TcpClient
                    iv.sn = relay.tcp_r_sn
                    p = decode_packet(packet[2:], relay.key, iv)
                    relay.tcp_r_sn += 1
                    if len(p.payload) > 1 and p.payload[1] == 1:
                        subscr = udp_node_msgs_pb2.ClientToServer()
                        try:
                            subscr.ParseFromString(p.payload[2:-8])
                        except Exception as exc:
                            print('TCPHandler ParseFromString exception: %s' % repr(exc))
                        if subscr.subsSegments:
                            msg1 = udp_node_msgs_pb2.ServerToClient()
                            msg1.server_realm = udp_node_msgs_pb2.ZofflineConstants.RealmID
                            msg1.player_id = subscr.player_id
                            msg1.world_time = zo.world_time()
                            msg1.ackSubsSegm.extend(subscr.subsSegments)
                            payload1 = msg1.SerializeToString()
                            iv.ct = ChannelType.TcpServer
                            iv.sn = relay.tcp_t_sn
                            r = encode_packet(payload1, relay.key, iv, None, None, None)
                            relay.tcp_t_sn += 1
                            self.request.sendall(struct.pack('!h', len(r)) + r)
                    i += size + 2
            except:
                pass #timeout is ok here

            try:
                #if ZC need to be registered
                if player_id in zo.zc_connect_queue:
                    zc_params = udp_node_msgs_pb2.ServerToClient()
                    zc_params.player_id = player_id
                    zc_params.world_time = 0
                    zc_params.zc_local_ip = zo.zc_connect_queue[player_id][0]
                    zc_params.zc_local_port = zo.zc_connect_queue[player_id][1] #simple:21587, secure:21588
                    if zo.zc_connect_queue[player_id][2] != "None":
                        zc_params.zc_key = zo.zc_connect_queue[player_id][2]
                    zc_params.zc_protocol = udp_node_msgs_pb2.IPProtocol.TCP #=2
                    zc_params_payload = zc_params.SerializeToString()
                    iv.ct = ChannelType.TcpServer
                    iv.sn = relay.tcp_t_sn
                    r = encode_packet(zc_params_payload, relay.key, iv, None, None, None)
                    relay.tcp_t_sn += 1
                    self.request.sendall(struct.pack('!h', len(r)) + r)
                    zo.zc_connect_queue.pop(player_id)

                message = udp_node_msgs_pb2.ServerToClient()
                message.server_realm = udp_node_msgs_pb2.ZofflineConstants.RealmID
                message.player_id = player_id
                message.world_time = zo.world_time()

                #PlayerUpdate
                if player_id in player_update_queue and len(player_update_queue[player_id]) > 0:
                    added_player_updates = list()
                    for player_update_proto in player_update_queue[player_id]:
                        player_update = message.updates.add()
                        player_update.ParseFromString(player_update_proto)

                        #Send if 10 updates has already been added and start a new message
                        if len(message.updates) > 9:
                            message_payload = message.SerializeToString()
                            iv.ct = ChannelType.TcpServer
                            iv.sn = relay.tcp_t_sn
                            r = encode_packet(message_payload, relay.key, iv, None, None, None)
                            relay.tcp_t_sn += 1
                            self.request.sendall(struct.pack('!h', len(r)) + r)

                            message = udp_node_msgs_pb2.ServerToClient()
                            message.server_realm = udp_node_msgs_pb2.ZofflineConstants.RealmID
                            message.player_id = player_id
                            message.world_time = zo.world_time()

                        added_player_updates.append(player_update_proto)
                    for player_update_proto in added_player_updates:
                        player_update_queue[player_id].remove(player_update_proto)

                #Check if any updates are added and should be sent to client, otherwise just keep alive
                if len(message.updates) > 0:
                    message_payload = message.SerializeToString()
                    iv.ct = ChannelType.TcpServer
                    iv.sn = relay.tcp_t_sn
                    r = encode_packet(message_payload, relay.key, iv, None, None, None)
                    relay.tcp_t_sn += 1
                    self.request.sendall(struct.pack('!h', len(r)) + r)
                else:
                    iv.ct = ChannelType.TcpServer
                    iv.sn = relay.tcp_t_sn
                    r = encode_packet(payload, relay.key, iv, None, None, None)
                    relay.tcp_t_sn += 1
                    self.request.sendall(struct.pack('!h', len(r)) + r)
            except Exception as exc:
                print('TCPHandler loop exception: %s' % repr(exc))
                break

class GhostsVariables:
    loaded = False
    started = False
    rec = None
    play = []
    last_rec = 0
    last_play = 0
    last_rt = 0
    start_road = 0
    start_rt = 0

def boolean(s):
    if s.lower() in ['true', 'yes', '1']: return True
    if s.lower() in ['false', 'no', '0']: return False
    return None

def save_ghost(name, player_id):
    if not player_id in global_ghosts.keys(): return
    ghosts = global_ghosts[player_id]
    if len(ghosts.rec.states) > 0:
        folder = '%s/%s/ghosts/%s/%s' % (STORAGE_DIR, player_id, zo.get_course(ghosts.rec.states[0]), zo.road_id(ghosts.rec.states[0]))
        if not zo.is_forward(ghosts.rec.states[0]): folder += '/reverse'
        try:
            if not os.path.isdir(folder):
                os.makedirs(folder)
        except Exception as exc:
            print('save_ghost: %s' % repr(exc))
            return
        ghosts.rec.player_id = player_id
        f = '%s/%s-%s.bin' % (folder, datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S"), name)
        with open(f, 'wb') as fd:
            fd.write(ghosts.rec.SerializeToString())

def load_ghosts(player_id, state, ghosts):
    folder = '%s/%s/ghosts/%s/%s' % (STORAGE_DIR, player_id, zo.get_course(state), zo.road_id(state))
    if not zo.is_forward(state): folder += '/reverse'
    if not os.path.isdir(folder): return
    s = list()
    for f in os.listdir(folder):
        if f.endswith('.bin'):
            with open(os.path.join(folder, f), 'rb') as fd:
                g = udp_node_msgs_pb2.Ghost()
                g.ParseFromString(fd.read())
                g.position = 0
                ghosts.play.append(g)
                s.append(g.states[0].roadTime)
    ghosts.start_road = zo.road_id(state)
    ghosts.start_rt = 0
    if os.path.isfile(START_LINES_FILE):
        with open(START_LINES_FILE, 'r') as fd:
            sl = [tuple(line) for line in csv.reader(fd)]
            rt = [t for t in sl if t[0] == str(zo.get_course(state)) and t[1] == str(zo.road_id(state)) and (boolean(t[2]) == zo.is_forward(state) or not t[2])]
            if rt:
                ghosts.start_road = int(rt[0][3])
                ghosts.start_rt = int(rt[0][4])
    if not ghosts.start_rt:
        s.append(state.roadTime)
        if zo.is_forward(state): ghosts.start_rt = max(s)
        else: ghosts.start_rt = min(s)
    for g in ghosts.play:
        try:
            while zo.road_id(g.states[g.position]) != ghosts.start_road:
                g.position += 1
            if zo.is_forward(g.states[g.position]):
                while g.states[g.position].roadTime < ghosts.start_rt or abs(g.states[g.position].roadTime - ghosts.start_rt) > 500000:
                    g.position += 1
            else:
                while g.states[g.position].roadTime > ghosts.start_rt or abs(g.states[g.position].roadTime - ghosts.start_rt) > 500000:
                    g.position += 1
        except IndexError:
            pass

def regroup_ghosts(player_id):
    p = online[player_id]
    ghosts = global_ghosts[player_id]
    for g in ghosts.play:
        states = []
        for s in g.states:
            if zo.road_id(s) == zo.road_id(p) and zo.is_forward(s) == zo.is_forward(p):
                states.append((s.roadTime, s.distance))
        if states:
            c = min(states, key=lambda x: sum(abs(r - d) for r, d in zip((p.roadTime, p.distance), x)))
            g.position = 0
            while g.states[g.position].roadTime != c[0] or g.states[g.position].distance != c[1]:
                g.position += 1
            g.position += 1
    if not ghosts.started and ghosts.play:
        ghosts.started = True

class PacePartnerVariables:
    profile = None
    route = None
    position = 0

def load_pace_partners():
    for (root, dirs, files) in os.walk(PACE_PARTNERS_DIR):
        for d in dirs:
            profile = os.path.join(PACE_PARTNERS_DIR, d, 'profile.bin')
            route = os.path.join(PACE_PARTNERS_DIR, d, 'route.bin')
            if os.path.isfile(profile) and os.path.isfile(route):
                with open(profile, 'rb') as fd:
                    p = profile_pb2.PlayerProfile()
                    p.ParseFromString(fd.read())
                    global_pace_partners[p.id] = PacePartnerVariables()
                    pp = global_pace_partners[p.id]
                    pp.profile = p
                with open(route, 'rb') as fd:
                    pp.route = udp_node_msgs_pb2.Ghost()
                    pp.route.ParseFromString(fd.read())
                    pp.position = 0

def play_pace_partners():
    while True:
        for pp_id in global_pace_partners.keys():
            pp = global_pace_partners[pp_id]
            if pp.position < len(pp.route.states) - 1: pp.position += 1
            else: pp.position = 0
            state = pp.route.states[pp.position]
            state.id = pp_id
            state.watchingRiderId = pp_id
            state.worldTime = zo.world_time()
        ppthreadevent.wait(timeout=pacer_update_freq)

def load_bots():
    i = 1
    for name in os.listdir(STORAGE_DIR):
        path = '%s/%s/ghosts' % (STORAGE_DIR, name)
        if os.path.isdir(path):
            for (root, dirs, files) in os.walk(path):
                for f in files:
                    if f.endswith('.bin'):
                        p = profile_pb2.PlayerProfile()
                        p.CopyFrom(zo.random_profile(p))
                        p.id = i + 1000000
                        global_bots[p.id] = PacePartnerVariables()
                        bot = global_bots[p.id]
                        bot.route = udp_node_msgs_pb2.Ghost()
                        with open(os.path.join(root, f), 'rb') as fd:
                            bot.route.ParseFromString(fd.read())
                        bot.position = random.randrange(len(bot.route.states))
                        p.first_name = ''
                        p.last_name = zo.time_since(bot.route.states[0]) + ' [bot]'
                        p.is_male = bool(random.getrandbits(1))
                        p.country_code = 0
                        bot.profile = p
                        i += 1

def play_bots():
    while True:
        if zo.reload_pacer_bots:
            zo.reload_pacer_bots = False
            global_bots.clear()
            load_bots()
        for bot_id in global_bots.keys():
            bot = global_bots[bot_id]
            if bot.position < len(bot.route.states) - 1: bot.position += 1
            else: bot.position = 0
            state = bot.route.states[bot.position]
            state.id = bot_id
            state.watchingRiderId = bot_id
            state.worldTime = zo.world_time()
        botthreadevent.wait(timeout=ghost_update_freq)

def remove_inactive():
    while True:
        for p_id in list(online.keys()):
            if zo.world_time() > online[p_id].worldTime + 10000:
                zo.logout_player(p_id)
        rithreadevent.wait(timeout=1)

def get_empty_message(player_id):
    message = udp_node_msgs_pb2.ServerToClient()
    message.server_realm = udp_node_msgs_pb2.ZofflineConstants.RealmID
    message.player_id = player_id
    message.seqno = 1
    message.stc_f5 = 1
    message.stc_f11 = 1
    message.msgnum = 1
    return message

def is_state_new_for(peer_player_state, player_id):
    if not player_id in global_news.keys():
        global_news[player_id] = {}
    for_news = global_news[player_id]
    if peer_player_state.id in for_news.keys():
        if for_news[peer_player_state.id] == peer_player_state.worldTime:
            return False #already sent
    for_news[peer_player_state.id] = peer_player_state.worldTime
    return True

def nearby_distance(s1, s2):
    if s1 is None or s2 is None:
        return False, None
    if zo.get_course(s1) == zo.get_course(s2):
        dist = math.sqrt((s2.x - s1.x)**2 + (s2.z - s1.z)**2 + (s2.y_altitude - s1.y_altitude)**2)
        if dist <= 100000 or zo.road_id(s1) == zo.road_id(s2):
            return True, dist
    return False, None

class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        socket = self.request[1]
        ip = self.client_address[0] + str(self.client_address[1])
        if not ip in global_clients.keys():
            relay_id = int.from_bytes(data[1:5], "big")
            if relay_id in global_relay.keys():
                global_clients[ip] = global_relay[relay_id]
            else:
                return
        relay = global_clients[ip]
        iv = InitializationVector(DeviceType.Relay, ChannelType.UdpClient, relay.udp_ci, relay.udp_r_sn)
        p = decode_packet(data, relay.key, iv)
        relay.udp_r_sn += 1
        if p.ci is not None:
            relay.udp_ci = p.ci
            relay.udp_t_sn = 0
            iv.ci = p.ci
        if p.sn is not None:
            relay.udp_r_sn = p.sn

        recv = udp_node_msgs_pb2.ClientToServer()

        try:
            recv.ParseFromString(p.payload[:-8])
        except:
            try:
                #If no sensors connected, first byte must be skipped
                recv.ParseFromString(p.payload[1:-8])
            except Exception as exc:
                print('UDPHandler ParseFromString exception: %s' % repr(exc))
                return

        client_address = self.client_address
        player_id = recv.player_id
        state = recv.state

        #Add last updates for player if missing
        if not player_id in last_pp_updates.keys():
            last_pp_updates[player_id] = 0
        if not player_id in last_bot_updates.keys():
            last_bot_updates[player_id] = 0

        t = int(zo.get_utc_time())

        #Update player online state
        if state.roadTime:
            if player_id in online.keys():
                if online[player_id].worldTime > state.worldTime:
                    return #udp is unordered -> drop old state
            elif time.time() > start_time + 10:
                discord.change_presence(len(online) + 1)
            online[player_id] = state

        #Add handling of ghosts for player if it's missing
        if not player_id in global_ghosts.keys():
            global_ghosts[player_id] = GhostsVariables()
            global_ghosts[player_id].rec = udp_node_msgs_pb2.Ghost()

        ghosts = global_ghosts[player_id]

        if player_id in ghosts_enabled and ghosts_enabled[player_id]:
            #Load ghosts for current course
            if not ghosts.loaded and zo.get_course(state):
                ghosts.loaded = True
                load_ghosts(player_id, state, ghosts)
            #Save player state as ghost if moving
            if state.roadTime and ghosts.last_rt and state.roadTime != ghosts.last_rt:
                if t >= ghosts.last_rec + ghost_update_freq:
                    ghosts.rec.states.append(state)
                    ghosts.last_rec = t
                #Start loaded ghosts
                if not ghosts.started and ghosts.play and zo.road_id(state) == ghosts.start_road:
                    if zo.is_forward(state):
                        if state.roadTime > ghosts.start_rt and abs(state.roadTime - ghosts.start_rt) < 500000:
                            ghosts.started = True
                    else:
                        if state.roadTime < ghosts.start_rt and abs(state.roadTime - ghosts.start_rt) < 500000:
                            ghosts.started = True
            #Uncomment to print player state when stopped (to find new start lines)
            #else: print('course', zo.get_course(state), 'road', zo.road_id(state), 'isForward', zo.is_forward(state), 'roadTime', state.roadTime)
            ghosts.last_rt = state.roadTime

        #Set state of player being watched
        watching_state = None
        if state.watchingRiderId == player_id:
            watching_state = state
        elif state.watchingRiderId in online.keys():
            watching_state = online[state.watchingRiderId]
        elif state.watchingRiderId in global_pace_partners.keys():
            pp = global_pace_partners[state.watchingRiderId]
            watching_state = pp.route.states[pp.position]
        elif state.watchingRiderId in global_bots.keys():
            bot = global_bots[state.watchingRiderId]
            watching_state = bot.route.states[bot.position]
        elif state.watchingRiderId > 10000000:
            ghost = ghosts.play[math.floor(state.watchingRiderId / 10000000) - 1]
            if len(ghost.states) > ghost.position:
                watching_state = ghost.states[ghost.position]

        #Check if online players, pace partners, bots and ghosts are nearby
        nearby = {}
        for p_id in online.keys():
            player = online[p_id]
            if player.id != player_id:
                is_nearby, distance = nearby_distance(watching_state, player)
                if is_nearby and is_state_new_for(player, player_id):
                    nearby[p_id] = distance
        if t >= last_pp_updates[player_id] + pacer_update_freq:
            last_pp_updates[player_id] = t
            for p_id in global_pace_partners.keys():
                pace_partner_variables = global_pace_partners[p_id]
                pace_partner = pace_partner_variables.route.states[pace_partner_variables.position]
                is_nearby, distance = nearby_distance(watching_state, pace_partner)
                if is_nearby:
                    nearby[p_id] = distance
        if t >= last_bot_updates[player_id] + ghost_update_freq:
            last_bot_updates[player_id] = t
            for p_id in global_bots.keys():
                bot_variables = global_bots[p_id]
                bot = bot_variables.route.states[bot_variables.position]
                is_nearby, distance = nearby_distance(watching_state, bot)
                if is_nearby:
                    nearby[p_id] = distance
        elif ghosts.started and t >= ghosts.last_play + ghost_update_freq:
            ghosts.last_play = t
            ghost_id = 1
            for g in ghosts.play:
                if len(g.states) > g.position:
                    is_nearby, distance = nearby_distance(watching_state, g.states[g.position])
                    if is_nearby:
                        nearby[player_id + ghost_id * 10000000] = distance
                    g.position += 1
                ghost_id += 1

        #Send nearby riders states or empty message
        message = get_empty_message(player_id)
        if nearby:
            if len(nearby) > 100:
                nearby = dict(sorted(nearby.items(), key=lambda item: item[1]))
                nearby = dict(itertools.islice(nearby.items(), 100))
            message.num_msgs = math.ceil(len(nearby) / 10)
            for p_id in nearby:
                player = None
                if p_id in online.keys():
                    player = online[p_id]
                elif p_id in global_pace_partners.keys():
                    pace_partner_variables = global_pace_partners[p_id]
                    player = pace_partner_variables.route.states[pace_partner_variables.position]
                elif p_id in global_bots.keys():
                    bot_variables = global_bots[p_id]
                    player = bot_variables.route.states[bot_variables.position]
                elif p_id > 10000000:
                    player = udp_node_msgs_pb2.PlayerState()
                    ghost = ghosts.play[math.floor(p_id / 10000000) - 1]
                    player.CopyFrom(ghost.states[ghost.position - 1])
                    player.id = p_id
                    player.worldTime = zo.world_time()
                if player != None:
                    if len(message.states) > 9:
                        message.world_time = zo.world_time()
                        message.cts_latency = message.world_time - recv.world_time
                        iv.ct = ChannelType.UdpServer
                        iv.sn = relay.udp_t_sn
                        r = encode_packet(message.SerializeToString(), relay.key, iv, None, None, relay.udp_t_sn)
                        relay.udp_t_sn += 1
                        socket.sendto(r, client_address)
                        message.msgnum += 1
                        del message.states[:]
                    message.states.append(player)
        else:
            message.num_msgs = 1
        message.world_time = zo.world_time()
        message.cts_latency = message.world_time - recv.world_time
        iv.ct = ChannelType.UdpServer
        iv.sn = relay.udp_t_sn
        r = encode_packet(message.SerializeToString(), relay.key, iv, None, None, relay.udp_t_sn)
        relay.udp_t_sn += 1
        socket.sendto(r, client_address)

if os.path.isdir(PACE_PARTNERS_DIR):
    load_pace_partners()
    ppthreadevent = threading.Event()
    pp = threading.Thread(target=play_pace_partners)
    pp.start()

if os.path.isfile('%s/enable_bots.txt' % STORAGE_DIR):
    load_bots()
    botthreadevent = threading.Event()
    bot = threading.Thread(target=play_bots)
    bot.start()

socketserver.ThreadingTCPServer.allow_reuse_address = True
httpd = socketserver.ThreadingTCPServer(('', 80), CDNHandler)
zoffline_thread = threading.Thread(target=httpd.serve_forever)
zoffline_thread.daemon = True
zoffline_thread.start()

tcpserver = socketserver.ThreadingTCPServer(('', 3025), TCPHandler)
tcpserver_thread = threading.Thread(target=tcpserver.serve_forever)
tcpserver_thread.daemon = True
tcpserver_thread.start()

socketserver.ThreadingUDPServer.allow_reuse_address = True
udpserver = socketserver.ThreadingUDPServer(('', 3024), UDPHandler)
udpserver_thread = threading.Thread(target=udpserver.serve_forever)
udpserver_thread.daemon = True
udpserver_thread.start()

rithreadevent = threading.Event()
ri = threading.Thread(target=remove_inactive)
ri.start()

if os.path.exists(FAKE_DNS_FILE) and os.path.exists(SERVER_IP_FILE):
    from fake_dns import fake_dns
    with open(SERVER_IP_FILE, 'r') as f:
        server_ip = f.read().rstrip('\r\n')
        dns = threading.Thread(target=fake_dns, args=(server_ip,))
        dns.start()

zo.run_standalone(online, global_relay, global_pace_partners, global_bots, global_ghosts, ghosts_enabled, save_ghost, regroup_ghosts, player_update_queue, discord)
