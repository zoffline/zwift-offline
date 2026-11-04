#!/usr/bin/env python3
"""Builds data/road_limits.json for solo_blob.py from rides recorded in the game.

Every recorded ghost / RoboPacer route holds the real roadPosition of a rider on a road. In Zwift the road
centre line (roadPosition 10,000,000) is a wall: forward riders stay on the + side, riders going the other
way on the - side, and the outer edge differs per road. The blob needs that to keep its riders off the
invisible wall (the game pulls anybody who crosses it back, which looks like a rider steering into a wall).

Output: {"<course>:<road>:<f|r>" (f = the + side of the centre line, r = the - side): [inner, outer], ...}  (metres from the centre line, always positive: the side
of the road a rider may use runs from `inner` to `outer`; inner is NOT always 0, e.g. London keeps ~1.5 m off the line)
Also writes data/road_width_profile.json (with --xml): how the width changes along a road.
Usage:  python3 scripts/gen_road_limits.py
"""
import argparse
import collections
import json
import os
import statistics
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'protobuf'))

import udp_node_msgs_pb2  # noqa: E402
from peloton import plus_side_forward  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import zwift_wad  # noqa: E402

CENTER = 10000000
UNITS_PER_M = 100000.0
MIN_SAMPLES = 150          # roads with fewer recorded samples fall back to the configured width
OUTER_PERCENTILE = 99.0    # riders rarely touch the real edge, p99 is a safe outer limit
INNER_PERCENTILE = 1.0     # the invisible wall next to the centre line: the closest 1% of riders are AT the wall
MIRROR_BELOW = 1000        # a direction with fewer samples than this takes the inner edge of the other direction when that has enough
MIN_OUTER_M, MAX_OUTER_M = 2.3, 6.0
XML_OUTER_RATIO = 0.77     # measured: p99 of recorded riders / (road.xml width / 2) is ~0.77 on roads that have both
XML_INNER_M = 0.8          # road.xml has no equivalent of the invisible wall next to the centre line, use a typical value
# <world> directory number in the game's Worlds/ -> course id (courses_lookup in zwift_offline.py)
WORLD_COURSE = {1: 6, 2: 2, 3: 7, 4: 8, 5: 9, 6: 10, 7: 11, 8: 12, 9: 13, 10: 14, 11: 15, 12: 16, 13: 17}
PROFILE_STEPS = 200        # the width along a road is sampled this many times (roadTime 0..1)
PROFILE_MIN_FACTOR, PROFILE_MAX_FACTOR = 0.6, 1.25    # the recorded rides stay in charge of the overall level
PROFILE_MIN_CHANGE = 0.1   # a road whose width changes less than this (relative) has no profile
SAMPLE_EVERY = 5           # states are ~1 per second of riding, no need for all of them


def course_of(state):
    return (state.f19 & 0xff0000) >> 16


def road_of(state):
    return (state.aux3 & 0xff00) >> 8


def route_files():
    for base in (os.path.join(ROOT, 'storage'), os.path.join(ROOT, 'pace_partners')):
        for root, _, files in os.walk(base):
            for name in files:
                if name == 'route.bin' or (name.endswith('.bin') and os.sep + 'ghosts' in root + os.sep):
                    yield os.path.join(root, name)


GAME_ASSETS = (        # where the game keeps its .wad files
    os.path.expanduser('~/Library/Application Support/Zwift/assets'),
    os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), 'Zwift', 'assets'),
    os.path.expanduser('~/Documents/Zwift/assets'),
)


def road_xml_texts(source):
    """{world number: text of its road.xml}. `source` is a directory with worldN/road.xml (already extracted), a game
    'assets' directory (worldN/data_1.wad is read directly, see scripts/zwift_wad.py), or 'auto' to look for the game."""
    if source == 'auto':
        source = next((d for d in GAME_ASSETS if os.path.isdir(os.path.join(d, 'Worlds'))), None)
        if source is None:
            sys.exit('Zwift assets not found, give the directory: --xml DIR')
    texts = {}
    for world in WORLD_COURSE:
        loose = os.path.join(source, 'world%d' % world, 'road.xml')
        wad = os.path.join(source, 'Worlds', 'world%d' % world, 'data_1.wad')
        if os.path.exists(loose):
            with open(loose, encoding='utf-8', errors='replace') as f:
                texts[world] = f.read()
        elif os.path.exists(wad):
            files = dict(zwift_wad.entries(zwift_wad.read_wad(wad)))
            if 'Worlds/world%d/road.xml' % world in files:
                texts[world] = files['Worlds/world%d/road.xml' % world].decode('utf-8', 'replace')
    return texts


