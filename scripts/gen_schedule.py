#!/usr/bin/env python

# Quick and dirty script for generating a random MapSchedule.xml

import datetime
import random
import sys
import json

from xml.dom import minidom
from dateutil.relativedelta import relativedelta

MAPS = ['FRANCE', 'INNSBRUCK', 'LONDON', 'MAKURIISLANDS', 'RICHMOND', 'SCOTLAND']

dom = minidom.parseString('<MapSchedule><appointments></appointments><VERSION>1</VERSION></MapSchedule>')
appts = dom.getElementsByTagName('appointments')[0]

now = datetime.datetime.now(datetime.timezone.utc).replace(day=1)
maps_loop = []
prev_map = None
for _ in range(0, 200):
    if not maps_loop:
        maps_loop = list(MAPS)
        random.shuffle(maps_loop)
    map_choice = maps_loop.pop()
    while map_choice == prev_map:
        map_choice = random.choice(MAPS)
    prev_map = map_choice
    appt = dom.createElement('appointment')
    appt.setAttribute('map', map_choice)
    appt.setAttribute('start', now.strftime("%Y-%m-%dT00:01-04"))

    appts.appendChild(appt)
    now += datetime.timedelta(days=2)

with open('MapSchedule_v2.xml', 'w') as f:
    f.write(dom.toprettyxml())

with open('../data/climbs.txt') as f:
    data = json.load(f)
CLIMBS = [x['road'] for x in data]

dom = minidom.parseString('<PortalRoads><PortalRoadSchedule><appointments></appointments><VERSION>1</VERSION></PortalRoadSchedule></PortalRoads>')
appts = dom.getElementsByTagName('appointments')[0]

month = datetime.datetime.now(datetime.timezone.utc).replace(day=1)
climbs_loop = []
climbs_loop_month = []
prev_climb = None
prev_climb_month = None
for _ in range(0, 13):
    if not climbs_loop_month:
        climbs_loop_month = list(CLIMBS)
        random.shuffle(climbs_loop_month)
    climb_choice_month = climbs_loop_month.pop()
    while climb_choice_month == prev_climb_month:
        climb_choice_month = random.choice(CLIMBS)
    prev_climb_month = climb_choice_month
    appt = dom.createElement('appointment')
    appt.setAttribute('road', climb_choice_month)
    appt.setAttribute('world', '10')
    appt.setAttribute('portal_of_month', 'true')
    appt.setAttribute('portal', '0')
    appt.setAttribute('start', month.strftime("%Y-%m-%dT00:01-04"))

    appts.appendChild(appt)
    day = month
    month += relativedelta(months=+1)

    for _ in range(0, 10):
        if not climbs_loop:
            climbs_loop = list(CLIMBS)
            random.shuffle(climbs_loop)
        climb_choice = climbs_loop.pop()
        while climb_choice == prev_climb or climb_choice == climb_choice_month:
            climb_choice = random.choice(CLIMBS)
        prev_climb = climb_choice
        appt = dom.createElement('appointment')
        appt.setAttribute('road', climb_choice)
        appt.setAttribute('world', '1')
        appt.setAttribute('portal', '0')
        appt.setAttribute('start', day.strftime("%Y-%m-%dT00:01-04"))

        appts.appendChild(appt)
        day += datetime.timedelta(days=3)

with open('PortalRoadSchedule_v1.xml', 'w') as f:
    f.write(dom.toprettyxml())
