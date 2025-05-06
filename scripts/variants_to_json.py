import json
import sys
sys.path.insert(0, '../protobuf')
import variants_pb2
from google.protobuf.json_format import MessageToDict

with open("variant", "rb") as f:
    variants = variants_pb2.FeatureResponse()
    variants.ParseFromString(f.read())

keep = ['zwift_launcher_', 'game_1_26_event_survey']

with open("../data/variants.txt") as f:
    vs = [d for d in json.load(f)['variants'] if any(d['name'].startswith(s) for s in keep)]

for v in MessageToDict(variants)['variants']:
    if 'values' in v and 'fields' in v['values']:
        v['values']['fields'] = dict(sorted(v['values']['fields'].items()))
    vs.append(v)

with open("../data/variants.txt", "w") as f:
    json.dump({'variants': sorted(vs, key=lambda x: x['name'])}, f, indent=2)
