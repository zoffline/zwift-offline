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
jerseys = {}
for x in tree.findall("./JERSEYS/JERSEY"):
    jerseys[x.get('name')] = int(x.get('signature'))
bikes = {}
for x in tree.findall("./BIKEFRAMES/BIKEFRAME"):
    bikes[x.get('name')] = int(x.get('signature'))
fwheel = {}
for x in tree.findall("./BIKEFRONTWHEELS/BIKEFRONTWHEEL"):
    fwheel[x.get('name')] = int(x.get('signature'))
rwheel = {}
for x in tree.findall("./BIKEREARWHEELS/BIKEREARWHEEL"):
    rwheel[x.get('name')] = int(x.get('signature'))
helmets = {}
for x in tree.findall("./HEADGEARS/HEADGEAR"):
    helmets[x.get('name')] = int(x.get('signature'))
glasses = {}
for x in tree.findall("./GLASSES/GLASS"):
    glasses[x.get('name')] = int(x.get('signature'))
socks = {}
for x in tree.findall("./SOCKS/SOCK"):
    socks[x.get('name')] = int(x.get('signature'))
paintjobs = {}
for x in tree.findall("./PAINTJOBS/PAINTJOB"):
    paintjobs[x.get('name')] = int(x.get('signature'))
shoes = {}
for x in tree.findall("./BIKESHOES/BIKESHOE"):
    shoes[x.get('name')] = int(x.get('signature'))

def main(argv):
    global args

    parser = argparse.ArgumentParser(description='Print out json for bot.txt or ghost_profile.txt')
    parser.add_argument('-n', '--nation', help='Specify nation', default=False)
    parser.add_argument('-j', '--jersey', help='Get jersey', default=False)
    parser.add_argument('-b', '--bike', help='Get bike', default=False)
    parser.add_argument('-w', '--wheels', help='Get wheels', default=False)
    parser.add_argument('-e', '--helmet', help='Get helmet', default=False)
    parser.add_argument('-s', '--shoes', help='Get shoes', default=False)
    parser.add_argument('-o', '--socks', help='Get socks', default=False)
    parser.add_argument('-g', '--glasses', help='Get glasses', default=False)
    parser.add_argument('-p', '--paintjob', help='Get paintjob', default=False)
    args = parser.parse_args()

    total_data = {}
    if args.nation:
        total_data['country_code'] = cc.convert(names=args.nation, to='ISOnumeric')
    if args.jersey:
        best_match = process.extractOne(args.jersey, jerseys.keys(), scorer=fuzz.token_set_ratio)
        total_data['ride_jersey'] = jerseys[best_match[0]]
        total_data['ride_jersey_name'] = best_match[0]
    if args.bike:
        best_match = process.extractOne(args.bike, bikes.keys(), scorer=fuzz.token_set_ratio)
        total_data['bike_frame'] = bikes[best_match[0]]
        total_data['bike_frame_name'] = best_match[0]
    if args.wheels:
        best_match = process.extractOne(args.wheels, fwheel.keys(), scorer=fuzz.token_set_ratio)
        total_data['bike_wheel_front'] = fwheel[best_match[0]]
        total_data['bike_wheel_front_name'] = best_match[0]
        best_match = process.extractOne(args.wheels, rwheel.keys(), scorer=fuzz.token_set_ratio)
        total_data['bike_wheel_rear'] = rwheel[best_match[0]]
        total_data['bike_wheel_rear_name'] = best_match[0]
    if args.helmet:
        best_match = process.extractOne(args.helmet, helmets.keys(), scorer=fuzz.token_set_ratio)
        total_data['ride_helmet_type'] = helmets[best_match[0]]
        total_data['ride_helmet_type_name'] = best_match[0]
    if args.socks:
        best_match = process.extractOne(args.socks, socks.keys(), scorer=fuzz.token_set_ratio)
        total_data['ride_socks_type'] = socks[best_match[0]]
        total_data['ride_socks_name'] = best_match[0]
    if args.shoes:
        best_match = process.extractOne(args.shoes, shoes.keys(), scorer=fuzz.token_set_ratio)
        total_data['ride_shoes_type'] = shoes[best_match[0]]
        total_data['ride_shoes_type_name'] = best_match[0]
    if args.glasses:
        best_match = process.extractOne(args.glasses, glasses.keys(), scorer=fuzz.token_set_ratio)
        total_data['glass_type'] = glasses[best_match[0]]
        total_data['glass_type_name'] = best_match[0]
    if args.paintjob:
        best_match = process.extractOne(args.paintjob, paintjobs.keys(), scorer=fuzz.token_set_ratio)
        total_data['bike_frame_colour'] = paintjobs[best_match[0]]
        total_data['bike_frame_colour_name'] = best_match[0]
        bike_frame_match = process.extractOne(best_match[0].split('-')[0], bikes.keys(), scorer=fuzz.token_set_ratio)
        total_data['bike_frame'] = bikes[bike_frame_match[0]]
        total_data['bike_frame_name'] = bike_frame_match[0]

    data = json.dumps(total_data, indent=2)
    print(data)

if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
    except SystemExit as se:
        print("ERROR:", se)

