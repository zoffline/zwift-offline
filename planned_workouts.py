"""Local Intervals workouts exposed using the scheduled-workout API contract."""
import bisect
import datetime
import math
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET


MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_DURATION = 7 * 24 * 3600
ZONE_LIMITS = (0.55, 0.75, 0.90, 1.05, 1.20)


def number(value, default=0):
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) and result >= 0 else default


def planned_day(metadata):
    local = metadata.get('start_date_local')
    if local:
        return datetime.datetime.fromisoformat(local).date()
    value = metadata.get('start_date')
    if not value:
        return None
    parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone().date()


def workout_details(content):
    if b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():
        return None
    root = ET.fromstring(content)
    workout = root.find('workout')
    if root.tag != 'workout_file' or workout is None:
        return None
    # The supplied reference covers cycling; leave running workouts unchanged.
    if (root.findtext('sportType') or 'bike').lower() not in ('bike', 'cycling'):
        return None
    duration = 0
    zones = [0.0] * 6
    known_power = True

    def add(seconds, low=None, high=None):
        nonlocal duration, known_power
        if seconds <= 0:
            return
        duration += seconds
        low = number(low, None)
        high = number(high, None) if high is not None else low
        if low is None or high is None:
            known_power = False
            return
        # Split a linear ramp exactly at power-zone boundaries.
        cuts = [0.0, 1.0]
        if low != high:
            cuts += [(limit - low) / (high - low) for limit in ZONE_LIMITS
                     if min(low, high) < limit < max(low, high)]
        cuts.sort()
        for start, end in zip(cuts, cuts[1:]):
            power = low + (high - low) * (start + end) / 2
            zones[bisect.bisect_left(ZONE_LIMITS, power)] += seconds * (end - start)

    for step in workout:
        if step.tag == 'IntervalsT':
            repeat = number(step.get('Repeat'))
            if repeat < 1 or repeat != int(repeat) or repeat > MAX_DURATION:
                return None
            add(repeat * number(step.get('OnDuration')), step.get('OnPower'))
            add(repeat * number(step.get('OffDuration')), step.get('OffPower'))
        elif step.tag in ('Warmup', 'Cooldown', 'Ramp'):
            add(number(step.get('Duration')), step.get('PowerLow'), step.get('PowerHigh'))
        else:
            add(number(step.get('Duration')), step.get('Power'))
    if duration <= 0 or duration > MAX_DURATION:
        return None
    percentages = [0] * 6
    if known_power:
        exact = [100 * seconds / duration for seconds in zones]
        percentages = [int(value) for value in exact]
        order = sorted(range(6), key=lambda i: exact[i] - percentages[i], reverse=True)
        for i in order[:100 - sum(percentages)]:
            percentages[i] += 1
    return {
        'name': root.findtext('name') or '',
        'description': root.findtext('description') or '',
        'duration': int(round(duration)),
        'zonePercentages': percentages,
        # Zero means unrated; do not invent a workout difficulty estimate.
        'difficulty': min(number(root.findtext('difficulty')), 5),
    }


def build_workout(storage_dir, player_id, metadata, asset_url, today=None):
    """Return one current workout or None; no network calls or state writes.

    asset_url is a callback taking the stable workout UUID. All public response
    fields are kept separate from the local filename and the source bytes.
    """
    if not isinstance(metadata, dict) or metadata.get('provider') != 'intervals-icu':
        return None
    try:
        day = planned_day(metadata)
        if day != (today or datetime.date.today()):
            return None
        event_id = metadata.get('event_id')
        filename = metadata.get('filename')
        if not isinstance(event_id, (str, int)) or isinstance(event_id, bool) or not str(event_id):
            return None
        if (not isinstance(filename, str) or Path(filename).name != filename or
                not filename.startswith('intervals-icu-') or not filename.endswith('.zwo')):
            return None
        profile = Path(storage_dir) / str(player_id)
        folder = profile / 'customworkouts'
        path = folder / filename
        if any(p.is_symlink() for p in (profile, folder, path)):
            return None
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            return None
        content = path.read_bytes()
        if len(content) > MAX_FILE_BYTES:
            return None
        details = workout_details(content)
        if details is None:
            return None
        identity = '%s:intervals-icu:%s' % (player_id, event_id)
        workout_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'zoffline:workout:' + identity))
        schedule_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'zoffline:schedule:' + identity + ':' + day.isoformat()))
        uri = asset_url(workout_id)
        midnight = datetime.datetime.combine(day, datetime.time.min)
        tomorrow = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time.min)
        summary = {
            'description': metadata.get('description') or details['description'],
            'workoutAssetUrl': uri, 'workoutId': workout_id, 'legacyId': 0,
            'name': metadata.get('name') or details['name'],
            'difficulty': details['difficulty'], 'duration': details['duration'],
            'sport': 'CYCLING', 'lastCompletion': None,
            'zonePercentages': details['zonePercentages'],
            'stressPoints': number(metadata.get('icu_training_load')),
            'primaryTrainingFocus': None, 'secondaryTrainingFocus': None,
        }
        schedule = {
            'scheduleId': schedule_id, 'workoutId': workout_id, 'workoutUri': uri,
            'trainingProviderId': 'intervalsicu',
            'availableAfter': int(midnight.timestamp()),
            'notAvailableAfter': int(tomorrow.timestamp()) - 1,
            'workoutSummary': summary,
        }
        home = {'nextUp': {
            'selected': {'entityId': workout_id, 'entityType': 'WORKOUT',
                         'recommendedDurationMinutes': None, 'tags': [],
                         'token': 'Component.Card.Activity'},
            'recommendation': None, 'source': 'SCHEDULED', 'sourceId': schedule_id,
            'explanation': None, 'expires': None, 'title': 'LOC_TODAY_LOWER',
            'provider': 'intervalsicu', 'providerProperties': None, 'metadata': [],
        }}
        return {'id': workout_id, 'filename': filename, 'content': content,
                'schedule': schedule, 'home': home}
    except (OSError, ValueError, TypeError, OverflowError, ET.ParseError):
        return None
