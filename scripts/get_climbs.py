import os
import xml.etree.ElementTree as ET
import json
import subprocess

data = []

subprocess.run(['wad_unpack.exe', 'C:\\Program Files (x86)\\Zwift\\assets\\Worlds\\roads.wad'])
climbs = 'Worlds\\portal'
for file in os.listdir(climbs):
    if file.startswith('road_'):
        tree = ET.parse(os.path.join(climbs, file))
        metadata = tree.find('.//metadata')
        climb = {
            'name': metadata.find('m_PortalRoadUserFacingName').text,
            'road': metadata.find('m_PortalRoadHash').text
        }
        data.append(climb)

with open('../data/climbs.txt', 'w') as f:
    json.dump(sorted(data, key=lambda row: row['name']), f, indent=2)
