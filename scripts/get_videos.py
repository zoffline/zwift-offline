"""Download the live Zwift Video catalogue; safe to interrupt and run again."""
import argparse
import copy
import json
import logging
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import time
from urllib.parse import quote
import zlib

import requests

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'storage' / 'mochi'
BASE_URL = 'https://loveturtle.zwift.com/1.0.2/'
MANIFEST = 'watopian/watopian.manifest.json'
BLOCK = 1024 * 1024
LOG = logging.getLogger('video-download')


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def local_path(key):
    p = PurePosixPath(key)
    if not key or p.is_absolute() or '..' in p.parts or '\\' in key or ':' in key:
        raise ValueError('Unsafe manifest path: ' + key)
    result = DEST.joinpath(*p.parts)
    if not result.resolve().is_relative_to(DEST.resolve()):
        raise ValueError('Path outside storage/mochi: ' + key)
    return result


def get_files(data):
    if isinstance(data, dict):
        if all(k in data for k in ('key', 'crc', 'size')):
            yield data
        for value in data.values():
            yield from get_files(value)
    elif isinstance(data, list):
        for value in data:
            yield from get_files(value)


def unique_files(data):
    files = {}
    for entry in get_files(data):
        key = entry['key']
        local_path(key)
        item = {'key': key, 'size': int(entry['size']), 'crc': int(entry['crc']) & 0xffffffff}
        if item['size'] < 0:
            raise ValueError('Negative file size')
        if key in files and files[key] != item:
            raise ValueError('Conflicting manifest entries: ' + key)
        files[key] = item
    return list(files.values())


def crc_file(path):
    crc = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(BLOCK), b''):
            crc = zlib.crc32(block, crc)
    return crc & 0xffffffff


def valid(path, item):
    return path.is_file() and path.stat().st_size == item['size'] and crc_file(path) == item['crc']


def select_manifest(data, names, resolution):
    selected = copy.deepcopy(data)
    found = set()
    for collection in selected['collections']:
        rides = []
        for ride in collection['rides']:
            if names and ride['name'].casefold() not in names and ride.get('pretty_name', '').casefold() not in names:
                continue
            found.update((ride['name'].casefold(), ride.get('pretty_name', '').casefold()))
            ride['resolutions'] = [r for r in ride['resolutions'] if r['resolution'] == resolution]
            if not ride['resolutions']:
                raise ValueError(f"{ride['name']}: {resolution} unavailable")
            rides.append(ride)
        collection['rides'] = rides
    selected['collections'] = [c for c in selected['collections'] if c['rides']]
    if names and names - found:
        raise ValueError('Unknown routes: ' + ', '.join(sorted(names - found)))
    if not selected['collections']:
        raise ValueError('No routes found')
    return selected


