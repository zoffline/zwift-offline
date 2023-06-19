#! /usr/bin/env python

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

def get_pros(url, male):
    data = []
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
                best_match = process.extractOne(td.a.contents[0], GD['jersey_name'], scorer=fuzz.token_sort_ratio)
                print ("%s %s : %s - %s" % (tmp['first_name'],tmp['last_name'],td.a.contents[0], best_match))
                for index, item in enumerate(GD['jersey_name']):
                    if item.startswith(best_match[0]):
                        tmp['jersey'] = (GD['jerseys'][index])
                        data.append(tmp)

    return data

if getattr(sys, 'frozen', False):
    # If we're running as a pyinstaller bundle
    SCRIPT_DIR = sys._MEIPASS
    STORAGE_DIR = "%s/storage" % os.path.dirname(sys.executable)
    LOGS_DIR = "%s/logs" % os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
    STORAGE_DIR = "%s/storage" % SCRIPT_DIR
    LOGS_DIR = "%s/logs" % SCRIPT_DIR

def load_game_dictionary():
    tree = ET.parse('%s/../cdn/gameassets/GameDictionary.xml' % SCRIPT_DIR)
    root = tree.getroot()
    gd = {}
    gd['headgears'] = [int(x.get('signature')) for x in root.findall("./HEADGEARS/HEADGEAR")]
    gd['glasses'] = [int(x.get('signature')) for x in root.findall("./GLASSES/GLASS")]
    gd['bikeshoes'] = [int(x.get('signature')) for x in root.findall("./BIKESHOES/BIKESHOE")]
    gd['socks'] = [int(x.get('signature')) for x in root.findall("./SOCKS/SOCK")]
    gd['jerseys'] = [int(x.get('signature')) for x in root.findall("./JERSEYS/JERSEY")]
    gd['jersey_name'] = [(x.get('name')) for x in root.findall("./JERSEYS/JERSEY")]
    gd['bikefrontwheels'] = [int(x.get('signature')) for x in root.findall("./BIKEFRONTWHEELS/BIKEFRONTWHEEL")]
    gd['bikerearwheels'] = [int(x.get('signature')) for x in root.findall("./BIKEREARWHEELS/BIKEREARWHEEL")]
    gd['runshirts'] = [int(x.get('signature')) for x in root.findall("./RUNSHIRTS/RUNSHIRT")]
    gd['runshorts'] = [int(x.get('signature')) for x in root.findall("./RUNSHORTS/RUNSHORT")]
    gd['runshoes'] = [int(x.get('signature')) for x in root.findall("./RUNSHOES/RUNSHOE")]
    bikeframes = {}
    for x in root.findall("./BIKEFRAMES/BIKEFRAME"):
        bikeframes[int(x.get('signature'))] = x.get('name')
    gd['bikeframes'] = bikeframes
    routes = {}
    for x in root.findall("./ACHIEVEMENTS/ACHIEVEMENT"):
        if x.get('imageName') == "RouteComplete": routes[x.get('name')] = int(x.get('signature'))
    achievements = {}
    for x in root.findall("./ROUTES/ROUTE"):
        name = x.get('name').upper()
        if name in routes: achievements[routes[name]] = int(x.get('signature'))
    gd['achievements'] = achievements
    return gd

GD = load_game_dictionary()

def main(argv):
    global args

    parser = argparse.ArgumentParser(description='Populate Bot names with professional riders')
    parser.add_argument('-n', '--nation', help='Riders from specified nation only', default=False)
    parser.add_argument('-f', '--female', help='Female riders only', default=False, action='store_true')
    parser.add_argument('-m', '--male', help='Male riders only', default=False, action='store_true')
    parser.add_argument('-a', '--alltime', help='Use all time ranking', default=False, action='store_true')
    parser.add_argument('-p', '--pages', help='Number of pages to process', default=1)
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
        total_data['riders'] = total_data['riders'] + get_pros(item['url'], item['is_male'])
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
