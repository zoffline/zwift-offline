import os
import xml.etree.ElementTree as ET
import re
import csv
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

data = []

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
            name = route.get('name').strip()
            nameHash = int.from_bytes(int(route.get('nameHash')).to_bytes(4, 'little'), 'little', signed=True)
            checkpoints = list(tree.find('highrescheckpoint').iter('entry'))
            startRoad = checkpoints[0].get('road')
            startTime = int(float(checkpoints[0].get('time')) * 1000000 + 5000)
            data.append([nameHash, startRoad, startTime, world_names[world], name])

with open('start_lines.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['nameHash', 'startRoad', 'startTime', 'world', 'route'])
    writer.writerows(sorted(data, key=lambda row: (row[3], row[4])))
