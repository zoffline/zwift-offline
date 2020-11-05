#!/usr/bin/env python

import os
import signal
import struct
import sys
import threading
import time
import csv
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
MAP_OVERRIDE = None

update_freq = 3
globalGhosts = {}
ghostsEnabled = {}
online = {}
sentRideOn = False
sentMessage = False

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

def saveGhost(name, player_id):
    global globalGhosts
    if not player_id in globalGhosts.keys(): return
    ghosts = globalGhosts[player_id]
    folder = '%s/%s/ghosts/%s/%s' % (STORAGE_DIR, player_id, course(ghosts.rec.states[0]), roadID(ghosts.rec.states[0]))
    if not isForward(ghosts.rec.states[0]): folder += '/reverse'
    try:
        if not os.path.isdir(folder):
            os.makedirs(folder)
    except:
        return
    f = '%s/%s-%s.bin' % (folder, time.strftime("%Y-%m-%d-%H-%M-%S"), name)
    with open(f, 'wb') as fd:
        fd.write(ghosts.rec.SerializeToString())

def organizeGhosts(player_id):
    # organize ghosts in course/roadID directory structure
    # previously they were saved directly in player_id/ghosts
    folder = '%s/%s/ghosts' % (STORAGE_DIR, player_id)
    if not os.path.isdir(folder): return
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

def loadGhosts(player_id, state, ghosts):
    folder = '%s/%s/ghosts/%s/%s' % (STORAGE_DIR, player_id, course(state), roadID(state))
    if not isForward(state): folder += '/reverse'
    if not os.path.isdir(folder): return
    s = list()
    for f in os.listdir(folder):
        if f.endswith('.bin'):
            with open(os.path.join(folder, f), 'rb') as fd:
                g = ghosts.play.ghosts.add()
                g.ParseFromString(fd.read())
                s.append(g.states[0].roadTime)
    ghosts.start_road = roadID(state)
    ghosts.start_rt = 0
    if os.path.isfile(START_LINES_FILE):
        with open(START_LINES_FILE, 'r') as fd:
            sl = [tuple(line) for line in csv.reader(fd)]
            rt = [t for t in sl if t[0] == str(course(state)) and t[1] == str(roadID(state)) and (boolean(t[2]) == isForward(state) or not t[2])]
            if rt:
                ghosts.start_road = int(rt[0][3])
                ghosts.start_rt = int(rt[0][4])
    if not ghosts.start_rt:
        s.append(state.roadTime)
        if isForward(state): ghosts.start_rt = max(s)
        else: ghosts.start_rt = min(s)
    for g in ghosts.play.ghosts:
        try:
            while roadID(g.states[0]) != ghosts.start_road:
                del g.states[0]
            if isForward(g.states[0]):
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

        SimpleHTTPRequestHandler.do_GET(self)

