import datetime
import unittest
from types import SimpleNamespace

from intervals_workouts import sync_workout, upload_activity


class FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200):
        self._payload = payload
        self.content = content
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def _pop(self):
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self._pop()

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self._pop()


class SyncWorkoutTests(unittest.TestCase):
    def test_sync_workout_downloads_next_planned_workout_and_saves_it(self):
        now = datetime.datetime(2026, 4, 22, 10, 30, tzinfo=datetime.timezone.utc)
        session = FakeSession([
            FakeResponse(payload={
                "events": [
                    {
                        "id": 41,
                        "name": "Morning opener",
                        "start_date_local": "2026-04-22T08:00:00+00:00",
                    },
                    {
                        "id": 42,
                        "name": "Threshold Session",
                        "start_date_local": "2026-04-22T18:00:00+00:00",
                    },
                ]
            }),
            FakeResponse(content=b"<workout_file />"),
        ])
        saved = []

        result = sync_workout(
            athlete_id="123",
            api_key="secret",
            store_workout=lambda filename, content, event: saved.append((filename, content, event)),
            today=now.date(),
            now=now,
            session=session,
        )

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["event"]["id"], 42)
        self.assertEqual(saved[0][0], "intervals-icu-42-threshold-session.zwo")
        self.assertEqual(saved[0][1], b"<workout_file />")
        self.assertEqual(saved[0][2]["id"], 42)
        self.assertIn("/athlete/123/events?oldest=2026-04-22", session.calls[0][1])
        self.assertTrue(session.calls[1][1].endswith("/athlete/123/events/42/download.zwo"))

    def test_sync_workout_returns_no_workout_when_none_found(self):
        today = datetime.date(2026, 4, 22)
        session = FakeSession([FakeResponse(payload=[])])
        saved = []

        result = sync_workout(
            athlete_id="123",
            api_key="secret",
            store_workout=lambda filename, content, event: saved.append((filename, content, event)),
            today=today,
            session=session,
        )

        self.assertEqual(result["status"], "no_workout")
        self.assertEqual(saved, [])
        self.assertEqual(len(session.calls), 1)

    def test_upload_activity_pairs_synced_workout_and_marks_event_done(self):
        activity = SimpleNamespace(
            name="VO2 ride",
            fit=b"FITDATA",
            start_date="2026-04-22T18:05:00Z",
        )
        metadata = {
            "event_id": 42,
            "start_date_local": "2026-04-22T18:00:00+00:00",
            "filename": "intervals-icu-42-threshold-session.zwo",
        }
        session = FakeSession([FakeResponse(), FakeResponse()])

        result = upload_activity(
            athlete_id="123",
            api_key="secret",
            activity=activity,
            workout_metadata=metadata,
            session=session,
        )

        self.assertEqual(result["status"], "uploaded")
        self.assertTrue(result["paired"])
        self.assertIn("paired_event_id=42", session.calls[0][1])
        self.assertEqual(session.calls[0][0], "POST")
        self.assertEqual(session.calls[1][1], "https://intervals.icu/api/v1/athlete/123/events/42/mark-done")
        uploaded = session.calls[0][2]["files"]["file"]
        self.assertEqual(uploaded.read(), b"FITDATA")

    def test_upload_activity_without_matching_synced_workout_skips_pairing(self):
        activity = SimpleNamespace(
            name="VO2 ride",
            fit=b"FITDATA",
            start_date="2026-04-23T06:00:00Z",
        )
        metadata = {
            "event_id": 42,
            "start_date_local": "2026-04-22T18:00:00+00:00",
            "filename": "intervals-icu-42-threshold-session.zwo",
        }
        session = FakeSession([FakeResponse()])

        result = upload_activity(
            athlete_id="123",
            api_key="secret",
            activity=activity,
            workout_metadata=metadata,
            session=session,
        )

        self.assertEqual(result["status"], "uploaded")
        self.assertFalse(result["paired"])
        self.assertNotIn("paired_event_id=42", session.calls[0][1])
        self.assertEqual(len(session.calls), 1)


if __name__ == "__main__":
    unittest.main()
