#!/usr/bin/env python

# Quick and dirty script for generating a random MapSchedule.xml

import datetime
import random
import sys

from xml.dom import minidom

MAPS = ['FRANCE', 'INNSBRUCK', 'LONDON', 'MAKURIISLANDS', 'RICHMOND', 'SCOTLAND']

dom = minidom.parseString('<MapSchedule><appointments></appointments><VERSION>1</VERSION></MapSchedule>')
appts = dom.getElementsByTagName('appointments')[0]

now = datetime.datetime.utcnow().replace(day=1)
prev_map = None
for i in range(0, 500):
    map_choice = random.choice(MAPS)
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


CLIMBS = [str(x) for x in range(10000, 10021)]

dom = minidom.parseString('<PortalRoads><PortalRoadSchedule><appointments></appointments><VERSION>1</VERSION></PortalRoadSchedule></PortalRoads>')
appts = dom.getElementsByTagName('appointments')[0]

now = datetime.datetime.utcnow()
prev_climb = None
for i in range(0, 100):
    climb_choice = random.choice(CLIMBS)
    while climb_choice == prev_climb:
        climb_choice = random.choice(CLIMBS)
    prev_climb = climb_choice
    appt = dom.createElement('appointment')
    appt.setAttribute('road', climb_choice)
    appt.setAttribute('portal', '0')
    appt.setAttribute('start', now.strftime("%Y-%m-%dT00:01-04"))

    appts.appendChild(appt)
    now += datetime.timedelta(days=2)

with open('PortalRoadSchedule_v1.xml', 'w') as f:
    f.write(dom.toprettyxml())
