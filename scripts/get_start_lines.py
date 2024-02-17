import os
import xml.etree.ElementTree as ET
import re
import json
import subprocess

worlds = 'C:\\Program Files (x86)\\Zwift\\assets\\Worlds'

world_names = {
    '1': 'Watopia',
    '2': 'Richmond',
    '3': 'London',
    '4': 'New York',
    '5': 'Innsbruck',
    '6': 'Bologna',
    '7': 'Yorkshire',
    '8': 'Crit City',
    '9': 'Makuri Islands',
    '10': 'France',
    '11': 'Paris',
    '12': 'Gravel Mountain',
    '13': 'Scotland'
}

with open('../data/start_lines.txt') as f:
    data = json.load(f, object_hook=lambda d: {int(k) if k.lstrip('-').isdigit() else k: v for k, v in d.items()})

new_routes = []

for directory in os.listdir(worlds):
    world = directory[5:]
    if os.path.isdir(os.path.join(worlds, directory)) and world in world_names:
        subprocess.run(['wad_unpack.exe', os.path.join(worlds, directory, 'data_1.wad')])
        routes = os.path.join('Worlds', directory, 'routes')
        for file in os.listdir(routes):
            with open(os.path.join(routes, file)) as f:
                xml = f.read()
            tree = ET.fromstring(re.sub(r"(<\?xml[^>]+\?>)", r"\1<root>", xml) + "</root>")
            route = tree.find('route')
            nameHash = int.from_bytes(int(route.get('nameHash')).to_bytes(4, 'little'), 'little', signed=True)
            new_routes.append(nameHash)
            if not nameHash in data:
                checkpoints = list(tree.find('highrescheckpoint').iter('entry'))
                data[nameHash] = {
                    'name': '%s - %s' % (world_names[world], route.get('name').strip()),
                    'road': int(checkpoints[0].get('road')),
                    'time': int(float(checkpoints[0].get('time')) * 1000000 + 5000)
                }

for route in list(data.keys()):
    if not route in new_routes:
        del data[route]

with open('../data/start_lines.txt', 'w') as f:
    json.dump({k: v for k, v in sorted(data.items(), key=lambda d: d[1]['name'])}, f, indent=2)
