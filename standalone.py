#!/usr/bin/env python

import os
import signal
import struct
import sys
import threading
import time
import json
import math
import random
import itertools
import socketserver
from urllib3 import PoolManager
from http.server import SimpleHTTPRequestHandler
from datetime import datetime, timedelta
from Crypto.Cipher import AES

import zwift_offline as zo
import udp_node_msgs_pb2
import tcp_node_msgs_pb2
import profile_pb2

if getattr(sys, 'frozen', False):
    # If we're running as a pyinstaller bundle
    SCRIPT_DIR = sys._MEIPASS
    STORAGE_DIR = "%s/storage" % os.path.dirname(sys.executable)
    PACE_PARTNERS_DIR = '%s/pace_partners' % os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
    STORAGE_DIR = "%s/storage" % SCRIPT_DIR
    PACE_PARTNERS_DIR = '%s/pace_partners' % SCRIPT_DIR

CDN_DIR = "%s/cdn" % SCRIPT_DIR
CDN_PROXY = os.path.isfile('%s/cdn-proxy.txt' % STORAGE_DIR)
if not CDN_PROXY and not os.path.isfile('%s/disable_proxy.txt' % STORAGE_DIR):
    # If CDN proxy is disabled, try to resolve zwift.com using Google public DNS
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = ['8.8.8.8', '8.8.4.4']
        resolver.cache = dns.resolver.Cache()
        resolver.resolve('zwift.com')
        # If succeeded, patch create_connection to use resolver
        from urllib3.util import connection
        orig_create_connection = connection.create_connection
        def patched_create_connection(address, *args, **kwargs):
            host, port = address
            answer = resolver.cache.data.get((host, 1, 1))
            if not answer:
                try:
                    answer = resolver.resolve(host)
                    resolver.cache.put((host, 1, 1), answer)
                except Exception as exc:
                    print('dns.resolver: %s' % repr(exc))
            if answer:
                address = (answer[0].to_text(), port)
            return orig_create_connection(address, *args, **kwargs)
        connection.create_connection = patched_create_connection
        CDN_PROXY = True
    except:
        pass

FAKE_DNS_FILE = "%s/fake-dns.txt" % STORAGE_DIR
ENABLE_BOTS_FILE = "%s/enable_bots.txt" % STORAGE_DIR
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

bot_update_freq = 3
pacer_update_freq = 1
simulated_latency = 300 #makes bots animation smoother than using current time
last_pp_updates = {}
last_bot_updates = {}
last_bookmark_updates = {}
global_ghosts = {}
online = {}
global_pace_partners = {}
global_bots = {}
global_news = {} #player id to dictionary of peer_player_id->worldTime
global_relay = {}
global_clients = {}

def sigint_handler(num, frame):
    httpd.shutdown()
    httpd.server_close()
    tcpserver.shutdown()
    tcpserver.server_close()
    udpserver.shutdown()
    udpserver.server_close()
    os._exit(0)

signal.signal(signal.SIGINT, sigint_handler)

class CDNHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = SimpleHTTPRequestHandler.translate_path(self, path)
        relpath = os.path.relpath(path, os.getcwd())
        fullpath = os.path.join(CDN_DIR, relpath)
        return fullpath

    def do_GET(self):
        # Check if client requested the map be overridden
        if self.path == '/gameassets/MapSchedule_v2.xml' and self.client_address[0] in zo.map_override:
            self.send_response(200)
            self.send_header('Content-type', 'text/xml')
            self.end_headers()
            start = datetime.today() - timedelta(days=1)
            output = '<MapSchedule><appointments><appointment map="%s" start="%s"/></appointments><VERSION>1</VERSION></MapSchedule>' % (zo.map_override[self.client_address[0]], start.strftime("%Y-%m-%dT00:01-04"))
            self.wfile.write(output.encode())
            del zo.map_override[self.client_address[0]]
            return
        if self.path == '/gameassets/PortalRoadSchedule_v1.xml' and self.client_address[0] in zo.climb_override:
            self.send_response(200)
            self.send_header('Content-type', 'text/xml')
            self.end_headers()
            start = datetime.today() - timedelta(days=1)
            output = '<PortalRoads><PortalRoadSchedule><appointments><appointment road="%s" portal="0" start="%s"/></appointments><VERSION>1</VERSION></PortalRoadSchedule></PortalRoads>' % (zo.climb_override[self.client_address[0]], start.strftime("%Y-%m-%dT00:01-04"))
            self.wfile.write(output.encode())
            del zo.climb_override[self.client_address[0]]
            return
        if CDN_PROXY and self.path.startswith('/gameassets/') and not self.path.endswith('_ver_cur.xml') and not ('User-Agent' in self.headers and 'python-urllib3' in self.headers['User-Agent']):
            try:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(PoolManager().request('GET', 'http://cdn.zwift.com%s' % self.path).data)
                return
            except Exception as exc:
                print('Error trying to proxy: %s' % repr(exc))

        SimpleHTTPRequestHandler.do_GET(self)

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
            hello.ParseFromString(p.payload[2:-4]) #2 bytes: payload length, 1 byte: =0x1 (TcpClient::sendClientToServer) 1 byte: type; payload; 4 bytes: hash
            #type: TcpClient::sayHello(=0x0), TcpClient::sendSubscribeToSegment(=0x1), TcpClient::processSegmentUnsubscription(=0x1)
        except Exception as exc:
            print('TCPHandler ParseFromString exception: %s' % repr(exc))
            return
        # send packet containing UDP server (127.0.0.1)
        msg = udp_node_msgs_pb2.ServerToClient()
        msg.player_id = hello.player_id
        msg.world_time = 0
        details1 = msg.udp_config.relay_addresses.add()
        details1.lb_realm = udp_node_msgs_pb2.ZofflineConstants.RealmID
        details1.lb_course = 6 # watopia crowd
        details1.ip = zo.server_ip
        details1.port = 3022
        details2 = msg.udp_config.relay_addresses.add()
        details2.lb_realm = 0 #generic load balancing realm
        details2.lb_course = 0 #generic load balancing course
        details2.ip = zo.server_ip
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
                            subscr.ParseFromString(p.payload[2:-4])
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

                messages = []

                #PlayerUpdate
                if player_id in zo.player_update_queue and len(zo.player_update_queue[player_id]) > 0:
                    message = udp_node_msgs_pb2.ServerToClient()
                    message.server_realm = udp_node_msgs_pb2.ZofflineConstants.RealmID
                    message.player_id = player_id
                    message.world_time = zo.world_time()
                    for player_update_proto in list(zo.player_update_queue[player_id]):
                        if len(message.SerializeToString()) + len(player_update_proto) > 1400:
                            new_msg = udp_node_msgs_pb2.ServerToClient()
                            new_msg.CopyFrom(message)
                            messages.append(new_msg)
                            del message.updates[:]
                        player_update = message.updates.add()
                        player_update.ParseFromString(player_update_proto)
                        zo.player_update_queue[player_id].remove(player_update_proto)
                    messages.append(message)
                else: #keepalive
                    messages.append(msg)

                for message in messages:
                    message_payload = message.SerializeToString()
                    iv.ct = ChannelType.TcpServer
                    iv.sn = relay.tcp_t_sn
                    r = encode_packet(message_payload, relay.key, iv, None, None, None)
                    relay.tcp_t_sn += 1
                    self.request.sendall(struct.pack('!h', len(r)) + r)
            except Exception as exc:
                print('TCPHandler loop exception: %s' % repr(exc))
                break

class BotVariables:
    profile = None
    route = None
    date = 0
    position = 0

class GhostsVariables:
    loaded = False
    started = False
    rec = None
    play = None
    last_rec = 0
    last_play = 0
    last_rt = 0
    start_road = 0
    start_rt = 0

def load_ghosts_folder(folder, ghosts):
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            if f.endswith('.bin'):
                with open(os.path.join(folder, f), 'rb') as fd:
                    g = BotVariables()
                    g.route = udp_node_msgs_pb2.Ghost()
                    g.route.ParseFromString(fd.read())
                    g.date = g.route.states[0].worldTime
                    ghosts.play.append(g)

