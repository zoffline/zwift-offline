import datetime
import json
import os
import re


def normalize_provider_name(provider):
    return re.sub(r'[^a-z0-9]+', '_', provider.lower()).strip('_') or 'provider'


def metadata_file(storage_dir, player_id, provider):
    return os.path.join(storage_dir, str(player_id), f'{normalize_provider_name(provider)}_workout.json')


def build_metadata(provider, workout, filename):
    return {
        'provider': provider,
        'event_id': workout.get('event_id', workout.get('id')),
        'name': workout.get('name', workout.get('title')),
        'filename': filename,
        'start_date_local': workout.get('start_date_local'),
        'start_date': workout.get('start_date'),
        'synced_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def save_metadata(storage_dir, player_id, provider, workout, filename):
    payload = build_metadata(provider, workout, filename)
    file = metadata_file(storage_dir, player_id, provider)
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, 'w') as fd:
        json.dump(payload, fd)
    return payload


def load_metadata(storage_dir, player_id, provider):
    file = metadata_file(storage_dir, player_id, provider)
    if not os.path.exists(file):
        return None
    try:
        with open(file) as fd:
            return json.load(fd)
    except Exception:
        return None


def clear_metadata(storage_dir, player_id, provider):
    file = metadata_file(storage_dir, player_id, provider)
    if os.path.exists(file):
        os.remove(file)


def active_provider_file(storage_dir, player_id):
    return os.path.join(storage_dir, str(player_id), 'active_workout_provider.txt')


def save_active_provider(storage_dir, player_id, provider):
    file = active_provider_file(storage_dir, player_id)
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, 'w') as fd:
        fd.write((provider or '').strip())


def load_active_provider(storage_dir, player_id):
    file = active_provider_file(storage_dir, player_id)
    if not os.path.exists(file):
        return None
    with open(file) as fd:
        provider = fd.read().strip()
    return provider or None


def resolve_active_provider(saved_provider, available_providers):
    available = set(available_providers or set())
    if saved_provider and saved_provider in available:
        return saved_provider
    for candidate in ('intervals-icu', 'trainingpeaks'):
        if candidate in available:
            return candidate
    return None
