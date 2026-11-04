"""
Solo peloton "blob" for zoffline: virtual riders that swarm around the
LOCAL player himself, in real time - no RoboPacer needed.

The riders ride the actual trail you just rode (real corners, hills and
speed), sit wheel to wheel behind you to use the draft, mix and rotate:
somebody comes up to your handlebars, pulls for a while, then drifts back
through the group and somebody else takes over.

Enable in storage/solo_blob.txt (JSON) or with the in-game chat commands:
  .blob <n>   start/keep a blob of n riders around you
  .blob       show status
  .blob new   same number of riders, new faces
  .blob off   stop

The followers are published into the same registry as RoboPacer pelotons
(zoffline's global_peloton_bots) so the world listing, the nearby stream
and camera following work unchanged. The module does not import
zwift_offline so it can be tested in isolation; its dependencies (game
dictionary, world clock, names) are injected.
"""

import json
import logging
import math
import os
import random
import threading
import time

from google.protobuf.message import DecodeError

import profile_pb2
import udp_node_msgs_pb2

import blob_gestures
from peloton import (course_of, road_of, clamp, lerp, plus_side_forward,
                     ROAD_POSITION_MIN, ROAD_POSITION_MAX, ROAD_POSITION_UNITS_PER_METER)

CONFIG_FILE_NAME = 'solo_blob.txt'
ROAD_POSITION_CENTER = 10000000      # roadPosition of the middle of the road (as in peloton.py)

# equipment taken over from a bot.txt entry (the same list standalone.py uses for bots): the team kit,
# bike, wheels... Anything a rider does not define stays random.
EQUIPMENT_ITEMS = ('bike_frame', 'bike_frame_colour', 'bike_wheel_front', 'bike_wheel_rear', 'glasses_type',
                   'ride_jersey', 'ride_helmet_type', 'ride_shoes_type', 'ride_socks_type',
                   'run_shirt_type', 'run_shorts_type', 'run_shoes_type')

# Rider IDs reserved for blobs: peloton followers live at 8000000+n*1000+i
# (never above 8009200), bookmarks at 9000000+ and ghosts at 10000000+, so
# 8500000..8500399 is free.
RIDER_ID_BASE = 8500000
RIDERS_PER_BLOB = 1000
MAX_BLOBS = 4
MAX_RIDERS = 30
# Every (re)build of a blob draws its rider ids from the next block of
# MAX_RIDERS ids. The game client caches profiles by rider id, so reusing the
# same ids would keep showing the old riders after a restart.
ID_GENERATIONS = RIDERS_PER_BLOB // MAX_RIDERS
_generation = int(time.time()) % ID_GENERATIONS


def next_generation():
    global _generation
    _generation = (_generation + 1) % ID_GENERATIONS
    return _generation


CONFIG_CHECK_INTERVAL_SECONDS = 5
TICK_SECONDS = 0.5

# Zwift protocol units (PlayerState: speed in mm/h, x/y_altitude/z floats)
MMH_PER_MS = 3600000
CM_PER_M = 100

# Trail handling
TRAIL_STALE_SECONDS = 8
TRAIL_MIN_STEP_METERS = 0.2
TRAIL_TELEPORT_METERS = 150
TRAIL_RESTART_JUMP_METERS = 40       # a roadTime drop counts as a ride restart only with a jump in the world this big
TRAIL_PRUNE_METERS = 90
# your state reaches the server ~1 s late; advance the trail head by
# speed x age, otherwise the whole group is always behind by that distance
MAX_ADVANCE_M = 30.0

# your speed is extrapolated with its recent trend (acceleration), otherwise the
# group lags behind on every descent and overshoots when a climb starts
ACCEL_WINDOW_S = 2.5                 # speed trend is measured over at least this long
ACCEL_MAX_WINDOW_S = 6.0             # ...and never over older samples than this
ACCEL_MAX_MS2 = 3.0                  # clamp for the measured acceleration
ACCEL_HORIZON_S = 2.5                # the trend is only trusted this far into the future
GRADE_WINDOW_M = 25.0                # grade is measured over this much road...
GRADE_MIN_WINDOW_M = 8.0             # ...but at least this much (less is just noise)
GRADE_SMOOTHING = 0.25               # weight of the newest grade per tick
MAX_LATENCY_COMP_S = 0.6             # cap for the packet latency compensation (see 'latency_comp')

# Group physics
CLIMB_GRADE_START = 0.02             # the tail starts to stretch gradually from here...
CLIMB_GRADE_FULL = 0.04              # ...and fully from here (no on/off flicker around 3%)
CLIMB_STRETCH_PER_GRADE = 6.0
MAX_ABS_GRADE = 0.25
MAX_LATERAL_CHANGE_PER_S = 0.45      # m/s lateral movement
GAP_NOISE_SIGMA_M = 0.03             # per tick, low-passed (see NOISE_REVERSION)
NOISE_REVERSION = 0.1
MAX_GAP_NOISE_M = 0.1
LATERAL_NOISE_SIGMA_M = 0.05
RATE_SMOOTHING = 0.35                # weight of the newest closing speed, avoids speed jitter
DRAFT_FRACTION = 0.75                # power needed when sitting on a wheel
EFFORT_WHEN_MOVING_UP = 1.18
EFFORT_WHEN_FALLING_BACK = 0.9
PULL_MIN_GAP = 2.2                   # meters behind you for the nearest riders (a bike is ~1.8 m long)
BEHIND_SPEED_MARGIN_S = 0.08         # extra gap per m/s: your position is extrapolated, so keep a margin
PASSING_CLEARANCE_M = 0.9            # sideways offset while a rider passes through your position
MAX_STRETCH_EXTRA_M = 1.0             # a climb stretches the group by at most this much
LEAD_LATERAL_M = 0.8                 # sideways offset of the riders in front (side by side at 1.6 m)
LEAD_SHARE = 0.33                    # share of the group riding in front of you
MAX_LEADERS = 4
MAX_LEAD_ROWS = 5                    # rows in front of you (a row is one rider or a pair side by side)
LEAD_SPEED_MARGIN_S = 0.04           # extra gap per m/s for the riders in front (same reason as BEHIND_...)
MAX_LEAD_M = 12.0                    # furthest ahead of you a lead rider may sit (hard limit)
PASS_ZONE_M = 6.0                    # an overtaking rider slows down this far behind the leader...
PASS_TAKEOVER_M = 1.2                # ...and takes over the front once he is this far ahead of him
FALL_BACK_RATE_M_PER_S = 0.7         # the old leader drifts back to the tail at this speed
LANE_SWAP_ZONE_M = 2.5               # nobody changes sides this close to your position
DROP_SIDE_M = 1.3                    # sideways offset of the old leader while he drifts back

DEFAULT_CONFIG = {
    'enabled': False,
    'riders': 8,
    'row_gap': 1.8,                 # meters between rows (staggered, a bike is ~1.8 m long)
    'tail_gap': 4.0,                # the group tries to stay within this many meters behind you
    'lateral_spacing': 0.95,          # meters between riders side to side
    'lead_gap': 1.6,                 # meters a lead rider sits in front of you
    'lead_lateral': 0.8,             # meters the lead riders sit to the side of you (alternating)
    'columns': 0,                    # max group width (0 = automatic)
    'shuffle_interval': 25,          # average seconds between position changes
    'rotate': True,                  # false = nobody takes the front on their own (gestures still work)
    'pull_interval': 60,             # average seconds between front rotations
    'lead_spread': 1,                # the number of riders in front changes by up to this many at once (0 = fixed)
    'full_range': False,              # true = anything from nobody in front (you lead) to everybody in front (you are last)
    'max_lead': 8,                 # meters: the whole group in front is squeezed into this distance ahead of you
    'diag_interval': 5,             # seconds between diagnostic log lines (0 = off)
    'latency_comp': 0,               # seconds your packets are old when sent (the group then rides that much
                                     # further ahead of the last packet), or "auto" = use the measured
                                     # packet_lag from the diag log line. Matters most at speed (descents).
    'formation_interval': 45,        # average seconds between changes in the formation in front of you
    'turn_interval': 1200,            # every this many seconds YOU take a turn at the front (0 = never)
    'rotation_rate': 0.7,            # m/s the riders move up or back when the line rotates
    'pull_duration': 18,             # seconds a pull lasts
    'pass_time': 18,                 # seconds an overtaking rider needs to get past the leader
    'climb_stretch': 1.0,            # how much the group stretches on climbs
    'max_drop': 30,                  # max meters behind you a rider can sit
    'hammer_time': 180,              # seconds the HAMMER gesture drives a hard pace
    'toast_time': 120,               # seconds the TOAST gesture makes everyone ease off
    'lead_time': 120,                # seconds the BELL gesture keeps you at the front
    'wander_gap': 0.3,               # meters: riders behind you drift randomly this far along the road around
                                     # their slot (0 = off, 0.6-0.9 looks like a real peloton)
    'wander_lateral': 0.15,           # meters: the same sideways (0 = off, 0.25-0.35 is plenty)
    'bot_gestures': True,            # riders of the group give hand signals now and then (elbow flick, toast, nice, bell, ride on)
    'gesture_interval': 75,          # seconds between two random "Ride On" gestures of the group (0 = none)
    'gesture_chance': 1.0,           # scales the chance of every other signal (0 = none, 2 = twice as often)
    'wander_time': 7,                # seconds a drift takes to change direction (higher = slower, calmer)
    'ragged_rows': False,            # true = rows behind you differ in width, spacing and stagger
    'lateral_via': 'both',             # how the sideways offset reaches the game: 'xz' = world position only (the game
                                     # flattens a wide group), 'both' = world position AND roadPosition (like the
                                     # peloton option, recommended), 'road' = roadPosition only
    'lateral_scale': 1.0,            # multiplies every sideways offset on the way out (a last resort if the game still
                                     # shows the group narrower than it is)
    'road_half_width': 3.0,          # meters: half the width of the drivable road around its centre (0 = off). Nobody is ever
                                    # placed outside it: when you ride near an edge the whole group slides sideways (max 0.5 m/s)
                                    # and every single rider is clamped to the road, also while he sidesteps another one.
                                    # 3.0 fits a narrow bridge. Everything below about the axis needs this to be > 0
    'road_limits': 'auto',           # 'auto' = the road centre line is a wall and the side you may ride on depends on your direction
                                    # of travel (forward = + side, the other way = - side); the outer edge comes from real recorded
                                    # rides (data/road_limits.json, scripts/gen_road_limits.py), road_half_width is the fallback
                                    # for roads that are not in the table. 'off' = the fixed zone below (road_axis_limit/side)
    'max_road_shift': 4.0,          # (road_limits 'auto') meters: the most the whole group may slide sideways off you to stay on the road.
                                    # Ride in the middle and the shift is 0; ride at an edge (or next to the invisible wall by the centre
                                    # line) and the group slides just far enough that its outermost rider is in line with you.
                                    # 0 = never slide: the group is squeezed on that side instead
    'road_axis_limit': 1.5,         # (road_limits 'off' only) meters from the road centre (roadPosition 10,000,000) to the road AXIS (the centre line
                                    # you must not cross), measured towards the side given by road_axis_side. Riders beyond it
                                    # get pulled back by the game, which looks like an invisible wall, so the group keeps
                                    # (this - 0.25 m) from it. 0 = no axis, that side ends at road_half_width like the other
    'road_axis_side': -1,           # which side of the road centre the axis is on: -1 = lower roadPosition (default),
                                    # +1 = higher roadPosition. Riders on that side of the group still veer towards the axis?
                                    # then flip it
    'only_kitted': True,            # true = draw the riders only from bot.txt entries that have a team kit
                                    # (the others would ride in a random kit)
    'scatter': True,                # true = riders behind you are scattered over the width of the road
                                    # (blue-noise layout) instead of sitting in rows; ignores columns/tail_gap
    'scatter_width': 3.8,           # meters: how wide the scattered group may spread
    'scatter_gap': 1.75,            # meters along the road between riders of the same lane when scattered
    'scatter_side': 1.3,            # meters: riders that sit level with each other are at least this far apart sideways
                                    # (not shoulder to shoulder; anyone closer sideways is further apart along the road)
    'scatter_beside': 1.2,          # meters sideways at which scattered riders may ride right beside you
    'keep_apart_long': 1.75,        # meters along the road between the centres of two riders (their ellipse, with keep_apart)
    'keep_apart': 0.85,             # meters of sideways clearance riders behind you keep from each other
                                    # (0 = off, 0.8-0.9 = nobody rides through anybody: they go around or wait; a sidestep
                                    # never goes past the road edge or axis, it goes the other way or waits instead)
}