def load_ghosts(player_id, state, ghosts):
    folder = '%s/%s/ghosts/%s' % (STORAGE_DIR, player_id, zo.get_course(state))
    road_folder = '%s/%s' % (folder, zo.road_id(state))
    if not zo.is_forward(state): road_folder += '/reverse'
    load_ghosts_folder(road_folder, ghosts)
    if state.route:
        load_ghosts_folder('%s/%s' % (folder, state.route), ghosts)
    ghosts.start_road = zo.road_id(state)
    ghosts.start_rt = state.roadTime
    with open('%s/data/start_lines.txt' % SCRIPT_DIR) as fd:
        sl = json.load(fd, object_hook=lambda d: {int(k) if k.lstrip('-').isdigit() else k: v for k, v in d.items()})
        if state.route in sl:
            ghosts.start_road = sl[state.route]['road']
            ghosts.start_rt = sl[state.route]['time']

def regroup_ghosts(player_id):
    p = online[player_id]
    ghosts = global_ghosts[player_id]
    if not ghosts.loaded:
        ghosts.loaded = True
        load_ghosts(player_id, p, ghosts)
    if not ghosts.started and ghosts.play:
        ghosts.started = True
    for g in ghosts.play:
        states = [(s.roadTime, s.distance) for s in g.route.states if zo.road_id(s) == zo.road_id(p) and zo.is_forward(s) == zo.is_forward(p)]
        if states:
            c = min(states, key=lambda x: sum(abs(r - d) for r, d in zip((p.roadTime, p.distance), x)))
            g.position = 0
            while g.route.states[g.position].roadTime != c[0] or g.route.states[g.position].distance != c[1]:
                g.position += 1
            if is_ahead(p, g.route.states[g.position].roadTime):
                g.position += 1
    ghosts.last_play = 0

def load_pace_partners():
    for (root, dirs, files) in os.walk(PACE_PARTNERS_DIR):
        for d in dirs:
            profile = os.path.join(PACE_PARTNERS_DIR, d, 'profile.bin')
            route = os.path.join(PACE_PARTNERS_DIR, d, 'route.bin')
            if os.path.isfile(profile) and os.path.isfile(route):
                with open(profile, 'rb') as fd:
                    p = profile_pb2.PlayerProfile()
                    p.ParseFromString(fd.read())
                    global_pace_partners[p.id] = BotVariables()
                    pp = global_pace_partners[p.id]
                    pp.profile = p
                with open(route, 'rb') as fd:
                    pp.route = udp_node_msgs_pb2.Ghost()
                    pp.route.ParseFromString(fd.read())
                    pp.position = 0

def play_pace_partners():
    while True:
        start = time.perf_counter()
        for pp_id in global_pace_partners.keys():
            pp = global_pace_partners[pp_id]
            if pp.position < len(pp.route.states) - 1: pp.position += 1
            else: pp.position = 0
            pp.route.states[pp.position].id = pp_id
        pause = pacer_update_freq - (time.perf_counter() - start)
        if pause > 0: time.sleep(pause)

def get_names():
    bots_file = '%s/bot.txt' % STORAGE_DIR
    if os.path.isfile(bots_file):
        with open(bots_file) as f:
            return json.load(f)['riders']
    with open('%s/data/names.txt' % SCRIPT_DIR) as f:
        data = json.load(f)
    riders = []
    for _ in range(1000):
        is_male = bool(random.getrandbits(1))
        riders.append({'first_name': random.choice(data['male_first_names']) if is_male else random.choice(data['female_first_names']),
            'last_name': random.choice(data['last_names']), 'is_male': is_male, 'country_code': random.choice(zo.GD['country_codes'])})
    return riders

