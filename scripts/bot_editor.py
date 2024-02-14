# Script to manipulate zoffline bot files
#
# Route ID can be found in http://cdn.zwift.com/gameassets/GameDictionary.xml (signature)
#
# Type .position in chat to find start road and roadTime, the values will be printed in console
# Choose a position where the bot passes both times at the same speed to have a smooth loop

import os
import sys
import csv
sys.path.insert(0, '../protobuf')
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
        if a.id == 1766985504:
            a.number_value = int(input("Route ID: "))
    with open(PROFILE_FILE, 'wb') as f:
        f.write(p.SerializeToString())

ROUTE_FILE = 'route.bin'
if file_exists(ROUTE_FILE):
    g = udp_node_msgs_pb2.Ghost()
    with open(ROUTE_FILE, 'rb') as f:
        g.ParseFromString(f.read())
    start_road = int(input("Start road: "))
    start_rt = int(input("Start roadTime: "))
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

print('\nDone')
