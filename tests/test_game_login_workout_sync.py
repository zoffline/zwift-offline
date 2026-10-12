"""Run with python tests/test_game_login_workout_sync.py; uses temporary storage and fake API."""
import datetime
import json
import importlib.metadata
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import requests
import werkzeug
# Older Flask's test client expects this attribute; production WSGI does not.
if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = importlib.metadata.version('werkzeug')
from flask_login import LoginManager
from flask_login import encode_cookie
# Run the real server module with isolated storage; data assets are read-only.
ROOT = Path(__file__).resolve().parents[1]
isolated = tempfile.TemporaryDirectory(prefix='zoffline-game-login-test-')
test_root = Path(isolated.name)
shutil.copyfile(ROOT/'zwift_offline.py', test_root/'zwift_offline.py')
for name in ['data', 'cdn', 'ssl', 'protobuf']:
    (test_root/name).symlink_to(ROOT/name, target_is_directory=True)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(test_root))
import intervals_workouts
import zwift_offline as zo

zo.app.config['TESTING'] = True
zo.MULTIPLAYER = True
zo.global_relay = {}
zo.login_manager = LoginManager(zo.app)
zo.login_manager.login_view = 'login'
zo.login_manager.session_protection = None

@zo.login_manager.user_loader
def load_user(player_id):
    return zo.db.session.get(zo.User, int(player_id))

with zo.app.app_context():
    user = zo.User(username='test@example.invalid', pass_hash='unused', first_name='Test', last_name='Test',
                   player_id=901, enable_ghosts=False)
    zo.db.session.add(user)
    zo.db.session.commit()
    user_id = str(user.player_id)
    zo.make_profile_dir(901)

client = zo.app.test_client()
with client.session_transaction() as session:
    session['_user_id'] = user_id
    session['_fresh'] = True

login = zo.login_pb2.LoginRequest(key=b'0123456789abcdef')

def game_login():
    response = client.post('/api/users/login', data=login.SerializeToString())
    assert response.status_code == 200, response.data
    parsed = zo.login_pb2.LoginResponse()
    parsed.ParseFromString(response.data)
    assert parsed.session_state == 'abc'
    return parsed

# Android token reuse reaches game login without visiting the web launcher.
with patch.object(zo, 'resolve_workout_provider_for_player', return_value='intervals-icu'), \
     patch.object(zo, 'sync_intervals_workout_for_player', return_value={'status':'synced'}) as sync:
    game_login()
    sync.assert_called_once_with(901, timeout=(2, 3))

# Exercise the real bearer-token-to-session decorator used by a cached app login.
with zo.app.test_request_context():
    saved_token = zo.fake_jwt_with_session_cookie(encode_cookie(user_id))['access_token']
with patch.object(zo, 'resolve_workout_provider_for_player', return_value='intervals-icu'), \
     patch.object(zo, 'sync_intervals_workout_for_player', return_value={'status':'synced'}) as sync:
    response = zo.app.test_client().post('/api/users/login', data=login.SerializeToString(),
                                        headers={'Authorization':'Bearer '+saved_token})
    assert response.status_code == 200
    sync.assert_called_once_with(901, timeout=(2, 3))

# Intervals outages and credential/provider exceptions must not deny game login.
for failure in [requests.Timeout('simulated outage'), ValueError('bad credentials')]:
    with patch.object(zo, 'resolve_workout_provider_for_player', return_value='intervals-icu'), \
         patch.object(zo, 'sync_intervals_workout_for_player', side_effect=failure):
        game_login()

with patch.object(zo, 'resolve_workout_provider_for_player', return_value='intervals-icu'), \
     patch.object(zo, 'sync_intervals_workout_for_player', return_value={'status':'error'}):
    game_login()

with patch.object(zo, 'resolve_workout_provider_for_player', side_effect=RuntimeError('state failure')):
    game_login()

# Never change TrainingPeaks selection or require Intervals for unlinked profiles.
for provider in [None, 'trainingpeaks']:
    with patch.object(zo, 'resolve_workout_provider_for_player', return_value=provider), \
         patch.object(zo, 'sync_intervals_workout_for_player') as sync:
        game_login()
        sync.assert_not_called()

# Authentication still rejects requests that have no session/token.
assert zo.app.test_client().post('/api/users/login', data=login.SerializeToString()).status_code != 200

class Response:
    def __init__(self, payload=None, content=b''):
        self.payload, self.content = payload, content
    def raise_for_status(self):
        pass
    def json(self):
        return self.payload

class FakeIntervals:
    def __init__(self, events):
        self.events, self.timeouts = events, []
    def get(self, url, **kwargs):
        self.timeouts.append(kwargs['timeout'])
        if '/events?' in url:
            assert 'category=WORKOUT' in url
            return Response(self.events)
        assert url.endswith('/download.zwo')
        return Response(content=b'<workout_file><name>Test</name><workout><SteadyState Duration="60" Power="0.5"/></workout></workout_file>')

today = datetime.date.today()
event = {'id': 1234, 'name': 'Test', 'start_date_local': today.isoformat()+'T18:00:00'}
api = FakeIntervals([event])
with zo.app.test_request_context():
    zo.encrypt_credentials(str(Path(zo.STORAGE_DIR)/'901/intervals_credentials.bin'), ('test-athlete', 'test-key'))
real_sync = intervals_workouts.sync_workout
def offline_sync(athlete, key, store, **kwargs):
    return real_sync(athlete, key, store, session=api, **kwargs)

# Full authenticated game login -> import -> database/manifest/file, using fake API.
with patch.object(zo.intervals_workouts, 'sync_workout', side_effect=offline_sync):
    game_login()
assert api.timeouts == [(2, 3), (2, 3)]
files = list((Path(zo.STORAGE_DIR)/'901/customworkouts').glob('intervals-icu-*.zwo'))
assert len(files) == 1 and b'<workout_file>' in files[0].read_bytes()
entries = zo.workouts_manifest.load_manifest(str(files[0].parent))
assert any(entry['name'] == files[0].name and not entry['deleted'] for entry in entries)
with zo.app.app_context():
    assert zo.current_workout_sync_status(901, 'intervals-icu')['server_file_exists']

# Repeated game login keeps one managed workout, rather than accumulating copies.
with patch.object(zo.intervals_workouts, 'sync_workout', side_effect=offline_sync):
    game_login()
assert len(list(files[0].parent.glob('intervals-icu-*.zwo'))) == 1
entries = zo.workouts_manifest.load_manifest(str(files[0].parent))
assert sum(entry['name'] == files[0].name and not entry['deleted'] for entry in entries) == 1

# No training today follows the existing cleanup behavior and keeps login working.
api.events = []
with patch.object(zo.intervals_workouts, 'sync_workout', side_effect=offline_sync):
    game_login()
assert not list(files[0].parent.glob('intervals-icu-*.zwo'))

# Web/manual sync retains its original 30-second HTTP timeout.
default_api = FakeIntervals([event])
real_sync('test-athlete', 'test-key', lambda *args: None, session=default_api)
assert default_api.timeouts == [30, 30]
print(json.dumps({'status':'passed', 'checks':[
    'authenticated game login imports today workout without web launcher',
    'timeouts and credential/provider errors do not deny login',
    'other providers and unlinked profiles untouched',
    'unauthenticated request rejected',
    'bounded HTTP timeouts for game login',
    'real workout file/database/manifest created',
    'repeat login does not duplicate managed workouts',
    'no-workout behavior preserved',
    'manual sync timeout preserved'
]}))
