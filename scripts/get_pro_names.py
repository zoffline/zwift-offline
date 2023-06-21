#! /usr/bin/env python

# Use this script to populate bot.txt with names from https://www.procyclingstats.com
# pip install beautifulsoup4 country-converter fuzzywuzzy
# scripts/get_pro_names.py -h


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

base_url = "https://www.procyclingstats.com/rankings.php?filter=Filter"
cc = coco.CountryConverter()

def get_pros(url, male, get_jersey, get_equipment):
    data = []
    bikes = {}
    bikes['AG2R Citroën Team'] = { 'Bike': 'BMC BMCTeammachine', 'Wheels': 'Campagnolo Bora WTO' }
    bikes['Alpecin-Deceuninck'] = { 'Bike': 'Canyon Aeroad CFR', 'Wheels': 'Shimano C50' }
    bikes['Astana Qazaqstan Team'] = { 'Bike': 'Wilier Triestina Filante', 'Wheels': 'Corima' }
    bikes['Bahrain - Victorious'] = { 'Bike': 'Merida Scultura', 'Wheels': 'Vision Metron 45SL' }
    bikes['BORA - hansgrohe'] = { 'Bike': 'Specialized Tarmac SL7', 'Wheels': 'Roval Rapide CLX' }
    bikes['Cofidis'] = { 'Bike': 'Look', 'Wheels': 'Corima' }
    bikes['EF Education-EasyPost'] = { 'Bike': 'Cannondale SystemSix', 'Wheels': 'Vision Metron' }
    bikes['Groupama - FDJ'] = { 'Bike': 'Lapierre Xelius SL3', 'Wheels': 'Shimano C50' }
    bikes['INEOS Grenadiers'] = { 'Bike': 'Pinarello Dogma F', 'Wheels': 'Princeton Carbonworks' }
    bikes['Intermarché - Circus - Wanty'] = { 'Bike': 'Cube Litening Aero C:68X Pro', 'Wheels': 'Newmen Advanced SL' }
    bikes['Jumbo-Visma'] = { 'Bike': 'Cervélo R5 Disc', 'Wheels': 'Reserve 52' }
    bikes['Movistar Team'] = { 'Bike': 'Canyon Aeroad CFR', 'Wheels': 'Zipp' }
    bikes['Soudal - Quick Step'] = { 'Bike': 'Specialized S-Works Tarmac SL7', 'Wheels': 'Roval Rapide CLX' }
    bikes['Team Arkéa Samsic'] = { 'Bike': 'Bianchi Oltre RC', 'Wheels': 'Vision' }
    bikes['Team DSM'] = { 'Bike': 'Scott Foil RC', 'Wheels': 'Shimano C50' }
    bikes['Team Jayco AlUla'] = { 'Bike': 'Giant Propel', 'Wheels': 'Cadex 42' }
    bikes['Trek - Segafredo'] = { 'Bike': 'Trek Madone SLR', 'Wheels': 'Bontrager Aeolus' }
    bikes['UAE Team Emirates'] = { 'Bike': 'Colnago V4Rs', 'Wheels': 'Enve' }

    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    site = urllib.request.urlopen(req).read()
    soup = BeautifulSoup(site)

    for td in soup.find_all('td'):
        if td.span and td.contents[0]:
            tmp = {}
            if "flag" in repr(td.contents[0]):
                code = td.span.get_attribute_list("class")[1]
                tmp['country_code'] = cc.convert(names=code, to='ISOnumeric')
                tmp['is_male'] = male
                if td.a:
                    tmp['first_name'] = (td.a.contents[1].strip())
                    tmp['last_name'] = (td.a.span.contents[0])
        if td.a and td.contents[0]:
            if "cu600" in repr(td) and td.a.contents:
                best_match = process.extractOne(td.a.contents[0], jerseys.keys(), scorer=fuzz.token_set_ratio)
                if 'first_name' in tmp:
                    print ("%s %s : %s - %s" % (tmp['first_name'],tmp['last_name'],td.a.contents[0], best_match))
                    if get_jersey:
                        if best_match[0] in jerseys:
                            tmp['jersey'] = jerseys[best_match[0]]
                    if get_equipment:
                        if td.a.contents[0] in bikes:
                            bike_match = process.extractOne(bikes[td.a.contents[0]]['Bike'], bikeframes.keys(), scorer=fuzz.token_sort_ratio)
                            fwheel_match = process.extractOne(bikes[td.a.contents[0]]['Wheels'], bikefrontwheels.keys(), scorer=fuzz.token_set_ratio)
                            rwheel_match = process.extractOne(bikes[td.a.contents[0]]['Wheels'], bikerearwheels.keys(), scorer=fuzz.token_set_ratio)
                            print ("%s : %s - %s" %(bike_match, fwheel_match, rwheel_match))
                            if bike_match[0] in bikeframes:
                                tmp['bike_frame'] = bikeframes[bike_match[0]]
                            if fwheel_match[0] in bikefrontwheels:
                                tmp['bike_wheel_front'] = bikefrontwheels[fwheel_match[0]]
                            if rwheel_match[0] in bikerearwheels:
                                tmp['bike_wheel_rear'] = bikerearwheels[rwheel_match[0]]

                    data.append(tmp)

    return data

