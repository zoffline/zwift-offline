#!/usr/bin/env python

import os
import signal
import struct
import sys
import threading
import time
import csv
import math
from collections import deque
from datetime import datetime
from shutil import copyfile
if sys.version_info[0] > 2:
    import socketserver
    from http.server import SimpleHTTPRequestHandler
    from http.cookies import SimpleCookie
else:
    import SocketServer as socketserver
    from SimpleHTTPServer import SimpleHTTPRequestHandler
    from Cookie import SimpleCookie

import zwift_offline
import protobuf.udp_node_msgs_pb2 as udp_node_msgs_pb2
import protobuf.tcp_node_msgs_pb2 as tcp_node_msgs_pb2
import protobuf.profile_pb2 as profile_pb2

if getattr(sys, 'frozen', False):
    # If we're running as a pyinstaller bundle
    SCRIPT_DIR = sys._MEIPASS
    STORAGE_DIR = "%s/storage" % os.path.dirname(sys.executable)
    START_LINES_FILE = '%s/start_lines.csv' % STORAGE_DIR
    if not os.path.isfile(START_LINES_FILE):
        copyfile('%s/start_lines.csv' % SCRIPT_DIR, START_LINES_FILE)
else:
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
    STORAGE_DIR = "%s/storage" % SCRIPT_DIR
    START_LINES_FILE = '%s/start_lines.csv' % SCRIPT_DIR

CDN_DIR = "%s/cdn" % SCRIPT_DIR
PACE_PARTNERS_DIR = '%s/pace_partners' % SCRIPT_DIR
BOTS_DIR = '%s/bots' % SCRIPT_DIR

PROXYPASS_FILE = "%s/cdn-proxy.txt" % STORAGE_DIR
SERVER_IP_FILE = "%s/server-ip.txt" % STORAGE_DIR
DISCORD_CONFIG_FILE = "%s/discord.cfg" % STORAGE_DIR
MAP_OVERRIDE = deque(maxlen=16)

online_update_freq = 1
ghost_update_freq = 3
pacer_update_freq = 1
bot_update_freq = 3
last_updates = {}
last_online_updates = {}
last_pp_updates = {}
last_bot_updates = {}
global_ghosts = {}
ghosts_enabled = {}
online = {}
player_update_queue = {}
global_pace_partners = {}
global_bots = {}

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
    ghosts.rec = None

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
                while g.states[0].roadTime < ghosts.start_rt or abs(g.states[0].roadTime - ghosts.start_rt) > 500000:
                    del g.states[0]
            else:
                while g.states[0].roadTime > ghosts.start_rt or abs(g.states[0].roadTime - ghosts.start_rt) > 500000:
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
            import requests
            try:
                url = 'http://{}{}'.format(hostname, self.path)
                req_header = self.parse_headers()
                resp = requests.get(url, headers=merge_two_dicts(req_header, set_header()), verify=False)
            except:
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
        if self.request.getpeername()[0] == '127.0.0.1':  # to avoid needing hairpinning
            udp_node_ip = "127.0.0.1"
        elif os.path.exists(SERVER_IP_FILE):
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
            except:
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
    course = 0
    last_package_time = 0

class PacePartnerVariables:
    route = None
    position = 0

class BotVariables:
    route = None
    position = 0

def load_pace_partners():
    if not os.path.isdir(PACE_PARTNERS_DIR): return
    for (root, dirs, files) in os.walk(PACE_PARTNERS_DIR):
        for pp_id in dirs:
            p_id = int(pp_id)
            route = '%s/%s/route.bin' % (PACE_PARTNERS_DIR, pp_id)
            if os.path.isfile(route):
                with open(route, 'rb') as fd:
                    global_pace_partners[p_id] = PacePartnerVariables()
                    pp = global_pace_partners[p_id]
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
            state.worldTime = zwift_offline.world_time()
        ppthreadevent.wait(timeout=pacer_update_freq)