def load_bots():
    multiplier = 1
    with open(ENABLE_BOTS_FILE) as f:
        try:
            multiplier = min(int(f.readline().rstrip('\r\n')), 100)
        except ValueError:
            pass
    i = 1
    loop_riders = []
    for name in os.listdir(STORAGE_DIR):
        path = '%s/%s/ghosts' % (STORAGE_DIR, name)
        if os.path.isdir(path):
            for (root, dirs, files) in os.walk(path):
                for f in files:
                    if f.endswith('.bin'):
                        positions = []
                        for n in range(0, multiplier):
                            p = profile_pb2.PlayerProfile()
                            p.CopyFrom(zo.random_profile(p))
                            p.id = i + 1000000 + n * 10000
                            global_bots[p.id] = BotVariables()
                            bot = global_bots[p.id]
                            if n == 0:
                                bot.route = udp_node_msgs_pb2.Ghost()
                                with open(os.path.join(root, f), 'rb') as fd:
                                    bot.route.ParseFromString(fd.read())
                            else:
                                bot.route = global_bots[i + 1000000].route
                            if not positions:
                                positions = list(range(len(bot.route.states)))
                                random.shuffle(positions)
                            bot.position = positions.pop()
                            if not loop_riders:
                                loop_riders = get_names()
                                random.shuffle(loop_riders)
                            rider = loop_riders.pop()
                            for item in ['first_name', 'last_name', 'is_male', 'country_code', 'ride_jersey', 'bike_frame', 'bike_frame_colour', 'bike_wheel_front', 'bike_wheel_rear', 'ride_helmet_type', 'glasses_type', 'ride_shoes_type', 'ride_socks_type']:
                                if item in rider:
                                    setattr(p, item, rider[item])
                            p.hair_type = random.choice(zo.GD['hair_types'])
                            p.hair_colour = random.randrange(5)
                            if p.is_male:
                                p.body_type = random.choice(zo.GD['body_types_male'])
                                p.facial_hair_type = random.choice(zo.GD['facial_hair_types'])
                                p.facial_hair_colour = random.randrange(5)
                            else:
                                p.body_type = random.choice(zo.GD['body_types_female'])
                            bot.profile = p
                        i += 1

def play_bots():
    while True:
        start = time.perf_counter()
        if zo.reload_pacer_bots:
            zo.reload_pacer_bots = False
            if os.path.isfile(ENABLE_BOTS_FILE):
                global_bots.clear()
                load_bots()
        for bot_id in global_bots.keys():
            bot = global_bots[bot_id]
            if bot.position < len(bot.route.states) - 1: bot.position += 1
            else: bot.position = 0
            bot.route.states[bot.position].id = bot_id
        pause = bot_update_freq - (time.perf_counter() - start)
        if pause > 0: time.sleep(pause)

def remove_inactive():
    while True:
        for p_id in list(online.keys()):
            if zo.world_time() > online[p_id].worldTime + 10000:
                zo.logout_player(p_id)
        time.sleep(1)

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

