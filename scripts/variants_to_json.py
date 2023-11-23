import json
import sys
sys.path.insert(0, '../protobuf')
import variants_pb2
from google.protobuf.json_format import MessageToDict

with open("variant", "rb") as f:
    variants = variants_pb2.FeatureResponse()
    variants.ParseFromString(f.read())

with open("../variants.txt") as f:
    vs = json.load(f)['variants']

for v in MessageToDict(variants)['variants']:
    if 'fields' in v['values']:
        v['values']['fields'] = dict(sorted(v['values']['fields'].items()))
    vs[:] = [d for d in vs if d.get('name') != v['name']]
    vs.append(v)

with open("../variants.txt", "w") as f:
    json.dump({'variants': sorted(vs, key=lambda x: x['name'])}, f, indent=2)
