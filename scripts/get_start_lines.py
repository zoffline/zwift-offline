# Get start lines from files Zwift\assets\Worlds\world*\data_1.wad\Worlds\world*\routes\routes*.xml

import os
import xml.etree.ElementTree as ET
import re
import csv

data = []

for directory in os.listdir('.'):
    if not os.path.isdir(directory):
        continue

    for file in os.listdir(directory):
        if not file.endswith('.xml'):
            continue

        with open(os.path.join(directory, file)) as f:
            xml = f.read()

        tree = ET.fromstring(re.sub(r"(<\?xml[^>]+\?>)", r"\1<root>", xml) + "</root>")
        route = tree.find('route')
        name = route.get('name').strip()
        nameHash = int.from_bytes(int(route.get('nameHash')).to_bytes(4, 'little'), 'little', signed=True)
        checkpoints = list(tree.find('highrescheckpoint').iter('entry'))
        startRoad = checkpoints[0].get('road')
        startTime = int(float(checkpoints[0].get('time')) * 1000000 + 5000)
        data.append([nameHash, startRoad, startTime, directory, name])

with open('start_lines.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['nameHash', 'startRoad', 'startTime', 'world', 'route'])
    writer.writerows(sorted(data, key=lambda row: (row[3], row[4])))
