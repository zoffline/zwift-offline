import xml.etree.ElementTree as ET
import json
from urllib3 import PoolManager

frame_exceptions = [270803031, 1409258486, 1444415023, 2029842509, 3079625256, 3814159195, 4150853780, 4243692575, 3988344633, 3017804836, 1952131384, 990301571]
frontwheel_exceptions = [69023253, 1344753875, 1361038541, 1547965258, 2004537892, 2365488570, 2907165694, 3787145210, 3849702821, 4221174482, 998391700, 4249063997, 3207647806, 1572602779, 1114387765, 3557711998, 3752892537, 214744904]
rearwheel_exceptions = [345690674, 413430806, 1547965258, 1796445915, 1965395406, 2602078812, 2740373137, 4088741326, 4111310185, 4151822963, 961116451, 4097663513, 1040669859, 21937401, 201030698, 1810163955, 247713340, 2752513115]

with open('../data/game_dictionary.txt') as f:
    gd = json.load(f, object_hook=lambda d: {int(k) if k.lstrip('-').isdigit() else k: v for k, v in d.items()})

base_url = 'http://cdn.zwift.com/gameassets/'
filename = 'GameDictionary.xml'
open(filename, 'wb').write(PoolManager().request('GET', base_url + filename).data)
tree = ET.parse(filename)
root = tree.getroot()
gd['headgears'] = [int(x.get('signature')) for x in root.findall("./HEADGEARS/HEADGEAR")]
gd['glasses'] = [int(x.get('signature')) for x in root.findall("./GLASSES/GLASS")]
gd['bikeshoes'] = [int(x.get('signature')) for x in root.findall("./BIKESHOES/BIKESHOE")]
gd['socks'] = [int(x.get('signature')) for x in root.findall("./SOCKS/SOCK")]
gd['jerseys'] = [int(x.get('signature')) for x in root.findall("./JERSEYS/JERSEY")]
frontwheels = {}
for x in root.findall("./BIKEFRONTWHEELS/BIKEFRONTWHEEL"):
    signature = int(x.get('signature'))
    if not signature in frontwheel_exceptions:
        frontwheels[x.get('imageName')] = signature
rearwheels = {}
for x in root.findall("./BIKEREARWHEELS/BIKEREARWHEEL"):
    signature = int(x.get('signature'))
    if not signature in rearwheel_exceptions:
        rearwheels[x.get('imageName')] = signature
gd['wheels'] = [(rearwheels[x], frontwheels[x]) for x in rearwheels if x in frontwheels]
gd['runshirts'] = [int(x.get('signature')) for x in root.findall("./RUNSHIRTS/RUNSHIRT")]
gd['runshorts'] = [int(x.get('signature')) for x in root.findall("./RUNSHORTS/RUNSHORT")]
gd['runshoes'] = [int(x.get('signature')) for x in root.findall("./RUNSHOES/RUNSHOE")]
bikeframes = {}
for x in root.findall("./BIKEFRAMES/BIKEFRAME"):
    signature = int(x.get('signature'))
    if not signature in frame_exceptions:
        bikeframes[signature] = x.get('name')
gd['bikeframes'] = bikeframes
achievements = {}
for x in root.findall("./ACHIEVEMENTS/ACHIEVEMENT"):
    if x.get('imageName') == "RouteComplete":
        signature = int(x.get('signature'))
        route = int(x.get('routeSignature'))
        achievements[signature] = route
gd['achievements'] = achievements

with open('../data/game_dictionary.txt', 'w') as f:
    json.dump(gd, f, indent=2)
