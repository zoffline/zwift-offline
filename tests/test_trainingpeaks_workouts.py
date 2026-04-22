import os
import tempfile
import unittest
from types import SimpleNamespace

from trainingpeaks_workouts import (
    build_workout_filename,
    sync_exported_workouts,
    sync_workout,
    upload_activity,
)


class TrainingPeaksWorkoutTests(unittest.TestCase):
    def test_build_workout_filename_uses_trainingpeaks_prefix(self):
        workout = {'id': 51, 'title': 'VO2 Max Builder'}
        self.assertEqual(build_workout_filename(workout), 'trainingpeaks-51-vo2-max-builder.zwo')

    def test_sync_exported_workouts_imports_zwo_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'VO2 Builder.zwo'), 'wb') as fd:
                fd.write(b'<workout_file id="1"/>')
            with open(os.path.join(tmp, 'Tempo Ride.zwo'), 'wb') as fd:
                fd.write(b'<workout_file id="2"/>')
            with open(os.path.join(tmp, 'ignore.txt'), 'w') as fd:
                fd.write('ignore me')

            saved = []
            result = sync_exported_workouts(tmp, lambda filename, content, workout: saved.append((filename, content, workout)))

            self.assertEqual(result['status'], 'synced')
            self.assertEqual(result['count'], 2)
            self.assertEqual([item[0] for item in saved], [
                'trainingpeaks-tempo-ride.zwo',
                'trainingpeaks-vo2-builder.zwo',
            ])

    def test_sync_exported_workouts_handles_missing_folder(self):
        result = sync_exported_workouts('/tmp/does-not-exist-hermes', lambda *args: None)
        self.assertEqual(result['status'], 'missing_folder')

    def test_sync_workout_reports_partner_access_requirement(self):
        result = sync_workout(credentials={'client_id': 'abc'})
        self.assertEqual(result['status'], 'unsupported')
        self.assertIn('partner', result['message'].lower())

    def test_upload_activity_reports_partner_access_requirement(self):
        activity = SimpleNamespace(name='Ride', fit=b'FIT')
        result = upload_activity(credentials={'access_token': 'abc'}, activity=activity)
        self.assertEqual(result['status'], 'unsupported')
        self.assertIn('partner', result['message'].lower())


if __name__ == '__main__':
    unittest.main()
