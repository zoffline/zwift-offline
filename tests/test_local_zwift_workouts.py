import os
import tempfile
import unittest

from local_zwift_workouts import (
    export_workout,
    file_checksum,
    file_guid,
    health_report,
    load_manifest,
    manifest_file,
    remove_prefixed_workouts,
    save_manifest,
    workouts_dir,
)


class LocalZwiftWorkoutsTests(unittest.TestCase):
    def test_workouts_dir_is_player_scoped(self):
        self.assertEqual(workouts_dir('/tmp/zwift', 1), '/tmp/zwift/1')

    def test_file_checksum_uses_8bit_twos_complement(self):
        self.assertEqual(file_checksum(b'\x01'), 255)
        self.assertEqual(file_checksum(b'ABC'), (-ord('A') - ord('B') - ord('C')) % 256)

    def test_export_workout_creates_file_and_manifest_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = export_workout(tmp, 1, 'intervals-icu-test.zwo', b'<workout_file/>')

            self.assertTrue(os.path.exists(result['path']))
            self.assertTrue(os.path.exists(result['manifest_path']))
            entries = load_manifest(tmp, 1)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]['name'], 'intervals-icu-test.zwo')
            self.assertEqual(entries[0]['guid'], file_guid('intervals-icu-test.zwo'))
            self.assertEqual(entries[0]['checksum'], file_checksum(b'<workout_file/>'))

    def test_export_workout_preserves_unmanaged_manifest_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_manifest(tmp, 1, [{
                'name': 'custom-other.zwo',
                'time': 123,
                'guid': 456,
                'checksum': 78,
                'deleted': False,
            }])

            export_workout(tmp, 1, 'intervals-icu-test.zwo', b'<workout_file/>')

            names = {entry['name'] for entry in load_manifest(tmp, 1)}
            self.assertEqual(names, {'custom-other.zwo', 'intervals-icu-test.zwo'})

    def test_load_manifest_tolerates_bad_numeric_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(workouts_dir(tmp, 1))
            with open(manifest_file(tmp, 1), 'w', encoding='utf-8') as fd:
                fd.write(
                    '<custom_file_directory>'
                    '<custom_file>'
                    '<name>intervals-icu-test.zwo</name>'
                    '<time>bad</time>'
                    '<guid></guid>'
                    '<checksum>also-bad</checksum>'
                    '<deleted>false</deleted>'
                    '</custom_file>'
                    '</custom_file_directory>'
                )

            entries = load_manifest(tmp, 1)
            self.assertEqual(entries[0]['time'], 0)
            self.assertEqual(entries[0]['guid'], 0)
            self.assertEqual(entries[0]['checksum'], 0)

    def test_remove_prefixed_workouts_removes_matching_files_and_manifest_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_workout(tmp, 1, 'intervals-icu-a.zwo', b'a')
            export_workout(tmp, 1, 'trainingpeaks-b.zwo', b'b')
            export_workout(tmp, 1, 'custom-other.zwo', b'c')

            removed = remove_prefixed_workouts(tmp, 1, {'intervals-icu-'})

            self.assertEqual(removed['removed_files'], 1)
            self.assertFalse(os.path.exists(os.path.join(tmp, '1', 'intervals-icu-a.zwo')))
            self.assertTrue(os.path.exists(os.path.join(tmp, '1', 'trainingpeaks-b.zwo')))
            self.assertTrue(os.path.exists(os.path.join(tmp, '1', 'custom-other.zwo')))
            names = {entry['name'] for entry in load_manifest(tmp, 1)}
            self.assertEqual(names, {'trainingpeaks-b.zwo', 'custom-other.zwo'})

    def test_health_report_detects_consistent_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_workout(tmp, 1, 'intervals-icu-a.zwo', b'a')
            report = health_report(tmp, 1, 'intervals-icu-a.zwo')
            self.assertTrue(report['healthy'])
            self.assertTrue(report['manifest_entry_exists'])
            self.assertEqual(report['manifest_entry']['guid'], file_guid('intervals-icu-a.zwo'))

    def test_health_report_detects_manifest_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_workout(tmp, 1, 'intervals-icu-a.zwo', b'a')
            save_manifest(tmp, 1, [{
                'name': 'intervals-icu-a.zwo',
                'time': 123,
                'guid': 999,
                'checksum': 42,
                'deleted': False,
            }])
            report = health_report(tmp, 1, 'intervals-icu-a.zwo')
            self.assertFalse(report['healthy'])
            self.assertTrue(os.path.exists(manifest_file(tmp, 1)))


if __name__ == '__main__':
    unittest.main()