def load_bots():
    if not os.path.isdir(BOTS_DIR): return
    for (root, dirs, files) in os.walk(BOTS_DIR):
        for bot_id in dirs:
            p_id = int(bot_id)
            route = '%s/%s/route.bin' % (BOTS_DIR, bot_id)
            if os.path.isfile(route):
                with open(route, 'rb') as fd:
                    global_bots[p_id] = BotVariables()
                    bot = global_bots[p_id]
                    bot.route = udp_node_msgs_pb2.Ghost()
                    bot.route.ParseFromString(fd.read())
                    bot.position = 0

def play_bots():
    global global_bots
    while True:
        if zwift_offline.reload_pacer_bots:
            zwift_offline.reload_pacer_bots = False
            global_bots.clear()
            load_bots()
        for bot_id in global_bots.keys():
            bot = global_bots[bot_id]
            if bot.position < len(bot.route.states) - 1: bot.position += 1
            else: bot.position = 0
            state = bot.route.states[bot.position]
            state.id = bot_id
            state.watchingRiderId = bot_id
            state.worldTime = zwift_offline.world_time()
        botthreadevent.wait(timeout=bot_update_freq)

def remove_inactive():
    while True:
        remove_players = list()
        for p_id in online.keys():
            if zwift_offline.world_time() > online[p_id].worldTime + 10000:
                remove_players.insert(0, p_id)
        for p_id in remove_players:
            zwift_offline.logout_player(p_id)

        remove_players = list()
        for p_id in global_ghosts.keys():
            if zwift_offline.get_utc_time() > global_ghosts[p_id].last_package_time + 10:
                remove_players.insert(0, p_id)
        for p_id in remove_players:
            global_ghosts.pop(p_id)
        rithreadevent.wait(timeout=1)

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
                #If no sensors connected, first byte must be skipped
                recv.ParseFromString(data[1:-4])
            except:
                return

        client_address = self.client_address
        player_id = recv.player_id
        state = recv.state

        #Add last updates for player if missing
        if not player_id in last_updates.keys():
            last_updates[player_id] = 0
        if not player_id in last_online_updates.keys():
            last_online_updates[player_id] = 0
        if not player_id in last_pp_updates.keys():
            last_pp_updates[player_id] = 0
        if not player_id in last_bot_updates.keys():
            last_bot_updates[player_id] = 0

        t = int(zwift_offline.get_utc_time())

        #Update player online state
        if state.roadTime and t >= last_updates[player_id] + online_update_freq:
            last_updates[player_id] = t
            if not player_id in online.keys():
                discord.send_message('%s riders online' % (len(online) + 1))
            online[player_id] = state

        #Add handling of ghosts for player if it's missing
        if not player_id in global_ghosts.keys():
            global_ghosts[player_id] = GhostsVariables()

        ghosts = global_ghosts[player_id]
        ghosts.last_package_time = t

        if recv.seqno == 1:
            ghosts.rec = None
            organize_ghosts(player_id)

        #Changed course
        if get_course(state) and ghosts.course != get_course(state):
            ghosts.rec = None
            ghosts.course = get_course(state)

        if ghosts.rec == None:
            ghosts.rec = udp_node_msgs_pb2.Ghost()
            ghosts.play = udp_node_msgs_pb2.Ghosts()
            ghosts.last_rt = 0
            ghosts.play_count = 0
            ghosts.loaded = False
            ghosts.started = False
            ghosts.rec.player_id = player_id

        if player_id in ghosts_enabled and ghosts_enabled[player_id]:
            #Load ghosts for current course
            if not ghosts.loaded and get_course(state):
                ghosts.loaded = True
                load_ghosts(player_id, state, ghosts)
            #Save player state as ghost if moving
            if state.roadTime and ghosts.last_rt and state.roadTime != ghosts.last_rt:
                if t >= ghosts.last_rec + ghost_update_freq:
                    s = ghosts.rec.states.add()
                    s.CopyFrom(state)
                    ghosts.last_rec = t
                #Start loaded ghosts
                if not ghosts.started and ghosts.play.ghosts and road_id(state) == ghosts.start_road:
                    if is_forward(state):
                        if state.roadTime > ghosts.start_rt and abs(state.roadTime - ghosts.start_rt) < 500000:
                            ghosts.started = True
                    else:
                        if state.roadTime < ghosts.start_rt and abs(state.roadTime - ghosts.start_rt) < 500000:
                            ghosts.started = True
            #Uncomment to print player state when stopped (to find new start lines)
            #else: print('course', get_course(state), 'road', road_id(state), 'isForward', is_forward(state), 'roadTime', state.roadTime)
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
            ghost = ghosts.play.ghosts[math.floor(state.watchingRiderId / 10000000) - 1]
            if len(ghost.states) > ghosts.play_count:
                watching_state = ghost.states[ghosts.play_count]

        #Check if online players, pace partners, bots and ghosts are nearby
        nearby = list()
        if t >= last_online_updates[player_id] + online_update_freq:
            last_online_updates[player_id] = t
            for p_id in online.keys():
                player = online[p_id]
                if player.id != player_id and zwift_offline.is_nearby(watching_state, player):
                    nearby.append(p_id)
        if t >= last_pp_updates[player_id] + pacer_update_freq:
            last_pp_updates[player_id] = t
            for p_id in global_pace_partners.keys():
                pace_partner_variables = global_pace_partners[p_id]
                pace_partner = pace_partner_variables.route.states[pace_partner_variables.position]
                if zwift_offline.is_nearby(watching_state, pace_partner):
                    nearby.append(p_id)
        if t >= last_bot_updates[player_id] + bot_update_freq:
            last_bot_updates[player_id] = t
            for p_id in global_bots.keys():
                bot_variables = global_bots[p_id]
                bot = bot_variables.route.states[bot_variables.position]
                if zwift_offline.is_nearby(watching_state, bot):
                    nearby.append(p_id)
        if ghosts.started and t >= ghosts.last_play + ghost_update_freq:
            ghosts.last_play = t
            ghost_id = 1
            for g in ghosts.play.ghosts:
                if len(g.states) > ghosts.play_count and zwift_offline.is_nearby(watching_state, g.states[ghosts.play_count]):
                    nearby.append(player_id + ghost_id * 10000000)
                ghost_id += 1
            ghosts.play_count += 1

        #Send nearby riders states or empty message
        message = get_empty_message(player_id)
        if nearby:
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
                    player.CopyFrom(ghosts.play.ghosts[math.floor(p_id / 10000000) - 1].states[ghosts.play_count - 1])
                    player.id = p_id
                    player.worldTime = zwift_offline.world_time()
                if player != None:
                    if len(message.states) > 9:
                        message.world_time = zwift_offline.world_time()
                        socket.sendto(message.SerializeToString(), client_address)
                        message.msgnum += 1
                        del message.states[:]
                    s = message.states.add()
                    s.CopyFrom(player)
        else:
            message.num_msgs = 1
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

rithreadevent = threading.Event()
ri = threading.Thread(target=remove_inactive)
ri.start()

load_pace_partners()
ppthreadevent = threading.Event()
pp = threading.Thread(target=play_pace_partners)
pp.start()

load_bots()
botthreadevent = threading.Event()
bot = threading.Thread(target=play_bots)
bot.start()

if os.path.isfile(DISCORD_CONFIG_FILE):
    from discord_bot import DiscordThread
    discord = DiscordThread(DISCORD_CONFIG_FILE)
else:
    class DummyDiscord():
        def send_message(self, msg, sender_id=None):
            pass
    discord = DummyDiscord()

zwift_offline.run_standalone(online, global_pace_partners, global_bots, global_ghosts, ghosts_enabled, save_ghost, player_update_queue, discord)
