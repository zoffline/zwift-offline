#! /usr/bin/env python

# Use this script to populate bot.txt with names from https://www.procyclingstats.com
# Refer to http://cdn.zwift.com/gameassets/GameDictionary.xml
# pip install beautifulsoup4 country-converter fuzzywuzzy
# scripts/get_pro_names.py -h


from bs4 import BeautifulSoup
import urllib.request
import json
import country_converter as coco
import argparse
import os
import sys
import xml.etree.ElementTree as ET
from fuzzywuzzy import process
from fuzzywuzzy import fuzz

base_url = "https://www.procyclingstats.com/rankings.php?filter=Filter"
cc = coco.CountryConverter()

teams = {
  "UAE Team Emirates - XRG": {
    "abv": "UAD",
    "jersey_name": "UAE",
    "jersey_signature": 1751349769,
    "bike_name": "Colnago V3RS",
    "bike_signature": 3628259811,
    "front_wheel_name": "Enve SES 3.4",
    "front_wheel_signature": 2223270801,
    "rear_wheel_name": "Enve SES 3.4",
    "rear_wheel_signature": 3835575171
  },
  "Soudal Quick-Step": {
    "abv": "SOQ",
    "jersey_name": "Deceuninck-Quick-Step",
    "jersey_signature": 2906189156,
    "bike_name": "Specialized Tarmac SL7",
    "bike_signature": 935373427,
    "front_wheel_name": "Roval Rapide CLX",
    "front_wheel_signature": 2181416413,
    "rear_wheel_name": "Roval Rapide CLX",
    "rear_wheel_signature": 3548735686,
    "helmet_name": "S-Works Evade",
    "helmet_signature": 3109903878
  },
  "Team Visma | Lease a Bike": {
    "abv": "TVL",
    "jersey_name": "Jumbo Visma TdF Edition 2023",
    "jersey_signature": 2246416303,
    "womens_jersey": 2922761319,
    "bike_name": "Cervelo CerveloS52021",
    "bike_signature": 1972610461,
    "front_wheel_name": "Reserve Reserve 25 GR",
    "front_wheel_signature": 635220876,
    "rear_wheel_name": "Reserve Reserve 25 GR",
    "rear_wheel_signature": 1842698274,
    "helmet_name": "LOC_ACCESSORY_LAZERBULLET",
    "helmet_signature": 1292376041
  },
  "Alpecin - Deceuninck": {
    "abv": "ADC",
    "jersey_name": "Alpecin Deceuninck 2023",
    "jersey_signature": 1905664161,
    "bike_name": "Canyon Aeroad2024",
    "bike_signature": 2629993294,
    "bike_frame_colour_name": "Canyon Aeroad2024-Aeroad Alpecin-Deceuninck",
    "bike_frame_colour_signature": 1978783051,
    "front_wheel_name": "Shimano C50",
    "front_wheel_signature": 1742598126,
    "rear_wheel_name": "Shimano C50",
    "rear_wheel_signature": 3725678091,
    "helmet_name": "ABUS GameChanger",
    "helmet_signature": 1387973863
  },
  "Lidl - Trek": {
    "abv": "TRK",
    "jersey_name": "Trek-Segafredo Men",
    "jersey_signature": 2140478849,
    "womens_jersey_signature": 1154847422,
    "bike_name": "Trek Madone",
    "bike_signature": 4129467727,
    "front_wheel_name": "Bontrager Aeolus5",
    "front_wheel_signature": 702195190,
    "rear_wheel_name": "Bontrager Aeolus5",
    "rear_wheel_signature": 3594144634
  },
  "Movistar Team": {
    "abv": "MOV",
    "jersey_name": "Movistar 2023",
    "jersey_signature": 436926002,
    "bike_name": "Canyon Aeroad Team Edition",
    "bike_signature": 390579581,
    "bike_frame_colour_name": "Canyon Aeroad Team Edition-Movistar 2023",
    "bike_frame_colour_signature": 2280475316,
    "front_wheel_name": "Zipp 404",
    "front_wheel_signature": 613983807,
    "rear_wheel_name": "Zipp 404",
    "rear_wheel_signature": 4183014640,
    "helmet_name": "ABUS GameChanger Movistar Team",
    "helmet_signature": 4241132751
  },
  "Lotto": {
    "abv": "LOT",
    "jersey_name": "Lotto Dstny 2023",
    "jersey_signature": 712380058,
    "bike_name": "Ridley Noah Fast 2019",
    "bike_signature": 4288910569,
    "bike_frame_colour_name": "Ridley Noah Fast 2019-Lotto Soudal",
    "bike_frame_colour_signature": 1205664811,
    "front_wheel_name": "DTSwiss ARC 1100 DICUT 62",
    "front_wheel_signature": 346409677,
    "rear_wheel_name": "DTSwiss ARC 1100 DICUT 62",
    "rear_wheel_signature": 2049111692
  },
  "EF Education - EasyPost": {
    "abv": "EFE",
    "jersey_name": "EF Education First",
    "jersey_signature": 2349035663,
    "bike_name": "Cannondale System Six",
    "bike_signature": 2005280203,
    "bike_frame_colour_name": "Cannondale Super Six Evo-Education First",
    "bike_frame_colour_signature": 507139888,
    "front_wheel_name": "HED HED Vanquish RC6 Pro",
    "front_wheel_signature": 1791179228,
    "rear_wheel_name": "HED HED Vanquish RC6 Pro",
    "rear_wheel_signature": 2913819265,
    "helmet_name": "POC Ventral Air EF",
    "helmet_signature": 3707571564
  },
  "INEOS Grenadiers": {
    "abv": "IGD",
    "jersey_name": "INEOS Grenadiers 2022 Pro",
    "jersey_signature": 542207259,
    "bike_name": "Pinarello Dogma F",
    "bike_signature": 4208139356,
    "bike_frame_colour_name": "Pinarello Dogma F-Ineos",
    "bike_frame_colour_signature": 870887764,
    "front_wheel_name": "Shimano C50",
    "front_wheel_signature": 1742598126,
    "rear_wheel_name": "Shimano C50",
    "rear_wheel_signature": 3725678091,
    "helmet_name": "Protone INEOS Grenadier",
    "helmet_signature": 3438211262
  },
  "Groupama - FDJ": {
    "abv": "GFC",
    "jersey_name": "Groupama FDJ 2023",
    "jersey_signature": 2814449542,
    "bike_name": "Specialized Tarmac SL7",
    "bike_signature": 935373427,
    "front_wheel_name": "Shimano C50",
    "front_wheel_signature": 1742598126,
    "rear_wheel_name": "Shimano C50",
    "rear_wheel_signature": 3725678091,
    "helmet_name": "Giro Eclipse FDJ",
    "helmet_signature": 3912703277
  },
  "Bahrain - Victorious": {
    "abv": "TBV",
    "jersey_name": "Bahrain McLaren",
    "jersey_signature": 2155858980,
    "bike_frame_colour_name": "Merida Scultura-Merida Scultura Bahrain McLaren",
    "bike_frame_colour_signature": 2063693653,
    "bike_name": "Merida Scultura",
    "bike_signature": 3033010663
  },
  "Team Picnic PostNL": {
    "abv": "TPP",
    "jersey_name": "Team ODZ",
    "jersey_signature": 2695025247,
    "bike_name": "Scott Foil",
    "bike_signature": 1315158373,
    "front_wheel_name": "Shimano C50",
    "front_wheel_signature": 1742598126,
    "rear_wheel_name": "Shimano C50",
    "rear_wheel_signature": 3725678091
  },
  "Team Jayco AlUla": {
    "abv": "JAY",
    "jersey_name": "Team Jayco Alula 2023",
    "jersey_signature": 91507230,
    "womens_jersey": 1912060275,
    "bike_name": "Giant Propel Advanced SL Disc",
    "bike_signature": 103914490,
    "front_wheel_name": "Cadex CADEX 42",
    "front_wheel_signature": 1497226614,
    "rear_wheel_name": "Cadex CADEX 42",
    "rear_wheel_signature": 1347687916
  },
  "Uno-X Mobility": {
    "abv": "UXT",
    "bike_name": "Ridley Noah Fast 2019",
    "bike_signature": 4288910569,
    "jersey_name": "UnoXPro2022",
    "jersey_signature": 1756517729
  },
  "Cofidis": {
    "abv": "COF",
    "bike_name": "Zwift Carbon",
    "bike_signature": 2106340733,
    "bike_frame_colour_name": "Zwift Carbon-Cofidis De Rosa",
    "bike_frame_colour_signature": 2273815071,
    "jersey_name": "Cofidis 2018",
    "jersey_signature": 927604154,
    "front_wheel_name": "Shimano C50",
    "front_wheel_signature": 1742598126,
    "rear_wheel_name": "Shimano C50",
    "rear_wheel_signature": 3725678091
  },
  "Intermarché - Wanty": {
    "abv": "ICW",
    "jersey_name": "Intermarché Wanty Circus 2023",
    "jersey_signature": 2642337455,
    "bike_name": "Cube Cube Litening",
    "bike_signature": 1767548815,
    "front_wheel_name": "Shimano C50",
    "front_wheel_signature": 1742598126,
    "rear_wheel_name": "Shimano C50",
    "rear_wheel_signature": 3725678091
  },
  "Red Bull - BORA - hansgrohe": {
    "abv": "BOH",
    "jersey_name": "Bora Hansgrohe",
    "jersey_signature": 3798832688,
    "bike_name": "Specialized Tarmac SL7",
    "bike_signature": 935373427,
    "front_wheel_name": "Roval Rapide CLX",
    "front_wheel_signature": 2181416413,
    "rear_wheel_name": "Roval Rapide CLX",
    "rear_wheel_signature": 3548735686,
    "helmet_name": "S-Works Evade",
    "helmet_signature": 3109903878
  },
  "Arkéa - B&B Hotels": {
    "abv": "ARK",
    "jersey_name": "Arkea-Samsic",
    "jersey_signature": 598687666,
    "front_wheel_name": "Shimano C50",
    "front_wheel_signature": 1742598126,
    "rear_wheel_name": "Shimano C50",
    "rear_wheel_signature": 3725678091
  },
  "Decathlon AG2R La Mondiale Team": {
    "abv": "ACT",
    "bike_name": "Zwift Carbon",
    "bike_signature": 2106340733,
    "bike_frame_colour_name": "Zwift Carbon-AG2R",
    "bike_frame_colour_signature": 455876950,
    "jersey_name": "AG2R La Mondiale",
    "jersey_signature": 1587982785,
    "front_wheel_name": "Campagnolo Bora Ultra 35",
    "front_wheel_signature": 1053884173,
    "rear_wheel_name": "Campagnolo Bora Ultra 35",
    "rear_wheel_signature": 1614586487
  },
  "XDS Astana Team": {
    "abv": "XAT",
    "jersey_name": "ASTANA PRO TEAM",
    "jersey_signature": 1969335676,
    "bike_name": "Zwift Carbon",
    "bike_signature": 2106340733,
    "bike_frame_colour_name": "Zwift Carbon-Astana",
    "bike_frame_colour_signature": 1208416225,
    "front_wheel_name": "Shimano C50",
    "front_wheel_signature": 1742598126,
    "rear_wheel_name": "Shimano C50",
    "rear_wheel_signature": 3725678091,
    "helmet_name": "Limar Air Speed TWENTY24",
    "helmet_signature": 9439966
  },
  "Israel - Premier Tech": {
    "abv": "IPT",
    "jersey_name": "Israel Premier-Tech",
    "jersey_signature": 552170906,
    "bike_name": "Factor One",
    "bike_signature": 3469325930
  },
  "Team TotalEnergies": {
    "abv": "TEN",
    "bike_name": "Zwift Carbon",
    "bike_signature": 2106340733,
    "bike_frame_colour_name": "Zwift Carbon-Total Direct Energie",
    "bike_frame_colour_signature": 1215759893,
    "jersey_name": "Total Direct Energie",
    "jersey_signature": 2092402045,
    "front_wheel_name": "Shimano C50",
    "front_wheel_signature": 1742598126,
    "rear_wheel_name": "Shimano C50",
    "rear_wheel_signature": 3725678091
  },
  "Q36.5 Pro Cycling Team": {
    "abv": "Q36",
    "bike_name": "Scott Addict RC",
    "bike_signature": 4100131524,
    "bike_frame_colour_name": "Scott ScottAddict2021-2022",
    "bike_frame_colour_signature": 2522283696,
    "jersey_name": "Q36.5 Pro Team",
    "jersey_signature": 1185917078,
    "front_wheel_name": "Zipp 454",
    "front_wheel_signature": 667389725,
    "rear_wheel_name": "Zipp 454",
    "rear_wheel_signature": 461030369,
  },
  "Team SD Worx - Protime": {
    "abv": "SDW",
    "jersey_name": "Team SD Worx",
    "jersey_signature": 1494272741,
    "bike_name": "Specialized Tarmac SL7",
    "bike_signature": 935373427,
    "helmet_name": "S-Works Evade",
    "helmet_signature": 3109903878
  },
  "UAE Team ADQ": {
    "abv": "UAD",
    "jersey_name": "UAE",
    "jersey_signature": 1751349769,
    "bike_name": "Colnago Colnago V3RS",
    "bike_signature": 3628259811,
    "front_wheel_name": "Enve SES 3.4",
    "front_wheel_signature": 2223270801,
    "rear_wheel_name": "Enve SES 3.4",
    "rear_wheel_signature": 3835575171
  },
  "UAE Development Team": {
    "abv": "UDT",
    "bike_name": "Colnago Colnago V3RS",
    "bike_signature": 3628259811,
    "jersey_name": "UAE",
    "jersey_signature": 1751349769
  },
  "FDJ - SUEZ": {
    "abv": "FST",
    "bike_name": "Zwift Carbon",
    "bike_signature": 2106340733,
    "bike_frame_colour_name": "Zwift Carbon-Lapierre FDJ",
    "bike_frame_colour_signature": 1248651886,
    "jersey_name": "FDJ Suez 2023",
    "jersey_signature": 3360845221,
    "front_wheel_name": "Shimano C50",
    "front_wheel_signature": 1742598126,
    "rear_wheel_name": "Shimano C50",
    "rear_wheel_signature": 3725678091
  },
  "CANYON//SRAM zondacrypto": {
    "abv": "CSZ",
    "jersey_name": "CANYON//SRAM Racing",
    "jersey_signature": 3970245639,
    "bike_name": "Canyon AeroadSRAM2024",
    "bike_signature": 1122831861,
    "front_wheel_name": "Zipp 404",
    "front_wheel_signature": 613983807,
    "rear_wheel_name": "Zipp 404",
    "rear_wheel_signature": 4183014640,
    "helmet_name": "Giro Eclipse Canyon SRAM",
    "helmet_signature": 3346861673
  },
  "CANYON//SRAM zondacrypto Generation": {
    "abv": "CSG",
    "jersey_name": "Canyon//SRAM Generation",
    "jersey_signature": 189587516,
    "bike_name": "Canyon AeroadSRAM2024",
    "bike_signature": 1122831861,
    "front_wheel_name": "Zipp 404",
    "front_wheel_signature": 613983807,
    "rear_wheel_name": "Zipp 404",
    "rear_wheel_signature": 4183014640,
    "helmet_name": "Giro Eclipse Canyon SRAM",
    "helmet_signature": 3346861673
  },
  "AG Insurance - Soudal Team": {
    "abv": "AGS",
    "jersey_name": "Lotto-Soudal",
    "jersey_signature": 3103938066,
    "bike_name": "Specialized Tarmac SL7",
    "bike_signature": 935373427,
    "helmet_name": "S-Works Evade",
    "helmet_signature": 3109903878
  },
  "Human Powered Health": {
    "abv": "HPW",
    "jersey_name": "Human Powered Health Fan",
    "jersey_signature": 854534852,
    "bike_name": "Felt AR",
    "bike_signature": 3002729519
  },
  "Liv AlUla Jayco": {
    "abv": "LAJ",
    "jersey_name": "Liv AlUla Jayco 2024",
    "jersey_signature": 2095486697,
    "bike_name": "Liv Langma Advanced SL",
    "bike_signature": 3495124341
  },
  "Roland Le Dévoluy": {
    "abv": "CGS",
    "jersey_name": "Team Roland Cogeas Edelweiss",
    "jersey_signature": 3398931495,
    "bike_name": "Factor One",
    "bike_signature": 3469325930,
    "bike_frame_colour_name": "Factor One-One Israel",
    "bike_frame_colour_signature": 3959514452,
    "helmet_name": "Limar Air Speed TWENTY24",
    "helmet_signature": 9439966
  },
  "Fenix-Deceuninck": {
    "abv": "FDC",
    "jersey_name": "Fenix Deceuninck 2023",
    "jersey_signature": 3290712389,
    "bike_name": "Canyon Aeroad2024",
    "bike_signature": 2629993294
  },
  "Fenix-Deceuninck Development Team": {
    "abv": "FDD",
    "bike_name": "Canyon Aeroad2024",
    "bike_signature": 2629993294,
    "jersey_name": "Fenix Deceuninck 2023",
    "jersey_signature": 3290712389
  },
  "CERATIZIT Pro Cycling Team": {
    "abv": "CTC",
    "bike_name": "Zwift Carbon",
    "bike_signature": 2106340733,
    "bike_frame_colour_name": "Zwift Carbon-Orbea Orca",
    "bike_frame_colour_signature": 806402273,
    "jersey_name": "Ceratizit-WNT",
    "jersey_signature": 97975537
  },
  "St Michel - Preference Home - Auber93 WE": {
    "abv": "AUB",
    "jersey_name": "South Africa Elite",
    "jersey_signature": 3305515323,
    "bike_name": "Cannondale System Six",
    "bike_signature": 2005280203,
    "front_wheel_name": "Mavic Comete Pro Carbon SL UST",
    "front_wheel_signature": 897949453,
    "rear_wheel_name": "Mavic Comete Pro Carbon SL UST",
    "rear_wheel_signature": 4001596344
  },
  "Cofidis Women Team": {
    "abv": "CWT",
    "bike_name": "Zwift Carbon",
    "bike_signature": 2106340733,
    "bike_frame_colour_name": "Zwift Carbon-Cofidis De Rosa",
    "bike_frame_colour_signature": 2273815071,
    "jersey_name": "Cofidis",
    "jersey_signature": 4191972189
  },
  "Arkéa - B&B Hotels Women": {
    "abv": "ARK",
    "jersey_name": "Arkea",
    "jersey_signature": 1128201030
  },
  "MAT Atom Deweloper Wrocław": {
    "abv": "MAT",
    "bike_name": "Ridley Noah Fast 2019",
    "bike_signature": 4288910569,
    "jersey_name": "Atom Racing Team",
    "jersey_signature": 851470392
  },
  "Top Girls Fassa Bortolo": {
    "abv": "TOP",
    "bike_name": "Pinarello Dogma F",
    "bike_signature": 4208139356,
    "jersey_name": "Clash Of Clubs Blue",
    "jersey_signature": 520081294
  },
  "Team Polti VisitMalta": {
    "abv": "PTV",
    "jersey_name": "Eolo Kometa",
    "jersey_signature": 2422819298,
    "front_wheel_name": "Enve SES 3.4",
    "front_wheel_signature": 2223270801,
    "rear_wheel_name": "Enve SES 3.4",
    "rear_wheel_signature": 3835575171
  },
  "VF Group - Bardiani CSF - Faizanè": {
    "abv": "VBF",
    "jersey_name": "Bardiani 2019",
    "jersey_signature": 3503002798,
    "front_wheel_name": "Campagnolo Bora Ultra 35",
    "front_wheel_signature": 1053884173,
    "rear_wheel_name": "Campagnolo Bora Ultra 35",
    "rear_wheel_signature": 1614586487
  },
  "L39ION of Los Angeles": {
    "abv": "LLA",
    "bike_name": "Factor One",
    "bike_signature": 3469325930,
    "jersey_name": "L39ION of LA 2022",
    "jersey_signature": 2330819669
  },
  "Lotto Ladies": {
    "abv": "LOL",
    "jersey_name": "Lotto Dstny 2023",
    "jersey_signature": 712380058
  },
  "Parkhotel Valkenburg": {
    "abv": "PHV",
    "bike_name": "Giant Propel Advanced SL Disc",
    "bike_signature": 103914490,
    "jersey_name": "Parkhotel Valkenburg",
    "jersey_signature": 4102459937
  },
  "Tudor Pro Cycling Team": {
    "abv": "TUD",
    "jersey_name": "Assos Superleger",
    "jersey_signature": 142676981,
    "bike_name": "BMC TeamMachine",
    "bike_signature": 3868468027,
    "bike_frame_colour_name": "BMC Timemachine01-BMC Timemachine01 Black",
    "bike_frame_colour_signature": 2850354759,
    "front_wheel_name": "DTSwiss ARC 1100 DICUT 85/Disc",
    "front_wheel_signature": 1213183664,
    "rear_wheel_name": "DTSwiss ARC 1100 DICUT 85/Disc",
    "rear_wheel_signature": 590647095,
  },
  "EF Education-Oatly": {
    "abv": "EFO",
    "jersey_name": "EF Education First",
    "jersey_signature": 2349035663,
    "bike_name": "Cannondale System Six",
    "bike_signature": 2005280203
  },
  "Roland": {
    "abv": "CGS",
    "bike_name": "Pinarello Dogma F",
    "bike_signature": 4208139356
  },
  "AG Insurance - Soudal Team": {
    "abv": "AGS",
    "jersey_name": "Lotto-Soudal",
    "jersey_signature": 3103938066,
    "bike_name": "Specialized Tarmac SL7",
    "bike_signature": 935373427
  },
  "VolkerWessels Women\"s Pro Cycling Team": {
    "abv": "VWT",
    "bike_name": "Specialized Tarmac SL7",
    "bike_signature": 935373427
  }
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
                    fn = []
                    ln = []
                    for n in td.a.contents[0].split():
                        if n.isupper():
                            ln.append(n.title())
                        else:
                            fn.append(n)
                    tmp['first_name'] = ' '.join(fn)
                    tmp['last_name'] = ' '.join(ln)
        if td.a and td.contents[0]:
            if "cu600" in repr(td) and td.a.contents:
                if 'first_name' in tmp:
                    if team_abbrv:
                        if td.a.contents[0] in teams and 'abv' in teams[td.a.contents[0]]:
                            tmp['last_name'] += " ("+teams[td.a.contents[0]]['abv']+")"
                    if get_jersey:
                        if not male and td.a.contents[0] in teams and 'womens_jersey_signature' in teams[td.a.contents[0]]:
                            tmp['ride_jersey'] = teams[td.a.contents[0]]['womens_jersey_signature']
                        elif td.a.contents[0] in teams and 'jersey_signature' in teams[td.a.contents[0]]:
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
                            if 'bike_frame_colour_signature' in team:
                                tmp['bike_frame_colour'] = team['bike_frame_colour_signature'] << 32
                            if 'front_wheel_signature' in team:
                                tmp['bike_wheel_front'] = team['front_wheel_signature']
                            if 'rear_wheel_signature' in team:
                                tmp['bike_wheel_rear'] = team['rear_wheel_signature']
                            if 'helmet_signature' in team:
                                tmp['ride_helmet_type'] = team['helmet_signature']

                    data.append(tmp)

    return data

gd_file = 'GameDictionary.xml'
if not os.path.isfile(gd_file):
    open(gd_file, 'wb').write(urllib.request.urlopen('http://cdn.zwift.com/gameassets/%s' % gd_file).read())
tree = ET.parse(gd_file)
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

