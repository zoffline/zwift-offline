import hashlib
import os
import xml.etree.ElementTree as ET


MANIFEST_FILENAME = 'workouts.files'


def manifest_file(workouts_dir):
    return os.path.join(workouts_dir, MANIFEST_FILENAME)


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


def load_manifest(workouts_dir):
    path = manifest_file(workouts_dir)
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


def save_manifest(workouts_dir, entries):
    os.makedirs(workouts_dir, exist_ok=True)
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
    path = manifest_file(workouts_dir)
    tree.write(path, encoding='utf-8', xml_declaration=False)
    with open(path, 'a', encoding='utf-8') as fd:
        fd.write('\n')
    return path


def upsert_manifest_entry(workouts_dir, filename, content, timestamp=None):
    entries = [entry for entry in load_manifest(workouts_dir) if entry['name'] != filename]
    timestamp = int(timestamp if timestamp is not None else os.path.getmtime(os.path.join(workouts_dir, filename)))
    entry = {
        'name': filename,
        'time': timestamp,
        'guid': file_guid(filename),
        'checksum': file_checksum(content),
        'deleted': False,
    }
    entries.append(entry)
    save_manifest(workouts_dir, entries)
    return entry


def remove_prefixed_workouts(workouts_dir, prefixes):
    entries = load_manifest(workouts_dir)
    removed = 0
    for entry in entries:
        if entry['name'].startswith(tuple(prefixes)):
            entry['deleted'] = True
            removed += 1
    save_manifest(workouts_dir, entries)
    return removed