SEP_LONG_M = 1.7                     # keep_apart: bike length plus a little air along the road
KEEP_APART_PATIENCE_S = 5.0          # a rider blocked this long is let through (never a deadlock)

WANDER_FIRST_ROW_LATERAL = 0.5       # the pair on your wheel only drifts sideways, and only half as far
OVERLAP_LONG_M = 1.1                 # a drift is cancelled while it would put a rider this close to another...
OVERLAP_LAT_M = 0.5                  # ...along the road and this close sideways
ROAD_EDGE_MARGIN_M = 0.25            # half a body: nobody's centre gets closer than this to the road edge or axis
MAX_ROAD_HALF_WIDTH_M = 2.6          # riders never wander wider than this from your line
ROAD_LIMITS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'road_limits.json')
MAX_ROAD_SHIFT_M = 4.0               # road_limits 'auto': the most the group may slide sideways off you to stay on the road
DEFAULT_LANE_OUTER_M = 4.4           # outer edge for roads that are not in the table (median of the recorded roads)
DEFAULT_LANE_INNER_M = 1.0           # invisible wall next to the centre line for roads that are not in the table
SQUEEZE_REACH_MARGIN_M = 0.0         # extra reach on top of the outermost slot when the group is squeezed
AXIS_SIDE_TOLERANCE_M = 0.5          # how far the anchor may be on the "wrong" side before his position overrules the forward flag
ROAD_WIDTH_PROFILE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'road_width_profile.json')
ROAD_WIDTH_LOOKAROUND = 0.004        # roadTime (0..1) either side of you in which the narrowest stretch of road counts
ROAD_TIME_UNITS = 1000000.0          # state.roadTime of a whole road
MIN_OUTER_EDGE_M, MAX_OUTER_EDGE_M = 2.3, 6.0
GESTURE_REPEAT_IGNORE_S = 2.0        # the game repeats a gesture while the key is held: only the first counts
_road_limits_cache = None
_road_width_profile_cache = None


def road_width_profile():
    """{"course:road": [[t1, t2, factor], ...]}: how wide the road is along its length (roadTime 0..1) relative to its
    usual width, from the game's road.xml (scripts/gen_road_limits.py --xml). Only roads whose width changes are in it."""
    global _road_width_profile_cache
    if _road_width_profile_cache is None:
        try:
            with open(ROAD_WIDTH_PROFILE_FILE) as f:
                _road_width_profile_cache = {str(k): [(float(a), float(b), float(c)) for a, b, c in v]
                                             for k, v in json.load(f).items()}
        except (OSError, ValueError, AttributeError, TypeError):
            _road_width_profile_cache = {}
    return _road_width_profile_cache


def road_width_factor(course, road, road_time):
    """The road's width where you ride relative to its usual width (1.0 = as in road_limits.json): the narrowest
    factor within ROAD_WIDTH_LOOKAROUND of you, so the group is squeezed a moment before a narrow stretch."""
    segments = road_width_profile().get('%d:%d' % (course, road))
    if not segments:
        return 1.0
    t = road_time / ROAD_TIME_UNITS
    low, high = t - ROAD_WIDTH_LOOKAROUND, t + ROAD_WIDTH_LOOKAROUND
    return min((f for a, b, f in segments if a <= high and b >= low), default=1.0)


def road_limits():
    """{"course:road:f|r": (inner, outer)}: the part of the road, in metres from the centre line, that riders really
    use in that direction. Built by scripts/gen_road_limits.py from recorded rides. `inner` is the invisible wall
    next to the centre line and is NOT always 0 (London: about 1.5 m). Empty when the file is missing."""
    global _road_limits_cache
    if _road_limits_cache is None:
        try:
            with open(ROAD_LIMITS_FILE) as f:
                raw = json.load(f)
            _road_limits_cache = {str(k): ((float(v[0]), float(v[1])) if isinstance(v, (list, tuple)) else (0.0, float(v)))
                                  for k, v in raw.items()}
        except (OSError, ValueError, AttributeError, TypeError, IndexError):
            _road_limits_cache = {}
    return _road_limits_cache


RAGGED_ROW_PATTERN_LEN = 12

# in-game gestures (F-keys) that move the group - UserBikeAction in the proto
GESTURE_ATTACK = udp_node_msgs_pb2.UBA_ELBOW    # F1: "come and pass me"
GESTURE_HAMMER = udp_node_msgs_pb2.UBA_HAMMER   # F4: full gas, segment on
GESTURE_TOAST  = udp_node_msgs_pb2.UBA_TOAST    # F7: easing off
GESTURE_LEAD   = udp_node_msgs_pb2.UBA_BELL     # F8: I want a turn in front


class Trail:
    """Ring of the anchor's recent positions with cumulative distance.

    The trail is what the blob rides on: everything the player already
    rode exists here, so riders placed X meters behind follow real corners
    and hills without needing any knowledge of the future.
    """

    def __init__(self):
        self.entries = []     # list of snapshot dicts (see _snapshot)
        self.distances = []   # cumulative meters, same length
        self.resets = 0       # how many times the trail was restarted
        self.last_heading = (0.0, 0.0)   # last non-zero heading, for standstills
        self.latency_comp = 0.0          # seconds the newest packet is older than its arrival says

    @staticmethod
    def _snapshot(state, lag_s=None):
        proto = udp_node_msgs_pb2.PlayerState()
        proto.CopyFrom(state)
        return {
            'lag': lag_s,     # measured age of the packet on arrival (s), None if unknown; diagnostics only
            'proto': proto,
            't': time.monotonic(),
            'x': state.x,
            'z': state.z,
            'y': state.y_altitude,
            'rt': state.roadTime,
            'rp': state.roadPosition,
            'road': road_of(state),
            'course': course_of(state),
            'sign': 1,        # +1 when roadTime grows along your travel on this road, -1 when it shrinks
            'speed': state.speed / MMH_PER_MS if state.speed else 0.0,
            'power': state.power if state.power else 0,
        }

    def reset(self):
        self.entries = []
        self.distances = []
        self.resets += 1

    def push(self, state, lag_s=None):
        snap = self._snapshot(state, lag_s)
        if not self.entries:
            self.entries.append(snap)
            self.distances.append(0.0)
            return
        last = self.entries[-1]
        dx = snap['x'] - last['x']
        dz = snap['z'] - last['z']
        d = math.hypot(dx, dz) / CM_PER_M
        # a ride restart jumps in roadTime AND in the world. roadTime alone also drops when you ride onto another road
        # or round the end of a lap (the world position stays continuous): that is no new ride, keep the roster
        if (snap['rt'] + 60000 < last['rt'] and d > TRAIL_RESTART_JUMP_METERS) or d > TRAIL_TELEPORT_METERS:
            self.reset()
        if not self.entries:
            self.entries.append(snap)
            self.distances.append(0.0)
            return
        last = self.entries[-1]
        snap['sign'] = last['sign']
        if snap['road'] == last['road'] and abs(snap['rt'] - last['rt']) < 60000 and snap['rt'] != last['rt']:
            snap['sign'] = 1 if snap['rt'] > last['rt'] else -1
        if d < TRAIL_MIN_STEP_METERS:
            if snap['rt'] >= last['rt']:
                self.entries[-1] = snap        # keep the head fresh
            return
        self.entries.append(snap)
        self.distances.append(self.distances[-1] + d)
        self._prune()

    def _prune(self):
        if len(self.entries) < 3:
            return
        keep_from = self.distances[-1] - TRAIL_PRUNE_METERS
        idx = 0
        while idx + 2 < len(self.distances) and self.distances[idx] < keep_from:
            idx += 1
        if idx > 1:
            base = self.distances[idx]
            self.entries = self.entries[idx:]
            self.distances = [d - base for d in self.distances[idx:]]

    def ready(self):
        # need real history to place anybody, and the head must be fresh
        return (len(self.entries) >= 2 and self.distances[-1] > PULL_MIN_GAP + 1.0
                and (time.monotonic() - self.entries[-1]['t']) < TRAIL_STALE_SECONDS)

    def sample_behind(self, gap):
        """Like _sample_behind, but at a standstill (no usable heading) it
        reuses the last known one so the group does not collapse into a
        single point."""
        sampled = self._sample_behind(gap)
        if not sampled:
            return None
        snap, hx, hz = sampled
        if hx == 0.0 and hz == 0.0:
            hx, hz = self.last_heading
        else:
            self.last_heading = (hx, hz)
        return (snap, hx, hz)

    def _sample_behind(self, gap):
        """Interpolated snapshot `gap` meters behind the player's CURRENT
        position (negative gap = that many meters AHEAD, for lead riders).

        The last state packet is ~1 s old, so the trail head is advanced
        by speed x age first - without that the whole group would always
        ride ~10 m behind the anchor even when told to lead.

        Returns (snapshot_dict, heading_x, heading_z) or None.
        """
        if not self.entries:
            return None
        b = self.entries[-1]
        a = self.entries[-2] if len(self.entries) > 1 else b
        _, _, advance = self.motion()
        offset = advance - gap        # meters ahead of the last packet's spot
        if offset >= 0:
            snap = dict(b)
            vx = b['x'] - a['x']
            vz = b['z'] - a['z']
            vlen = math.hypot(vx, vz)
            if vlen < 1.0:
                return (snap, 0.0, 0.0)
            # follow the road curve: estimate curvature from the last three
            # trail points and integrate along the arc instead of projecting
            # a straight line (straight lines fly off the road at corners)
            lead = min(offset, MAX_ADVANCE_M + MAX_LEAD_M)
            ux, uz = vx / vlen, vz / vlen
            # roadTime / roadPosition must move along with x and z, otherwise
            # a rider placed ahead of you is drawn at your last known road
            # position (level with you); extrapolate them with the rate of
            # the last trail step
            rt_rate = rp_rate = y_rate = 0.0
            base = None
            # use a baseline of at least 3 m (less noise); at a crawl on a steep climb
            # that can be many trail entries, so walk back as far as needed
            for j in range(len(self.entries) - 2, -1, -1):
                if self.entries[j]['road'] != b['road']:
                    break
                base = self.entries[j]
                span = self.distances[-1] - self.distances[j]
                if span >= 3.0:
                    break
            if base is not None and span >= 0.5:
                rt_rate = (b['rt'] - base['rt']) / span
                rp_rate = (b['rp'] - base['rp']) / span
                # a rider placed ahead of you on a hill must be higher up the hill too
                max_y_rate = MAX_ABS_GRADE * CM_PER_M
                y_rate = clamp((b['y'] - base['y']) / span, -max_y_rate, max_y_rate)
            if len(self.entries) >= 3:
                c = self.entries[-3]
                ax = a['x'] - c['x']
                az = a['z'] - c['z']
                seg = math.hypot(ax, az)
                if seg > 0.5:
                    dtheta = math.atan2(ax * vz - az * vx, ax * vx + az * vz)
                    k = clamp(dtheta / seg, -0.06, 0.06)
                else:
                    k = 0.0
            else:
                k = 0.0
            x = b['x']
            z = b['z']
            step = 0.25
            n = max(1, int(round(lead / step)))
            cos_k = math.cos(k * step)
            sin_k = math.sin(k * step)
            for _ in range(n):
                ux, uz = ux * cos_k - uz * sin_k, ux * sin_k + uz * cos_k
                x += ux * step * CM_PER_M
                z += uz * step * CM_PER_M
            snap['x'] = x
            snap['z'] = z
            snap['rt'] = b['rt'] + rt_rate * lead
            snap['rp'] = b['rp'] + rp_rate * lead
            snap['y'] = b['y'] + y_rate * lead
            snap['proto'] = b['proto']
            return (snap, ux, uz)
        target = self.distances[-1] + offset
        if target <= self.distances[0]:
            return (dict(self.entries[0]), 0.0, 0.0)
        i = len(self.distances) - 1
        while i > 0 and self.distances[i - 1] > target:
            i -= 1
        a = self.entries[i - 1]
        b = self.entries[i]
        seg = self.distances[i] - self.distances[i - 1]
        f = 0.0 if seg <= 0 else (target - self.distances[i - 1]) / seg
        snap = {}
        # across a change of road (or a lap wrap) roadTime and roadPosition of the two points do not belong
        # together: never average them, take the nearer point's road data
        jump = a['road'] != b['road'] or abs(a['rt'] - b['rt']) > 60000
        src = a if (jump and f < 0.5) else b
        for key in ('x', 'z', 'y'):
            snap[key] = lerp(a[key], b[key], f)
        for key in ('rt', 'rp'):
            snap[key] = src[key] if jump else lerp(a[key], b[key], f)
        snap['proto'] = src['proto']
        snap['speed'] = lerp(a['speed'], b['speed'], f)
        snap['power'] = b['power']
        snap['road'] = src['road']
        snap['course'] = src['course']
        snap['sign'] = src['sign']
        dx = b['x'] - a['x']
        dz = b['z'] - a['z']
        vlen = math.hypot(dx, dz)
        if vlen < 1e-6:
            return (snap, 0.0, 0.0)
        return (snap, dx / vlen, dz / vlen)

    def _accel(self):
        """Trend of the player's speed (m/s^2) over the last few seconds."""
        if len(self.entries) < 3:
            return 0.0
        b = self.entries[-1]
        ref = None
        for j in range(len(self.entries) - 2, -1, -1):
            dt = b['t'] - self.entries[j]['t']
            if dt > ACCEL_MAX_WINDOW_S:
                break
            ref = self.entries[j]
            if dt >= ACCEL_WINDOW_S:
                break
        if ref is None:
            return 0.0
        dt = b['t'] - ref['t']
        if dt < 1.0:       # too short a baseline: packet jitter would look like acceleration
            return 0.0
        return clamp((b['speed'] - ref['speed']) / dt, -ACCEL_MAX_MS2, ACCEL_MAX_MS2)

    def motion(self):
        """(speed_now, accel, advance) of the player RIGHT NOW, extrapolated from the
        last packet: `advance` is how far he has ridden since that packet (meters),
        speed_now his estimated speed this moment (m/s)."""
        b = self.entries[-1]
        age = clamp(time.monotonic() - b['t'] + self.latency_comp, 0.0, TRAIL_STALE_SECONDS)
        v0 = b['speed']
        accel = self._accel()
        t_acc = min(age, ACCEL_HORIZON_S)
        if accel < 0:
            t_acc = min(t_acc, v0 / -accel)      # braking: never rides backwards
        speed_now = max(0.0, v0 + accel * t_acc)
        advance = v0 * t_acc + 0.5 * accel * t_acc * t_acc + speed_now * (age - t_acc)
        return (speed_now, accel, clamp(advance, 0.0, MAX_ADVANCE_M))

    def grade(self):
        """Current grade (m/m) over the last GRADE_WINDOW_M meters of road (a window by
        distance, not by packet count: at a crawl a fixed number of packets is only
        a meter or two and altitude noise would dominate)."""
        n = len(self.entries)
        if n < 3:
            return 0.0
        start = n - 2
        while start > 0 and self.distances[-1] - self.distances[start] < GRADE_WINDOW_M:
            start -= 1
        dist = self.distances[-1] - self.distances[start]
        if dist < GRADE_MIN_WINDOW_M:
            return 0.0
        climb = (self.entries[-1]['y'] - self.entries[start]['y']) / CM_PER_M
        return clamp(climb / dist, -MAX_ABS_GRADE, MAX_ABS_GRADE)


