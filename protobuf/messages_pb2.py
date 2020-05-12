# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: messages.proto

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='messages.proto',
  package='',
  syntax='proto2',
  serialized_options=None,
  serialized_pb=b'\n\x0emessages.proto\"\x8d\x01\n\x0eServerToClient\x12\n\n\x02\x66\x31\x18\x01 \x02(\x05\x12\x11\n\tplayer_id\x18\x02 \x02(\x05\x12\x12\n\nworld_time\x18\x03 \x02(\x03\x12\r\n\x05seqno\x18\x04 \x02(\x05\x12\n\n\x02\x66\x35\x18\x05 \x02(\x05\x12\x0b\n\x03\x66\x31\x31\x18\x0b \x02(\x03\x12\x10\n\x08num_msgs\x18\x12 \x02(\x05\x12\x0e\n\x06msgnum\x18\x13 \x02(\x05'
)




_SERVERTOCLIENT = _descriptor.Descriptor(
  name='ServerToClient',
  full_name='ServerToClient',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='f1', full_name='ServerToClient.f1', index=0,
      number=1, type=5, cpp_type=1, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='player_id', full_name='ServerToClient.player_id', index=1,
      number=2, type=5, cpp_type=1, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='world_time', full_name='ServerToClient.world_time', index=2,
      number=3, type=3, cpp_type=2, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='seqno', full_name='ServerToClient.seqno', index=3,
      number=4, type=5, cpp_type=1, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='f5', full_name='ServerToClient.f5', index=4,
      number=5, type=5, cpp_type=1, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='f11', full_name='ServerToClient.f11', index=5,
      number=11, type=3, cpp_type=2, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='num_msgs', full_name='ServerToClient.num_msgs', index=6,
      number=18, type=5, cpp_type=1, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='msgnum', full_name='ServerToClient.msgnum', index=7,
      number=19, type=5, cpp_type=1, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=19,
  serialized_end=160,
)

DESCRIPTOR.message_types_by_name['ServerToClient'] = _SERVERTOCLIENT
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

ServerToClient = _reflection.GeneratedProtocolMessageType('ServerToClient', (_message.Message,), {
  'DESCRIPTOR' : _SERVERTOCLIENT,
  '__module__' : 'messages_pb2'
  # @@protoc_insertion_point(class_scope:ServerToClient)
  })
_sym_db.RegisterMessage(ServerToClient)


# @@protoc_insertion_point(module_scope)
