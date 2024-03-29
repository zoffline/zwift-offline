# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: goal.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


import profile_pb2 as profile__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\ngoal.proto\x1a\rprofile.proto\"\xc5\x02\n\x04Goal\x12\n\n\x02id\x18\x01 \x01(\x04\x12\x11\n\tplayer_id\x18\x02 \x01(\x04\x12\x15\n\x05sport\x18\x03 \x01(\x0e\x32\x06.Sport\x12\x0c\n\x04name\x18\x04 \x01(\t\x12\x17\n\x04type\x18\x05 \x01(\x0e\x32\t.GoalType\x12 \n\x0bperiodicity\x18\x06 \x01(\x0e\x32\x0b.GoalPeriod\x12\x17\n\x0ftarget_distance\x18\x07 \x01(\x02\x12\x17\n\x0ftarget_duration\x18\x08 \x01(\x02\x12\x17\n\x0f\x61\x63tual_distance\x18\t \x01(\x02\x12\x17\n\x0f\x61\x63tual_duration\x18\n \x01(\x02\x12\x12\n\ncreated_on\x18\x0b \x01(\x04\x12\x17\n\x0fperiod_end_date\x18\x0c \x01(\x04\x12\x1b\n\x06status\x18\r \x01(\x0e\x32\x0b.GoalStatus\x12\x10\n\x08timezone\x18\x0e \x01(\t\"\x1d\n\x05Goals\x12\x14\n\x05goals\x18\x01 \x03(\x0b\x32\x05.Goal*\"\n\x08GoalType\x12\x0c\n\x08\x44ISTANCE\x10\x00\x12\x08\n\x04TIME\x10\x01*%\n\nGoalPeriod\x12\n\n\x06WEEKLY\x10\x00\x12\x0b\n\x07MONTHLY\x10\x01*%\n\nGoalStatus\x12\n\n\x06\x41\x43TIVE\x10\x00\x12\x0b\n\x07RETIRED\x10\x01')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'goal_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _GOALTYPE._serialized_start=388
  _GOALTYPE._serialized_end=422
  _GOALPERIOD._serialized_start=424
  _GOALPERIOD._serialized_end=461
  _GOALSTATUS._serialized_start=463
  _GOALSTATUS._serialized_end=500
  _GOAL._serialized_start=30
  _GOAL._serialized_end=355
  _GOALS._serialized_start=357
  _GOALS._serialized_end=386
# @@protoc_insertion_point(module_scope)
