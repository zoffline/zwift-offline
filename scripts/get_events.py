import os
import xml.etree.ElementTree as ET
import re
import json
import subprocess

worlds = 'C:\\Program Files (x86)\\Zwift\\assets\\Worlds'

world_to_course = {
    '1': 6,
    '2': 2,
    '3': 7,
    '4': 8,
    '5': 9,
    '6': 10,
    '7': 11,
    '8': 12,
    '9': 13,
    '10': 14,
    '11': 15,
    '12': 16,
    '13': 17
}

data = []
event_id = 1000

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
                event = {
                    'id': event_id,
                    'name': route.get('name').strip(),
                    'route': int(route.get('nameHash')),
                    'course': world_to_course[world],
                    'sport': 1 if route.get('sportType') == '2' else 0
                }
                data.append(event)
                event_id += 1000

with open('../events.txt', 'w') as f:
    json.dump(sorted(data, key=lambda row: row['name']), f, indent=2)
