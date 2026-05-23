import hashlib
import os
import xml.etree.ElementTree as ET


MANIFEST_FILENAME = 'workouts.files'


def workouts_dir(root_dir, player_id):
    return os.path.join(root_dir, str(player_id))


def manifest_file(root_dir, player_id):
    return os.path.join(workouts_dir(root_dir, player_id), MANIFEST_FILENAME)


def parse_int(value):
    try:
        return int((value or '0').strip() or '0')
    except ValueError:
        return 0


def file_checksum(content):
    return (-sum(content)) % 256


def file_guid(filename):
    digest = hashlib.sha1(filename.encode('utf-8')).digest()
    return (int.from_bytes(digest[:4], 'big') & 0x7fffffff) or 1


def load_manifest(root_dir, player_id):
    path = manifest_file(root_dir, player_id)
    if not os.path.exists(path):
        return []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    entries = []
    for node in root.findall('custom_file'):
        name = (node.findtext('name') or '').strip()
        if not name:
            continue
        entries.append({
            'name': name,
            'time': parse_int(node.findtext('time')),
            'guid': parse_int(node.findtext('guid')),
            'checksum': parse_int(node.findtext('checksum')),
            'deleted': (node.findtext('deleted') or 'false').strip().lower() == 'true',
        })
    return entries


def save_manifest(root_dir, player_id, entries):
    directory = workouts_dir(root_dir, player_id)
    os.makedirs(directory, exist_ok=True)
    root = ET.Element('custom_file_directory')
    for entry in sorted(entries, key=lambda item: item['name'].lower()):
        node = ET.SubElement(root, 'custom_file')
        ET.SubElement(node, 'name').text = entry['name']
        ET.SubElement(node, 'time').text = str(int(entry['time']))
        ET.SubElement(node, 'guid').text = str(int(entry['guid']))
        ET.SubElement(node, 'checksum').text = str(int(entry['checksum']))
        ET.SubElement(node, 'deleted').text = 'true' if entry.get('deleted') else 'false'
    ET.SubElement(root, 'deleted_files')
    tree = ET.ElementTree(root)
    ET.indent(tree, space='    ')
    path = manifest_file(root_dir, player_id)
    tree.write(path, encoding='utf-8', xml_declaration=False)
    with open(path, 'a', encoding='utf-8') as fd:
        fd.write('\n')
    return path


def upsert_manifest_entry(root_dir, player_id, filename, content, timestamp=None):
    entries = [entry for entry in load_manifest(root_dir, player_id) if entry['name'] != filename]
    timestamp = int(timestamp if timestamp is not None else os.path.getmtime(os.path.join(workouts_dir(root_dir, player_id), filename)))
    entry = {
        'name': filename,
        'time': timestamp,
        'guid': file_guid(filename),
        'checksum': file_checksum(content),
        'deleted': False,
    }
    entries.append(entry)
    save_manifest(root_dir, player_id, entries)
    return entry


def remove_manifest_entries(root_dir, player_id, names):
    names = set(names)
    if not names:
        return 0
    existing = load_manifest(root_dir, player_id)
    remaining = [entry for entry in existing if entry['name'] not in names]
    removed = len(existing) - len(remaining)
    if removed or os.path.exists(manifest_file(root_dir, player_id)):
        save_manifest(root_dir, player_id, remaining)
    return removed


def export_workout(root_dir, player_id, filename, content):
    directory = workouts_dir(root_dir, player_id)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    with open(path, 'wb') as fd:
        fd.write(content)
    timestamp = int(os.path.getmtime(path))
    manifest_entry = upsert_manifest_entry(root_dir, player_id, filename, content, timestamp=timestamp)
    return {
        'path': path,
        'manifest_path': manifest_file(root_dir, player_id),
        'manifest_entry': manifest_entry,
    }


def remove_prefixed_workouts(root_dir, player_id, prefixes):
    directory = workouts_dir(root_dir, player_id)
    if not os.path.isdir(directory):
        return {'removed_files': 0, 'removed_manifest_entries': 0}
    names_to_remove = []
    removed_files = 0
    for name in os.listdir(directory):
        if name == MANIFEST_FILENAME or not any(name.startswith(prefix) for prefix in prefixes):
            continue
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        os.remove(path)
        names_to_remove.append(name)
        removed_files += 1
    removed_manifest_entries = remove_manifest_entries(root_dir, player_id, names_to_remove)
    return {
        'removed_files': removed_files,
        'removed_manifest_entries': removed_manifest_entries,
    }


def health_report(root_dir, player_id, filename):
    directory = workouts_dir(root_dir, player_id)
    path = os.path.join(directory, filename)
    entries = {entry['name']: entry for entry in load_manifest(root_dir, player_id)}
    entry = entries.get(filename)
    report = {
        'directory': directory,
        'path': path,
        'manifest_path': manifest_file(root_dir, player_id),
        'file_exists': os.path.exists(path),
        'manifest_entry_exists': entry is not None,
        'manifest_entry': entry,
    }
    if report['file_exists']:
        with open(path, 'rb') as fd:
            content = fd.read()
        report['expected_checksum'] = file_checksum(content)
        report['expected_guid'] = file_guid(filename)
    else:
        report['expected_checksum'] = None
        report['expected_guid'] = file_guid(filename)
    report['healthy'] = (
        report['file_exists']
        and report['manifest_entry_exists']
        and entry.get('checksum') == report['expected_checksum']
        and int(entry.get('guid') or 0) > 0
    ) if entry else False
    return report