class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        global sentMessage
        global sentRideOn

        self.data = self.request.recv(1024)
        hello = tcp_node_msgs_pb2.TCPHello()
        try:
            hello.ParseFromString(self.data[3:-4])
        except:
            pass
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
        while True:
            tcpthreadevent.wait(timeout=25)
            try:
                self.request.sendall(struct.pack('!h', len(payload)))
                self.request.sendall(payload)

                #RideOn Test
                #sentRideOn = True
                if not sentRideOn and '1001' in online and '1003' in online:#not player_id == 1003 and not sentRideOn and str(1003) in online:
                    sentRideOn = True

                    message = udp_node_msgs_pb2.ServerToClient()
                    message.f1 = 1
                    message.player_id = player_id
                    message.world_time = zwift_offline.world_time()

                    ride_on = udp_node_msgs_pb2.RideOn()
                    if player_id == 1001:
                        ride_on.rider_id = 1003
                        ride_on.to_rider_id = player_id
                        ride_on.firstName = 'Fanny'
                        ride_on.lastName = 'Astrand'
                        ride_on.countryCode = 752
                    else:
                        ride_on.rider_id = 1001
                        ride_on.to_rider_id = player_id
                        ride_on.firstName = 'Per'
                        ride_on.lastName = 'Astrand'
                        ride_on.countryCode = 752

                    update = message.updates.add()
                    #update.f1 = 587845624533328784
                    update.f2 = 1
                    update.type = 4 #ride on type
                    update.world_time1 = message.world_time - 1000#recv.world_time#recv.world_time
                    update.world_time2 = message.world_time + 8890#recv.world_time + 9890#message.world_time#recv.world_time + 6000
                    update.f14 = int(time.time() * 1000000)#t#1604516817408239 #some kind of time?
                    update.payload = ride_on.SerializeToString()

                    ride_on_payload = message.SerializeToString()
                    self.request.sendall(struct.pack('!h', len(ride_on_payload)))
                    self.request.sendall(ride_on_payload)

                #Message
                #sentMessage = True
                if not sentMessage and '1001' in online and '1003' in online:
                    #sentMessage = True

                    message = udp_node_msgs_pb2.ServerToClient()
                    message.f1 = 1
                    message.player_id = player_id
                    message.seqno = 1
                    message.f5 = 1
                    message.f11 = 1
                    message.world_time = zwift_offline.world_time()
                    message.msgnum = 2
                    message.num_msgs = 2
                    
                    chat_message1 = udp_node_msgs_pb2.ChatMessage()
                    chat_message1.avatar = ''
                    chat_message1.countryCode = 752
                    chat_message1.eventSubgroup = 0
                    chat_message1.f3 = 1
                    chat_message1.firstName = 'Fanny'
                    chat_message1.lastName = 'Astrand'
                    chat_message1.message = 'Comon!'
                    chat_message1.rider_id = 1003
                    chat_message1.to_rider_id = 0

                    chat_message2 = udp_node_msgs_pb2.ChatMessage()
                    chat_message2.avatar = ''
                    chat_message2.countryCode = 752
                    chat_message2.eventSubgroup = 0
                    chat_message2.f3 = 1
                    chat_message2.firstName = 'Per'
                    chat_message2.lastName = 'Astrand'
                    chat_message2.message = 'Ride on!'
                    chat_message2.rider_id = 1001
                    chat_message2.to_rider_id = 0
                    
                    update1 = message.updates.add()
                    update1.f2 = 1
                    update1.type = 5 #chat message type
                    update1.world_time1 = message.world_time - 1000
                    state = online.get(str(player_id))
                    if not state == None:
                        update1.x = int(state.x)
                        update1.altitude = int(state.altitude)
                        update1.y = int(state.y)
                    update1.world_time2 = message.world_time + 59000
                    update1.f11 = 75000
                    update1.f12 = 1
                    update1.f14 = int(str(int(time.time()*1000000)))
                    update1.payload = chat_message1.SerializeToString()

                    update2 = message.updates.add()
                    update2.f2 = 1
                    update2.type = 5 #chat message type
                    update2.world_time1 = message.world_time - 1000
                    state = online.get(str(player_id))
                    if not state == None:
                        update2.x = int(state.x)
                        update2.altitude = int(state.altitude)
                        update2.y = int(state.y)
                    update2.world_time2 = message.world_time + 59000
                    update2.f11 = 75000
                    update2.f12 = 1
                    update2.f14 = int(str(int(time.time()*1000000)))
                    update2.payload = chat_message2.SerializeToString()

                    chat_message_payload = message.SerializeToString()
                    self.request.sendall(struct.pack('!h', len(chat_message_payload)))
                    self.request.sendall(chat_message_payload)
            except Exception as e:
                print(e)
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

