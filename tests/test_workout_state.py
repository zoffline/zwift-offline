import json
import os
import tempfile
import unittest

from workout_state import (
    clear_metadata,
    load_active_provider,
    load_metadata,
    metadata_file,
    resolve_active_provider,
    save_active_provider,
    save_metadata,
)


class WorkoutStateTests(unittest.TestCase):
    def test_metadata_file_is_provider_specific(self):
        path = metadata_file('/tmp/storage', 7, 'intervals-icu')
        self.assertEqual(path, '/tmp/storage/7/intervals_icu_workout.json')

    def test_save_and_load_metadata_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = save_metadata(
                tmp,
                1,
                'intervals-icu',
                {
                    'id': 42,
                    'name': 'Threshold Session',
                    'start_date_local': '2026-04-22T18:00:00+00:00',
                },
                'intervals-icu-42-threshold-session.zwo',
            )
            self.assertEqual(payload['provider'], 'intervals-icu')
            self.assertEqual(payload['event_id'], 42)
            self.assertEqual(payload['filename'], 'intervals-icu-42-threshold-session.zwo')

            loaded = load_metadata(tmp, 1, 'intervals-icu')
            self.assertEqual(loaded['event_id'], 42)
            self.assertEqual(loaded['provider'], 'intervals-icu')

    def test_clear_metadata_removes_only_selected_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_metadata(tmp, 1, 'intervals-icu', {'id': 42, 'name': 'A'}, 'a.zwo')
            save_metadata(tmp, 1, 'trainingpeaks', {'id': 99, 'name': 'B'}, 'b.zwo')

            clear_metadata(tmp, 1, 'intervals-icu')

            self.assertIsNone(load_metadata(tmp, 1, 'intervals-icu'))
            self.assertEqual(load_metadata(tmp, 1, 'trainingpeaks')['event_id'], 99)

    def test_save_and_load_active_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(load_active_provider(tmp, 1))
            save_active_provider(tmp, 1, 'trainingpeaks')
            self.assertEqual(load_active_provider(tmp, 1), 'trainingpeaks')

    def test_resolve_active_provider_uses_saved_provider_when_available(self):
        active = resolve_active_provider('trainingpeaks', {'intervals-icu', 'trainingpeaks'})
        self.assertEqual(active, 'trainingpeaks')

    def test_resolve_active_provider_falls_back_to_first_available(self):
        active = resolve_active_provider('trainingpeaks', {'intervals-icu'})
        self.assertEqual(active, 'intervals-icu')

    def test_resolve_active_provider_prefers_intervals_when_nothing_saved(self):
        active = resolve_active_provider(None, {'trainingpeaks', 'intervals-icu'})
        self.assertEqual(active, 'intervals-icu')


if __name__ == '__main__':
    unittest.main()
