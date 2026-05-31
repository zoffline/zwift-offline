import os
import re


PARTNER_ACCESS_MESSAGE = (
    'TrainingPeaks automatic sync requires approved partner API access and app credentials. '
    'This provider is scaffolded but not yet live-configured.'
)


def slugify_filename(value):
    value = (value or '').strip().lower()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    return value.strip('-')


def build_workout_filename(workout):
    workout_id = workout.get('id', 'workout')
    name = slugify_filename(workout.get('name') or workout.get('title') or f'workout-{workout_id}')
    if not name:
        name = f'workout-{workout_id}'
    return f'trainingpeaks-{workout_id}-{name}.zwo'


def build_exported_filename(path):
    base = os.path.splitext(os.path.basename(path))[0]
    slug = slugify_filename(base)
    if not slug:
        slug = 'workout'
    return f'trainingpeaks-{slug}.zwo'


def sync_exported_workouts(folder, store_workout):
    if not folder or not os.path.isdir(folder):
        return {
            'status': 'missing_folder',
            'message': 'TrainingPeaks bridge folder is missing or unreadable.',
        }
    entries = []
    for name in sorted(os.listdir(folder), key=lambda item: item.lower()):
        path = os.path.join(folder, name)
        if not os.path.isfile(path) or not name.lower().endswith('.zwo'):
            continue
        with open(path, 'rb') as fd:
            content = fd.read()
        filename = build_exported_filename(path)
        workout = {'title': os.path.splitext(name)[0], 'source_path': path}
        store_workout(filename, content, workout)
        entries.append(filename)
    if not entries:
        return {
            'status': 'no_workout',
            'message': 'No .zwo workouts were found in the TrainingPeaks bridge folder.',
            'count': 0,
        }
    return {
        'status': 'synced',
        'message': f'Imported {len(entries)} TrainingPeaks workout(s) from bridge folder.',
        'count': len(entries),
        'filenames': entries,
    }


def sync_workout(credentials=None, **kwargs):
    return {
        'status': 'unsupported',
        'message': PARTNER_ACCESS_MESSAGE,
        'credentials_present': bool(credentials),
    }


def upload_activity(credentials=None, activity=None, **kwargs):
    return {
        'status': 'unsupported',
        'message': PARTNER_ACCESS_MESSAGE,
        'credentials_present': bool(credentials),
        'activity_present': activity is not None,
    }
