"""Batch import and conservative activity pairing, with a fake provider only."""
import datetime
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import intervals_workouts as iw
import workout_state as ws


class Provider:
    def __init__(self, events, fail_id=None, invalid_id=None):
        self.events, self.fail_id, self.invalid_id = events, fail_id, invalid_id
        self.timeouts = []
    def get(self, url, **kwargs):
        self.timeouts.append(kwargs['timeout'])
        if '/events?' in url:
            return SimpleNamespace(json=lambda: self.events, raise_for_status=lambda: None)
        event_id = int(url.split('/events/')[1].split('/')[0])
        if event_id == self.fail_id:
            raise TimeoutError('synthetic failure')
        content = b'<broken' if event_id == self.invalid_id else b'<workout_file><workout><SteadyState Duration="60" Power="0.5"/></workout></workout_file>'
        return SimpleNamespace(content=content, raise_for_status=lambda: None)


class MultipleIntervalsWorkouts(unittest.TestCase):
    day = datetime.date(2026, 10, 19)
    def events(self):
        return [{'id': 101, 'name': 'First', 'start_date_local': '2026-10-19T08:00:00'},
                {'id': 102, 'name': 'Second', 'start_date_local': '2026-10-19T18:00:00'}]
    def sync(self, provider, stored):
        return iw.sync_workout('synthetic-athlete', 'synthetic-key', lambda *args: stored.append(args),
                               today=self.day, session=provider, timeout=(2, 3))
    def test_imports_all_events_once_in_local_time_order(self):
        events = self.events()
        provider = Provider([events[1], events[0], events[1],
                             dict(events[0], id=103, start_date_local='2026-10-20T08:00:00'),
                             dict(events[0], id=104, category='NOTE'), {'id': '../unsafe'}])
        stored = []
        result = self.sync(provider, stored)
        self.assertEqual([item[2]['id'] for item in stored], [101, 102])
        self.assertEqual(result['count'], 2)
        self.assertEqual(provider.timeouts, [(2, 3)] * 3)
    def test_failed_download_does_not_store_any_part_of_the_batch(self):
        stored = []
        with self.assertRaises(TimeoutError):
            self.sync(Provider(self.events(), fail_id=102), stored)
        self.assertEqual(stored, [])
    def test_invalid_xml_does_not_store_any_part_of_the_batch(self):
        stored = []
        with self.assertRaises(ET.ParseError):
            self.sync(Provider(self.events(), invalid_id=102), stored)
        self.assertEqual(stored, [])
    def test_unexpected_provider_payload_is_not_an_empty_calendar(self):
        for payload in (None, {}, {'error': 'synthetic failure'}, {'events': None}):
            with self.subTest(payload=payload):
                stored = []
                with self.assertRaises(ValueError):
                    self.sync(Provider(payload), stored)
                self.assertEqual(stored, [])
    def test_explicit_empty_calendar_remains_no_workout(self):
        stored = []
        self.assertEqual(self.sync(Provider([]), stored)['status'], 'no_workout')
        self.assertEqual(stored, [])
    def test_all_today_events_are_imported_including_previously_paired(self):
        events = self.events()
        events[0]['paired_activity_id'] = 'synthetic-completed-activity'
        stored = []
        self.assertEqual(self.sync(Provider(events), stored)['count'], 2)
    def test_ambiguous_same_day_activity_is_not_forced_to_a_workout(self):
        metadata = {'workouts': [ws.build_metadata('intervals-icu', item, str(item['id'])+'.zwo')
                                 for item in self.events()]}
        activity = SimpleNamespace(name='Zwift ride', start_date='2026-10-19T12:00:00Z')
        self.assertIsNone(iw.matching_workout_metadata(activity, metadata))
        activity.name = 'Second'
        self.assertEqual(iw.matching_workout_metadata(activity, metadata)['event_id'], 102)
        metadata['workouts'][0]['name'] = 'Second'
        self.assertIsNone(iw.matching_workout_metadata(activity, metadata))
        metadata['workouts'] = metadata['workouts'][1:]
        activity.name = 'Unrelated free ride'
        self.assertIsNone(iw.matching_workout_metadata(activity, metadata))
    def test_original_single_metadata_remains_readable_and_pairable(self):
        metadata = ws.build_metadata('intervals-icu', self.events()[0], 'first.zwo')
        activity = SimpleNamespace(name='Zwift ride', start_date='2026-10-19T12:00:00Z')
        self.assertEqual(iw.matching_workout_metadata(activity, metadata), metadata)
        self.assertEqual(ws.metadata_entries(metadata), [metadata])
    def test_removing_one_metadata_entry_keeps_the_other_and_legacy_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            entries = [ws.build_metadata('intervals-icu', item, str(item['id'])+'.zwo')
                       for item in self.events()]
            ws.save_metadata_collection(folder, 901, 'intervals-icu', entries)
            ws.remove_metadata_entry(folder, 901, 'intervals-icu', 101)
            payload = ws.load_metadata(folder, 901, 'intervals-icu')
            self.assertEqual(ws.metadata_entries(payload), [entries[1]])
            self.assertEqual(payload['filename'], '102.zwo')


if __name__ == '__main__':
    unittest.main(verbosity=2)
