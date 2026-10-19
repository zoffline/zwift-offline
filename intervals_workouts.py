import datetime
import re
import xml.etree.ElementTree as ET
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
    elif isinstance(value, str):
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            parsed = datetime.datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
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


def matching_workout_metadata(activity, metadata):
    if not isinstance(metadata, dict):
        return None
    values = metadata.get('workouts', [metadata])
    if not isinstance(values, list):
        return None
    matches = [item for item in values if isinstance(item, dict) and activity_matches_workout(activity, item)]
    if len(matches) == 1 and 'workouts' not in metadata:
        return matches[0]
    # Date alone cannot identify one of several workouts. Only an exact,
    # unique workout title may disambiguate; otherwise let the provider pair.
    name = (getattr(activity, 'name', None) or '').strip().casefold()
    matches = [item for item in matches if name and (item.get('name') or '').strip().casefold() == name]
    return matches[0] if len(matches) == 1 else None


def upload_activity(athlete_id, api_key, activity, workout_metadata=None, session=None, base_url=DEFAULT_BASE_URL):
    session = session or __import__("requests")
    paired_event_id = None
    workout_metadata = matching_workout_metadata(activity, workout_metadata)
    if workout_metadata:
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


def sync_workout(athlete_id, api_key, store_workout, today=None, now=None, session=None, base_url=DEFAULT_BASE_URL, timeout=30):
    today = today or datetime.date.today()
    now = now or datetime.datetime.now(datetime.timezone.utc)
    session = session or __import__("requests")

    query = urlencode({
        "oldest": today.isoformat(),
        "newest": today.isoformat(),
        "category": "WORKOUT",
    })
    events_url = f"{base_url}/athlete/{athlete_id}/events?{query}"
    events_response = session.get(events_url, auth=HTTPBasicAuth("API_KEY", api_key), timeout=timeout)
    events_response.raise_for_status()
    unique = {}
    for event in normalize_events_payload(events_response.json()):
        if not isinstance(event, dict):
            continue
        event_id = event.get('id')
        if isinstance(event_id, bool) or not str(event_id).isdigit() or int(event_id) <= 0:
            continue
        date_value = event.get('start_date_local') or event.get('start_date') or event.get('date')
        parsed = parse_datetime(date_value)
        event_day = parsed.date() if parsed and event.get('start_date_local') else parsed.astimezone().date() if parsed else None
        if event_day != today or event.get('category', 'WORKOUT') != 'WORKOUT':
            continue
        unique[str(event_id)] = event
    events = sorted(unique.values(), key=lambda event: (str(event.get('start_date_local') or event.get('start_date') or event.get('date')), str(event['id'])))
    if not events:
        return {"status": "no_workout", "message": f"No Intervals.icu workout found for {today.isoformat()}"}

    # Download and validate the complete batch before touching stored files.
    downloaded = []
    for event in events:
        workout_url = f"{base_url}/athlete/{athlete_id}/events/{event['id']}/download.zwo"
        response = session.get(workout_url, auth=HTTPBasicAuth("API_KEY", api_key), timeout=timeout)
        response.raise_for_status()
        content = response.content
        if (len(content) > 16 * 1024 * 1024 or b'<!DOCTYPE' in content.upper() or
                b'<!ENTITY' in content.upper() or ET.fromstring(content).tag != 'workout_file'):
            raise ValueError('Invalid Intervals workout file')
        downloaded.append((build_workout_filename(event), content, event))
    for filename, content, event in downloaded:
        store_workout(filename, content, event)
    return {
        "status": "synced",
        "event": events[0], "filename": downloaded[0][0],
        "events": events, "filenames": [item[0] for item in downloaded], "count": len(downloaded),
        "message": f"Synced {len(downloaded)} Intervals.icu workouts.",
    }
