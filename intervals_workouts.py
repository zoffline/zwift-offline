import datetime
import re
from io import BytesIO
from urllib.parse import urlencode

from requests.auth import HTTPBasicAuth


DEFAULT_BASE_URL = "https://intervals.icu/api/v1"


def normalize_events_payload(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("events", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        parsed = value
    else:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            parsed = datetime.datetime.fromisoformat(value)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def parse_event_datetime(event):
    value = event.get("start_date_local") or event.get("start_date") or event.get("date")
    return parse_datetime(value)


def choose_workout_event(events, now=None):
    if not events:
        return None
    now = now or datetime.datetime.now(datetime.timezone.utc)
    ordered = sorted(events, key=lambda event: parse_event_datetime(event) or datetime.datetime.max.replace(tzinfo=datetime.timezone.utc))
    future = [event for event in ordered if (parse_event_datetime(event) or now) >= now]
    if future:
        return future[0]
    return ordered[-1]


def slugify_filename(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def build_workout_filename(event):
    event_id = event.get("id", "workout")
    name = slugify_filename(event.get("name") or f"workout-{event_id}")
    if not name:
        name = f"workout-{event_id}"
    return f"intervals-icu-{event_id}-{name}.zwo"


def build_activity_upload_url(base_url, athlete_id, activity_name, paired_event_id=None):
    params = {"name": activity_name}
    if paired_event_id:
        params["paired_event_id"] = paired_event_id
    return f"{base_url}/athlete/{athlete_id}/activities?{urlencode(params)}"


def activity_matches_workout(activity, workout_metadata):
    if not workout_metadata:
        return False
    event_dt = parse_datetime(workout_metadata.get("start_date_local") or workout_metadata.get("start_date") or workout_metadata.get("synced_for_date"))
    activity_dt = parse_datetime(getattr(activity, "start_date", None) or getattr(activity, "date", None))
    if not event_dt or not activity_dt:
        return False
    return event_dt.date() == activity_dt.date()


def upload_activity(athlete_id, api_key, activity, workout_metadata=None, session=None, base_url=DEFAULT_BASE_URL):
    session = session or __import__("requests")
    paired_event_id = None
    if activity_matches_workout(activity, workout_metadata):
        paired_event_id = workout_metadata.get("event_id") or workout_metadata.get("id")
    upload_url = build_activity_upload_url(base_url, athlete_id, activity.name, paired_event_id=paired_event_id)
    upload_response = session.post(upload_url, files={"file": BytesIO(activity.fit)}, auth=HTTPBasicAuth("API_KEY", api_key), timeout=30)
    upload_response.raise_for_status()
    if paired_event_id:
        mark_done_url = f"{base_url}/athlete/{athlete_id}/events/{paired_event_id}/mark-done"
        mark_done_response = session.post(mark_done_url, auth=HTTPBasicAuth("API_KEY", api_key), timeout=30)
        mark_done_response.raise_for_status()
    return {
        "status": "uploaded",
        "paired": bool(paired_event_id),
        "paired_event_id": paired_event_id,
    }


def sync_workout(athlete_id, api_key, store_workout, today=None, now=None, session=None, base_url=DEFAULT_BASE_URL):
    today = today or datetime.date.today()
    now = now or datetime.datetime.now(datetime.timezone.utc)
    session = session or __import__("requests")

    query = urlencode({
        "oldest": today.isoformat(),
        "newest": today.isoformat(),
        "category": "WORKOUT",
    })
    events_url = f"{base_url}/athlete/{athlete_id}/events?{query}"
    events_response = session.get(events_url, auth=HTTPBasicAuth("API_KEY", api_key), timeout=30)
    events_response.raise_for_status()
    events = normalize_events_payload(events_response.json())
    event = choose_workout_event(events, now=now)
    if not event:
        return {"status": "no_workout", "message": f"No Intervals.icu workout found for {today.isoformat()}"}

    workout_url = f"{base_url}/athlete/{athlete_id}/events/{event['id']}/download.zwo"
    workout_response = session.get(workout_url, auth=HTTPBasicAuth("API_KEY", api_key), timeout=30)
    workout_response.raise_for_status()

    filename = build_workout_filename(event)
    store_workout(filename, workout_response.content, event)
    return {
        "status": "synced",
        "event": event,
        "filename": filename,
        "message": f"Synced Intervals.icu workout: {event.get('name', filename)}",
    }
