"""Standard-library tests for the local scheduled-workout projection."""
import datetime
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import planned_workouts as pw


class PlannedWorkouts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.today = datetime.date(2026, 10, 19)
        self.event = {'id': 1234, 'name': 'Test',
                      'start_date_local': '2026-10-19T18:00:00', 'icu_training_load': 12}
        content = b'<workout_file><name>Test</name><sportType>bike</sportType><workout><SteadyState Duration="60" Power="0.5"/></workout></workout_file>'
        self.metadata = pw.store_workout(self.root, self.event, content)
        self.folder = pw.cache_dir(self.root)
        self.filename = self.metadata['filename']
        self.content = (self.folder / self.filename).read_bytes()

    def build(self, metadata=None, player_id=901):
        return pw.build_workout(self.root, player_id, self.metadata if metadata is None else metadata,
                                lambda uid: 'https://example.invalid/workouts/' + uid + '.zwo', self.today)

    def test_ids_link_card_schedule_and_asset_and_stay_stable(self):
        first = self.build()
        self.assertEqual(first['id'], self.build()['id'])
        self.assertNotEqual(first['id'], first['schedule']['scheduleId'])
        self.assertEqual(first['id'], first['home']['nextUp']['selected']['entityId'])
        self.assertEqual(first['schedule']['scheduleId'], first['home']['nextUp']['sourceId'])
        self.assertEqual(first['schedule']['workoutUri'], first['schedule']['workoutSummary']['workoutAssetUrl'])
        self.assertEqual(first['schedule']['workoutSummary']['stressPoints'], 12)

    def test_separate_imports_get_different_random_ids(self):
        other = pw.store_workout(self.root, self.event, self.content)
        self.assertNotEqual(self.build()['id'], self.build(other, player_id=902)['id'])
        self.assertEqual(uuid.UUID(other['workout_id']).version, 4)

    def test_stale_future_and_missing_dates_are_not_exposed(self):
        for date in ['2026-10-18T18:00:00', '2026-10-20T18:00:00', 'invalid', None]:
            with self.subTest(date=date):
                self.assertIsNone(self.build(dict(self.metadata, start_date_local=date)))

    def test_utc_fallback_converts_to_server_local_day(self):
        if not hasattr(time, 'tzset'):
            self.skipTest('tzset unavailable')
        try:
            with patch.dict(os.environ, {'TZ': 'Europe/Zurich'}):
                time.tzset()
                meta = dict(self.metadata, start_date_local=None, start_date='2026-10-18T23:30:00Z')
                self.assertIsNotNone(self.build(meta))
        finally:
            time.tzset()

    @unittest.skipUnless(hasattr(time, 'tzset'), 'tzset unavailable')
    def test_dst_days_use_real_local_midnights(self):
        try:
            with patch.dict(os.environ, {'TZ': 'Europe/Zurich'}):
                time.tzset()
                for day, hours in [('2026-03-29', 23), ('2026-10-25', 25)]:
                    self.today = datetime.date.fromisoformat(day)
                    self.metadata['start_date_local'] = day + 'T12:00:00'
                    item = self.build()['schedule']
                    self.assertEqual(item['notAvailableAfter'] + 1 - item['availableAfter'], hours * 3600)
        finally:
            time.tzset()

    def test_bad_metadata_and_paths_are_rejected(self):
        for metadata in [None, [], {}, dict(self.metadata, event_id=None),
                         dict(self.metadata, event_id=True), dict(self.metadata, provider='trainingpeaks'),
                         dict(self.metadata, workout_id='../private'),
                         dict(self.metadata, workout_id='not-a-uuid'),
                         dict(self.metadata, start_date_local=123),
                         dict(self.metadata, start_date_local=None, start_date=123)]:
            with self.subTest(metadata=metadata):
                # None is deliberately passed straight through, not self.build's default.
                self.assertIsNone(pw.build_workout(self.root, 901, metadata, lambda uid: uid, self.today))

    def test_missing_malformed_and_oversized_files_are_not_exposed(self):
        path = self.folder / self.filename
        path.unlink()
        self.assertIsNone(self.build())
        path.write_bytes(b'<broken')
        self.assertIsNone(self.build())
        path.write_bytes(self.content)
        with patch.object(pw, 'MAX_FILE_BYTES', 8):
            self.assertIsNone(self.build())

    def test_symlink_is_rejected_before_reading(self):
        path = self.folder / self.filename
        path.unlink()
        path.symlink_to(self.root / 'outside.zwo')
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('must not read')):
            self.assertIsNone(self.build())

    def test_zwo_interval_and_ramp_duration_and_zones(self):
        content = b'<workout_file><workout><Warmup Duration="60" PowerLow="0.5" PowerHigh="1.0"/><IntervalsT Repeat="3" OnDuration="30" OffDuration="10" OnPower="1.1" OffPower="0.5"/></workout></workout_file>'
        detail = pw.workout_details(content)
        self.assertEqual(detail['duration'], 180)
        self.assertEqual(sum(detail['zonePercentages']), 100)
        self.assertGreater(detail['zonePercentages'][0], 0)
        self.assertGreater(detail['zonePercentages'][4], 0)

    def test_free_ride_has_no_invented_power_distribution(self):
        detail = pw.workout_details(b'<workout_file><workout><FreeRide Duration="60"/></workout></workout_file>')
        self.assertEqual(detail['duration'], 60)
        self.assertEqual(detail['zonePercentages'], [0] * 6)

    def test_running_empty_and_entity_workouts_are_not_exposed(self):
        for content in [b'<workout_file><sportType>run</sportType><workout><SteadyState Duration="60" Power="0.5"/></workout></workout_file>',
                        b'<workout_file><workout/></workout_file>',
                        b'<!DOCTYPE x [<!ENTITY a "x">]><workout_file><workout/></workout_file>']:
            with self.subTest(content=content):
                self.assertIsNone(pw.workout_details(content))

    def test_nonfinite_and_negative_numbers_are_not_serialized(self):
        item = self.build(dict(self.metadata, icu_training_load=float('nan')))
        self.assertEqual(item['schedule']['workoutSummary']['stressPoints'], 0)
        for value in ['nan', 'inf', -1, True]:
            self.assertEqual(pw.number(value), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
