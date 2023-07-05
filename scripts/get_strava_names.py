#! /usr/bin/env python

# Use this script to update bot.txt with your accounts you follow on Strava
# pip install requests_toolbelt nameparser geograpy3 country3
# get_strava_names.py us

import os
import json
import re
import argparse
import binascii
from requests import Request, Session
import urllib.parse
from requests_toolbelt.multipart.encoder import MultipartEncoder
from bs4 import BeautifulSoup
import re
from nameparser import HumanName
import geograpy
import country_converter as coco
import sys
import getpass

cc = coco.CountryConverter()
parser = argparse.ArgumentParser()
parser = argparse.ArgumentParser(description='Populate Bot names with your strava following list')
parser.add_argument('-u', '--user', help='Zwift user name')
parser.add_argument('country', help="Default country")
args = parser.parse_args()
s = Session()

def find_follows(tag):
    return tag and re.compile("type=following").search(tag)

def find_next(tag):
    return tag and tag.has_attr("rel") and  tag.string == u"→"

def find_athelete(tag):
    return tag.name == 'li' and tag.has_attr("data-athlete-id")

def get_names(response, defcode):
    data = []
    follow_soup = BeautifulSoup(response.text)
    for div in follow_soup.find_all(find_athelete):
        tmp = {}
        name = HumanName(div.div['title'])
        tmp['first_name']=name.first
        tmp['last_name']=name.last
        resp = urllib.request.urlopen("https://api.genderize.io?name="+name.first.encode("ascii",errors="ignore").decode()).read()
        sex = json.loads(resp)
        tmp['is_male']=(sex['gender']=="male")
        country = geograpy.get_geoPlace_context(text=div.contents[5].text)
        code = defcode
        if len(country.countries) > 0:
            code = cc.convert(names=country.countries[0], to='ISOnumeric')
        tmp['country_code'] = code
        data.append(tmp)

    for tag in follow_soup.find_all(find_next):
        next_link = "https://www.strava.com/" + tag['href']
        try:
            fresponse = s.get(next_link);
        except Exception as e:
            print('unknown error: ')
            return data

        data = data + get_names(fresponse, code)
        return data

    return data

def login(url, username, password, code):
    data = []

    # acquire cookie
    response = s.get(url);
    text = response.text

    # Get authenticity_token
    try:
        token = re.search(r'type="hidden" name="authenticity_token" value="(.+?)"', text).group(1)
    except AttributeError as e:
        print('Cannot find token')
        return data

    #print ('found token:' + token)

    # Login
    loginData = urllib.parse.urlencode({
        'utf8' : '&#x2713;',
        'authenticity_token' : token,
        'plan' : '',
        'email' : username, 
        'password' : password})
    binary_data = loginData.encode('utf-8')
    try:
        response = s.post("https://www.strava.com/session", data=loginData);
    except Exception as e:
        print('unknown error: ')
        return data
    else:
        m = re.search('Log Out', response.text)
        if m:
            print('Successfully logged in')
        else:
            print('Unsuccessfull login')
            sys.exit()

    soup = BeautifulSoup(response.text)
    for tag in soup.find_all(href=find_follows):
        following_link = "https://www.strava.com/" + tag['href']

        try:
            response = s.get(following_link);
        except Exception as e:
            print('unknown error: ')
            sys.exit()

        data = get_names(response, code)

        #should be only 1 follow page, so return here
        return data

def main() :
    if args.user:
        username = args.user
    else:
        username = input("Enter Strava login (e-mail): ")

    if not sys.stdin.isatty():  # This terminal cannot support input without displaying text
        print('*WARNING* The current shell (%s) cannot support hidden text entry.' % os.name)
        print('Your password entry WILL BE VISIBLE.')
        print('If you are running a bash shell under windows, try executing this program via winpty:')
        print('>winpty python %s' % argv[0])
        password = input("Enter password (will be shown):")
    else:
        password = getpass.getpass("Enter password: ")
    code = cc.convert(args.country, to='ISOnumeric')
    total_data = {}
    total_data['riders'] = login("https://www.strava.com/login", username, password, code)

    with open('bot.txt', 'w') as outfile:
        json.dump(total_data, outfile, indent=2)

if __name__ == "__main__":
    main()

