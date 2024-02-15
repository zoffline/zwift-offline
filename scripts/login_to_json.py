import json
import sys
sys.path.insert(0, '../protobuf')
import login_pb2
from google.protobuf.json_format import MessageToDict

with open("login", "rb") as f:
    login = login_pb2.LoginResponse()
    login.ParseFromString(f.read())

with open('../data/economy_config.txt', 'w') as f:
    json.dump(MessageToDict(login, preserving_proto_field_name=True)['economy_config'], f)
