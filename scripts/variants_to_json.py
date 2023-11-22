import json
import protobuf.variants_pb2 as variants_pb2
from google.protobuf.json_format import MessageToDict

variants = variants_pb2.FeatureResponse()

with open("variant", "rb") as f:
    variants.ParseFromString(f.read())

vs = []

with open("variants.txt") as f:
    j = json.load(f)
    vs = j['variants']

for variant in variants.variants:
    d = MessageToDict(variant)
    v = {}
    v['name'] = d['name']
    if 'value' in d:
        v['value'] = d['value']
    d['values'] = dict(d['values'])
    for f in d['values']:
        d['values'][f] = dict(sorted(d['values'][f].items()))
    v['values'] = d['values']
    vs[:] = [d for d in vs if d.get('name') != v['name']]
    vs.append(v)

with open("variants.txt", "w") as f:
    json.dump({'variants': sorted(vs, key=lambda x: x['name'])}, f, indent=2)