tree = ET.parse('../cdn/gameassets/GameDictionary.xml')
root = tree.getroot()
jerseys = {}
for x in root.findall("./JERSEYS/JERSEY"):
    jerseys[x.get('name')] = int(x.get('signature'))
bikeframes = {}
for x in root.findall("./BIKEFRAMES/BIKEFRAME"):
    bikeframes[x.get('name')] = int(x.get('signature'))
bikefrontwheels = {}
for x in root.findall("./BIKEFRONTWHEELS/BIKEFRONTWHEEL"):
    bikefrontwheels[x.get('name')] = int(x.get('signature'))
bikerearwheels = {}
for x in root.findall("./BIKEREARWHEELS/BIKEREARWHEEL"):
    bikerearwheels[x.get('name')] = int(x.get('signature'))

def main(argv):
    global args

    parser = argparse.ArgumentParser(description='Populate Bot names with professional riders')
    parser.add_argument('-n', '--nation', help='Riders from specified nation only', default=False)
    parser.add_argument('-f', '--female', help='Female riders only', default=False, action='store_true')
    parser.add_argument('-m', '--male', help='Male riders only', default=False, action='store_true')
    parser.add_argument('-a', '--alltime', help='Use all time ranking', default=False, action='store_true')
    parser.add_argument('-p', '--pages', help='Number of pages to process', default=1)
    parser.add_argument('-j', '--jersey', help='Get team jerseys', default=False, action='store_true')
    parser.add_argument('-e', '--equipment', help='Get team bike and wheels', default=False, action='store_true')
    args = parser.parse_args()
    url_additions = ""
    url_list = []
    if args.alltime:
        url_additions += "&s=all-time"
    if args.nation:
        url_additions += "&nation="+args.nation
    if args.female:
        url_list = [ { "url": base_url + url_additions + "&p=we", "is_male": False } ]
    elif args.male:
        url_list = [ { "url": base_url + url_additions + "&p=me", "is_male": True } ]
    else:
        url_list = [ { "url": base_url + url_additions + "&p=me", "is_male": True }, { "url": base_url + url_additions + "&p=we", "is_male": False } ]
    if args.pages:
        new_url_list = url_list.copy()
        for x in range(1,int(args.pages)):
            offset = str(x*100)
            for url in url_list:
                new_url_list += [ { "url": url['url'] + "&offset=" + offset, "is_male": url['is_male'] }]
        url_list = new_url_list.copy()

    total_data = {}
    total_data['riders'] = []
    for item in url_list:
        total_data['riders'] = total_data['riders'] + get_pros(item['url'], item['is_male'], args.jersey, args.equipment)
    total_data['body_types'] = [16, 48, 80, 272, 304, 336, 528, 560, 592]
    total_data['hair_types'] = [25953412, 175379869, 398510584, 659452569, 838618949, 924073005, 1022111028, 1262230565, 1305767757, 1569595897, 1626212425, 1985754517, 2234835005, 2507058825, 3092564365, 3200039653, 3296520581, 3351295312, 3536770137, 4021222889, 4179410997, 4294226781]
    total_data['facial_hair_types'] = [248681634, 398510584, 867351826, 1947387842, 2173853954, 3169994930, 4131541011, 4216468066]

    with open('bot.txt', 'w') as outfile:
        json.dump(total_data, outfile, indent=2)

if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
    except SystemExit as se:
        print("ERROR:", se)
