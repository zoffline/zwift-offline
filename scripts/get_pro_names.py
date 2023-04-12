#! /usr/bin/env python

from bs4 import BeautifulSoup
import urllib.request
import json
import country_converter as coco

base_url = "https://www.procyclingstats.com/rankings.php?filter=Filter"
url_list = [ { "url": base_url + "&p=me" , "is_male": True }, { "url": base_url + "&p=we", "is_male": False } ]

cc = coco.CountryConverter()

def get_pros(url, male):
    data = []
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    site = urllib.request.urlopen(req).read()
    soup = BeautifulSoup(site)

    for td in soup.find_all('td'):
        if td.span and td.contents[0]:
            if "flag" in repr(td.contents[0]):
                tmp = {}
                code = td.span.get_attribute_list("class")[1]
                tmp['country_code'] = cc.convert(names=code, to='ISOnumeric')
                tmp['is_male'] = male
                if td.a:
                    tmp['first_name'] = (td.a.contents[1].strip())
                    tmp['last_name'] = (td.a.span.contents[0])
                    data.append(tmp)
    return data

total_data = {}
total_data['riders'] = []
for item in url_list:
    total_data['riders'] = total_data['riders'] + get_pros(item['url'], item['is_male'])
total_data['body_types'] = [16, 48, 80, 272, 304, 336, 528, 560, 592]
total_data['hair_types'] = [25953412, 175379869, 398510584, 659452569, 838618949, 924073005, 1022111028, 1262230565, 1305767757, 1569595897, 1626212425, 1985754517, 2234835005, 2507058825, 3092564365, 3200039653, 3296520581, 3351295312, 3536770137, 4021222889, 4179410997, 4294226781]
total_data['facial_hair_types'] = [248681634, 398510584, 867351826, 1947387842, 2173853954, 3169994930, 4131541011, 4216468066]

with open('bot.txt', 'w') as outfile:
    json.dump(total_data, outfile)
