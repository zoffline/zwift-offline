import xml.etree.ElementTree as ET
import json
from urllib3 import PoolManager
from fuzzywuzzy import process, fuzz

frame_exceptions = [270803031, 1409258486, 1444415023, 2029842509, 3079625256, 3814159195, 4150853780, 4243692575, 3988344633, 3017804836]
frontwheel_exceptions = [69023253, 1344753875, 1361038541, 1547965258, 2004537892, 2365488570, 2907165694, 3787145210, 3849702821, 4221174482, 998391700, 4249063997, 3207647806, 1572602779, 1114387765, 3557711998]
rearwheel_exceptions = [345690674, 413430806, 1547965258, 1796445915, 1965395406, 2602078812, 2740373137, 4088741326, 4111310185, 4151822963, 961116451, 4097663513, 1040669859, 21937401, 201030698, 1810163955]
route_exceptions = {
    '2018 UCI WORLDS SHORT LAP': '2018 WORLDS SHORT LAP',
    '2015 UCI WORLDS COURSE': 'RICHMOND UCI WORLDS',
    'HILLY ROUTE': 'WATOPIA HILLY ROUTE',
    '2019 UCI WORLDS HARROGATE CIRCUIT': '2019 WORLDS HARROGATE CIRCUIT',
    'THE PRETZEL': 'THE LONDON PRETZEL',
    'MOUNTAIN ROUTE': 'WATOPIA MOUNTAIN ROUTE',
    'MOUNTAIN 8': 'WATOPIA MOUNTAIN 8',
    'FIGURE 8': 'WATOPIA FIGURE 8',
    'FIGURE 8 REVERSE': 'WATOPIA FIGURE 8 REVERSE',
    'FLAT ROUTE': 'WATOPIA FLAT ROUTE',
    'THE PRL HALF': 'LONDON PRL HALF',
    'THE PRL FULL': 'LONDON PRL FULL',
    'CASSE PATTES': 'CASSE-PATTES',
    'TIRE BOUCHON': 'TIRE-BOUCHON',
    'HANDFUL OF GRAVEL (CYCLING)': 'HANDFUL OF GRAVEL',
    'HANDFUL OF GRAVEL (RUNNING)': 'HANDFUL OF GRAVEL RUN',
    'WATOPIAS WAISTBAND': 'WATOPIA\'S WAISTBAND',
    'RICHMOND UCI REVERSE': 'RICHMOND 2015 WORLDS REVERSE',
    'CASTLE CRIT (RUNNING)': 'CASTLE CRIT RUN',
    'TRIPLE TWISTS': 'TRIPLE TWIST'
}

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
        frontwheels[x.get('name')] = signature
rearwheels = {}
for x in root.findall("./BIKEREARWHEELS/BIKEREARWHEEL"):
    signature = int(x.get('signature'))
    if not signature in rearwheel_exceptions:
        rearwheels[x.get('name')] = signature
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
routes = {}
for x in root.findall("./ROUTES/ROUTE"):
    routes[x.get('name').upper()] = int(x.get('signature'))
achievements = {}
for x in root.findall("./ACHIEVEMENTS/ACHIEVEMENT"):
    if x.get('imageName') == "RouteComplete":
        name = x.get('name')
        signature = int(x.get('signature'))
        if name in routes:
            achievements[signature] = routes[name]
        elif name in route_exceptions:
            achievements[signature] = routes[route_exceptions[name]]
        else:
            best_match = process.extractOne(name, routes.keys(), scorer=fuzz.token_set_ratio)
            print("'%s': '%s'," % (name, best_match[0]))
gd['achievements'] = achievements

with open('../data/game_dictionary.txt', 'w') as f:
    json.dump(gd, f, indent=2)
