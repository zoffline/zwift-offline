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

teams = {
        'UAE Team Emirates': {'abv': 'UAD', 'jersey_name': 'UAE', 'jersey_signature': 1751349769, 'bike_name': 'Colnago Colnago V3RS', 'bike_signature': 3628259811, 'front_wheel_name': 'Enve SES 3.4', 'front_wheel_signature': 2223270801, 'rear_wheel_name': 'Enve SES 3.4', 'rear_wheel_signature': 3835575171},
        'Soudal - Quick Step': {'abv': 'SOQ', 'jersey_name': 'Deceuninck-Quick-Step', 'jersey_signature': 2906189156, 'bike_name': 'Specialized Tarmac SL7', 'bike_signature': 935373427, 'front_wheel_name': 'Roval Rapide CLX', 'front_wheel_signature': 2181416413, 'rear_wheel_name': 'Roval Rapide CLX', 'rear_wheel_signature': 3548735686, 'helmet_name': 'S-Works Evade', 'helmet_signature': 3109903878},
        'Jumbo-Visma': {'abv': 'TJV', 'jersey_name': 'Jumbo Visma TdF Edition 2023', 'jersey_signature': 2246416303, 'womens_jersey': 2922761319, 'bike_name': 'Cervelo R5', 'bike_signature': 106535518, 'front_wheel_name': 'Reserve Reserve 25 GR', 'front_wheel_signature': 635220876, 'rear_wheel_name': 'Reserve Reserve 25 GR', 'rear_wheel_signature': 1842698274, 'helmet_name': 'LOC_ACCESSORY_LAZERBULLET', 'helmet_signature': 1292376041},
        'Team Visma | Lease a Bike': {'abv': 'TJV', 'jersey_name': 'Jumbo Visma TdF Edition 2023', 'jersey_signature': 2246416303, 'womens_jersey': 2922761319, 'bike_name': 'Cervelo R5', 'bike_signature': 106535518, 'front_wheel_name': 'Reserve Reserve 25 GR', 'front_wheel_signature': 635220876, 'rear_wheel_name': 'Reserve Reserve 25 GR', 'rear_wheel_signature': 1842698274, 'helmet_name': 'LOC_ACCESSORY_LAZERBULLET', 'helmet_signature': 1292376041},
        'Alpecin-Deceuninck': {'abv': 'ADC', 'jersey_name': 'Alpecin Deceuninck 2023', 'jersey_signature': 1905664161, 'bike_name': 'Canyon Aeroad 2015', 'bike_signature': 1520594784, 'front_wheel_name': 'Shimano C50', 'front_wheel_signature': 1742598126, 'rear_wheel_name': 'Shimano C50', 'rear_wheel_signature': 3725678091, 'helmet_name': 'ABUS GameChanger', 'helmet_signature': 1387973863},
        'Alpecin - Deceuninck': {'abv': 'ADC', 'jersey_name': 'Alpecin Deceuninck 2023', 'jersey_signature': 1905664161, 'bike_name': 'Canyon Aeroad 2015', 'bike_signature': 1520594784, 'front_wheel_name': 'Shimano C50', 'front_wheel_signature': 1742598126, 'rear_wheel_name': 'Shimano C50', 'rear_wheel_signature': 3725678091, 'helmet_name': 'ABUS GameChanger', 'helmet_signature': 1387973863},
        'Lidl - Trek': {'abv': 'TRK', 'jersey_name': 'Trek-Segafredo Men', 'jersey_signature': 2140478849, 'womens_jersey_signature': 1154847422, 'bike_name': 'Trek Madone', 'bike_signature': 4129467727, 'front_wheel_name': 'Bontrager Aeolus5', 'front_wheel_signature': 702195190, 'rear_wheel_name': 'Bontrager Aeolus5', 'rear_wheel_signature': 3594144634},
        'Movistar Team': {'abv': 'MOV', 'jersey_name': 'Movistar 2023', 'jersey_signature': 436926002, 'bike_name': 'Canyon Aeroad 2015', 'bike_signature': 1520594784, 'front_wheel_name': 'Zipp 404', 'front_wheel_signature': 613983807, 'rear_wheel_name': 'Zipp 404', 'rear_wheel_signature': 4183014640, 'helmet_name': 'ABUS GameChanger Movistar Team', 'helmet_signature': 4241132751},
        'Lotto Dstny': {'abv': 'LTD', 'jersey_name': 'Lotto Dstny 2023', 'jersey_signature': 712380058, 'bike_name': 'Ridley Noah Fast 2019', 'bike_signature': 4288910569, 'front_wheel_name': 'DTSwiss ARC 1100 DICUT 62', 'front_wheel_signature': 346409677, 'rear_wheel_name': 'DTSwiss ARC 1100 DICUT 62', 'rear_wheel_signature': 2049111692},
        'EF Education - EasyPost': {'abv': 'EFE', 'jersey_name': 'EF Education First', 'jersey_signature': 2349035663, 'bike_name': 'Cannondale System Six', 'bike_signature': 2005280203, 'front_wheel_name': 'HED HED Vanquish RC6 Pro', 'front_wheel_signature': 1791179228, 'rear_wheel_name': 'HED HED Vanquish RC6 Pro', 'rear_wheel_signature': 2913819265, 'helmet_name': 'POC Ventral Air EF', 'helmet_signature': 3707571564},
        'INEOS Grenadiers': {'abv': 'IGD', 'jersey_name': 'INEOS Grenadiers 2022 Pro', 'jersey_signature': 542207259, 'bike_name': 'Pinarello Dogma F', 'bike_signature': 4208139356, 'front_wheel_name': 'Shimano C50', 'front_wheel_signature': 1742598126, 'rear_wheel_name': 'Shimano C50', 'rear_wheel_signature': 3725678091, 'helmet_name': 'Protone INEOS Grenadier', 'helmet_signature': 3438211262},
        'Groupama - FDJ': {'abv': 'GFC', 'jersey_name': 'Groupama FDJ 2023', 'jersey_signature': 2814449542, 'bike_name': 'Specialized Tarmac SL7', 'bike_signature': 935373427, 'front_wheel_name': 'Shimano C50', 'front_wheel_signature': 1742598126, 'rear_wheel_name': 'Shimano C50', 'rear_wheel_signature': 3725678091, 'helmet_name': 'Giro Eclipse FDJ', 'helmet_signature': 3912703277},
        'Bahrain - Victorious': {'abv': 'TBV', 'jersey_name': 'Bahrain McLaren', 'jersey_signature': 2155858980, 'bike_name': 'Merida Scultura', 'bike_signature': 3033010663},
        'Team dsm-firmenich PostNL': {'abv': 'DSM', 'jersey_name': 'Team ODZ', 'jersey_signature': 2695025247, 'bike_name': 'Scott Foil', 'bike_signature': 1315158373, 'front_wheel_name': 'Shimano C50', 'front_wheel_signature': 1742598126, 'rear_wheel_name': 'Shimano C50', 'rear_wheel_signature': 3725678091},
        'Team Jayco AlUla': {'abv': 'JAY', 'jersey_name': 'Team Jayco Alula 2023', 'jersey_signature': 91507230, 'womens_jersey': 1912060275, 'bike_name': 'Giant Propel Advanced SL Disc', 'bike_signature': 103914490, 'front_wheel_name': 'Cadex CADEX 42', 'front_wheel_signature': 1497226614, 'rear_wheel_name': 'Cadex CADEX 42', 'rear_wheel_signature': 1347687916},
        'Uno-X Mobility': {'abv': 'UXT', 'jersey_name': 'UnoXPro2022', 'jersey_signature': 1756517729},
    'Cofidis': {'abv': 'COF', 'jersey_name': 'Cofidis 2018', 'jersey_signature': 927604154, 'bike_name': 'Cervelo R5', 'bike_signature': 106535518, 'front_wheel_name': 'Shimano C50', 'front_wheel_signature': 1742598126, 'rear_wheel_name': 'Shimano C50', 'rear_wheel_signature': 3725678091},
    'Intermarché - Wanty': {'abv': 'ICW', 'jersey_name': 'Intermarché Wanty Circus 2023', 'jersey_signature': 2642337455, 'bike_name': 'Cube Cube Litening', 'bike_signature': 1767548815,  'front_wheel_name': 'Shimano C50', 'front_wheel_signature': 1742598126, 'rear_wheel_name': 'Shimano C50', 'rear_wheel_signature': 3725678091},
    'BORA - hansgrohe': {'abv': 'BOH', 'jersey_name': 'Bora Hansgrohe', 'jersey_signature': 3798832688, 'bike_name': 'Specialized Tarmac SL7', 'bike_signature': 935373427, 'front_wheel_name': 'Roval Rapide CLX', 'front_wheel_signature': 2181416413, 'rear_wheel_name': 'Roval Rapide CLX', 'rear_wheel_signature': 3548735686, 'helmet_name': 'S-Works Evade', 'helmet_signature': 3109903878},
    'Team Arkéa Samsic': {'abv': 'ARK', 'jersey_name': 'Arkea-Samsic', 'jersey_signature': 598687666, 'front_wheel_name': 'Shimano C50', 'front_wheel_signature': 1742598126, 'rear_wheel_name': 'Shimano C50', 'rear_wheel_signature': 3725678091},
    'Arkéa - B&B Hotels': {'abv': 'ARK', 'jersey_name': 'Arkea-Samsic', 'jersey_signature': 598687666, 'front_wheel_name': 'Shimano C50', 'front_wheel_signature': 1742598126, 'rear_wheel_name': 'Shimano C50', 'rear_wheel_signature': 3725678091},
    'Decathlon AG2R La Mondiale Team': {'abv': 'ACT', 'jersey_name': 'AG2R La Mondiale', 'jersey_signature': 1587982785, 'bike_name': 'BMC BmcTeamMachine2022', 'bike_signature': 3868468027, 'front_wheel_name': 'Campagnolo Bora Ultra 35', 'front_wheel_signature': 1053884173, 'rear_wheel_name': 'Campagnolo Bora Ultra 35', 'rear_wheel_signature': 1614586487},
    'Astana Qazaqstan Team': {'abv': 'AST', 'jersey_name': 'ASTANA PRO TEAM', 'jersey_signature': 1969335676, 'bike_name': 'Giant GiantRevolt2022', 'bike_signature': 2360271970, 'front_wheel_name': 'Shimano C50', 'front_wheel_signature': 1742598126, 'rear_wheel_name': 'Shimano C50', 'rear_wheel_signature': 3725678091, 'helmet_name': 'Limar Air Speed TWENTY24', 'helmet_signature': 9439966},
    'Israel - Premier Tech': {'abv': 'IPT', 'jersey_name': 'Israel Premier-Tech', 'jersey_signature': 552170906, 'bike_name': 'Factor One', 'bike_signature': 3469325930},
    'TotalEnergies': {'abv': 'TEN', 'jersey_name': 'Total Direct Energie', 'jersey_signature': 2092402045, 'bike_name': 'Specialized Tarmac SL7', 'bike_signature': 935373427, 'front_wheel_name': 'Shimano C50', 'front_wheel_signature': 1742598126, 'rear_wheel_name': 'Shimano C50', 'rear_wheel_signature': 3725678091},
    'Team SD Worx': {'abv': 'SDW', 'jersey_name': 'Team SD Worx', 'jersey_signature': 1494272741, 'bike_name': 'Specialized Tarmac SL7', 'bike_signature': 935373427, 'helmet_name': 'S-Works Evade', 'helmet_signature': 3109903878},
    'UAE Team ADQ': {'abv': 'UAD', 'jersey_name': 'UAE', 'jersey_signature': 1751349769, 'bike_name': 'Colnago Colnago V3RS', 'bike_signature': 3628259811, 'front_wheel_name': 'Enve SES 3.4', 'front_wheel_signature': 2223270801, 'rear_wheel_name': 'Enve SES 3.4', 'rear_wheel_signature': 3835575171},
    'UAE Development Team': {'abv': 'UDT', 'jersey_name': 'UAE', 'jersey_signature': 1751349769},
    'FDJ - SUEZ': {'abv': 'FST', 'jersey_name': 'FDJ Suez 2023', 'jersey_signature': 3360845221, 'front_wheel_name': 'Shimano C50', 'front_wheel_signature': 1742598126, 'rear_wheel_name': 'Shimano C50', 'rear_wheel_signature': 3725678091},
    'Canyon//SRAM Racing': {'abv': 'CSR', 'jersey_name': 'CANYON//SRAM Racing', 'jersey_signature': 3970245639, 'bike_name': 'Canyon Aeroad 2015', 'bike_signature': 1520594784, 'front_wheel_name': 'Zipp 404', 'front_wheel_signature': 613983807, 'rear_wheel_name': 'Zipp 404', 'rear_wheel_signature': 4183014640, 'helmet_name': 'Giro Eclipse Canyon SRAM', 'helmet_signature': 3346861673},
    'AG Insurance - Soudal Quick-Step': {'abv': 'AGS', 'jersey_name': 'Lotto-Soudal', 'jersey_signature': 3103938066, 'bike_name': 'Specialized Tarmac SL7', 'bike_signature': 935373427, 'helmet_name': 'S-Works Evade', 'helmet_signature': 3109903878},
    'Human Powered Health': {'abv': 'HPW', 'jersey_name': 'Human Powered Health Fan', 'jersey_signature': 854534852, 'bike_name': 'Felt AR', 'bike_signature': 3002729519},
    'Team Jumbo-Visma': {'abv': 'JVW', 'jersey_name': 'Jumbo Visma TdFFaZ Edition 2023', 'jersey_signature': 2922761319, 'bike_name': 'Cervelo R5', 'bike_signature': 106535518, 'front_wheel_name': 'Reserve Reserve 25 GR', 'front_wheel_signature': 635220876, 'rear_wheel_name': 'Reserve Reserve 25 GR', 'rear_wheel_signature': 1842698274, 'helmet_name': 'LOC_ACCESSORY_LAZERBULLET', 'helmet_signature': 1292376041},
    'Liv Racing TeqFind': {'abv': 'LIV', 'jersey_name': 'Liv Racing 2019', 'jersey_signature': 3932519699, 'bike_name': 'Liv Langma Advanced SL', 'bike_signature': 3495124341},
    'Israel Premier Tech Roland': {'abv': 'CGS', 'jersey_name': 'Israel Premier-Tech', 'jersey_signature': 552170906, 'bike_name': 'Factor One', 'bike_signature': 3469325930, 'helmet_name': 'Limar Air Speed TWENTY24', 'helmet_signature': 9439966},
    'EF Education-TIBCO-SVB': {'abv': 'TIB', 'jersey_name': 'Team EF Education-TIBCO-SVB', 'jersey_signature': 2795352821, 'bike_name': 'Cannondale System Six', 'bike_signature': 2005280203, 'helmet_name': 'POC Ventral Air EF', 'helmet_signature': 3707571564},
    'Fenix-Deceuninck': {'abv': 'FED', 'jersey_name': 'Fenix Deceuninck 2023', 'jersey_signature': 3290712389, 'bike_name': 'Canyon Aeroad 2015', 'bike_signature': 1520594784},
    'Fenix-Deceuninck Continental': {'abv': 'FDD', 'jersey_name': 'Fenix Deceuninck 2023', 'jersey_signature': 3290712389},
    'CERATIZIT-WNT Pro Cycling': {'abv': 'WNT', 'jersey_name': 'Ceratizit-WNT', 'jersey_signature': 97975537},
    'St Michel - Mavic - Auber93 WE': {'abv': 'AUB', 'jersey_name': 'South Africa Elite', 'jersey_signature': 3305515323, 'bike_name': 'Cannondale System Six', 'bike_signature': 2005280203, 'front_wheel_name': 'Mavic Comete Pro Carbon SL UST', 'front_wheel_signature': 897949453, 'rear_wheel_name': 'Mavic Comete Pro Carbon SL UST', 'rear_wheel_signature': 4001596344},
    'Lifeplus Wahoo': {'abv': 'DRP', 'jersey_name': 'Wahoo', 'jersey_signature': 3553917933},
    'Cofidis Women Team': {'abv': 'COF', 'jersey_name': 'Cofidis', 'jersey_signature': 4191972189},
    'Arkéa Pro Cycling Team': {'abv': 'ARK', 'jersey_name': 'Arkea', 'jersey_signature': 1128201030},
    'MAT Atom Deweloper Wrocław': {'abv': 'MAW', 'jersey_name': 'Atom Racing Team', 'jersey_signature': 851470392},
    'Top Girls Fassa Bortolo': {'abv': 'TOP', 'jersey_name': 'Clash Of Clubs Blue', 'jersey_signature': 520081294},
    'EOLO-Kometa': {'abv': 'EOK', 'jersey_name': 'Eolo Kometa', 'jersey_signature': 2422819298, 'front_wheel_name': 'Enve SES 3.4', 'front_wheel_signature': 2223270801, 'rear_wheel_name': 'Enve SES 3.4', 'rear_wheel_signature': 3835575171},
    'Green Project-Bardiani CSF-Faizanè': {'abv': 'GBF', 'jersey_name': 'Bardiani 2019', 'jersey_signature': 3503002798, 'front_wheel_name': 'Campagnolo Bora Ultra 35', 'front_wheel_signature': 1053884173, 'rear_wheel_name': 'Campagnolo Bora Ultra 35', 'rear_wheel_signature': 1614586487},
    'L39ION of Los Angeles': {'abv': 'LLA', 'jersey_name':'L39ION of LA 2022', 'jersey_signature': 2330819669},
    'Lotto Dstny Ladies': {'abv': 'LDL', 'jersey_name': 'Lotto Soudal Ladies', 'jersey_signature': 1423767803},
    'Parkhotel Valkenburg': {'abv': 'PHV', 'jersey_name': 'Parkhotel Valkenburg', 'jersey_signature': 4102459937}
}

