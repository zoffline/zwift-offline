# Script to manipulate zoffline bot files
#
# Route ID can be found in Zwift\assets\Worlds\worldX\data_1.wad\Worlds\worldX\routes\routesX.xml (nameHash)
#
# To find new start line values, uncomment this line (the values will be printed when you are stopped)
# https://github.com/zoffline/zwift-offline/blob/d84e82c72086a8994b8b43042b76f70dc1f1e059/standalone.py#L509

import os
import sys
import csv
sys.path.append(os.path.join(sys.path[0], 'protobuf')) # otherwise import in .proto does not work
import profile_pb2
import udp_node_msgs_pb2

try:
    input = raw_input
except NameError:
    pass

def road_id(state):
    return (state.aux3 & 0xff00) >> 8

def is_forward(state):
    return (state.f19 & 4) != 0

def get_course(state):
    return (state.f19 & 0xff0000) >> 16

def boolean(s):
    if s.lower() in ['true', 'yes', '1']: return True
    if s.lower() in ['false', 'no', '0']: return False
    return None

def delete(s, i):
    print('course %s road %s isForward %s roadTime %s' % (get_course(s[i]), road_id(s[i]), is_forward(s[i]), s[i].roadTime))
    del s[i]

def file_exists(file):
    if not os.path.isfile(file):
        print('%s not found\n' % file)
        return False
    return True

PROFILE_FILE = 'profile.bin'
if file_exists(PROFILE_FILE):
    p = profile_pb2.PlayerProfile()
    with open(PROFILE_FILE, 'rb') as f:
        p.ParseFromString(f.read())
    p.id = int(input("Player ID: "))
    p.first_name = input("First name: ")
    p.last_name = input("Last name: ")
    for a in p.public_attributes:
        #0x69520F20=1766985504 - crc32 of "PACE PARTNER - ROUTE"
        #TODO: -1021012238: figure out
        if a.id == 1766985504 or a.id == -1021012238:  #-1021012238 == 3273955058
            a.number_value = int(input("Route ID: "))
    with open(PROFILE_FILE, 'wb') as f:
        f.write(p.SerializeToString())

ROUTE_FILE = 'route.bin'
if file_exists(ROUTE_FILE):
    g = udp_node_msgs_pb2.Ghost()
    with open(ROUTE_FILE, 'rb') as f:
        g.ParseFromString(f.read())
    START_LINES_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'bot_start_lines.csv')
    if file_exists(START_LINES_FILE) and len(g.states) > 0:
        f = open(START_LINES_FILE, 'r')
        sl = [tuple(line) for line in csv.reader(f)]
        f.close()
        rt = [t for t in sl if t[0] == str(get_course(g.states[0])) and t[1] == str(road_id(g.states[0])) and (boolean(t[2]) == is_forward(g.states[0]) or not t[2])]
        if rt:
            start_road = int(rt[0][3])
            start_rt = int(rt[0][4])
            print('Start line: course %s road %s isForward %s roadTime %s\n' % (get_course(g.states[0]), start_road, is_forward(g.states[0]), start_rt))
            print('Deleted records:\n')
            try:
                while road_id(g.states[0]) != start_road:
                    delete(g.states, 0)
                while road_id(g.states[-1]) != start_road:
                    delete(g.states, -1)
                if is_forward(g.states[0]):
                    while g.states[0].roadTime < start_rt or abs(g.states[0].roadTime - start_rt) > 500000:
                        delete(g.states, 0)
                    while g.states[-1].roadTime > start_rt or abs(g.states[-1].roadTime - start_rt) > 500000:
                        delete(g.states, -1)
                else:
                    while g.states[0].roadTime > start_rt or abs(g.states[0].roadTime - start_rt) > 500000:
                        delete(g.states, 0)
                    while g.states[-1].roadTime < start_rt or abs(g.states[-1].roadTime - start_rt) > 500000:
                        delete(g.states, -1)
            except IndexError:
                pass
            with open(ROUTE_FILE, 'wb') as f:
                f.write(g.SerializeToString())
        else:
            print('Start line not found (course %s road %s isForward %s)' % (get_course(g.states[0]), road_id(g.states[0]), is_forward(g.states[0])))

print('\nDone')
