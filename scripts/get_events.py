import os
import xml.etree.ElementTree as ET
import re
import json
import subprocess

worlds = 'C:\\Program Files (x86)\\Zwift\\assets\\Worlds'

world_to_course = {
    '1': (6, 'Watopia'),
    '2': (2, 'Richmond'),
    '3': (7, 'London'),
    '4': (8, 'New York'),
    '5': (9, 'Innsbruck'),
    '6': (10, 'Bologna'),
    '7': (11, 'Yorkshire'),
    '8': (12, 'Crit City'),
    '9': (13, 'Makuri Islands'),
    '10': (14, 'France'),
    '11': (15, 'Paris'),
    '12': (16, 'Gravel Mountain'),
    '13': (17, 'Scotland')
}

data = []

for directory in os.listdir(worlds):
    world = directory[5:]
    if os.path.isdir(os.path.join(worlds, directory)) and world in world_to_course:
        subprocess.run(['wad_unpack.exe', os.path.join(worlds, directory, 'data_1.wad')])
        routes = os.path.join('Worlds', directory, 'routes')
        for file in os.listdir(routes):
            with open(os.path.join(routes, file)) as f:
                xml = f.read()
            tree = ET.fromstring(re.sub(r"(<\?xml[^>]+\?>)", r"\1<root>", xml) + "</root>")
            route = tree.find('route')
            if route.get('eventOnly') == '1':
                wname = world_to_course[world][1]
                name = route.get('name').strip()
                if not name.startswith(wname):
                    name = '%s - %s' % (wname, name)
                event = {
                    'name': name,
                    'route': int(route.get('nameHash')),
                    'distance': round(float(route.get('distanceInMeters')) + float(route.get('leadinDistanceInMeters')), 1),
                    'course': world_to_course[world][0],
                    'sport': 1 if route.get('sportType') == '2' else 0
                }
                data.append(event)

with open('../data/events.txt', 'w') as f:
    json.dump(sorted(data, key=lambda row: row['name']), f, indent=2)