def get_pros(url, male, get_jersey, get_equipment, team_abbrv):
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
                if 'first_name' in tmp:
                    if team_abbrv:
                        if td.a.contents[0] in teams and 'abv' in teams[td.a.contents[0]]:
                            tmp['last_name'] += " ("+teams[td.a.contents[0]]['abv']+")"
                    if get_jersey:
                        if not male and td.a.contents[0] in teams and 'womens_jersey_signature' in teams[td.a.contents[0]]:
                            tmp['ride_jersey'] = teams[td.a.contents[0]]['womens_jersey_signature']
                        elif td.a.contents[0] in teams:
                            tmp['ride_jersey'] = teams[td.a.contents[0]]['jersey_signature']
                        else:
                            best_match = process.extractOne(td.a.contents[0], jerseys.keys(), scorer=fuzz.token_set_ratio)
                            print ("%s %s : %s - %s" % (tmp['first_name'],tmp['last_name'],td.a.contents[0], best_match))
                            tmp['ride_jersey'] = jerseys[best_match[0]]
                    if get_equipment:
                        if td.a.contents[0] in teams:
                            team = teams[td.a.contents[0]]
                            if 'bike_signature' in team:
                                tmp['bike_frame'] = team['bike_signature']
                            if 'front_wheel_signature' in team:
                                tmp['bike_wheel_front'] = team['front_wheel_signature']
                            if 'rear_wheel_signature' in team:
                                tmp['bike_wheel_rear'] = team['rear_wheel_signature']
                            if 'helmet_signature' in team:
                                tmp['ride_helmet_type'] = team['helmet_signature']

                    data.append(tmp)

    return data

tree = ET.fromstring(urllib.request.urlopen('http://cdn.zwift.com/gameassets/GameDictionary.xml').read())
jerseys = {}
for x in tree.findall("./JERSEYS/JERSEY"):
    jerseys[x.get('name')] = int(x.get('signature'))

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
    parser.add_argument('-t', '--teamabbrv', help='Add team abbreviation to last name', default=False, action='store_true')
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
        total_data['riders'] = total_data['riders'] + get_pros(item['url'], item['is_male'], args.jersey, args.equipment, args.teamabbrv)

    with open('bot.txt', 'w') as outfile:
        json.dump(total_data, outfile, indent=2)

if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
    except SystemExit as se:
        print("ERROR:", se)

