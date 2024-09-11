import os
import xml.etree.ElementTree as ET
import json
import subprocess

data = []

try:
    if not os.path.isdir('global'):
        os.makedirs('global')
except IOError as e:
    print("failed to create dir 'global': %s" % str(e))
os.chdir('global')
subprocess.run(['wad_unpack.exe', 'C:\\Program Files (x86)\\Zwift\\assets\\global.wad'])
tree = ET.parse('Entitlements.xml')
root = tree.getroot()
for entitlement in root.iter('Entitlement'):
    data.append({'id': int(entitlement.get('id')), 'name': entitlement.get('name')})

with open('../../data/entitlements.txt', 'w') as f:
    json.dump(data, f, indent=2)