class Downloader:
    def __init__(self, args):
        self.args = args
        self.http = requests.Session()
        self.http.headers.update({'User-Agent': 'zoffline-local-video/1.0', 'Accept-Encoding': 'identity'})
        self.status_path = ROOT / 'logs' / 'video-download-status.json'
        self.status = dict(started=time.strftime('%Y-%m-%dT%H:%M:%S%z'), pid=os.getpid(),
                           manifest=BASE_URL + MANIFEST, resolution=args.resolution,
                           state='starting', routes=0, files=0, total_bytes=0, completed_bytes=0,
                           existing_files=0, downloaded_files=0, transferred_bytes=0,
                           errors=0, failed_files=[], current_file=None, current_bytes=0)
        self.last_progress = 0

    def progress(self, force=False):
        if not force and time.monotonic() - self.last_progress < 10:
            return
        self.last_progress = time.monotonic()
        s = self.status
        s['updated'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        atomic_json(self.status_path, s)
        LOG.info('%s | files %d/%d | existing %d | downloaded %d | verified %.3f/%.3f GB | current %.1f MB | network %.3f GB | errors %d | failed %d',
                 s['state'], s['existing_files'] + s['downloaded_files'], s['files'],
                 s['existing_files'], s['downloaded_files'], s['completed_bytes'] / 1e9,
                 s['total_bytes'] / 1e9, s['current_bytes'] / 1e6,
                 s['transferred_bytes'] / 1e9, s['errors'], len(s['failed_files']))

    def manifest(self):
        for attempt in range(self.args.retries):
            try:
                with self.http.get(BASE_URL + MANIFEST, timeout=(15, 60)) as r:
                    r.raise_for_status()
                    data = r.json()
                if not isinstance(data.get('collections'), list):
                    raise ValueError('Invalid manifest')
                atomic_json(ROOT / 'logs' / 'video-manifest-source.json', data)
                return data
            except (requests.RequestException, ValueError) as exc:
                LOG.warning('Manifest attempt %d: %s', attempt + 1, exc)
                if attempt + 1 == self.args.retries:
                    raise
                time.sleep(min(60, 2 ** (attempt + 1)))

    def transfer(self, item):
        target = local_path(item['key'])
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + '.part')
        meta_path = target.with_name(target.name + '.part.json')
        # Resume only bytes that belong to this exact manifest entry.
        if part.exists():
            try:
                matching = json.loads(meta_path.read_text('utf-8')) == item
            except (OSError, ValueError):
                matching = False
            if not matching or part.stat().st_size > item['size']:
                part.unlink()
        atomic_json(meta_path, item)
        offset = part.stat().st_size if part.exists() else 0
        if offset == item['size'] and valid(part, item):
            os.replace(part, target)
            meta_path.unlink(missing_ok=True)
            return
        if offset == item['size']:
            part.unlink()
            offset = 0
        if shutil.disk_usage(DEST).free < item['size'] - offset + 2 * 1024**3:
            raise OSError('Less than 2 GiB reserve: download stopped to protect disk space')
        headers = {'Range': f'bytes={offset}-'} if offset else {}
        with self.http.get(BASE_URL + quote(item['key'], safe='/'), headers=headers,
                           stream=True, timeout=(15, 60)) as r:
            r.raise_for_status()
            if offset and r.status_code == 206:
                expected = f"bytes {offset}-{item['size'] - 1}/{item['size']}"
                if r.headers.get('Content-Range') != expected:
                    raise ValueError('Invalid Content-Range: ' + str(r.headers.get('Content-Range')))
            elif r.status_code == 200:
                offset = 0  # Server does not support Range; safely restart this file.
            else:
                raise ValueError(f'Unexpected HTTP status {r.status_code}')
            self.status['current_bytes'] = offset
            with part.open('ab' if offset else 'wb') as stream:
                for block in r.iter_content(BLOCK):
                    if not block:
                        continue
                    if stream.tell() + len(block) > item['size']:
                        raise ValueError('Response exceeds manifest size')
                    stream.write(block)
                    self.status['transferred_bytes'] += len(block)
                    self.status['current_bytes'] += len(block)
                    self.progress()
                stream.flush()
                os.fsync(stream.fileno())
        if not valid(part, item):
            # A short response may resume; a complete but corrupt file must restart.
            if part.stat().st_size >= item['size']:
                part.unlink()
            raise ValueError('Size/CRC mismatch: ' + item['key'])
        os.replace(part, target)
        meta_path.unlink(missing_ok=True)

    def download(self, item):
        for attempt in range(self.args.retries):
            try:
                self.transfer(item)
                LOG.info('OK %s size=%d crc=%d', item['key'], item['size'], item['crc'])
                return True
            except (requests.RequestException, OSError, ValueError) as exc:
                self.status['errors'] += 1
                LOG.error('Attempt %d/%d %s: %s', attempt + 1, self.args.retries, item['key'], exc)
                if isinstance(exc, OSError) and not isinstance(exc, requests.RequestException):
                    raise  # Disk / permission failures must not continue filling the drive.
                if attempt + 1 < self.args.retries:
                    time.sleep(min(60, 2 ** (attempt + 1)))
        return False

    def run(self):
        LOG.info('START %s manifest=%s', self.status['started'], BASE_URL + MANIFEST)
        data = self.manifest()
        rides = [r for c in data['collections'] for r in c['rides']]
        if self.args.list:
            for ride in rides:
                print(f"{ride['name']:22} {ride.get('pretty_name', '')} | " + ', '.join(r['resolution'] for r in ride['resolutions']))
            print(f'{len(rides)} routes')
            return 0
        selected = select_manifest(data, {n.casefold() for n in self.args.route}, self.args.resolution)
        files = unique_files(selected)
        routes = [r['name'] for c in selected['collections'] for r in c['rides']]
        total = sum(f['size'] for f in files)
        LOG.info('PLAN routes=%d files=%d bytes=%d (%.3f GB / %.3f GiB) resolution=%s',
                 len(routes), len(files), total, total / 1e9, total / 1024**3, self.args.resolution)
        LOG.info('ROUTES %s', ', '.join(routes))
        self.status.update(routes=len(routes), route_names=routes, files=len(files), total_bytes=total)
        atomic_json(ROOT / 'logs' / 'video-download-plan.json', dict(self.status, entries=files))
        if self.args.plan:
            return 0
        if self.args.max_files:
            files = files[:self.args.max_files]
            self.status.update(files=len(files), total_bytes=sum(f['size'] for f in files), sample=True)
        DEST.mkdir(parents=True, exist_ok=True)
        self.status['state'] = 'checking'
        pending = []
        for item in files:
            self.status['current_file'] = item['key']
            if valid(local_path(item['key']), item):
                self.status['existing_files'] += 1
                self.status['completed_bytes'] += item['size']
                LOG.info('SKIP verified %s bytes=%d', item['key'], item['size'])
            else:
                pending.append(item)
            self.progress()
        free = shutil.disk_usage(DEST).free
        required = sum(f['size'] for f in pending)
        # Account for trustworthy partial downloads when checking remaining space.
        for item in pending:
            p = local_path(item['key'])
            part = p.with_name(p.name + '.part')
            meta = p.with_name(p.name + '.part.json')
            try:
                if json.loads(meta.read_text('utf-8')) == item:
                    required -= min(part.stat().st_size, item['size'])
            except (OSError, ValueError):
                pass
        initial_full = self.args.all and not self.args.max_files and not self.status['existing_files'] and required == total
        if initial_full and free < 160_000_000_000:
            raise OSError('First full download requires at least 160 GB free')
        if free < required + 10_000_000_000:
            raise OSError(f'Insufficient free space: {free} bytes free, {required} + 10 GB reserve required')
        # A sample never overwrites a previously complete local catalogue.
        if not self.args.max_files:
            atomic_json(local_path(MANIFEST + '.pending'), selected)
        self.status['state'] = 'downloading'
        self.progress(True)
        for round_no in range(self.args.retry_rounds + 1):
            failed = []
            if round_no and pending:
                LOG.warning('Retry round %d for %d files after 30 seconds', round_no, len(pending))
                time.sleep(30)
            for item in pending:
                self.status.update(current_file=item['key'], current_bytes=0)
                if self.download(item):
                    self.status['downloaded_files'] += 1
                    self.status['completed_bytes'] += item['size']
                else:
                    failed.append(item)
                self.status['failed_files'] = [f['key'] for f in failed]
                self.status['current_bytes'] = 0
                self.progress()
            pending = failed
            if not pending:
                break
        self.status.update(state='incomplete' if pending else ('sample_complete' if self.args.max_files else 'complete'),
                           failed_files=[f['key'] for f in pending], current_file=None, current_bytes=0)
        if not pending and not self.args.max_files:
            destination = local_path(MANIFEST)
            if destination.exists():
                shutil.copy2(destination, ROOT / 'backups' / ('video-manifest-' + time.strftime('%Y%m%d-%H%M%S') + '.json'))
            # Only publish routes after all selected files are CRC verified.
            atomic_json(destination, selected)
            local_path(MANIFEST + '.pending').unlink(missing_ok=True)
        self.progress(True)
        LOG.info('END status=%s failed=%d', self.status['state'], len(pending))
        return 1 if pending else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--all', action='store_true')
    choice.add_argument('--list', action='store_true')
    choice.add_argument('--route', action='append', default=[], help='Manifest name or display name; repeatable')
    parser.add_argument('--resolution', default='1080p')
    parser.add_argument('--plan', action='store_true', help='Fetch manifest and report total size without downloading')
    parser.add_argument('--max-files', type=int, help='Download only first N files for a smoke test; do not publish manifest')
    parser.add_argument('--retries', type=int, default=4)
    parser.add_argument('--retry-rounds', type=int, default=1)
    args = parser.parse_args()
    if args.retries < 1 or args.retry_rounds < 0 or (args.max_files is not None and args.max_files < 1):
        parser.error('Invalid retry/file count')
    (ROOT / 'logs').mkdir(exist_ok=True)
    (ROOT / 'backups').mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.FileHandler(ROOT / 'logs' / 'video-download.log', encoding='utf-8'),
                                  logging.StreamHandler(sys.stdout)])
    # OS lock releases even on crash; stale PID files cannot block a later restart.
    with (ROOT / 'logs' / 'video-download.lock').open('a+b') as lock:
        try:
            # Windows denies reads of another process's locked byte too.
            if os.fstat(lock.fileno()).st_size == 0:
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            LOG.error('Another video downloader is already running')
            return 2
        runner = Downloader(args)
        try:
            return runner.run()
        except KeyboardInterrupt:
            runner.status['state'] = 'interrupted'
            runner.progress(True)
            LOG.warning('Cancelled with Ctrl+C; .part files retained. Run the same command to resume.')
            return 130
        except Exception:
            runner.status['state'] = 'error'
            runner.progress(True)
            LOG.exception('Download stopped; safe to restart')
            return 1
        finally:
            runner.http.close()


if __name__ == '__main__':
    sys.exit(main())
