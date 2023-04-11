#! /usr/bin/env python

from bs4 import BeautifulSoup
import urllib.request
import json
import country_converter as coco

male_url = "https://www.procyclingstats.com/rankings/me/individual"
female_url = "https://www.procyclingstats.com/rankings/we/individual"

cc = coco.CountryConverter()

def get_pros(url):
    data = []
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    site = urllib.request.urlopen(req).read()
    soup = BeautifulSoup(site)

    def has_class(tag):
        return tag.has_attr('class')

    for td in soup.find_all('td'):
        if td.span and td.contents[0]:
            if "flag" in repr(td.contents[0]):
                tmp = {}
                code = td.span.get_attribute_list("class")[1]
                tmp['country_code'] = cc.convert(names=code, to='ISOnumeric')
                if td.a:
                    tmp['first_name'] = (td.a.contents[1].strip())
                    tmp['last_name'] = (td.a.span.contents[0])
                    data.append(tmp)
    return data

total_data = {}
total_data['male_riders'] = get_pros(male_url)
total_data['female_riders'] = get_pros(female_url)

with open('pro_bots.json','w') as outfile:
    json.dump(total_data, outfile, indent=2)
