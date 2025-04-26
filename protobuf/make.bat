del *_pb2.py *_pb2.pyc
protoc --python_out=. activity.proto
protoc --python_out=. segment-result.proto
protoc --python_out=. profile.proto
protoc --python_out=. per-session-info.proto
protoc --python_out=. login.proto
protoc --python_out=. world.proto
protoc --python_out=. goal.proto
protoc --python_out=. zfiles.proto
protoc --python_out=. udp-node-msgs.proto
protoc --python_out=. tcp-node-msgs.proto
protoc --python_out=. hash-seeds.proto
protoc --python_out=. events.proto
protoc --python_out=. variants.proto
protoc --python_out=. playback.proto
protoc --python_out=. route-result.proto
protoc --python_out=. user_storage.proto
protoc --python_out=. fitness.proto
protoc --python_out=. race-result.proto

pause