class BlobRider:
    """One follower bot, published like a peloton bot (route = single state)."""

    def __init__(self, rider_id, profile, strength):
        self.id = rider_id
        self.profile = profile
        self.strength = strength
        self.route = udp_node_msgs_pb2.Ghost()
        self.route.states.add()
        self.preference = 'any'
        self.slot = 0
        self.gap = 5.0
        self.lateral = 0.0
        self.pull_phase = None     # None -> 'approach' -> 'pull'
        self.pull_until = 0.0
        self.pull_side = 0.9
        self.power_factor = 1.0
        self.rate = 0.0            # smoothed closing speed (m/s, < 0 when moving up)
        self.dropping = False      # old leader drifting back to the tail
        self.drop_side = 1.0
        self.gap_noise = 0.0
        self.wander_gap = 0.0      # slow random drift around the slot (see 'wander_gap')
        self.wander_lat = 0.0
        self.blocked = 0.0         # seconds the rider has been held back by keep_apart
        self.dbg = {}              # last per-tick decisions, for the debug record

    def fill_state(self, snap, hx, hz, speed_ms, power, via='xz', scale=1.0, road_sign=1, shift=0.0, edges=None):
        st = self.route.states[0]
        st.CopyFrom(snap['proto'])
        st.id = self.id
        st.roadTime = max(0, int(snap['rt']))
        lateral = self.lateral * scale + shift      # shift: the whole group slid sideways to stay on the road
        if edges is not None:
            # a rider follows the snapshot of your trail from `gap` metres ago, not where you are now: when you move
            # sideways his road position is that old one plus his offset. Keep the result on the road, in his own coordinates.
            snap_m = (snap['rp'] - ROAD_POSITION_CENTER) / ROAD_POSITION_UNITS_PER_METER
            low, high = edges[0] + ROAD_EDGE_MARGIN_M, edges[1] - ROAD_EDGE_MARGIN_M
            wanted_m = snap_m + road_sign * lateral
            fitted_m = clamp(wanted_m, low, high) if low <= high else (low + high) / 2.0
            lateral = road_sign * (fitted_m - snap_m)
        st.y_altitude = snap['y']
        if via == 'road':
            st.x = snap['x']
            st.z = snap['z']
        else:
            st.x = snap['x'] - hz * lateral * CM_PER_M
            st.z = snap['z'] + hx * lateral * CM_PER_M
        road_position = int(snap['rp'])
        if via in ('road', 'both'):
            # the road coordinate the game places riders by: + moves to your +lateral side when the road time
            # runs along your direction of travel (measured on a recorded ride), the opposite way when it does not
            road_position = round(clamp(road_position + road_sign * lateral * ROAD_POSITION_UNITS_PER_METER,
                                        ROAD_POSITION_MIN, ROAD_POSITION_MAX))
        st.roadPosition = max(0, road_position)
        st.speed = max(0, int(speed_ms * MMH_PER_MS))
        st.power = max(0, int(power))


