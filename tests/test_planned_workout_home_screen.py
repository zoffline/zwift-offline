"""Contract/integration tests: temporary storage, synthetic accounts, no network.
Run: python tests/test_planned_workout_home_screen.py
"""
import datetime
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
import uuid

import werkzeug
from flask_login import LoginManager, encode_cookie
if not hasattr(werkzeug, '__version__'):
    werkzeug.__version__ = importlib.metadata.version('werkzeug')

ROOT = Path(__file__).resolve().parents[1]
isolated = tempfile.TemporaryDirectory(prefix='zoffline-home-screen-test-')
test_root = Path(isolated.name)
shutil.copyfile(ROOT / 'zwift_offline.py', test_root / 'zwift_offline.py')
for name in ('data', 'cdn', 'ssl', 'protobuf'):
    (test_root / name).symlink_to(ROOT / name, target_is_directory=True)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(test_root))
import zwift_offline as zo

zo.app.config['TESTING'] = True
zo.MULTIPLAYER = True
zo.login_manager = LoginManager(zo.app)
zo.login_manager.login_view = 'login'
zo.login_manager.session_protection = None

@zo.login_manager.user_loader
def load_user(player_id):
    return zo.db.session.get(zo.User, int(player_id))

class PlannedWorkoutHomeScreen(unittest.TestCase):
    player_id = 901
    filename = 'intervals-icu-1234-home-screen-regression-workout.zwo'
    content = (b'<workout_file><name>Home screen regression workout</name>'
               b'<sportType>bike</sportType><workout>'
               b'<SteadyState Duration="60" Power="0.5"/></workout></workout_file>')

    @classmethod
    def setUpClass(cls):
        with zo.app.app_context():
            for player_id in (901, 902):
                zo.db.session.add(zo.User(
                    player_id=player_id, username='test-%s@example.invalid' % player_id,
                    pass_hash='unused', first_name='Test', last_name='Test'))
                zo.make_profile_dir(player_id)
                profile = Path(zo.STORAGE_DIR) / str(player_id)
                (profile / 'intervals_credentials.bin').write_bytes(b'not-real-credentials')
            zo.db.session.commit()

    def client_for(self, player_id):
        client = zo.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(player_id)
            session['_fresh'] = True
        return client

    def store_workout(self, player_id):
        with zo.app.app_context():
            zo.save_active_workout_provider(player_id, 'intervals-icu')
            row = zo.save_player_zfile(player_id, 'customworkouts', self.filename, self.content)
            file_id = row.id
            zo.update_workouts_manifest(player_id, 'customworkouts', self.filename, self.content)
            zo.save_intervals_workout_metadata(player_id, {
                'id': 1234, 'name': 'Home screen regression workout',
                'description': 'Synthetic provider description', 'icu_training_load': 12,
                'start_date_local': datetime.date.today().isoformat() + 'T18:00:00',
            }, self.filename)
        return file_id

    def setUp(self):
        self.client = self.client_for(self.player_id)
        with zo.app.app_context():
            zo.clear_intervals_workout_metadata(902)
        self.file_id = self.store_workout(self.player_id)

    def schedule(self):
        response = self.client.get('/api/workout/schedule/list')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        return response.get_json()

    def assert_no_card(self):
        self.assertEqual(self.schedule(), [])
        self.assertEqual(self.client.get('/api/head-unit-bff/game-home').get_json(), [])

    def update_metadata(self, **changes):
        path = Path(zo.workout_state.metadata_file(zo.STORAGE_DIR, self.player_id, 'intervals-icu'))
        metadata = json.loads(path.read_text())
        metadata.update(changes)
        path.write_text(json.dumps(metadata))

    def test_reference_schedule_and_next_up_contract(self):
        schedule = self.schedule()
        self.assertEqual(len(schedule), 1)
        home = self.client.get('/api/head-unit-bff/game-home').get_json()
        workout_id, schedule_id = schedule[0]['workoutId'], schedule[0]['scheduleId']
        self.assertNotEqual(workout_id, schedule_id)
        uuid.UUID(workout_id)
        uuid.UUID(schedule_id)
        mapping = {
            '11111111-1111-4111-8111-111111111111': workout_id,
            '22222222-2222-4222-8222-222222222222': schedule_id,
            'https://example.invalid/workout.zwo': schedule[0]['workoutUri'],
        }
        def substitute(value):
            if isinstance(value, dict):
                return {key: substitute(item) for key, item in value.items()}
            if isinstance(value, list):
                return [substitute(item) for item in value]
            return mapping.get(value, value) if isinstance(value, str) else value
        reference = substitute(json.loads((ROOT / 'tests/fixtures/planned_workout_reference.json').read_text()))
        day = datetime.date.today()
        reference['schedule'][0]['availableAfter'] = int(datetime.datetime.combine(day, datetime.time.min).timestamp())
        reference['schedule'][0]['notAvailableAfter'] = int(datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time.min).timestamp()) - 1
        self.assertEqual(schedule, reference['schedule'])
        self.assertEqual(home, reference['home'])
        self.assertNotIn(zo.STORAGE_DIR, json.dumps([schedule, home]))

    def test_definition_and_asset_resolve_to_same_available_workout(self):
        item = self.schedule()[0]
        uri = urlsplit(item['workoutUri'])
        self.assertEqual(uri.scheme, 'https')
        self.assertEqual(uri.netloc, 'cdn.zwift.com')
        self.assertEqual(uri.path, '/tp-workouts/intervalsicu/' + item['workoutId'] + '.zwo')
        self.assertTrue(parse_qs(uri.query)['token'][0])
        self.assertEqual(item['workoutSummary']['workoutAssetUrl'], item['workoutUri'])
        response = self.client.get('/api/workout/workouts/' + item['workoutId'])
        self.assertEqual(response.get_json(), item['workoutSummary'])
        response = zo.app.test_client().get(item['workoutUri'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.content)
        self.assertEqual(response.mimetype, 'application/xml')
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        response.close()

    def bearer_headers(self):
        with zo.app.test_request_context():
            token = zo.fake_jwt_with_session_cookie(encode_cookie(str(self.player_id)))['access_token']
        return {'Authorization': 'Bearer ' + token}

    def test_cdn_host_requires_a_valid_scoped_signature(self):
        item = self.schedule()[0]
        client = zo.app.test_client()
        path = urlsplit(item['workoutUri']).path
        for query in ('', '?token=invalid', '?token=' + 'x' * 2049):
            self.assertEqual(client.get(path + query).status_code, 403)
        self.store_workout(902)
        other_item = self.client_for(902).get('/api/workout/schedule/list').get_json()[0]
        wrong_path = urlsplit(other_item['workoutUri']).path
        query = urlsplit(item['workoutUri']).query
        self.assertEqual(client.get(wrong_path + '?' + query).status_code, 403)

    def signed_uri(self, uri, **changes):
        parts = urlsplit(uri)
        payload = zo.planned_workout_signer().loads(parse_qs(parts.query)['token'][0])
        payload.update(changes)
        query = urlencode({'token': zo.planned_workout_signer().dumps(payload)})
        return urlunsplit(parts._replace(query=query))

    def test_expired_tampered_and_invalid_download_grants_are_rejected(self):
        item = self.schedule()[0]
        client = zo.app.test_client()
        for changes in ({'expires': 0}, {'expires': True}, {'expires': 'tomorrow'},
                        {'player_id': '../901'}, {'player_id': True},
                        {'sha256': 'wrong-content'}):
            with self.subTest(changes=changes):
                self.assertEqual(client.get(self.signed_uri(item['workoutUri'], **changes)).status_code, 403)
        self.assertEqual(client.get(self.signed_uri(item['workoutUri'], player_id=902)).status_code, 404)
        # Real tampering is not re-signed with the server's key.
        uri = urlsplit(item['workoutUri'])
        token = parse_qs(uri.query)['token'][0]
        tampered = 'x' + token[1:]
        self.assertEqual(client.get(uri.path + '?' + urlencode({'token': tampered})).status_code, 403)
        self.assertNotIn('storage', client.get(uri.path).get_data(as_text=True))

    def test_download_grant_expires_at_the_advertised_local_midnight(self):
        item = self.schedule()[0]
        uri = urlsplit(item['workoutUri'])
        payload = zo.planned_workout_signer().loads(parse_qs(uri.query)['token'][0])
        self.assertEqual(payload['expires'], item['notAvailableAfter'] + 1)
        client = zo.app.test_client()
        with patch.object(zo.time, 'time', return_value=payload['expires'] - 1):
            response = client.get(item['workoutUri'])
            self.assertEqual(response.status_code, 200)
            response.close()
        with patch.object(zo.time, 'time', return_value=payload['expires']):
            self.assertEqual(client.get(item['workoutUri']).status_code, 403)

    def test_resync_with_changed_bytes_revokes_the_previous_download_grant(self):
        item = self.schedule()[0]
        path = Path(zo.STORAGE_DIR) / str(self.player_id) / 'customworkouts' / self.filename
        path.write_bytes(self.content.replace(b'Duration="60"', b'Duration="120"'))
        client = zo.app.test_client()
        self.assertEqual(client.get(item['workoutUri']).status_code, 403)
        response = client.get(self.schedule()[0]['workoutUri'])
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_signed_download_does_not_require_or_consult_the_logged_in_profile(self):
        item = self.schedule()[0]
        # The private URL is a bearer capability for exactly the signed file.
        response = self.client_for(902).get(item['workoutUri'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.content)
        response.close()

    def test_download_signature_is_redacted_from_access_logs(self):
        item = self.schedule()[0]
        uri = urlsplit(item['workoutUri'])
        token = parse_qs(uri.query)['token'][0]
        record = zo.logging.LogRecord('zoffline', zo.logging.INFO, '', 0,
                                      'client "GET %s HTTP/1.1" 200',
                                      (uri.path + '?' + uri.query,), None)
        zo.PlannedWorkoutLogFilter().filter(record)
        self.assertNotIn(token, record.getMessage())
        self.assertIn(uri.path + '?[redacted]', record.getMessage())
        self.assertIn('HTTP/1.1" 200', record.getMessage())

    def test_previous_api_download_stays_authenticated_and_byte_identical(self):
        item = self.schedule()[0]
        path = '/api/workout/workouts/' + item['workoutId'] + '/file.zwo'
        self.assertIn(zo.app.test_client().get(path).status_code, (302, 401))
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.content)
        response.close()

    def test_original_workout_selection_and_manifest_still_work(self):
        response = self.client.get('/api/zfiles/list?folder=customworkouts')
        listing = zo.zfiles_pb2.ZFilesProto()
        listing.ParseFromString(response.data)
        names = {item.filename for item in listing.zfiles}
        self.assertIn(self.filename, names)
        self.assertIn('workouts.files', names)

    def test_repeated_reads_and_resync_keep_stable_ids(self):
        first = self.schedule()
        self.assertEqual(self.schedule(), first)
        self.store_workout(self.player_id)
        self.assertEqual(self.schedule(), first)

    def test_other_profile_cannot_get_card_definition_or_asset(self):
        item = self.schedule()[0]
        other = self.client_for(902)
        self.assertEqual(other.get('/api/workout/schedule/list').get_json(), [])
        self.assertEqual(other.get('/api/head-unit-bff/game-home').get_json(), [])
        self.assertEqual(other.get('/api/workout/workouts/' + item['workoutId']).status_code, 404)
        self.assertEqual(other.get(urlsplit(item['workoutUri']).path).status_code, 403)
        self.store_workout(902)
        other_id = other.get('/api/workout/schedule/list').get_json()[0]['workoutId']
        self.assertNotEqual(other_id, item['workoutId'])

    def test_anonymous_requests_are_not_given_profile_data(self):
        item = self.schedule()[0]
        anonymous = zo.app.test_client()
        for path in ['/api/workout/schedule/list', '/api/head-unit-bff/game-home',
                     '/api/workout/workouts/' + item['workoutId']]:
            with self.subTest(path=path):
                self.assertIn(anonymous.get(path).status_code, (302, 401))
        self.assertEqual(anonymous.get(urlsplit(item['workoutUri']).path).status_code, 403)

    def test_bearer_token_authorizes_card_and_download(self):
        item = self.schedule()[0]
        with zo.app.test_request_context():
            token = zo.fake_jwt_with_session_cookie(encode_cookie(str(self.player_id)))['access_token']
        client = zo.app.test_client()
        headers = {'Authorization': 'Bearer ' + token}
        self.assertEqual(client.get('/api/workout/schedule/list', headers=headers).get_json(), [item])
        response = client.get(item['workoutUri'], headers=headers)
        self.assertEqual(response.data, self.content)
        response.close()

    def test_stale_and_future_workouts_have_no_card(self):
        old = self.schedule()[0]
        for offset in (-1, 1):
            self.update_metadata(start_date_local=(datetime.date.today() + datetime.timedelta(days=offset)).isoformat() + 'T18:00:00')
            self.assert_no_card()
            self.assertEqual(self.client.get(old['workoutUri']).status_code, 404)

    def test_cleared_completion_metadata_removes_card(self):
        item = self.schedule()[0]
        with zo.app.app_context():
            zo.clear_intervals_workout_metadata(self.player_id)
        self.assert_no_card()
        self.assertEqual(zo.app.test_client().get(item['workoutUri']).status_code, 404)

    def test_missing_or_invalid_zwo_removes_card(self):
        path = Path(zo.STORAGE_DIR) / str(self.player_id) / 'customworkouts' / self.filename
        path.unlink()
        self.assert_no_card()
        path.write_bytes(b'<broken')
        self.assert_no_card()

    def test_invalid_metadata_and_paths_fail_closed(self):
        for changes in [dict(filename='../secret.zwo'), dict(event_id=None), dict(start_date_local='invalid')]:
            self.store_workout(self.player_id)
            self.update_metadata(**changes)
            self.assert_no_card()
        path = Path(zo.workout_state.metadata_file(zo.STORAGE_DIR, self.player_id, 'intervals-icu'))
        path.write_text('[]')
        self.assert_no_card()

    def test_other_provider_and_unlinked_profile_remain_unchanged(self):
        with zo.app.app_context():
            zo.save_trainingpeaks_bridge_folder(self.player_id, str(test_root / 'unused-bridge'))
            zo.save_active_workout_provider(self.player_id, 'trainingpeaks')
        self.assert_no_card()
        profile = Path(zo.STORAGE_DIR) / str(self.player_id)
        (profile / 'intervals_credentials.bin').unlink()
        try:
            self.assert_no_card()
        finally:
            (profile / 'intervals_credentials.bin').write_bytes(b'not-real-credentials')

    def test_running_filter_does_not_show_cycling_card(self):
        self.assertEqual(self.client.get('/api/workout/schedule/list?sport=RUNNING').get_json(), [])
        self.assertEqual(self.client.get('/api/head-unit-bff/game-home?sport=RUNNING').get_json(), [])
        self.assertTrue(self.client.get('/api/workout/schedule/list?sport=CYCLING').get_json())

    def test_single_player_keeps_the_existing_anonymous_profile_behavior(self):
        expected = self.schedule()
        # run_standalone assigns the selected profile to AnonUser in this mode.
        zo.AnonUser.player_id = self.player_id
        with patch.object(zo, 'MULTIPLAYER', False), patch.object(zo.login_manager, 'anonymous_user', zo.AnonUser):
            client = zo.app.test_client()
            self.assertEqual(client.get('/api/workout/schedule/list').get_json(), expected)
            response = client.get(expected[0]['workoutUri'])
            self.assertEqual(response.data, self.content)
            response.close()

    def test_for_you_and_other_placeholders_remain_unchanged(self):
        self.assertEqual(self.client.get('/api/head-unit-bff/carousels/for-you').get_json(), {})
        self.assertEqual(self.client.get('/api/head-unit-bff/crm').get_json(), [])
        self.assertEqual(self.client.get('/api/head-unit-bff/carousels/home-challenges').get_json(), {'items': []})

    def test_home_reads_do_not_sync_or_modify_workout_state(self):
        path = Path(zo.workout_state.metadata_file(zo.STORAGE_DIR, self.player_id, 'intervals-icu'))
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        with patch.object(zo, 'sync_intervals_workout_for_player', side_effect=AssertionError('no sync on GET')):
            self.assertTrue(self.schedule())
            self.assertTrue(self.client.get('/api/head-unit-bff/game-home').get_json())
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def sync_events(self, events, fail_id=None):
        class Response:
            def __init__(self, payload=None, content=b''):
                self.payload, self.content = payload, content
            def raise_for_status(self):
                pass
            def json(self):
                return self.payload
        class Provider:
            def get(inner, url, **kwargs):
                if '/events?' in url:
                    return Response(payload=events)
                event_id = int(url.split('/events/')[1].split('/')[0])
                if event_id == fail_id:
                    raise TimeoutError('synthetic download failure')
                return Response(content=self.content.replace(b'Duration="60"',
                                ('Duration="%s"' % event_id).encode()))
        sync = zo.intervals_workouts.sync_workout
        with patch.object(zo, 'decrypt_credentials', return_value=('test-athlete', 'test-key')), \
             patch.object(zo.intervals_workouts, 'sync_workout',
                          side_effect=lambda *args, **kwargs: sync(*args, session=Provider(), **kwargs)):
            with zo.app.app_context():
                return zo.sync_intervals_workout_for_player(self.player_id, timeout=(2, 3))

    def today_events(self):
        day = datetime.date.today().isoformat()
        return [{'id': 101, 'name': 'First workout', 'start_date_local': day + 'T08:00:00'},
                {'id': 102, 'name': 'Second workout', 'start_date_local': day + 'T18:00:00'}]

    def test_all_today_workouts_have_distinct_cards_assets_and_stable_resync(self):
        result = self.sync_events(self.today_events())
        self.assertEqual((result['status'], result['count']), ('synced', 2))
        items = self.schedule()
        self.assertEqual(len(items), 2)
        self.assertEqual(len({item['workoutId'] for item in items}), 2)
        self.assertEqual(len({item['scheduleId'] for item in items}), 2)
        for item, duration in zip(items, (101, 102)):
            self.assertEqual(item['workoutSummary']['duration'], duration)
            response = zo.app.test_client().get(item['workoutUri'])
            self.assertEqual(response.status_code, 200)
            self.assertIn(('Duration="%s"' % duration).encode(), response.data)
            response.close()
            self.assertEqual(self.client.get('/api/workout/workouts/' + item['workoutId']).get_json(),
                             item['workoutSummary'])
        self.sync_events(self.today_events())
        self.assertEqual(self.schedule(), items)
        with zo.app.app_context():
            rows = zo.Zfile.query.filter_by(player_id=self.player_id, folder='customworkouts').all()
            self.assertEqual(len([row for row in rows if row.filename.startswith('intervals-icu-')]), 2)
        folder = Path(zo.STORAGE_DIR) / str(self.player_id) / 'customworkouts'
        self.assertEqual(len(list(folder.glob('intervals-icu-*.zwo'))), 2)
        entries = zo.workouts_manifest.load_manifest(str(folder))
        self.assertEqual(len([entry for entry in entries if not entry['deleted']]), 2)

    def test_partial_download_failure_preserves_the_previous_entire_collection(self):
        self.sync_events(self.today_events())
        before = self.schedule()
        changed = self.today_events() + [dict(self.today_events()[1], id=103, name='Third workout')]
        self.assertEqual(self.sync_events(changed, fail_id=103)['status'], 'error')
        self.assertEqual(self.schedule(), before)
        for item in before:
            response = zo.app.test_client().get(item['workoutUri'])
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_batch_sync_preserves_unmanaged_library_files(self):
        filename = 'manual-test-workout.zwo'
        with zo.app.app_context():
            zo.save_player_zfile(self.player_id, 'customworkouts', filename, self.content)
            zo.update_workouts_manifest(self.player_id, 'customworkouts', filename, self.content)
        try:
            self.sync_events(self.today_events())
            folder = Path(zo.STORAGE_DIR) / str(self.player_id) / 'customworkouts'
            self.assertEqual((folder / filename).read_bytes(), self.content)
            entries = zo.workouts_manifest.load_manifest(str(folder))
            self.assertTrue(any(entry['name'] == filename and not entry['deleted'] for entry in entries))
        finally:
            with zo.app.app_context():
                zo.remove_player_zfiles_by_prefix(self.player_id, 'customworkouts', 'manual-test-')
                zo.workouts_manifest.remove_prefixed_workouts(str(folder), {'manual-test-'})

    def test_removed_or_renamed_event_is_reconciled_without_affecting_others(self):
        events = self.today_events()
        self.sync_events(events)
        before = self.schedule()
        self.sync_events([dict(events[1], name='Renamed second workout')])
        remaining = self.schedule()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]['workoutId'], before[1]['workoutId'])
        self.assertEqual(zo.app.test_client().get(before[0]['workoutUri']).status_code, 404)
        response = zo.app.test_client().get(remaining[0]['workoutUri'])
        self.assertEqual(response.status_code, 200)
        response.close()
        folder = Path(zo.STORAGE_DIR) / str(self.player_id) / 'customworkouts'
        self.assertEqual(len(list(folder.glob('intervals-icu-*.zwo'))), 1)

    def test_completing_one_workout_keeps_the_other_download_available(self):
        self.sync_events(self.today_events())
        before = self.schedule()
        with patch.object(zo, 'decrypt_credentials', return_value=('test-athlete', 'test-key')), \
             patch.object(zo.intervals_workouts, 'upload_activity',
                          return_value={'paired': True, 'paired_event_id': 101}):
            with zo.app.app_context():
                zo.intervals_upload(self.player_id, object())
        self.assertEqual(self.schedule(), [before[1]])
        self.assertEqual(zo.app.test_client().get(before[0]['workoutUri']).status_code, 404)
        response = zo.app.test_client().get(before[1]['workoutUri'])
        self.assertEqual(response.status_code, 200)
        response.close()
        with zo.app.app_context():
            zo.clear_intervals_workout_metadata(self.player_id, 102)
            self.assertIsNone(zo.current_workout_sync_status(self.player_id, 'intervals-icu')['metadata'])
        self.assertEqual(self.schedule(), [])

    def test_unpaired_activity_does_not_clear_any_workout(self):
        self.sync_events(self.today_events())
        before = self.schedule()
        with patch.object(zo, 'decrypt_credentials', return_value=('test-athlete', 'test-key')), \
             patch.object(zo.intervals_workouts, 'upload_activity', return_value={'paired': False}):
            with zo.app.app_context():
                zo.intervals_upload(self.player_id, object())
        self.assertEqual(self.schedule(), before)

if __name__ == '__main__':
    unittest.main(verbosity=2)
