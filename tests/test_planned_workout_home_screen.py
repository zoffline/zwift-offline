"""Reproduce missing home-screen data for a successfully imported workout.

Run: python tests/test_planned_workout_home_screen.py
Uses temporary storage, synthetic profiles and no network. Two expected failures
document the missing feature, not an established Zwift response schema.
"""
import datetime
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import werkzeug
from flask_login import LoginManager

# Compatibility for older Flask test clients, without changing runtime packages.
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
    name = 'Home screen regression workout'
    filename = 'intervals-icu-1234-home-screen-regression-workout.zwo'
    content = (
        b'<workout_file><name>Home screen regression workout</name>'
        b'<sportType>bike</sportType><workout>'
        b'<SteadyState Duration="60" Power="0.5"/>'
        b'</workout></workout_file>'
    )

    @classmethod
    def setUpClass(cls):
        # Start after the import: this fixture is independent of the login-sync PR.
        with zo.app.app_context():
            zo.db.session.add(zo.User(
                player_id=cls.player_id, username='home-screen@example.invalid',
                pass_hash='unused', first_name='Test', last_name='Test',
            ))
            zo.db.session.commit()
            zo.make_profile_dir(cls.player_id)
            profile = Path(zo.STORAGE_DIR) / str(cls.player_id)
            # Provider detection checks existence only; no credentials are used.
            (profile / 'intervals_credentials.bin').write_bytes(b'not-real-credentials')
            zo.save_active_workout_provider(cls.player_id, 'intervals-icu')
            row = zo.save_player_zfile(cls.player_id, 'customworkouts', cls.filename, cls.content)
            cls.file_id = row.id
            zo.update_workouts_manifest(cls.player_id, 'customworkouts', cls.filename, cls.content)
            zo.save_intervals_workout_metadata(cls.player_id, {
                'id': 1234, 'name': cls.name,
                'start_date_local': datetime.date.today().isoformat() + 'T18:00:00',
            }, cls.filename)

    def setUp(self):
        self.client = zo.app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.player_id)
            session['_fresh'] = True

    def test_workout_is_available_to_the_game(self):
        response = self.client.get('/api/zfiles/list?folder=customworkouts')
        self.assertEqual(response.status_code, 200)
        listing = zo.zfiles_pb2.ZFilesProto()
        listing.ParseFromString(response.data)
        names = {item.filename for item in listing.zfiles}
        self.assertIn(self.filename, names)
        self.assertIn('workouts.files', names)
        response = self.client.get('/api/zfiles/%s/download' % self.file_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.content)
        response.close()
        with zo.app.app_context():
            status = zo.current_workout_sync_status(self.player_id, 'intervals-icu')
            self.assertTrue(status['server_file_exists'])
            self.assertEqual(status['metadata']['name'], self.name)

    def test_observed_home_endpoints_accept_requests(self):
        for path in (
            '/api/workout/schedule/list',
            '/api/head-unit-bff/game-home',
            '/api/head-unit-bff/carousels/for-you',
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.is_json)

    @unittest.expectedFailure
    def test_schedule_is_not_empty_after_successful_import(self):
        # Minimum regression condition only. Replace with a verified contract
        # fixture when the real schedule response is available.
        response = self.client.get('/api/workout/schedule/list')
        self.assertTrue(response.get_json(), 'An imported workout has no schedule entry')

    @unittest.expectedFailure
    def test_game_home_exposes_the_imported_workout(self):
        # The current implementation returns [] for both routes. This deliberately
        # avoids inventing card keys, artwork URLs, workout UUIDs or launch targets.
        responses = [self.client.get(path).get_json() for path in (
            '/api/head-unit-bff/game-home',
            '/api/head-unit-bff/carousels/for-you',
        )]
        self.assertIn(self.name, json.dumps(responses))


if __name__ == '__main__':
    unittest.main(verbosity=2)
