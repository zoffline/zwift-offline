#!/usr/bin/env python

# Quick and dirty script for generating a random MapSchedule.xml

import datetime
import random
import sys
import xml.etree.ElementTree as ET

from xml.dom import minidom

# Make london and new york more likely
MAPS = [ 'INNSBRUCK' ] + [ 'LONDON' ] * 2 + [ 'NEWYORK' ] * 2 + [ 'RICHMOND' ] + [ 'YORKSHIRE' ]


dom = minidom.parseString('<MapSchedule><appointments></appointments><VERSION>1</VERSION></MapSchedule>')
appts = dom.getElementsByTagName('appointments')[0]

now = datetime.datetime.now()
prev_map = None
for i in xrange(0, 500):
    map_choice = random.choice(MAPS)
    while map_choice == prev_map:
        map_choice = random.choice(MAPS)
    prev_map = map_choice
    appt = dom.createElement('appointment')
    appt.setAttribute('map', map_choice)
    appt.setAttribute('start', now.strftime("%Y-%m-%dT00:01-04"))

    appts.appendChild(appt)
    # Shorter duration for UCI course maps
    if map_choice in [ 'INNSBRUCK', 'RICHMOND', 'YORKSHIRE' ]:
        now += datetime.timedelta(days=random.randint(1,2))
    else:
        now += datetime.timedelta(days=random.randint(1,5))

sys.stdout.write(dom.toprettyxml())