def xml_road_widths(source):
    """({(course, road): half width in metres}, {(course, road): [[t1, t2, factor], ...]}) from the game's road.xml files
    (widths are in cm). Only roads that state a width are returned (about a third of them): the median of the road's
    markers' m_roadWidth, else defaultRoadWidth. The second dict is the width along the road (roadTime 0..1) relative
    to that median, only for roads whose width really changes; where markers overlap the narrowest wins."""
    half, profile = {}, {}
    for world, text in road_xml_texts(source).items():
        course = WORLD_COURSE[world]
        root = ET.fromstring(text[text.index('<world'):])      # the file starts with a comment before the xml declaration
        for road in root.iter('road'):
            key = (course, int(road.findtext('id')))
            markers = [(float(e.get('m_roadTime1', 0)), float(e.get('m_roadTime2', 1)), float(e.get('m_roadWidth')))
                       for e in road.iter('ent')
                       if e.get('type') == 'ENTITY_TYPE_ROADMARKER' and e.get('m_roadWidth') and e.get('m_applyWidth', '1') != '0']
            widths = [w for _, _, w in markers]
            if not widths and road.findtext('defaultRoadWidth'):
                widths = [float(road.findtext('defaultRoadWidth'))]
            if not widths:
                continue
            median = statistics.median(widths)
            half[key] = median / 200.0
            segments = width_profile(markers, median)
            if segments:
                profile[key] = segments
    return half, profile


def width_profile(markers, median):
    """Run-length list [[t1, t2, factor]] of the road width relative to `median`, sampled every 1/PROFILE_STEPS of the road
    (factor 1 where no marker says anything); [] when the width hardly changes."""
    factors = []
    for i in range(PROFILE_STEPS):
        t = (i + 0.5) / PROFILE_STEPS
        covering = [w for t1, t2, w in markers if t1 <= t <= t2]
        factors.append(round(min(max(min(covering) / median, PROFILE_MIN_FACTOR), PROFILE_MAX_FACTOR), 2) if covering else 1.0)
    if max(factors) - min(factors) < PROFILE_MIN_CHANGE:
        return []
    segments = []
    for i, factor in enumerate(factors):
        if segments and segments[-1][2] == factor:
            segments[-1][1] = round((i + 1) / PROFILE_STEPS, 4)
        else:
            segments.append([round(i / PROFILE_STEPS, 4), round((i + 1) / PROFILE_STEPS, 4), factor])
    return segments


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--xml', nargs='?', const='auto', metavar='DIR', help="roads without recorded rides get their outer limit from the "
                        "road width in the game's road.xml. DIR: the game's assets directory or a directory with worldN/road.xml "
                        "(default: look for the installed game)")
    args = parser.parse_args()
    samples = collections.defaultdict(list)
    count = 0
    for path in route_files():
        ghost = udp_node_msgs_pb2.Ghost()
        with open(path, 'rb') as f:
            ghost.ParseFromString(f.read())
        count += 1
        for state in ghost.states[::SAMPLE_EVERY]:
            forward = plus_side_forward(state)      # 'f' = the + side of the road: that is where forward riders go, except where traffic is on the left
            lateral = (state.roadPosition - CENTER) / UNITS_PER_M
            if (lateral > 0) == forward and lateral != 0:      # only riders on their own side of the centre line
                samples[(course_of(state), road_of(state), forward)].append(abs(lateral))
    stats = {}
    for (course, road, forward), values in sorted(samples.items()):
        if len(values) < MIN_SAMPLES:
            continue
        values.sort()
        pick = lambda q: values[min(len(values) - 1, int(q / 100.0 * len(values)))]
        stats[(course, road, forward)] = (len(values), pick(INNER_PERCENTILE), pick(OUTER_PERCENTILE))
    table = {}
    for (course, road, forward), (n, inner, outer) in stats.items():
        other = stats.get((course, road, not forward))
        if n < MIRROR_BELOW and other and other[0] >= MIRROR_BELOW:
            inner = other[1]
        outer = min(max(outer, MIN_OUTER_M), MAX_OUTER_M)
        inner = min(max(inner, 0.0), outer - 1.0)
        table['%d:%d:%s' % (course, road, 'f' if forward else 'r')] = [round(inner, 1), round(outer, 1)]
    from_xml = 0
    profile = {}
    if args.xml:
        halves, profile_raw = xml_road_widths(args.xml)
        profile = {'%d:%d' % key: segments for key, segments in sorted(profile_raw.items())}
        for (course, road), half in sorted(halves.items()):
            outer = round(min(max(half * XML_OUTER_RATIO, MIN_OUTER_M), MAX_OUTER_M), 1)
            for direction in 'fr':
                key = '%d:%d:%s' % (course, road, direction)
                if key not in table:
                    table[key] = [XML_INNER_M, outer]
                    from_xml += 1
    out = os.path.join(ROOT, 'data', 'road_limits.json')
    with open(out, 'w') as f:
        json.dump(table, f, indent=0, sort_keys=True)
        f.write('\n')
    profile_out = os.path.join(ROOT, 'data', 'road_width_profile.json')
    if args.xml:
        with open(profile_out, 'w') as f:
            json.dump(profile, f, separators=(',', ':'), sort_keys=True)
            f.write('\n')
    print('%d routes -> %d road limits (%d from road.xml) written to %s, %d road width profiles'
          % (count, len(table), from_xml, out, len(profile)))


if __name__ == '__main__':
    main()