def is_ahead(state, roadTime):
    if zo.is_forward(state):
        if state.roadTime > roadTime and abs(state.roadTime - roadTime) < 500000:
            return True
    else:
        if state.roadTime < roadTime and abs(state.roadTime - roadTime) < 500000:
            return True
    return False

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
            recv.ParseFromString(p.payload[1:-4])
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
        if not player_id in last_bookmark_updates.keys():
            last_bookmark_updates[player_id] = 0

        #Add bookmarks for player if missing
        if not player_id in zo.global_bookmarks.keys():
            zo.global_bookmarks[player_id] = {}
        bookmarks = zo.global_bookmarks[player_id]

        #Update player online state
        if state.roadTime:
            if player_id in online.keys():
                if online[player_id].worldTime > state.worldTime:
                    return #udp is unordered -> drop old state
            else:
                discord.change_presence(len(online) + 1)
            online[player_id] = state

        #Add handling of ghosts for player if it's missing
        if not player_id in global_ghosts.keys():
            global_ghosts[player_id] = GhostsVariables()
            global_ghosts[player_id].rec = udp_node_msgs_pb2.Ghost()
            global_ghosts[player_id].play = []
        ghosts = global_ghosts[player_id]

        t = time.monotonic()

        if player_id in zo.ghosts_enabled and zo.ghosts_enabled[player_id]:
            if state.roadTime and ghosts.last_rt and state.roadTime != ghosts.last_rt:
                #Load ghosts when start moving (as of version 1.39 player sometimes enters course 6 road 0 at home screen)
                if not ghosts.loaded:
                    ghosts.loaded = True
                    load_ghosts(player_id, state, ghosts)
                #Save player state as ghost
                if t >= ghosts.last_rec + bot_update_freq:
                    ghosts.rec.states.append(state)
                    ghosts.last_rec = t
                #Start loaded ghosts
                if not ghosts.started and ghosts.play and zo.road_id(state) == ghosts.start_road and is_ahead(state, ghosts.start_rt):
                    regroup_ghosts(player_id)
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
        elif state.watchingRiderId in bookmarks.keys():
            watching_state = bookmarks[state.watchingRiderId].state
        elif state.watchingRiderId > 10000000:
            ghost = ghosts.play[math.floor(state.watchingRiderId / 10000000) - 1]
            if len(ghost.route.states) > ghost.position:
                watching_state = ghost.route.states[ghost.position]

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
                pp = global_pace_partners[p_id]
                is_nearby, distance = nearby_distance(watching_state, pp.route.states[pp.position])
                if is_nearby:
                    nearby[p_id] = distance
        if t >= last_bot_updates[player_id] + bot_update_freq:
            last_bot_updates[player_id] = t
            for p_id in global_bots.keys():
                bot = global_bots[p_id]
                is_nearby, distance = nearby_distance(watching_state, bot.route.states[bot.position])
                if is_nearby:
                    nearby[p_id] = distance
        if t >= last_bookmark_updates[player_id] + 10:
            last_bookmark_updates[player_id] = t
            for p_id in bookmarks.keys():
                is_nearby, distance = nearby_distance(watching_state, bookmarks[p_id].state)
                if is_nearby:
                    nearby[p_id] = distance
        if ghosts.started and t >= ghosts.last_play + bot_update_freq:
            ghosts.last_play = t
            for i, g in enumerate(ghosts.play):
                if len(g.route.states) > g.position:
                    is_nearby, distance = nearby_distance(watching_state, g.route.states[g.position])
                    if is_nearby:
                        nearby[player_id + (i + 1) * 10000000] = distance
                    g.position += 1

        #Send nearby riders states or empty message
        messages = []
        message = udp_node_msgs_pb2.ServerToClient()
        message.server_realm = udp_node_msgs_pb2.ZofflineConstants.RealmID
        message.player_id = player_id
        message.world_time = zo.world_time()
        message.cts_latency = message.world_time - recv.world_time
        if len(nearby) > 100:
            nearby = dict(sorted(nearby.items(), key=lambda item: item[1]))
            nearby = dict(itertools.islice(nearby.items(), 100))
        for p_id in nearby:
            player = None
            if p_id in online.keys():
                player = online[p_id]
            elif p_id in global_pace_partners.keys():
                pp = global_pace_partners[p_id]
                player = pp.route.states[pp.position]
            elif p_id in global_bots.keys():
                bot = global_bots[p_id]
                player = bot.route.states[bot.position]
            elif p_id in bookmarks.keys():
                player = bookmarks[p_id].state
            elif p_id > 10000000:
                ghost = ghosts.play[math.floor(p_id / 10000000) - 1]
                player = ghost.route.states[ghost.position - 1]
                player.id = p_id
            if player != None:
                if not p_id in online.keys():
                    player.worldTime = message.world_time - simulated_latency
                    player.groupId = 0 # fix bots in event only routes
                if len(message.SerializeToString()) + len(player.SerializeToString()) > 1400:
                    new_msg = udp_node_msgs_pb2.ServerToClient()
                    new_msg.CopyFrom(message)
                    messages.append(new_msg)
                    del message.states[:]
                message.states.append(player)
        messages.append(message)
        for i, msg in enumerate(messages):
            msg.num_msgs = len(messages)
            msg.msgnum = i + 1
            iv.ct = ChannelType.UdpServer
            iv.sn = relay.udp_t_sn
            r = encode_packet(msg.SerializeToString(), relay.key, iv, None, None, relay.udp_t_sn)
            relay.udp_t_sn += 1
            socket.sendto(r, client_address)

if os.path.isdir(PACE_PARTNERS_DIR):
    load_pace_partners()
    pp = threading.Thread(target=play_pace_partners)
    pp.start()

if os.path.isfile(ENABLE_BOTS_FILE):
    load_bots()
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

ri = threading.Thread(target=remove_inactive)
ri.start()

if os.path.exists(FAKE_DNS_FILE):
    from fake_dns import fake_dns
    dns = threading.Thread(target=fake_dns, args=(zo.server_ip,))
    dns.start()

zo.run_standalone(online, global_relay, global_pace_partners, global_bots, global_ghosts, regroup_ghosts, discord)
