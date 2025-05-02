#! /usr/bin/env python

# pip install country-converter fuzzywuzzy
#
# use to find and print entries from http://cdn.zwift.com/gameassets/GameDictionary.xml
# scripts/find_equip.py -p emonda -s sworks -o blue -j zwift -e kask

import urllib.request
import json
import country_converter as coco
import argparse
import os
import sys
import xml.etree.ElementTree as ET
from fuzzywuzzy import process
from fuzzywuzzy import fuzz

cc = coco.CountryConverter()

gd_file = 'GameDictionary.xml'
if not os.path.isfile(gd_file):
    open(gd_file, 'wb').write(urllib.request.urlopen('http://cdn.zwift.com/gameassets/%s' % gd_file).read())
tree = ET.parse(gd_file)

def get_item(location, item, json_name):
    items = {}
    for x in tree.findall(location):
        items[x.get('name')] = int(x.get('signature'))
    best_match = process.extractOne(item, items.keys(), scorer=fuzz.token_set_ratio)
    equip = {}
    equip[json_name] = items[best_match[0]]
    equip[json_name+'_name'] = best_match[0]
    return equip

def main(argv):
    global args

    parser = argparse.ArgumentParser(description='Print out json for bot.txt or ghost_profile.txt')
    megroup = parser.add_mutually_exclusive_group()
    parser.add_argument('-n', '--nation', help='Specify nation', default=False)
    parser.add_argument('-j', '--jersey', help='Get jersey', default=False)
    megroup.add_argument('-b', '--bike', help='Get bike', default=False)
    parser.add_argument('-w', '--wheels', help='Get wheels', default=False)
    parser.add_argument('-e', '--helmet', help='Get helmet', default=False)
    parser.add_argument('-s', '--shoes', help='Get shoes', default=False)
    parser.add_argument('-o', '--socks', help='Get socks', default=False)
    parser.add_argument('-g', '--glasses', help='Get glasses', default=False)
    megroup.add_argument('-p', '--paintjob', help='Get paintjob', default=False)
    parser.add_argument('--run_shirt', help='Get run shirt', default=False)
    parser.add_argument('--run_shorts', help='Get run shorts', default=False)
    parser.add_argument('--run_shoes', help='Get run shoes', default=False)
    args = parser.parse_args()

    total_data = {}
    if args.nation:
        total_data['country_code'] = cc.convert(names=args.nation, to='ISOnumeric')
    if args.jersey:
        total_data.update(get_item("./JERSEYS/JERSEY", args.jersey, 'ride_jersey'))
    if args.bike:
        total_data.update(get_item("./BIKEFRAMES/BIKEFRAME", args.bike, 'bike_frame'))
    if args.wheels:
        total_data.update(get_item("./BIKEFRONTWHEELS/BIKEFRONTWHEEL", args.wheels, 'bike_wheel_front'))
        total_data.update(get_item("./BIKEREARWHEELS/BIKEREARWHEEL", args.wheels, 'bike_wheel_rear'))
    if args.helmet:
        total_data.update(get_item("./HEADGEARS/HEADGEAR", args.helmet, 'ride_helmet_type'))
    if args.socks:
        total_data.update(get_item("./SOCKS/SOCK", args.socks, 'ride_socks_type'))
    if args.shoes:
        total_data.update(get_item("./BIKESHOES/BIKESHOE", args.shoes, 'ride_shoes_type'))
    if args.glasses:
        total_data.update(get_item("./GLASSES/GLASS", args.glasses, 'glass_type'))
    if args.paintjob:
        total_data.update(get_item("./PAINTJOBS/PAINTJOB", args.paintjob, 'bike_frame_colour'))
        total_data['bike_frame_colour'] <<= 32
        total_data.update(get_item("./BIKEFRAMES/BIKEFRAME", total_data['bike_frame_colour_name'].split('-')[0], 'bike_frame'))
    if args.run_shirt:
        total_data.update(get_item("./RUNSHIRTS/RUNSHIRT", args.run_shirt, 'run_shirt_type'))
    if args.run_shorts:
        total_data.update(get_item("./RUNSHORTS/RUNSHORT", args.run_shorts, 'run_shorts_type'))
    if args.run_shoes:
        total_data.update(get_item("./RUNSHOES/RUNSHOE", args.run_shoes, 'run_shoes_type'))
    total_data['random_body'] = False

    data = json.dumps(total_data, indent=2)
    print(data)
    open('ghost_profile.txt', 'w').write(data)

if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
    except SystemExit as se:
        print("ERROR:", se)

