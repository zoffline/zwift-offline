# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: user_storage.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x12user_storage.proto\".\n\x0bUserStorage\x12\x1f\n\nattributes\x18\x02 \x01(\x0b\x32\x0b.Attributes\"2\n\nAttributes\x12$\n\rgame_settings\x18\x16 \x01(\x0b\x32\r.GameSettings\"\x9c\x01\n\x0cGameSettings\x12\n\n\x02\x66\x32\x18\x02 \x01(\x02\x12\x14\n\x0cleaderboards\x18\x03 \x01(\x05\x12\x19\n\x11power_meter_slot0\x18\x04 \x01(\x05\x12\x19\n\x11power_meter_slot1\x18\x05 \x01(\x05\x12\x19\n\x11power_meter_slot2\x18\x06 \x01(\x05\x12\x19\n\x11power_meter_slot3\x18\x07 \x01(\x05')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'user_storage_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _USERSTORAGE._serialized_start=22
  _USERSTORAGE._serialized_end=68
  _ATTRIBUTES._serialized_start=70
  _ATTRIBUTES._serialized_end=120
  _GAMESETTINGS._serialized_start=123
  _GAMESETTINGS._serialized_end=279
# @@protoc_insertion_point(module_scope)
