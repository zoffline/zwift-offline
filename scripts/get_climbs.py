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
        name = metadata.find('m_PortalRoadUserFacingName').text
        length = round(float(metadata.find('m_PortalRoadCourseLength').text) / 100000, 1)
        if length.is_integer():
            length = int(length)
        ascent = int(float(metadata.find('m_PortalRoadCourseAscentF').text) / 100)
        climb = {
            'name': '%s (%s km / %s m)' % (name, length, ascent),
            'road': metadata.find('m_PortalRoadHash').text
        }
        data.append(climb)

with open('../data/climbs.txt', 'w') as f:
    json.dump(sorted(data, key=lambda row: row['name']), f, indent=2)