class SoloBlob:
    """A live group riding around one local player (the anchor)."""

    def __init__(self, player_id, index, config, names, game_dictionary, logger=None):
        self.player_id = player_id
        self.index = index
        self.config = dict(DEFAULT_CONFIG)
        self.config.update(config or {})
        self.game_dictionary = game_dictionary
        self.rng = random.Random((player_id * 7919 + index) ^ time.time_ns())
        self.logger = logger or logging.getLogger('solo_blob')
        self.trail = Trail()
        self.riders = []
        self.slots = []
        self.mode = None          # None | 'attack' | 'hammer' | 'toast' | 'lead' (gestures)
        self.mode_until = 0.0
        self.generation = 0
        self.grade_now = 0.0       # smoothed grade (m/m)
        self.live_speed = 0.0      # your estimated speed this very moment (m/s)
        self.live_accel = 0.0
        self.road_shift = 0.0      # meters the whole group is slid sideways to stay on the road
        self.road_reach = {}       # 'course:road:f|r' -> [closest, furthest] you ever rode from the centre line (m): you can steer
                                   # to the wall and to the edge yourself, so this is the most reliable edge there is
        self.grade_raw = 0.0
        self.stretch_now = 1.0
        self._next_diag = 0.0
        self.pending_gestures = []  # (rider, UserBikeAction) the manager sends to the game after the tick
        self.gestures = blob_gestures.GestureDirector(self.rng, time.monotonic())
        self._names = names or []
        self._build(self._names)
        self._reset_timers()
        self._trail_resets = self.trail.resets

    def _reset_timers(self):
        now = time.monotonic()
        self.next_shuffle = now + self._rand(self.config['shuffle_interval'])
        self.next_pull = now + self._rand(self.config['pull_interval'], 0.4)
        self.next_turn = now + float(self.config.get('turn_interval', 0))
        self.next_formation = now + self._rand(self.config['formation_interval'], 0.6)
        self._next_diag = now + 5.0
        self.gestures.reset(now, self._cfg_float('gesture_interval', 75.0))

    def reroll(self):
        """Fresh roster with new rider ids, names and kits."""
        self.rng = random.Random((self.player_id * 7919 + self.index) ^ time.time_ns())
        self._build(self._names)
        self._reset_timers()
        self.grade_now = 0.0

    def _rand(self, base, spread=0.5):
        return max(5.0, float(base) * self.rng.uniform(1 - spread, 1 + spread))

    # ---------- gestures ----------

    def gesture(self, action):
        """React to an in-game gesture (F-key). Returns a chat reply or None."""
        now = time.monotonic()
        if action == GESTURE_ATTACK:
            self._set_mode('attack', now + 90)
            self.next_pull = now                     # somebody attacks right now
            self.logger.info('[SoloBlob] player %d elbow flick - attack!' % self.player_id)
            return 'Elbow flick noted - somebody is coming through.'
        if action == GESTURE_HAMMER:
            self._set_mode('hammer', now + float(self.config['hammer_time']))
            self.next_pull = now
            self.logger.info('[SoloBlob] player %d HAMMER TIME' % self.player_id)
            return 'HAMMER TIME! The grupetto goes full gas.'
        if action == GESTURE_TOAST:
            self._set_mode('toast', now + float(self.config['toast_time']))
            for rider in self.riders:
                rider.pull_phase = None              # everybody sits up
            self.next_pull = now + float(self.config['toast_time'])
            self.logger.info('[SoloBlob] player %d is toast - easing off' % self.player_id)
            return 'You are toast - everybody eases off and regroups.'
        if action == GESTURE_LEAD:
            if self.mode == 'lead':
                self._set_mode(None, 0)
                return 'Bell again - back to normal, we take the front.'
            self._set_mode('lead', now + float(self.config['lead_time']))
            self.logger.info('[SoloBlob] player %d bell - taking the front himself' % self.player_id)
            return 'Ding ding - you lead, we sit in.'
        return None

    def _set_mode(self, mode, until):
        self.mode = mode
        self.mode_until = until
        self.slots = self._build_slots(len(self.riders))
        # keep everybody roughly where he is: the riders fill the new slots in the same front-to-back order
        self._assign_slots(sorted(self.riders, key=lambda r: r.gap))

    def _assign_slots(self, ordered):
        """Give the riders (front to back) the slots (front to back). A rider whose new slot is on
        the other side of you and close to your position would have to cross your line right in
        front of or behind your wheel: take one from just behind who is already on the right side."""
        if self._cfg_bool('scatter', False) and getattr(self, '_carry_fresh', False):
            self._carry_fresh = False
            self._assign_scatter()
            return
        ordered = list(ordered)
        slot_order = sorted(range(len(self.slots)), key=lambda i: self.slots[i][0])
        for k, slot in enumerate(slot_order[:len(ordered)]):
            gap, lateral = self.slots[slot]
            if abs(gap) > LANE_SWAP_ZONE_M or ordered[k].lateral * lateral >= 0:
                continue
            for j in range(k + 1, min(k + 4, len(ordered))):
                if ordered[j].lateral * lateral > 0:
                    ordered[k], ordered[j] = ordered[j], ordered[k]
                    break
        for slot, rider in zip(slot_order, ordered):
            rider.slot = slot
        if self._cfg_bool('scatter', False):
            self._match_tail_by_position()

    def _match_tail_by_position(self):
        """With `scatter` the slots behind you are not interchangeable within a row: give each rider
        behind you the free slot nearest to where he rides right now, so a formation change or a
        rotation nudges everybody a little instead of sending riders across the whole group."""
        tail_slots = [i for i, (gap, _) in enumerate(self.slots) if gap > 0]
        tail_riders = [r for r in self.riders if r.slot in set(tail_slots)]
        if len(tail_riders) < 2:
            return
        costs = sorted((((r.gap - self.slots[i][0]) ** 2 + (2.0 * (r.lateral - self.slots[i][1])) ** 2), k, i)
                       for k, r in enumerate(tail_riders) for i in tail_slots)
        used_riders, used_slots = set(), set()
        for _, k, i in costs:
            if k not in used_riders and i not in used_slots:
                tail_riders[k].slot = i
                used_riders.add(k)
                used_slots.add(i)

    def _pass_rate(self):
        # closing speed while overtaking: (zone + takeover distance) / pass_time
        pass_time = max(4.0, float(self.config['pass_time']))
        if self.mode in ('hammer', 'attack'):
            pass_time *= 0.6
        return (PASS_ZONE_M + PASS_TAKEOVER_M) / pass_time

    def _pull_params(self):
        interval = float(self.config['pull_interval'])
        duration = float(self.config['pull_duration'])
        if self.mode == 'hammer':
            interval, duration = interval * 0.55, duration * 1.6
        elif self.mode == 'attack':
            interval, duration = interval * 0.7, duration * 1.3
        return interval, duration

    # ---------- riders ----------

    def _rider_id(self, i):
        return RIDER_ID_BASE + self.index * RIDERS_PER_BLOB + self.generation * MAX_RIDERS + i + 1

    def _build(self, names):
        count = clamp(int(self.config.get('riders', 8)), 0, MAX_RIDERS)
        self.generation = next_generation()
        self.lead_rows_now = None           # None = the normal share of the group in single file
        # rows in front of you, nearest first: 1 = a single rider, 2 = a pair side by side...
        self.lead_steps = [self.rng.uniform(1.0, 1.4) for _ in range(MAX_RIDERS + 2)]   # uneven spacing in front
        # per row behind you (used with 'ragged_rows'): width change, sideways shift (in lateral
        # spacings) and a gap change (in row gaps). Fixed per roster so rows do not jump around
        self.row_pattern = [(self.rng.choice((-1, 0, 0, 1)), self.rng.uniform(-0.45, 0.45),
                             self.rng.uniform(-0.2, 0.2)) for _ in range(RAGGED_ROW_PATTERN_LEN)]
        self.pool_seed = self.rng.getrandbits(32)
        self._pool_key = None
        self._ensure_pools()
        self._sc_front = self._sc_tail = None       # a fresh roster starts with fresh positions in use
        self._sc_pool_key = self._pool_key
        self._carry_fresh = False
        self.riders = []
        # draw WITHOUT replacement: one ride, one distinct roster; a fresh
        # draw happens on every new ride (see update() trail-reset hook)
        pool = names or []
        if self._cfg_bool('only_kitted', False):
            kitted = [n for n in pool if n.get('ride_jersey')]
            if len(kitted) >= count:
                pool = kitted
        if len(pool) >= count:
            picks = self.rng.sample(pool, count)
        elif pool:
            picks = [self.rng.choice(pool) for _ in range(count)]
        else:
            picks = [{}] * count
        for i, name in zip(range(count), picks):
            profile = self._create_profile(i, name)
            strength = clamp(self.rng.gauss(1.0, 0.07), 0.55, 1.45)
            rider = BlobRider(self._rider_id(i), profile, strength)
            rider.preference = ('front', 'any', 'back')[self.rng.randrange(3)]
            self.riders.append(rider)
        self.slots = self._build_slots(count)
        self._carry_fresh = False                    # the riders get their slots right below, no carry-over
        order = sorted(self.riders, key=lambda r: self.rng.random())
        for slot, rider in enumerate(order):
            rider.slot = slot
            rider.gap = self.slots[slot][0]
            rider.lateral = self.slots[slot][1]

    def _create_profile(self, i, name):
        rng = self.rng
        gd = self.game_dictionary
        profile = profile_pb2.PlayerProfile()
        profile.id = self._rider_id(i)
        profile.first_name = name.get('first_name') or 'Rider'
        profile.last_name = name.get('last_name') or str(i)
        profile.is_male = bool(name.get('is_male', bool(rng.getrandbits(1))))
        profile.country_code = name.get('country_code') or 804
        profile.weight_in_grams = round(rng.uniform(62, 86) * 1000)
        profile.height_in_millimeters = round(rng.uniform(165, 192) * 10)
        try:
            profile.ride_helmet_type = rng.choice(gd['headgears'])
            profile.glasses_type = rng.choice(gd['glasses'])
            profile.ride_shoes_type = rng.choice(gd['bikeshoes'])
            profile.ride_socks_type = rng.choice(gd['socks'])
            profile.ride_jersey = rng.choice(gd['jerseys'])
            profile.bike_wheel_rear, profile.bike_wheel_front = rng.choice(gd['wheels'])
            profile.bike_frame = rng.choice(list(gd['bikeframes'].keys()))
            profile.run_shirt_type = rng.choice(gd['runshirts'])
            profile.run_shorts_type = rng.choice(gd['runshorts'])
            profile.run_shoes_type = rng.choice(gd['runshoes'])
            profile.body_type = rng.choice(gd['body_types_male'] if profile.is_male else gd['body_types_female'])
            profile.hair_type = rng.choice(gd['hair_types'])
            if profile.is_male:
                profile.facial_hair_type = rng.choice(gd['facial_hair_types'])
        except Exception as exc:
            self.logger.warning('[SoloBlob] profile equipment randomization: %s' % repr(exc))
        for item in EQUIPMENT_ITEMS:       # kit, bike... from bot.txt override the random ones
            if item in name:
                setattr(profile, item, name[item])
        return profile

    @staticmethod
    def _lead_count(count):
        # about a third of the group rides in front of you (1 at 4 riders, 3 at 8)
        return clamp(round(count * LEAD_SHARE), 1, MAX_LEADERS) if count >= 4 else 0

    def _max_leaders(self, count):
        return clamp(count - 3, 1, MAX_LEADERS + 2)      # at least three riders stay behind you

    def _lead_rows_for(self, total):
        """Split `total` riders in front of you into rows, nearest to you first: singles
        and pairs side by side in a random order (e.g. [2, 1] = a pair right in front
        of you and a lone rider ahead of them)."""
        rows = []
        left = total
        while left > 0:
            size = 1 if left == 1 else self.rng.choices((1, 2), (45, 55))[0]
            rows.append(size)
            left -= size
        if len(rows) > MAX_LEAD_ROWS:       # a big group in front: wider rows instead of a long line
            width = -(-total // MAX_LEAD_ROWS)
            rows = [width] * (total // width) + ([total % width] if total % width else [])
        return rows

    @staticmethod
    def _blue_noise(rng, count, start, depth, band, taken, long_min, lat_min, half, player_long, player_lat):
        """Dart throwing band by band away from you: `count` points (distance along the road, lateral) with
        at least an ellipse of long_min x lat_min between any two, and never inside the ellipse around you."""
        points = []
        pos = start
        while len(points) < count and pos < start + depth:
            fails = 0
            while fails < 150 and len(points) < count:
                d, lat = rng.uniform(pos, pos + band), rng.uniform(-half, half)
                free = (d / player_long) ** 2 + (lat / player_lat) ** 2 >= 1.0 and all(
                    ((d - g) / long_min) ** 2 + ((lat - la) / lat_min) ** 2 >= 1.0 for g, la in taken)
                if free:
                    taken.append((d, lat))
                    points.append((d, lat))
                    fails = 0
                else:
                    fails += 1
            pos += band * 0.5
        return points

    def _ensure_pools(self):
        """Fixed scattered positions for the riders in front of you and behind you (see 'scatter'). Built per
        roster from a fixed seed and rebuilt only when a layout setting changes, so a group of n riders
        always uses the first n positions and a formation change never reshuffles the whole layout."""
        key = tuple(self._cfg_float(k, d) for k, d in (('scatter_gap', 2.0), ('keep_apart', 0.0), ('scatter_width', 6.0),
                                                       ('lead_gap', 1.8), ('max_lead', 9.0), ('scatter_beside', 1.4),
                                                       ('scatter_side', 1.3), ('keep_apart_long', SEP_LONG_M),
                                                       ('lateral_spacing', 0.6)))
        if key == self._pool_key:
            return
        self._pool_key = key
        gap, apart, width, lead_gap, max_lead, beside, side, keep_long, spacing = key
        long_min = max(1.7, gap, keep_long * 1.05)
        lat_min = max(0.9, apart * 1.15, side, spacing)     # lateral_spacing: riders level with each other are this far apart
        half = clamp(width / 2.0, 1.0, 3.2)
        beside = clamp(beside, 1.0, 2.5)
        rng = random.Random(self.pool_seed)
        band = long_min * 0.9
        self.scatter_front = self._blue_noise(rng, MAX_RIDERS, 0.5, clamp(max_lead, 4.0, MAX_LEAD_M - 1.0), band, [],
                                              long_min, lat_min, half, max(1.7, lead_gap), beside)
        # the front positions next to you are obstacles for the tail ones too (signed along the road: ahead < 0)
        across = [(-d, lat) for d, lat in self.scatter_front if d < long_min * 1.5]
        self.scatter_tail = self._blue_noise(rng, MAX_RIDERS, 0.8, 40.0, band, across,
                                             long_min, lat_min, half, PULL_MIN_GAP, beside)

    @staticmethod
    def _resize_set(current, n, pool):
        """Which pool positions are in use. Growing takes the free position nearest you, shrinking drops the
        one nearest you, so a change in the formation only moves the riders next to you, not the whole group."""
        if current is None:
            return list(range(n))
        current = list(current)
        while len(current) < n:
            free = [i for i in range(len(pool)) if i not in current]
            if not free:
                break
            current.append(min(free, key=lambda i: pool[i][0]))
        while len(current) > n:
            current.remove(min(current, key=lambda i: pool[i][0]))
        return current

    def _scatter_slots(self, count, lead_total):
        """Slots for a scattered group: the riders in front of you (nearest you first, as the lead slots are
        numbered from you outwards), then the ones behind you ordered by distance. Positions that stay in use
        keep their rider (see _assign_scatter)."""
        self._ensure_pools()
        lead_total = min(lead_total, len(self.scatter_front), count)
        if getattr(self, '_sc_pool_key', None) != self._pool_key:
            self._sc_front = self._sc_tail = None
            self._sc_pool_key = self._pool_key
        self._sc_front = self._resize_set(getattr(self, '_sc_front', None), lead_total, self.scatter_front)
        self._sc_tail = self._resize_set(getattr(self, '_sc_tail', None), count - lead_total, self.scatter_tail)
        front = sorted(((-self.scatter_front[i][0], self.scatter_front[i][1]) for i in self._sc_front),
                       key=lambda slot: -slot[0])
        tail = sorted(self.scatter_tail[i] for i in self._sc_tail)
        old = self.slots
        self._carry = {id(r): old[r.slot] for r in self.riders if 0 <= r.slot < len(old)}
        self._carry_fresh = True
        return front + tail

    def _assign_scatter(self):
        """After the slots were rebuilt: every rider whose position is still in use keeps it, the others (the
        ones whose position was dropped) take the nearest free positions."""
        index = {slot: i for i, slot in enumerate(self.slots)}
        free = set(range(len(self.slots)))
        pending = []
        for rider in self.riders:
            i = index.get(self._carry.get(id(rider)))
            if i is not None and i in free:
                rider.slot = i
                free.discard(i)
            else:
                pending.append(rider)
        costs = sorted((((r.gap - self.slots[i][0]) ** 2 + (2.0 * (r.lateral - self.slots[i][1])) ** 2), k, i)
                       for k, r in enumerate(pending) for i in free)
        used_riders, used_slots = set(), set()
        for _, k, i in costs:
            if k not in used_riders and i not in used_slots:
                pending[k].slot = i
                used_riders.add(k)
                used_slots.add(i)

    def _build_slots(self, count):
        spacing = float(self.config['lateral_spacing'])
        row_gap = float(self.config['row_gap'])
        lead_gap = float(self.config.get('lead_gap', 1.6))
        # gestures reshape the formation: hammer = tight and lethal, toast =
        # loose and calm, bell = the player leads so nobody sits in front
        lead_count = None
        if self.mode == 'hammer':
            row_gap, lead_gap = row_gap * 0.7, lead_gap * 0.75
            lead_count = min(3, max(1, count - 3))
        elif self.mode == 'attack':
            row_gap, lead_gap = row_gap * 0.85, lead_gap * 0.85
            lead_count = max(1, min(3, (count - 1) // 3)) if count >= 4 else 0
        elif self.mode == 'toast':
            row_gap = row_gap * 1.15
            lead_count = max(1, min(2, (count - 1) // 4)) if count >= 5 else 0
        elif self.mode == 'lead':
            lead_count = 0
        if lead_count is not None:
            rows = [1] * lead_count
        elif self.lead_rows_now is not None:
            rows = self.lead_rows_now
        else:
            rows = [1] * self._lead_count(count)
        if self._cfg_bool('scatter', False):
            return self._scatter_slots(count, sum(rows))

        slots = []
        lead_pos = 0.0
        single_side = 1
        lead_lateral = float(self.config.get('lead_lateral', LEAD_LATERAL_M))
        for i, size in enumerate(rows):
            size = min(size, count - len(slots))
            if size <= 0:
                break
            lead_pos += lead_gap * self.lead_steps[i % len(self.lead_steps)]
            if size == 1:      # a single rider rides a bit to one side, alternating
                laterals = [lead_lateral * single_side]
                single_side = -single_side
            else:              # a pair or more rides side by side
                pitch = 2 * spacing if size == 2 else 1.4 * spacing     # wide rows stay on the road
                laterals = [(j - (size - 1) / 2) * pitch for j in range(size)]
            slots.extend((-lead_pos, lateral) for lateral in laterals)
        # the whole group in front stays close to you: no big gaps, whatever the formation
        max_lead = clamp(self._cfg_float('max_lead', 9.0), 2.0, MAX_LEAD_M - 1.0)
        if slots and lead_pos > max_lead:
            squeeze = max_lead / lead_pos
            slots = [(gap * squeeze, lateral) for gap, lateral in slots]

        remaining = count - len(slots)
        if remaining == 1:           # a lone rider right on your wheel
            slots.append((PULL_MIN_GAP, 0.0))
        elif remaining >= 2:
            slots.append((PULL_MIN_GAP, -spacing))
            slots.append((PULL_MIN_GAP, spacing))
            # the rest sits in staggered rows; as wide as needed to keep the tail
            # within tail_gap (up to 5 abreast), more rows only for big groups
            rest = remaining - 2
            rows_fit = max(1, int((float(self.config.get('tail_gap', 4.0)) - PULL_MIN_GAP) / row_gap + 1e-6))
            columns = int(self.config['columns']) or clamp(-(-rest // rows_fit), 2, 5)
            ragged = self._cfg_bool('ragged_rows', False)
            row = 1
            while len(slots) < count:
                if ragged:
                    delta, shift, gap_change = self.row_pattern[row % len(self.row_pattern)]
                    width = clamp(columns + delta, 2, 5)
                    stagger = spacing * shift
                    row_pos = PULL_MIN_GAP + (row + gap_change) * row_gap
                else:
                    width = columns
                    stagger = spacing * 0.25 * (1 if row % 2 else -1)
                    row_pos = PULL_MIN_GAP + row * row_gap
                for column in range(width):
                    if len(slots) < count:
                        lateral = (column - (width - 1) / 2) * spacing + stagger
                        slots.append((row_pos, lateral))
                row += 1
        return slots

    # ---------- per-tick simulation ----------

    def on_state(self, state, lag_s=None):
        if state and state.roadTime:
            self.trail.push(state, lag_s)
            self._learn_road_reach(state)

    def _cfg_float(self, key, default):
        """Config value as a float; a wrong type in the JSON file falls back to the default."""
        try:
            return float(self.config.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    def _cfg_bool(self, key, default):
        value = self.config.get(key, default)
        if isinstance(value, str):
            return value.strip().lower() not in ('false', '0', 'no', 'off', '')
        return bool(value)

    def _median_lag(self):
        lags = sorted(e['lag'] for e in self.trail.entries[-12:] if e.get('lag') is not None)
        return lags[len(lags) // 2] if lags else None

    def _latency_comp(self):
        """Seconds to add to the age of your newest packet (config 'latency_comp')."""
        setting = self.config.get('latency_comp', 0)
        if setting == 'auto':
            lag = self._median_lag()
            return clamp(lag, 0.0, MAX_LATENCY_COMP_S) if lag is not None else 0.0
        try:
            return clamp(float(setting), 0.0, MAX_LATENCY_COMP_S)
        except (TypeError, ValueError):
            return 0.0

    def update(self, tick_seconds):
        if not self.riders:
            return {}
        if not self.trail.ready():
            return {}   # anchor not riding (yet) -> hide everybody, keep the world clean

        # new ride (player restarted): fresh roster mix so every ride draws
        # different riders/genders/kits from the names pool
        resets = self.trail.resets
        if resets != self._trail_resets:
            self._trail_resets = resets
            self.reroll()    # also resets the smoothed grade
            self.logger.info('[SoloBlob] player %d new ride - roster reshuffled' % self.player_id)

        now = time.monotonic()

        if now >= self.next_shuffle:
            self._shuffle()
            self.next_shuffle = now + self._rand(self.config['shuffle_interval'])

        # a gesture mode expires back to the normal grupetto on its own
        if self.mode and now > self.mode_until:
            self._set_mode(None, 0)
            self.next_pull = max(self.next_pull, now + 15)

        # your turn at the front: the riders in front ease back behind you for
        # lead_time seconds (like the bell gesture), then come through again
        busy = any(r.pull_phase or r.dropping for r in self.riders)
        turn_interval = float(self.config.get('turn_interval', 0))
        if turn_interval > 0 and self.mode is None and now >= self.next_turn and not busy:
            lead_time = float(self.config['lead_time'])
            self._set_mode('lead', now + lead_time)
            self.next_turn = now + lead_time + turn_interval
            self.logger.info('[SoloBlob] player %d takes a turn at the front' % self.player_id)

        # now and then more or fewer riders ride in front of you (1 or 2 move up or drop back)
        if now >= self.next_formation and self.mode is None and not busy:
            self._vary_leaders()
            self.next_formation = now + self._rand(self.config['formation_interval'], 0.6)

        if now >= self.next_pull and self.mode != 'toast' and not busy:
            if self.mode in ('attack', 'hammer'):
                # gestures: one rider attacks from behind and passes the leader slowly
                attacker = self._pick_puller()
                if attacker:
                    attacker.pull_phase = 'approach'
                    attacker.pull_side = DROP_SIDE_M if attacker.lateral >= 0 else -DROP_SIDE_M   # pass on his own side
                    interval, _ = self._pull_params()
                    self.next_pull = now + self._rand(interval, 0.7)
            elif self.mode is None and self.config.get('rotate', True):
                self._rotate_line()
                self.next_pull = now + self._rand(self.config['pull_interval'], 0.6)

        # where you are and how you move RIGHT NOW (speed and its trend, grade)
        self.trail.latency_comp = self._latency_comp()
        self.live_speed, self.live_accel, _ = self.trail.motion()
        self.grade_now += GRADE_SMOOTHING * (self.trail.grade() - self.grade_now)
        grade = self.grade_now
        self.grade_raw = self.trail.grade()
        # the tail stretches gradually on the way into a climb (a hard on/off switch at
        # 3% flickered and made the whole group jump when the grade hovered around it)
        ramp = clamp((grade - CLIMB_GRADE_START) / (CLIMB_GRADE_FULL - CLIMB_GRADE_START), 0.0, 1.0)
        ramp = ramp * ramp * (3.0 - 2.0 * ramp)
        stretch = 1.0 + ramp * grade * CLIMB_STRETCH_PER_GRADE * float(self.config['climb_stretch'])
        self.stretch_now = stretch

        self._update_road_shift(tick_seconds)
        for rider in self.riders:
            self._update_rider(rider, stretch, now, tick_seconds)

        if self._cfg_bool('bot_gestures', True):
            self.pending_gestures.extend(self.gestures.step(now, self.riders, self._cfg_float('gesture_interval', 75.0), self.live_speed,
                                                                 self._cfg_float('gesture_chance', 1.0)))
        diag_interval = self._cfg_float('diag_interval', 0.0)
        if diag_interval > 0 and now >= self._next_diag:
            self._next_diag = now + diag_interval
            self._log_diag(grade, stretch)
        return {r.id: r for r in self.riders}

    def _log_diag(self, grade, stretch):
        """One line that says why the group looks the way it does (for bug reports)."""
        ahead = sorted(r.gap for r in self.riders if r.gap < 0)
        behind = [r.gap for r in self.riders if r.gap >= 0]
        rows = self.lead_rows_now if self.lead_rows_now is not None else '-'
        lag = self._median_lag()
        self.logger.info('[SoloBlob] player %d diag: mode=%s v=%.1fm/s a=%+.2f grade=%.1f%% stretch=%.2f '
                         'rows=%s ahead=%s tail=%.1fm packet_lag=%s comp=%.2fs' % (
                             self.player_id, self.mode, self.live_speed, self.live_accel, grade * 100, stretch,
                             rows, ['%.1f' % g for g in ahead], max(behind) if behind else 0.0,
                             '%.2fs' % lag if lag is not None else 'n/a', self.trail.latency_comp) + self._road_diag())

    def _road_diag(self):
        """' road=...' for the diag line: which road the blob thinks you are on and the edges it works with."""
        if not self.trail.entries:
            return ''
        head = self.trail.entries[-1]
        key, forward, you = self._road_side(head['proto'])
        edges = self._road_edges()
        listed = key in road_limits()
        return (' road=%s you=%.1fm rt=%.3f table=%s factor=%.2f reach=%s edges=%s shift=%.1f' % (
            key, you, head['rt'] / ROAD_TIME_UNITS, road_limits().get(key) if listed else 'DEFAULT',
            road_width_factor(course_of(head['proto']), road_of(head['proto']), head['rt']),
            self.road_reach.get(key), ('%.1f..%.1f' % edges) if edges else None, self.road_shift))

    def _vary_leaders(self):
        """Change the formation in front of you: one or two riders more or fewer ride
        ahead (the ones from just behind move up and pass you on the side, or the last
        ones in front drop back), or the same riders just line up differently (a pair
        and a single swap places). With `full_range` everything from "nobody in front,
        you lead" to "everybody in front, you are last" is possible."""
        spread = int(self.config.get('lead_spread', 0))
        count = len(self.riders)
        if spread <= 0 or count < 1:
            return
        home = self._lead_count(count)
        current = self.lead_rows_now if self.lead_rows_now is not None else [1] * home
        base = sum(current)
        if self._cfg_bool('full_range', True):
            low, high = 0, count
        elif count >= 5:       # the old behaviour: a few riders in front, three always behind you
            low, high = max(1, home - spread), min(self._max_leaders(count), home + spread)
        else:
            return
        options = []
        for total in range(low, high + 1):
            step = abs(total - base)
            if step > spread:
                continue
            if step == 0:
                weight = 1.5 if total >= 2 else 0.0      # same riders, other arrangement
            else:
                weight = {1: 3.0, 2: 1.0}.get(step, 0.5)
            # you lead on your own already every turn_interval, and a random walk piles up
            # less time at the far end: weigh "you are last" up, "you are first" down
            weight *= {0: 0.5, count: 1.3}.get(total, 1.0)
            if weight > 0:
                options.append((total, weight))
        if not options:
            return
        totals = [t for t, _ in options]
        weights = [w for _, w in options]
        rows = current
        for _ in range(4):           # avoid "changing" into the very same formation
            total = self.rng.choices(totals, weights)[0]
            rows = self._lead_rows_for(total)
            if rows != current:
                break
        if rows == current:
            return
        self.lead_rows_now = rows
        self.slots = self._build_slots(count)
        self._assign_slots(sorted(self.riders, key=lambda r: r.gap))
        self.logger.info('[SoloBlob] player %d formation: rows ahead %s (%d in front, %d behind you)' % (
            self.player_id, rows, sum(rows), count - sum(rows)))

    def _rotate_line(self):
        """Paceline: the front rider peels off to the side and drifts back to the
        tail while everybody else moves up one place, so every rider goes
        through every position. Sometimes two (rarely three) riders peel off together."""
        if len(self.riders) < 3:
            return
        peel = min(self.rng.choices((1, 2, 3), (70, 25, 5))[0], len(self.riders) - 2)
        if self._cfg_bool('scatter', False):
            self._rotate_scatter(peel)
            return
        order = sorted(self.riders, key=lambda r: self.slots[r.slot][0])
        self._assign_slots(order[peel:] + order[:peel])
        side = min(max(DROP_SIDE_M, max(abs(lateral) for _, lateral in self.slots) + 0.6), MAX_ROAD_HALF_WIDTH_M + 0.4)
        for i, rider in enumerate(order[:peel]):
            rider.dropping = True
            rider.drop_side = side if (rider.lateral >= 0) == (i % 2 == 0) else -side

    def _rotate_scatter(self, peel):
        """A rotation in a scattered group. The front rider peels off along the OUTSIDE of the group and drifts
        back to its end. The riders that move up are only those on one path of slots from the front to the back
        (each takes the nearest slot ahead of his own), so nobody crosses the group and the others stay put."""
        apart = max(1.0, self._cfg_float('keep_apart', 0.0))
        lane = clamp(max(abs(lateral) for _, lateral in self.slots) + 0.9 * apart, DROP_SIDE_M, MAX_ROAD_HALF_WIDTH_M + 1.6)
        half_road = self._cfg_float('road_half_width', 0.0)
        if half_road > 0:        # the passing lane must stay on the road too
            lane = min(lane, max(half_road - 0.2, max(abs(lateral) for _, lateral in self.slots) + 0.5))
        long_m = max(1.5, self._cfg_float('keep_apart_long', SEP_LONG_M))
        for n in range(peel):
            moving = {r.slot for r in self.riders if r.dropping or r.pull_phase}
            free_riders = [r for r in self.riders if r.slot not in moving]
            if len(free_riders) < 3:
                return
            by_slot = {r.slot: r for r in free_riders}
            front = min(free_riders, key=lambda r: self.slots[r.slot][0])
            path = [front.slot]
            while True:
                gap, lateral = self.slots[path[-1]]
                options = [i for i in by_slot if i not in path and gap + 0.8 < self.slots[i][0] < gap + 3.2 * long_m]
                if not options:
                    break
                path.append(min(options, key=lambda i: ((self.slots[i][0] - gap) / long_m) ** 2
                                + (1.6 * (self.slots[i][1] - lateral) / apart) ** 2))
            if len(path) < 2:
                return
            for ahead, behind in zip(path, path[1:]):
                by_slot[behind].slot = ahead              # moves up one place along the path
            front.slot = path[-1]                         # the old leader takes the last place
            front.dropping = True
            front.drop_side = lane if (front.lateral >= 0) == (n % 2 == 0) else -lane

    def _pick_puller(self):
        candidates = [r for r in self.riders
                      if not r.pull_phase and not r.dropping and self.slots[r.slot][0] > 0]
        if not candidates:
            return None
        candidates.sort(key=lambda r: (-r.strength, r.slot))
        return candidates[0]

    def _shuffle(self):
        if self._cfg_bool('scatter', False):
            return      # a scattered group does not swap places (two riders would have to pass head-on through
                        # each other); it keeps changing through the drift, formation changes and rotations
        # shuffling only happens among the riders BEHIND you; the ones in
        # front change places only through a rotation (see update()), so
        # nobody suddenly drops from the lead to the back of the group
        first_behind = next((i for i, slot in enumerate(self.slots) if slot[0] > 0), None)
        if first_behind is None:       # everybody rides in front of you
            return
        by_slot = {r.slot: r for r in self.riders}
        quiet = [r for r in self.riders if not r.pull_phase and r.slot >= first_behind]
        if len(quiet) < 2:
            return
        rider = self.rng.choice(quiet)
        if rider.preference == 'front' or (rider.strength > 1.03 and self.rng.random() < 0.6):
            direction = -1
        elif rider.preference == 'back' or (rider.strength < 0.97 and self.rng.random() < 0.6):
            direction = 1
        else:
            direction = self.rng.choice((-1, 1))
        distance = self.rng.randint(1, 3)
        target_slot = clamp(rider.slot + direction * distance, first_behind, len(self.slots) - 1)
        if target_slot == rider.slot:
            return

        other = by_slot.get(target_slot)   # a slot can be empty in small groups
        original = rider.slot
        if other is not None:
            # two riders of the same row would swap sides and both cross the middle at the
            # same moment (clipping through each other for seconds): leave them alone
            (gap_a, lat_a), (gap_b, lat_b) = self.slots[original], self.slots[target_slot]
            if lat_a * lat_b < 0 and abs(gap_a - gap_b) < 1.5:
                return
        rider.slot = target_slot
        if other is not None:
            other.slot = original

    def _road_edges(self):
        """The drivable road in roadPosition metres from the road centre: (low edge, high edge), or None when
        road_half_width is off. The axis side may be closer than the real edge (road_axis_limit)."""
        half_road = self._cfg_float('road_half_width', 0.0)
        if half_road <= 0:
            return None
        if str(self.config.get('road_limits', 'auto')).lower() != 'off' and self.trail.entries:
            return self._recorded_road_edges(self.trail.entries[-1], half_road)
        axis = self._cfg_float('road_axis_limit', 0.0)
        axis = abs(axis) if axis > 0 else half_road
        if self._cfg_float('road_axis_side', -1.0) > 0:
            return -half_road, axis
        return -axis, half_road

    @staticmethod
    def _road_side(state):
        """('course:road:f|r' key, forward, where you ride in metres from the centre line). The game forces you to the
        lane of your direction, so when your position says otherwise the position wins over the forward flag."""
        forward = plus_side_forward(state)       # the + side of the road: forward riders there, except where traffic keeps left
        you = (state.roadPosition - ROAD_POSITION_CENTER) / ROAD_POSITION_UNITS_PER_METER
        if forward and you < -AXIS_SIDE_TOLERANCE_M:
            forward = False
        elif not forward and you > AXIS_SIDE_TOLERANCE_M:
            forward = True
        return '%d:%d:%s' % (course_of(state), road_of(state), 'f' if forward else 'r'), forward, you

    def _learn_road_reach(self, state):
        """Remember how close to the wall and how far to the edge you rode on this road and way: you steer yourself,
        so wherever you can ride is road, and the closest you ever get to the centre line is where the wall is."""
        key, forward, you = self._road_side(state)
        if (you > 0) != forward or you == 0:
            return
        reach = abs(you)
        seen = self.road_reach.get(key)
        if seen is None:
            self.road_reach[key] = [reach, reach]
        else:
            seen[0] = min(seen[0], reach)
            seen[1] = max(seen[1], reach)

    def _recorded_road_edges(self, head, fallback_width):
        """Drivable side of the road for the way you ride, in roadPosition metres from the centre line. Forward riders
        keep to the + side, the others to the - side; where the invisible wall next to the centre line and the outer
        edge are comes from real rides (data/road_limits.json, `inner` is not always 0), and is widened by wherever
        you yourself have ridden on this road."""
        key, forward, you = self._road_side(head['proto'])
        you = (head['rp'] - ROAD_POSITION_CENTER) / ROAD_POSITION_UNITS_PER_METER
        inner, outer = road_limits().get(key, (DEFAULT_LANE_INNER_M, max(fallback_width, DEFAULT_LANE_OUTER_M)))
        state = head['proto']
        factor = road_width_factor(course_of(state), road_of(state), head['rt'])
        if factor != 1.0:                    # the road narrows / widens here (road.xml): scale the usual outer edge
            outer = clamp(outer * factor, max(inner + 1.0, MIN_OUTER_EDGE_M), MAX_OUTER_EDGE_M)
        closest, furthest = self.road_reach.get(key, (abs(you), abs(you)))
        closest, furthest = min(closest, abs(you)), max(furthest, abs(you))
        # a rider may stand in line with you at the wall or at the edge, so the group never ends up further from the
        # wall / closer to the edge than you have been
        inner = max(0.0, min(inner, closest - ROAD_EDGE_MARGIN_M))
        outer = max(outer, furthest + ROAD_EDGE_MARGIN_M)
        return (inner, outer) if forward else (-outer, -inner)

    def _lateral_limits(self):
        """Where a rider's lateral (relative to you) may be so that his body stays on the road, given where you
        ride and how far the group is slid. None = no limit. Riders must never be pushed past it: the game
        pulls anybody outside the road back to its edge, which looks like an invisible wall."""
        edges = self._road_edges()
        entries = self.trail.entries
        if edges is None or not entries:
            return None
        head = entries[-1]
        you = (head['rp'] - ROAD_POSITION_CENTER) / ROAD_POSITION_UNITS_PER_METER
        sign = head.get('sign', 1)
        low, high = edges[0] - you + ROAD_EDGE_MARGIN_M, edges[1] - you - ROAD_EDGE_MARGIN_M
        if sign < 0:
            low, high = -high, -low
        return low - self.road_shift, high - self.road_shift

    def _update_road_shift(self, tick_seconds):
        """Slide the whole group sideways when you ride close to the edge of the road, so that its outer riders
        stay on the road (road = road_half_width either side of the road centre, roadPosition 10,000,000)."""
        half_road = self._cfg_float('road_half_width', 0.0)
        entries = self.trail.entries
        if half_road <= 0 or not entries or not self.slots:
            self.road_shift *= 0.9
            return
        head = entries[-1]
        you = (head['rp'] - ROAD_POSITION_CENTER) / ROAD_POSITION_UNITS_PER_METER      # where you ride across the road
        lo_edge, hi_edge = self._road_edges()
        sign = head.get('sign', 1)
        lat_min = min(lateral for _, lateral in self.slots)
        lat_max = max(lateral for _, lateral in self.slots)
        near, far = (lat_min, lat_max) if sign >= 0 else (-lat_max, -lat_min)      # the group's extent in roadPosition metres
        # slide the group just far enough that its outermost rider on each side stays on the road: ride at the edge
        # and the group's edge rider is in line with you, the rest sits further in; ride in the middle and it is 0
        low = lo_edge - you - near + ROAD_EDGE_MARGIN_M
        high = hi_edge - you - far - ROAD_EDGE_MARGIN_M
        wanted = (low + high) / 2.0 if low > high else clamp(0.0, low, high)
        wanted *= sign                                     # roadPosition counts the other way on a reversed road
        auto = str(self.config.get('road_limits', 'auto')).lower() != 'off'
        if auto:
            cap = clamp(self._cfg_float('max_road_shift', MAX_ROAD_SHIFT_M), 0.0, 4.0)
            wanted = clamp(wanted, -cap, cap)
        step = (1.0 if auto else 0.5) * tick_seconds       # the group glides along as you move to the side, it never jumps
        self.road_shift += clamp(wanted - self.road_shift, -step, step)

    def _apply_wander(self, rider, slot_gap, want_gap, want_lateral, tick_seconds):
        """Let a rider behind you drift slowly and randomly around his slot (a mean-reverting random
        walk), so the group stops looking like a drilled grid. Riders in front of you and the first
        row on your wheel keep their exact place along the road; a drift that would put a rider
        on top of another one is damped instead of applied."""
        amp_gap = max(0.0, self._cfg_float('wander_gap', 0.0))
        amp_lat = max(0.0, self._cfg_float('wander_lateral', 0.0))
        if slot_gap <= 0 or (amp_gap <= 0 and amp_lat <= 0):
            rider.wander_gap *= 0.8             # in front of you (or switched off): settle back to the slot
            rider.wander_lat *= 0.8
            return want_gap, want_lateral
        k = clamp(tick_seconds / max(2.0, self._cfg_float('wander_time', 7.0)), 0.0, 1.0)
        step = math.sqrt(2.0 * k)
        # the stationary spread of the walk is amp / 1.5: most of the time it uses a good part of +-amp
        rider.wander_gap += -rider.wander_gap * k + amp_gap / 1.5 * step * self.rng.gauss(0, 1)
        rider.wander_lat += -rider.wander_lat * k + amp_lat / 1.5 * step * self.rng.gauss(0, 1)
        rider.wander_gap = clamp(rider.wander_gap, -amp_gap, amp_gap)
        rider.wander_lat = clamp(rider.wander_lat, -amp_lat, amp_lat)

        first_row = slot_gap - PULL_MIN_GAP < 0.1
        gap_scale = 0.0 if first_row else 1.0
        lat_scale = WANDER_FIRST_ROW_LATERAL if first_row else 1.0
        cand_gap = want_gap + gap_scale * rider.wander_gap
        cand_lat = clamp(want_lateral + lat_scale * rider.wander_lat, -MAX_ROAD_HALF_WIDTH_M, MAX_ROAD_HALF_WIDTH_M)
        apart = max(self._cfg_float('keep_apart', 0.0), OVERLAP_LAT_M) * 1.1       # a drift needs extra room
        long_m = max(OVERLAP_LONG_M * 1.6, self._cfg_float('keep_apart_long', SEP_LONG_M)) * 1.05
        for other in self.riders:
            if other is rider:
                continue
            if self._too_close(other.gap - cand_gap, other.lateral - cand_lat, apart, long_m):
                rider.wander_gap *= 0.9          # blocked right now: hold the slot, the walk finds a free way later
                rider.wander_lat *= 0.9
                return want_gap, want_lateral
        return cand_gap, cand_lat

    @staticmethod
    def _too_close(d_gap, d_lat, apart, long_m=SEP_LONG_M):
        """Two riders are too close when they fall inside an ellipse: `long_m` along the road, `apart` sideways."""
        return (d_gap / long_m) ** 2 + (d_lat / apart) ** 2 < 1.0

    def _squeeze_to_road(self, lateral):
        """A slot's sideways offset (relative to you) squeezed so that the group ends where the road ends: the
        slots on each side of you are scaled to the room there is on that side, which keeps their order and their
        proportions. Ride at the edge of the road and that edge is the edge of the group. Only for road_limits
        'auto' (the old fixed zone just clamps)."""
        if str(self.config.get('road_limits', 'auto')).lower() == 'off' or not self.slots:
            return lateral
        limits = self._lateral_limits()
        if limits is None:
            return lateral
        low, high = limits
        if lateral >= 0:
            reach = max(l for _, l in self.slots) + SQUEEZE_REACH_MARGIN_M
            room = max(high, 0.0)
        else:
            reach = -min(l for _, l in self.slots) + SQUEEZE_REACH_MARGIN_M
            room = max(-low, 0.0)
        return lateral * min(1.0, room / reach) if reach > 0 else lateral

    @staticmethod
    def _within_road(lateral, limits):
        if limits is None:
            return lateral
        low, high = limits
        return clamp(lateral, low, high) if low <= high else (low + high) / 2.0

    def _keep_apart(self, rider, new_gap, new_lat, max_lat, tick_seconds):
        """Nobody rides through anybody: a rider behind you whose next step would land on another rider
        sidesteps (away from him), or holds his place along the road, or waits. After KEEP_APART_PATIENCE_S
        of being blocked he is let through so a rotation can never deadlock."""
        apart = self._cfg_float('keep_apart', 0.0)
        if apart <= 0 or abs(new_gap) <= 0.5 or rider.pull_phase or rider.dropping:
            rider.blocked = 0.0         # (a rider overtaking through the group has to pass the others)
            return new_gap, new_lat
        others = [o for o in self.riders if o is not rider and abs(o.gap) > 0.5]

        long_m = max(1.0, self._cfg_float('keep_apart_long', SEP_LONG_M))

        def hit(gap, lateral):
            return any(self._too_close(o.gap - gap, o.lateral - lateral, apart, long_m) for o in others)

        if not hit(new_gap, new_lat):
            rider.blocked = 0.0
            return new_gap, new_lat
        if rider.blocked > KEEP_APART_PATIENCE_S:
            return new_gap, new_lat
        rider.blocked += tick_seconds
        nearest = min(others, key=lambda o: abs(o.gap - new_gap) + 2.0 * abs(o.lateral - new_lat))
        if abs(new_lat - nearest.lateral) < 0.05:
            side = 1.0 if nearest.lateral <= 0 else -1.0
        else:
            side = 1.0 if new_lat > nearest.lateral else -1.0
        limits = self._lateral_limits()

        def sidestep(direction):
            lat = clamp(rider.lateral + direction * max_lat, -MAX_ROAD_HALF_WIDTH_M, MAX_ROAD_HALF_WIDTH_M)
            return self._within_road(lat, limits)

        side_lat = sidestep(side)
        if abs(side_lat - rider.lateral) < 0.2 * max_lat:       # the road (or axis) is in the way: go the other way
            side_lat = sidestep(-side)
        options = [(new_gap, side_lat), (rider.gap, side_lat), (rider.gap, rider.lateral)]
        for option in options:
            if not hit(*option):
                return option

        def clearance(option):
            return min(((o.gap - option[0]) / long_m) ** 2 + ((o.lateral - option[1]) / apart) ** 2
                       for o in others)
        # already tangled up: take the move that gets him furthest from the others
        return max(options + [(new_gap, new_lat)], key=clearance)

    def _update_rider(self, rider, stretch, now, tick_seconds):
        max_gap = float(self.config['max_drop'])

        slot_gap, slot_lateral = self.slots[rider.slot]
        # only the riders behind you get stretched on a climb; the ones in
        # front keep their distance
        want_gap = min(slot_gap * stretch, slot_gap + MAX_STRETCH_EXTRA_M) if slot_gap > 0 else slot_gap
        rider.gap_noise += (-rider.gap_noise * NOISE_REVERSION
                            + self.rng.gauss(0, GAP_NOISE_SIGMA_M))
        rider.gap_noise = clamp(rider.gap_noise, -MAX_GAP_NOISE_M, MAX_GAP_NOISE_M)
        want_gap += rider.gap_noise
        head_speed = self.live_speed     # your speed right now, not the one of the last packet
        if slot_gap > 0:
            want_gap += BEHIND_SPEED_MARGIN_S * head_speed     # margin for the extrapolated player position
        elif slot_gap < 0:
            # the same uncertainty applies to the riders in front: never let them end up
            # beside or behind your real position because it was extrapolated a bit short
            want_gap -= LEAD_SPEED_MARGIN_S * head_speed
            want_gap = max(want_gap, -MAX_LEAD_M)
        want_lateral = self._squeeze_to_road(slot_lateral) + self.rng.gauss(0, LATERAL_NOISE_SIGMA_M)
        want_gap, want_lateral = self._apply_wander(rider, slot_gap, want_gap, want_lateral, tick_seconds)
        want_gap = min(want_gap, max_gap)

        # pull state machine: attack from behind, close on the lead, then
        # take over the front slot exactly on arrival (the leader swaps
        # back), hold the pull, and stay at the head until displaced
        max_rate = float(self.config.get('rotation_rate', 0.7))
        if rider.pull_phase == 'approach':
            want_lateral = rider.pull_side
            others = [r for r in self.riders if r is not rider]
            # the leader is whoever holds the frontmost slot (lead slots are
            # numbered from the player outwards, so slot order is not gap order)
            leader = min(others, key=lambda r: self.slots[r.slot][0]) if others else None
            if leader is None:
                rider.pull_phase = None
            else:
                want_gap = leader.gap - (PASS_TAKEOVER_M + 0.5)
                if rider.gap - leader.gap < PASS_ZONE_M:
                    max_rate = self._pass_rate()     # the actual pass is slow
                if rider.gap <= leader.gap - PASS_TAKEOVER_M:
                    # he is clear of the leader: take the front, the old leader
                    # now drifts back to the tail of the group
                    by_gap = sorted((r for r in self.riders if r is not rider and r is not leader),
                                    key=lambda r: self.slots[r.slot][0])
                    slot_order = sorted(range(len(self.slots)), key=lambda i: self.slots[i][0])
                    for slot, r in zip(slot_order, [rider] + by_gap + [leader]):
                        r.slot = slot
                    leader.dropping = True
                    leader.drop_side = -DROP_SIDE_M if rider.pull_side > 0 else DROP_SIDE_M
                    rider.pull_phase = 'pull'
                    _, duration = self._pull_params()
                    rider.pull_until = now + duration * self.rng.uniform(0.7, 1.4)
        elif rider.pull_phase == 'pull':
            max_rate = self._pass_rate()             # settle into the front slot gently
            if now >= rider.pull_until:
                rider.pull_phase = None

        if rider.dropping:
            max_rate = FALL_BACK_RATE_M_PER_S
            want_lateral = rider.drop_side
            if rider.gap >= want_gap - 1.0:
                rider.dropping = False
        # a rider that moves through your position (rotation) passes on the side
        moving = abs(want_gap - rider.gap) > 0.5
        if moving and -4.0 < rider.gap < PULL_MIN_GAP + 1.0:
            side = 1 if rider.lateral >= 0 else -1
            if abs(want_lateral) < PASSING_CLEARANCE_M or want_lateral * side < 0:
                want_lateral = PASSING_CLEARANCE_M * side      # stay on his side until he is past you

        prev_gap = rider.gap
        max_move = max_rate * tick_seconds
        max_lat = MAX_LATERAL_CHANGE_PER_S * tick_seconds
        new_gap = clamp(rider.gap + clamp(want_gap - rider.gap, -max_move, max_move), -MAX_LEAD_M, max_gap)
        new_lat = rider.lateral + clamp(want_lateral - rider.lateral, -max_lat, max_lat)
        new_gap, new_lat = self._keep_apart(rider, new_gap, new_lat, max_lat, tick_seconds)
        new_lat = self._within_road(new_lat, self._lateral_limits())     # never off the road, whatever pushed him
        rider.gap = new_gap
        raw_rate = (rider.gap - prev_gap) / tick_seconds if tick_seconds > 0 else 0.0
        rider.rate += RATE_SMOOTHING * (raw_rate - rider.rate)
        rate = rider.rate
        rider.lateral = new_lat

        sampled = self.trail.sample_behind(rider.gap)
        if not sampled:
            return
        snap, hx, hz = sampled
        # to close on you the rider must ride faster than you did here;
        # rate < 0 when the gap is shrinking
        speed = max(0.0, head_speed - rate)
        if rate < -0.05:
            effort = EFFORT_WHEN_MOVING_UP
        elif rate > 0.05:
            effort = EFFORT_WHEN_FALLING_BACK
        elif rider.gap < 0:
            effort = 1.0 + self.rng.gauss(0, 0.03)     # in front: no draft, full wind
        else:
            effort = DRAFT_FRACTION + 0.25 * clamp(rider.gap / 10.0, 0.0, 1.0)
            effort += self.rng.gauss(0, 0.03)
        rider.dbg = {'want_gap': round(want_gap, 2), 'effort': round(effort, 3), 'speed': round(speed, 2),
                     'max_rate': round(max_rate, 2), 'strength': round(rider.strength, 2)}
        via = self.config.get('lateral_via', 'xz')
        rider.fill_state(snap, hx, hz, speed, snap['power'] * effort,
                         via if via in ('xz', 'road', 'both') else 'xz',
                         clamp(self._cfg_float('lateral_scale', 1.0), 0.2, 4.0), snap.get('sign', 1), self.road_shift,
                         self._road_edges() if str(self.config.get('road_limits', 'auto')).lower() != 'off' else None)


class SoloBlobManager:
    """Owns the config file, one SoloBlob per anchor player, and publishes
    the riders into zoffline's global_peloton_bots registry."""

    def __init__(self, storage_dir, names_provider, game_dictionary, world_time,
                 get_registry, set_registry, logger=None, send_update=None):
        self.storage_dir = storage_dir
        self.config_file = '%s/%s' % (storage_dir, CONFIG_FILE_NAME)
        self.names_provider = names_provider
        self.game_dictionary = game_dictionary
        self.world_time = world_time
        self.get_registry = get_registry
        self.set_registry = set_registry
        self.send_update = send_update          # send_update(player_id, serialized WorldAttribute): to that player's game
        self.logger = logger or logging.getLogger('solo_blob')
        self.lock = threading.RLock()
        self._last_gesture = {}                 # (player id, action) -> monotonic time: the game repeats a held key
        self.blobs = {}
        self.config_mtime = 0
        self.next_config_check = 0

    # ---------- config ----------

    def _read_config(self):
        try:
            with open(self.config_file) as f:
                return json.load(f)
        except Exception as exc:
            self.logger.warning('[SoloBlob] bad config %s: %s' % (self.config_file, repr(exc)))
            return {}

    def _write_config(self, config):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, sort_keys=True)
                f.write('\n')
        except Exception as exc:
            self.logger.warning('[SoloBlob] could not write config: %s' % repr(exc))

    def _config_mtime(self):
        try:
            return os.path.getmtime(self.config_file)
        except OSError:
            return 0

    def load(self):
        with self.lock:
            self.blobs = {}
            if os.path.isfile(self.config_file):
                self.config_mtime = self._config_mtime()
                config = self._read_config()
                if config.get('enabled'):
                    entry = dict(DEFAULT_CONFIG)
                    entry.update(config)
                    entry['riders'] = clamp(int(entry.get('riders', 8)), 1, MAX_RIDERS)
                    anchor = int(entry.get('player_id') or 1)
                    names = []
                    try:
                        names = self.names_provider() or []
                    except Exception as exc:
                        self.logger.warning('[SoloBlob] names provider: %s' % repr(exc))
                    self.blobs[anchor] = SoloBlob(anchor, 0, entry, names, self.game_dictionary, self.logger)
                    self.logger.info('[SoloBlob] load - %d rider(s) around player %d'
                                    % (entry['riders'], anchor))
                    return
            self._publish({})
            self.logger.info('[SoloBlob] load - disabled')

    def _publish(self, riders):
        registry = {k: v for k, v in self.get_registry().items()
                   if not (RIDER_ID_BASE <= k < RIDER_ID_BASE + MAX_BLOBS * RIDERS_PER_BLOB)}
        registry.update(riders)
        self.set_registry(registry)

    def _reload_if_needed(self):
        now = time.monotonic()
        if now < self.next_config_check:
            return
        self.next_config_check = now + CONFIG_CHECK_INTERVAL_SECONDS
        if self._config_mtime() != self.config_mtime:
            self.load()

    # ---------- state feed ----------

    def on_state(self, player_id, state):
        with self.lock:
            blob = self.blobs.get(player_id)
            if blob:
                lag_s = None
                if self.world_time and state.worldTime:
                    lag_s = clamp((self.world_time() - state.worldTime) / 1000.0, -5.0, 5.0)
                blob.on_state(state, lag_s)

    # ---------- gestures ----------

    def on_raw_gesture(self, player_id, payload):
        """Called from the world relay with a raw WAT_B_ACT payload."""
        _, action = blob_gestures.parse_bike_action(payload)
        if action is None:
            self.logger.info('[SoloBlob] unrecognized bike action payload: %s' % payload.hex())
            return None
        now = time.monotonic()
        with self.lock:
            blob = self.blobs.get(player_id)
            if not blob:
                return None
            if now - self._last_gesture.get((player_id, action), -1e9) < GESTURE_REPEAT_IGNORE_S:
                return None
            self._last_gesture[(player_id, action)] = now
            return blob.gesture(action)

    def _emit_gesture(self, blob, rider, action):
        state = rider.route.states[0]
        self.send_update(blob.player_id, blob_gestures.gesture_update(action, state, self.world_time(), rider.id))
        self.logger.info('[SoloBlob] rider %d gesture %s at x=%d y=%d z=%d' % (
            rider.id, udp_node_msgs_pb2.UserBikeAction.Name(action), state.x, state.y_altitude, state.z))

    def _send_gestures(self, blob):
        """Make the riders that decided to give a hand signal do it, in the game of the player they ride with."""
        pending, blob.pending_gestures = blob.pending_gestures, []
        if not pending or self.send_update is None:
            return
        for rider, action in pending:
            self._emit_gesture(blob, rider, action)

    # ---------- tick ----------

    def tick(self, tick_seconds=TICK_SECONDS):
        self._reload_if_needed()
        with self.lock:
            if not self.blobs:
                return
            merged = {}
            for anchor, blob in self.blobs.items():
                try:
                    riders = blob.update(tick_seconds)
                    merged.update(riders)
                    self._send_gestures(blob)
                    if blob.config.get('record') and riders:
                        self._record(blob, riders)
                except Exception as exc:
                    self.logger.error('[SoloBlob] tick player %s: %s' % (anchor, repr(exc)))
            self._publish(merged)

    # ---------- debug recording ----------

    RECORD_FILE_NAME = 'solo_blob_record.jsonl'
    RECORD_MAX_BYTES = 80 * 1024 * 1024
    RECORD_INTERVAL_SECONDS = 0.5

    def _record(self, blob, riders):
        """Debug aid ("record": true in solo_blob.txt): one JSON line per tick with everything
        needed to judge the blob offline - the anchor packet, how its position/speed was
        extrapolated, grade, formation, timers and, per rider, the decision and where he
        really ended up relative to the extrapolated anchor ('rel_long' > 0 = ahead of you;
        it should equal -gap, 'place_err' = rel_long + gap shows how far it is off).
        The previous file is kept as <name>.prev when a new session starts."""
        now = time.monotonic()
        if now < getattr(self, '_next_record', 0):
            return
        self._next_record = now + self.RECORD_INTERVAL_SECONDS
        path = '%s/%s' % (self.storage_dir, self.RECORD_FILE_NAME)
        if not getattr(self, '_record_started', False):
            self._record_started = True
            try:
                if os.path.isfile(path) and os.path.getsize(path) > 0:
                    os.replace(path, path + '.prev')
            except OSError as exc:
                self.logger.warning('[SoloBlob] could not rotate record file: %s' % repr(exc))
        if os.path.isfile(path) and os.path.getsize(path) > self.RECORD_MAX_BYTES:
            return
        trail = blob.trail
        head = trail.entries[-1]
        speed_now, accel, advance = trail.motion()
        ux = uz = 0.0
        if len(trail.entries) > 1:
            prev = trail.entries[-2]
            vx, vz = head['x'] - prev['x'], head['z'] - prev['z']
            vlen = math.hypot(vx, vz)
            if vlen >= 1.0:
                ux, uz = vx / vlen, vz / vlen
        est_x = head['x'] + ux * advance * CM_PER_M      # where the anchor is assumed to be right now
        est_z = head['z'] + uz * advance * CM_PER_M
        riders_out = []
        for r in riders.values():
            st = r.route.states[0]
            dx, dz = st.x - est_x, st.z - est_z
            rel_long = (dx * ux + dz * uz) / CM_PER_M
            rel_lat = (dx * -uz + dz * ux) / CM_PER_M
            row = {'id': r.id, 'slot': r.slot, 'slot_gap': round(blob.slots[r.slot][0], 2),
                   'slot_lat': round(blob.slots[r.slot][1], 2), 'gap': round(r.gap, 2), 'lat': round(r.lateral, 2),
                   'rate': round(r.rate, 2), 'phase': r.pull_phase, 'drop': r.dropping,
                   'rel_long': round(rel_long, 2), 'rel_lat': round(rel_lat, 2),
                   'place_err': round(rel_long + r.gap, 2),
                   'x': round(st.x), 'z': round(st.z), 'y': round(st.y_altitude), 'rt': st.roadTime,
                   'rp': st.roadPosition, 'speed': round(st.speed / MMH_PER_MS, 2), 'power': st.power}
            row.update(r.dbg)
            riders_out.append(row)
        front = sum(1 for r in riders.values() if r.gap < 0)
        line = {
            't': round(time.time(), 2), 'age': round(now - head['t'], 2),
            'anchor': {k: head[k] for k in ('x', 'z', 'y', 'rt', 'rp', 'speed', 'power')},
            'anchor_wt': head['proto'].worldTime, 'anchor_est': {'x': round(est_x), 'z': round(est_z)},
            'motion': {'speed_now': round(speed_now, 2), 'accel': round(accel, 2), 'advance': round(advance, 2),
                       'comp': round(trail.latency_comp, 2), 'lag_last': head.get('lag'),
                       'lag_median': blob._median_lag()},
            'grade': round(blob.grade_raw, 4), 'grade_smooth': round(blob.grade_now, 4),
            'stretch': round(blob.stretch_now, 3), 'mode': blob.mode, 'rows': blob.lead_rows_now,
            'front': front, 'behind': len(riders) - front, 'trail_resets': trail.resets,
            'trail_len_m': round(trail.distances[-1], 1) if trail.distances else 0.0,
            'timers': {'mode_left': round(max(0.0, blob.mode_until - now), 1),
                       'turn_in': round(blob.next_turn - now, 1), 'formation_in': round(blob.next_formation - now, 1),
                       'pull_in': round(blob.next_pull - now, 1), 'shuffle_in': round(blob.next_shuffle - now, 1)},
            'slots': [[round(g, 2), round(l, 2)] for g, l in blob.slots],
            'riders': riders_out,
        }
        with open(path, 'a') as f:
            f.write(json.dumps(line, separators=(',', ':')) + '\n')

    # ---------- chat ----------

    def chat_command(self, player_id, args):
        args = (args or '').strip().lower()
        gesture_words = {
            'hammer': GESTURE_HAMMER, 'toast': GESTURE_TOAST,
            'attack': GESTURE_ATTACK, 'lead': GESTURE_LEAD,
        }
        with self.lock:
            if args.startswith('bot '):          # ".blob bot wave": the nearest rider gives that hand signal right now
                word = args[4:].strip()
                action = blob_gestures.ACTION_WORDS.get(word)
                blob = self.blobs.get(player_id)
                if action is None or not blob or not blob.riders or self.send_update is None:
                    return 'Usage (blob running): .blob bot %s' % '|'.join(blob_gestures.ACTION_WORDS)
                rider = min(blob.riders, key=lambda r: abs(r.gap))
                self._emit_gesture(blob, rider, action)
                return 'Rider %s (gap %.1f m) signals %s.' % (rider.profile.first_name, rider.gap, word)
            if args in gesture_words:
                blob = self.blobs.get(player_id)
                if not blob:
                    return 'Start the blob first with ".blob <n>".'
                return blob.gesture(gesture_words[args])
            if not args:
                blob = self.blobs.get(player_id)
                if blob:
                    extra = ' Mode: %s.' % blob.mode if blob.mode else ''
                    return 'Blob active: %d rider(s) around you.%s' % (len(blob.riders), extra)
                if self.blobs:
                    return 'Blob active around another player.'
                return 'Blob off. Start it with ".blob <n>" (e.g. ".blob 8").'
            if args == 'record':
                config = self._read_config()
                config['record'] = not config.get('record')
                self._write_config(config)
                self.load()
                return 'Recording %s (storage/%s).' % ('ON' if config['record'] else 'off', self.RECORD_FILE_NAME)
            if args in ('new', 'restart', 'reroll'):
                blob = self.blobs.get(player_id)
                if not blob:
                    return 'Start the blob first with ".blob <n>".'
                blob.reroll()
                return 'New riders on the road.'
            if args == 'off':
                config = self._read_config()      # keep every other setting: only switch the blob off
                config['enabled'] = False
                self._write_config(config)
                self.load()
                return 'Blob off.'
            if args.isdigit():
                count = int(args)
                if count <= 0:
                    return self.chat_command(player_id, 'off')
                if count > MAX_RIDERS:
                    return 'Too many riders (max %d).' % MAX_RIDERS
                config = self._read_config()      # keep every other setting (scatter, keep_apart...): change only these three
                config.update({'enabled': True, 'player_id': player_id, 'riders': count})
                self._write_config(config)
                self.load()
                return 'Blob on: %d rider(s) around you.' % count
            return 'Usage: .blob <n>, .blob new, .blob off, .blob hammer|toast|attack|lead'