class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        socket = self.request[1]
        recv = udp_node_msgs_pb2.ClientToServer()
        
        try:
            recv.ParseFromString(data[:-4])
        except:
            recv.ParseFromString(data[3:-4])

        client_address = self.client_address
        player_id = recv.player_id
        #Add handling of ghosts for player if it's missing
        if not player_id in globalGhosts.keys():
            globalGhosts[player_id] = GhostsVariables()

        ghosts = globalGhosts[player_id]

        if recv.seqno == 1 or ghosts.rec == None:
            ghosts.rec = udp_node_msgs_pb2.Ghost()
            ghosts.play = udp_node_msgs_pb2.Ghosts()
            ghosts.last_rt = 0
            ghosts.play_count = 0
            ghosts.loaded = False
            ghosts.started = False
            ghosts.rec.player_id = player_id
            organizeGhosts(player_id)

        t = int(time.time())
        ghosts.lastPackageTime = t

        if str(player_id) in ghostsEnabled and ghostsEnabled[str(player_id)]:
            if not ghosts.loaded and recv.state.roadTime > 0:
                ghosts.loaded = True
                loadGhosts(player_id, recv.state, ghosts)
            if recv.state.roadTime and ghosts.last_rt and recv.state.roadTime != ghosts.last_rt:
                if t >= ghosts.last_rec + update_freq:
                    state = ghosts.rec.states.add()
                    state.CopyFrom(recv.state)
                    ghosts.last_rec = t
                if not ghosts.started and ghosts.play.ghosts and roadID(recv.state) == ghosts.start_road:
                    if isForward(recv.state):
                        if recv.state.roadTime >= ghosts.start_rt >= ghosts.last_rt:
                            ghosts.started = True
                    else:
                        if recv.state.roadTime <= ghosts.start_rt <= ghosts.last_rt:
                            ghosts.started = True
            ghosts.last_rt = recv.state.roadTime

        keys = online.keys()
        removePlayers = list()
        for p_id in keys:
            if zwift_offline.world_time() > online[p_id].worldTime + 10000:
                removePlayers.insert(0, p_id)
        for p_id in removePlayers:
            online.pop(p_id)
        if recv.state.roadTime:
            online[str(player_id)] = recv.state

        #Remove ghosts entries for inactive players (disconnected?)
        keys = globalGhosts.keys()
        removePlayers = list()
        for p_id in keys:
            if globalGhosts[p_id].lastPackageTime < t - 10:
                removePlayers.insert(0, p_id)
        for p_id in removePlayers:
            globalGhosts.pop(p_id)

        if ghosts.started and t >= ghosts.last_play + update_freq:
            message = udp_node_msgs_pb2.ServerToClient()
            message.f1 = 1
            message.player_id = player_id
            message.seqno = 1
            message.f5 = 1
            message.f11 = 1
            msgnum = 1
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
                            message.msgnum = msgnum
                            socket.sendto(message.SerializeToString(), client_address)
                            msgnum += 1
                            del message.states[:]
                            state = message.states.add()
                            state.CopyFrom(g.states[ghosts.play_count])
                            state.id = player_id + ghost_id * 10000000
                            state.worldTime = zwift_offline.world_time()
                    ghost_id += 1
            else: message.num_msgs = 1
            message.world_time = zwift_offline.world_time()
            message.msgnum = msgnum
            socket.sendto(message.SerializeToString(), client_address)
            ghosts.play_count += 1
            ghosts.last_play = t
        else:
            message = udp_node_msgs_pb2.ServerToClient()
            message.f1 = 1
            message.player_id = player_id
            message.seqno = 1
            message.f5 = 1
            message.f11 = 1
            msgnum = 1
            players = len(online)
            for p_id in online.keys():
                player = online[p_id]
                if player.id == player_id:
                    players -= 1
            message.num_msgs = players // 10
            if players % 10: message.num_msgs += 1
            for p_id in online.keys():
                player = online[p_id]
                if player.id != player_id:
                    if len(message.states) < 10:
                        state = message.states.add()
                        state.CopyFrom(player)
                    else:
                        message.world_time = zwift_offline.world_time()
                        message.msgnum = msgnum
                        socket.sendto(message.SerializeToString(), client_address)
                        msgnum += 1
                        del message.states[:]
                        state = message.states.add()
                        state.CopyFrom(player)
            message.world_time = zwift_offline.world_time()
            message.msgnum = msgnum
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

zwift_offline.run_standalone(online, ghostsEnabled, saveGhost)
