import json
import urllib.request
import os.path
import sys

def downloadImage(url):
    filepath = url.replace('https://cdn.zwift.com', '../cdn')
    if (not os.path.isfile(filepath)):
        #print('Loading: %s' % url)
        try:
            urllib.request.urlretrieve(url, filepath)
        except:
            print('Failed: %s' % url)
    #else:
        #print('Skipped: %s' % filepath)
    return

with open(os.path.join(sys.path[0], '../game_info.txt'), encoding='utf-8-sig') as f:
    data = json.load(f)

print(data['gameInfoHash'])

for m in data['maps']:
    for r in m['routes']:
        downloadImage(r['imageUrl'])

for a in data['achievements']:
    downloadImage(a['imageUrl'])

for u in data['unlockableCategories']:
    downloadImage(u['imageUrl'])

for c in data['challenges']:
    downloadImage(c['imageUrl'])

for j in data['jerseys']:
    downloadImage(j['imageUrl'])

for n in data['notableMomentTypes']:
    downloadImage(n['listImageUrl'])
    downloadImage(n['mapImageUrl'])

for t in data['trainingPlans']:
    downloadImage(t['imageUrl'])
