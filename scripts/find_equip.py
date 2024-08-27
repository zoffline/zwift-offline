#! /usr/bin/env python

# pip install beautifulsoup4 country-converter fuzzywuzzy
#
# use to find and print entries from http://cdn.zwift.com/gameassets/GameDictionary.xml
# scripts/find_equip.py -p emonda -s sworks -o blue -j zwift -e kask

from bs4 import BeautifulSoup
import urllib.request
import json
import country_converter as coco
import argparse
import getpass
import os
import sys
import xml.etree.ElementTree as ET
from fuzzywuzzy import process
from fuzzywuzzy import fuzz

cc = coco.CountryConverter()

tree = ET.fromstring(urllib.request.urlopen('http://cdn.zwift.com/gameassets/GameDictionary.xml').read())

def get_item(equip, location, item, json_name):
    items = {}
    for x in tree.findall(location):
        items[x.get('name')] = int(x.get('signature'))
    best_match = process.extractOne(item, items.keys(), scorer=fuzz.token_set_ratio)
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
    args = parser.parse_args()

    total_data = {}
    if args.nation:
        total_data['country_code'] = cc.convert(names=args.nation, to='ISOnumeric')
    if args.jersey:
        total_data = get_item(total_data, "./JERSEYS/JERSEY", args.jersey, 'ride_jersey')
    if args.bike:
        total_data = get_item(total_data, "./BIKEFRAMES/BIKEFRAME", args.bike, 'bike_frame')
    if args.wheels:
        total_data = get_item(total_data, "./BIKEFRONTWHEELS/BIKEFRONTWHEEL", args.wheels, 'bike_wheel_front')
        total_data = get_item(total_data, "./BIKEREARWHEELS/BIKEREARWHEEL", args.wheels, 'bike_wheel_rear')
    if args.helmet:
        total_data = get_item(total_data, "./HEADGEARS/HEADGEAR", args.helmet, 'ride_helmet_type')
    if args.socks:
        total_data = get_item(total_data, "./SOCKS/SOCK", args.socks, 'ride_socks_type')
    if args.shoes:
        total_data = get_item(total_data, "./BIKESHOES/BIKESHOE", args.shoes, 'ride_shoes_type')
    if args.glasses:
        total_data = get_item(total_data, "./GLASSES/GLASS", args.glasses, 'glass_type')
    if args.paintjob:
        total_data = get_item(total_data, "./PAINTJOBS/PAINTJOB", args.paintjob, 'bike_frame_colour')
        total_data = get_item(total_data, "./BIKEFRAMES/BIKEFRAME", total_data['bike_frame_colour_name'].split('-')[0], 'bike_frame')

    data = json.dumps(total_data, indent=2)
    print(data)

if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
    except SystemExit as se:
        print("ERROR:", se)

