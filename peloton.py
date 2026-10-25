"""
Pelotons for zoffline: a RoboPacer + a custom group of bots that follow it in
formation, move around inside the group, stretch out on climbs and adapt their
power, cadence and heart rate so the group looks real.

The configuration lives in storage/peloton.txt (JSON) and is reloaded
automatically when the file changes. A peloton can also be created/removed from
the chat with ".peloton <n>" / ".peloton off" while riding near a RoboPacer.

This module does not import zwift_offline so it can be tested in isolation; its
dependencies (game dictionary, world clock, logger) are injected.
"""

import bisect
import itertools
import json
import logging
import math
import os
import random
import threading
import time

import profile_pb2
import udp_node_msgs_pb2

CONFIG_FILE_NAME = 'peloton.txt'

# ID range reserved for followers. Must stay below 9000000 (bookmarks) and
# 10000000 (ghosts), and above RoboPacer IDs.
FOLLOWER_ID_BASE = 8000000
FOLLOWER_IDS_PER_PELOTON = 1000
MAX_PELOTONS = (9000000 - FOLLOWER_ID_BASE) // FOLLOWER_IDS_PER_PELOTON
MAX_BOTS_PER_PELOTON = 200

CONFIG_CHECK_INTERVAL_SECONDS = 5

# Zwift protocol units
MM_PER_HOUR_PER_M_PER_S = 3600000   # speed is in millimeters per hour
CM_PER_METER = 100                  # x, y_altitude, z are in centimeters
MICRO_HZ_PER_RPM = 1000000 / 60     # cadenceUHz = rpm / 60 * 1e6
# roadPosition: 1 unit = 0.01 mm (measured by comparing x/z of 2000+ pairs of RoboPacers
# at the same point of the same road). The road center is around 10000000 and real
# riders never leave ~9300000..10700000 (+-7 m).
ROAD_POSITION_UNITS_PER_METER = 100000
ROAD_POSITION_MIN = 9300000
ROAD_POSITION_MAX = 10700000
MAX_LATERAL_OFFSET = 3 * ROAD_POSITION_UNITS_PER_METER  # nobody drifts more than 3 m from the pacer
SIMULATED_LATENCY_MS = 300

# Thresholds to decide whether two consecutive states can be interpolated
MAX_ROAD_TIME_STEP = 50000
MAX_HEADING_STEP = 1000000
MAX_DISTANCE_STEP_METERS = 1000
MAX_SAMPLE_INTERVAL_MS = 5000
MIN_SEGMENT_LENGTH_METERS = 0.01
GRADE_SMOOTHING_WINDOW = 7
MAX_ABS_GRADE = 0.25

# "Believable" group physics
CLIMB_GRADE_THRESHOLD = 0.03        # from 3% the group starts to stretch
CLIMB_STRETCH_PER_GRADE = 6.0       # 8% -> rows 30% further apart
CLIMB_DROP_METERS_PER_GRADE = 1000  # how far weak riders drop per grade point
FULL_CLIMB_GRADE = 0.06             # at 6% drafting barely helps
MAX_GAP_CHANGE_M_PER_S = 0.9        # max relative speed to move up/back
MAX_LATERAL_CHANGE_PER_S = 0.5 * ROAD_POSITION_UNITS_PER_METER  # 0.5 m/s lateral movement
GAP_EASING = 0.25
LATERAL_EASING = 0.3
NOISE_REVERSION = 0.15
GAP_NOISE_SIGMA_M = 0.12
LATERAL_NOISE_SIGMA = 0.04 * ROAD_POSITION_UNITS_PER_METER     # sway of a few cm
MOVING_UP_EFFORT_FACTOR = 4.0
POWER_NOISE_SIGMA = 0.04
DEFAULT_PACER_WEIGHT_KG = 75
PACER_INTENSITY_OF_FTP = 0.8        # the pacer is assumed to ride at 80% of FTP
HEART_RATE_EASING = 0.05
HEART_RATE_IDLE_FRACTION = 0.35
STEEP_CLIMB_CADENCE_DROP_RPM = 8

PREFERENCE_RANK = {'front': 0, 'middle': 1, 'any': 1, 'back': 2}

PROFILE_ITEMS = ['first_name', 'last_name', 'is_male', 'country_code', 'bike_frame', 'bike_frame_colour', 'bike_wheel_front',
    'bike_wheel_rear', 'glasses_type', 'ride_jersey', 'ride_helmet_type', 'ride_shoes_type', 'ride_socks_type',
    'run_shirt_type', 'run_shorts_type', 'run_shoes_type']

DEFAULT_PELOTON_CONFIG = {
    'bots': 20,                 # number of followers
    'columns': 0,               # max group width (0 = automatic)
    'row_gap': 2.2,             # meters between rows
    'lateral_spacing': 65000,   # lateral spacing in roadPosition units (100000 = 1 m)
    'beside_pacer': 2,          # bots riding alongside the pacer
    'dynamics': 1.0,            # 0 = rigid formation, 1 = normal, 2 = very lively
    'shuffle_interval': 30,     # average seconds between position changes
    'draft': 0.7,               # fraction of power used by a bot on a wheel
    'climb_stretch': 1.0,       # how much the group stretches on climbs
    'max_drop': 40,             # max meters a weak bot can drop back
    'riders': [],               # custom bots (name, country, equipment, position, strength...)
}


def course_of(state):
    return (state.f19 & 0xff0000) >> 16

def road_of(state):
    return (state.aux3 & 0xff00) >> 8

def is_forward(state):
    return (state.f19 & 4) != 0

def clamp(value, low, high):
    return max(low, min(high, value))

def lerp(a, b, fraction):
    return a + (b - a) * fraction


class PelotonRider:
    """A follower bot. Exposes profile/route/position like zoffline bots
    (route holds a single state, position is always 0)."""

    def __init__(self, profile, preference, strength, weight_kg, cadence_rpm, hr_rest, hr_max):
        self.profile = profile
        self.route = None
        self.position = 0
        self.preference = preference
        self.strength = strength
        self.weight_kg = weight_kg
        self.cadence_rpm = cadence_rpm
        self.hr_rest = hr_rest
        self.hr_max = hr_max
        self.heart_rate = hr_rest
        self.ftp_watts = 0
        self.slot = 0
        self.gap = 0.0           # meters behind the pacer (smoothed)
        self.lateral = 0.0       # lateral offset (smoothed)
        self.gap_jitter = 0.0    # own deviation from the slot
        self.lateral_jitter = 0.0
        self.gap_noise = 0.0     # continuous noise (Ornstein-Uhlenbeck)
        self.lateral_noise = 0.0
        self.previous_total_gap = None

    @property
    def id(self):
        return self.profile.id


class Peloton:
    """A RoboPacer and its group of followers."""

    def __init__(self, index, pacer_id, pacer, config, names_pool, game_dictionary, world_time):
        self.index = index
        self.pacer_id = pacer_id
        self.pacer = pacer
        self.config = config
        self.world_time = world_time
        self.rng = random.Random(pacer_id)  # same config -> same bots after reloading
        self.game_dictionary = game_dictionary
        self.next_shuffle = time.monotonic() + self._random_shuffle_delay()
        self._prepare_route()
        self.pacer_weight_kg = (pacer.profile.weight_in_grams / 1000) or DEFAULT_PACER_WEIGHT_KG
        self.pacer_average_wkg = self._average_pacer_wkg()
        self.riders = self._create_riders(names_pool)
        self.slots = self._build_slots(len(self.riders))
        self._assign_initial_slots()

    # ---------- pacer route geometry ----------

    def _prepare_route(self):
        """Precomputes the real length of each segment (from speed) and the smoothed
        grade, to place each bot N meters behind the pacer."""
        states = self.pacer.route.states
        count = len(states)
        self.segment_lengths = []
        raw_grades = []
        for i in range(count):
            a, b = states[i], states[(i + 1) % count]
            elapsed_ms = b.worldTime - a.worldTime
            seconds = elapsed_ms / 1000 if 0 < elapsed_ms < MAX_SAMPLE_INTERVAL_MS else 1.0
            average_speed = (a.speed + b.speed) / 2 / MM_PER_HOUR_PER_M_PER_S
            length = max(average_speed * seconds, MIN_SEGMENT_LENGTH_METERS)
            self.segment_lengths.append(length)
            grade = 0.0
            if self._is_continuous(a, b) and length > 1:
                grade = (b.y_altitude - a.y_altitude) / CM_PER_METER / length
            raw_grades.append(clamp(grade, -MAX_ABS_GRADE, MAX_ABS_GRADE))
        self.segment_starts = [0.0] + list(itertools.accumulate(self.segment_lengths))[:-1]
        self.route_length = self.segment_starts[-1] + self.segment_lengths[-1]
        half_window = GRADE_SMOOTHING_WINDOW // 2
        self.grades = [sum(raw_grades[(i + k) % count] for k in range(-half_window, half_window + 1)) / GRADE_SMOOTHING_WINDOW
                       for i in range(count)]

    def _average_pacer_wkg(self):
        powers = [s.power for s in self.pacer.route.states if s.power > 0]
        if not powers:
            return 3.0
        return sum(powers) / len(powers) / self.pacer_weight_kg

    @staticmethod
    def _is_continuous(a, b):
        return (course_of(a) == course_of(b) and road_of(a) == road_of(b) and is_forward(a) == is_forward(b)
                and abs(b.roadTime - a.roadTime) < MAX_ROAD_TIME_STEP)

    def _locate(self, route_distance):
        """Returns (state index, fraction) for a distance along the route."""
        route_distance %= self.route_length
        index = bisect.bisect_right(self.segment_starts, route_distance) - 1
        fraction = (route_distance - self.segment_starts[index]) / self.segment_lengths[index]
        return index, clamp(fraction, 0.0, 1.0)

    def _interpolated_state(self, index, fraction):
        states = self.pacer.route.states
        a, b = states[index], states[(index + 1) % len(states)]
        state = udp_node_msgs_pb2.PlayerState()
        state.CopyFrom(a if fraction < 0.5 else b)
        if not self._is_continuous(a, b):
            return state  # road change or end of lap: use the nearest state
        state.roadTime = round(lerp(a.roadTime, b.roadTime, fraction))
        state.roadPosition = round(lerp(a.roadPosition, b.roadPosition, fraction))
        state.x = lerp(a.x, b.x, fraction)
        state.y_altitude = lerp(a.y_altitude, b.y_altitude, fraction)
        state.z = lerp(a.z, b.z, fraction)
        state.speed = round(lerp(a.speed, b.speed, fraction))
        state.power = round(lerp(a.power, b.power, fraction))
        if 0 <= b.distance - a.distance < MAX_DISTANCE_STEP_METERS:
            state.distance = round(lerp(a.distance, b.distance, fraction))
        if abs(b.heading - a.heading) < MAX_HEADING_STEP:
            state.heading = round(lerp(a.heading, b.heading, fraction))
        return state

    # ---------- bot creation ----------

    def _create_riders(self, names_pool):
        custom_riders = self.config.get('riders') or []
        total = clamp(int(self.config.get('bots', len(custom_riders))), 0, MAX_BOTS_PER_PELOTON)
        total = max(total, min(len(custom_riders), MAX_BOTS_PER_PELOTON))
        random_names = self.rng.sample(names_pool, min(len(names_pool), total)) if names_pool else []
        riders = []
        for i in range(total):
            spec = custom_riders[i] if i < len(custom_riders) else {}
            name_source = random_names[i % len(random_names)] if random_names else {}
            riders.append(self._create_rider(i, spec, name_source))
        return riders

    def _create_rider(self, rider_index, spec, name_source):
        rng = self.rng
        profile = profile_pb2.PlayerProfile()
        self._random_equipment(profile)
        profile.id = FOLLOWER_ID_BASE + self.index * FOLLOWER_IDS_PER_PELOTON + rider_index + 1
        for source in (name_source, spec):  # custom values override random ones
            for item in PROFILE_ITEMS:
                if item in source:
                    setattr(profile, item, source[item])
        if 'is_male' not in spec and 'is_male' not in name_source:
            profile.is_male = bool(rng.getrandbits(1))
        self._random_body(profile)
        weight_kg = float(spec.get('weight', rng.uniform(64, 84) if profile.is_male else rng.uniform(52, 68)))
        height_cm = float(spec.get('height', rng.uniform(170, 192) if profile.is_male else rng.uniform(158, 178)))
        profile.weight_in_grams = round(weight_kg * 1000)
        profile.height_in_millimeters = round(height_cm * 10)
        preference = spec.get('position', 'any')
        if preference not in PREFERENCE_RANK:
            preference = 'any'
        rider = PelotonRider(profile, preference,
                             strength=clamp(float(spec.get('strength', rng.gauss(1.0, 0.07))), 0.5, 1.5),
                             weight_kg=weight_kg,
                             cadence_rpm=float(spec.get('cadence', rng.uniform(80, 96))),
                             hr_rest=rng.uniform(52, 66),
                             hr_max=float(spec.get('max_heart_rate', rng.uniform(176, 196))))
        rider.ftp_watts = self.pacer_average_wkg / PACER_INTENSITY_OF_FTP * rider.strength * weight_kg
        return rider

    def _random_equipment(self, profile):
        gd, rng = self.game_dictionary, self.rng
        profile.ride_helmet_type = rng.choice(gd['headgears'])
        profile.glasses_type = rng.choice(gd['glasses'])
        profile.ride_shoes_type = rng.choice(gd['bikeshoes'])
        profile.ride_socks_type = rng.choice(gd['socks'])
        profile.ride_socks_length = rng.randrange(4)
        profile.ride_jersey = rng.choice(gd['jerseys'])
        profile.bike_wheel_rear, profile.bike_wheel_front = rng.choice(gd['wheels'])
        profile.bike_frame = rng.choice(list(gd['bikeframes'].keys()))
        profile.run_shirt_type = rng.choice(gd['runshirts'])
        profile.run_shorts_type = rng.choice(gd['runshorts'])
        profile.run_shoes_type = rng.choice(gd['runshoes'])

    def _random_body(self, profile):
        gd, rng = self.game_dictionary, self.rng
        profile.hair_type = rng.choice(gd['hair_types'])
        profile.hair_colour = rng.randrange(5)
        if profile.is_male:
            profile.body_type = rng.choice(gd['body_types_male'])
            profile.facial_hair_type = rng.choice(gd['facial_hair_types'])
            profile.facial_hair_colour = rng.randrange(5)
        else:
            profile.body_type = rng.choice(gd['body_types_female'])

    # ---------- formation ----------

    def _build_slots(self, count):
        """Builds the group slots as (meters behind, lateral offset).
        Narrow at the front (pacer's wheel), wider towards the back."""
        spacing = float(self.config['lateral_spacing'])
        row_gap = float(self.config['row_gap'])
        slots = []
        beside = min(int(self.config['beside_pacer']), count)
        for i in range(beside):
            side = -1 if i % 2 == 0 else 1
            depth = i // 2
            slots.append((0.6 + depth * row_gap * 0.3, side * spacing * (1 + depth)))
        columns = int(self.config['columns']) or clamp(round(math.sqrt(count / 2.5)) + 1, 2, 6)
        row = 1
        while len(slots) < count:
            width = min(columns, row + 1)
            stagger = spacing * 0.25 * (1 if row % 2 else -1) if width == columns else 0
            for column in range(width):
                if len(slots) < count:
                    slots.append((row * row_gap, (column - (width - 1) / 2) * spacing + stagger))
            row += 1
        return slots

    def _assign_initial_slots(self):
        ordered = sorted(self.riders, key=lambda r: PREFERENCE_RANK[r.preference] + self.rng.random() * 1.5)
        for slot_index, rider in enumerate(ordered):
            self._move_rider_to_slot(rider, slot_index)
            rider.gap = self.slots[slot_index][0]
            rider.lateral = self.slots[slot_index][1]

    def _move_rider_to_slot(self, rider, slot_index):
        rider.slot = slot_index
        rider.gap_jitter = self.rng.gauss(0, 0.3)
        rider.lateral_jitter = self.rng.gauss(0, float(self.config['lateral_spacing']) * 0.15)

    def _random_shuffle_delay(self):
        interval = float(self.config.get('shuffle_interval', DEFAULT_PELOTON_CONFIG['shuffle_interval']))
        return self.rng.uniform(0.5, 1.5) * interval

    def _shuffle(self):
        """A bot tries to move up or back a few positions and swaps its slot
        with whoever was there. The actual movement is gradual."""
        if len(self.riders) < 2:
            return
        by_slot = {r.slot: r for r in self.riders}
        moves = max(1, round(len(self.riders) / 15 * float(self.config['dynamics'])))
        for _ in range(moves):
            rider = self.rng.choice(self.riders)
            direction = self._shuffle_direction(rider)
            distance = self.rng.randint(1, max(2, int(self.config['columns']) or 3) * 2)
            target_slot = clamp(rider.slot + direction * distance, 0, len(self.slots) - 1)
            if target_slot == rider.slot:
                continue
            other = by_slot[target_slot]
            original_slot = rider.slot
            self._move_rider_to_slot(rider, target_slot)
            self._move_rider_to_slot(other, original_slot)
            by_slot[target_slot], by_slot[original_slot] = rider, other

    def _shuffle_direction(self, rider):
        if rider.preference == 'front' or (rider.strength > 1.03 and self.rng.random() < 0.6):
            return -1
        if rider.preference == 'back' or (rider.strength < 0.97 and self.rng.random() < 0.6):
            return 1
        return self.rng.choice((-1, 1))

    # ---------- per-tick simulation ----------

    def update(self, tick_seconds):
        if not self.riders or not self.pacer.route.states:
            return
        if float(self.config['dynamics']) > 0 and time.monotonic() >= self.next_shuffle:
            self._shuffle()
            self.next_shuffle = time.monotonic() + self._random_shuffle_delay()
        pacer_index = self.pacer.position % len(self.pacer.route.states)
        pacer_distance = self.segment_starts[pacer_index]
        grade = self.grades[pacer_index]
        world_time = self.world_time() - SIMULATED_LATENCY_MS
        for rider in self.riders:
            self._update_rider(rider, pacer_distance, grade, tick_seconds, world_time)

    def _target_gap(self, rider, grade):
        slot_gap = self.slots[rider.slot][0]
        climb_excess = max(0.0, grade - CLIMB_GRADE_THRESHOLD)
        climb_stretch = float(self.config['climb_stretch'])
        stretch = 1 + climb_excess * CLIMB_STRETCH_PER_GRADE * climb_stretch
        weakness = max(0.0, 1.0 - rider.strength)
        dropped = min(float(self.config['max_drop']), climb_excess * CLIMB_DROP_METERS_PER_GRADE * weakness * climb_stretch)
        return slot_gap * stretch + dropped + rider.gap_jitter

    def _update_noise(self, rider):
        dynamics = float(self.config['dynamics'])
        rider.gap_noise += -rider.gap_noise * NOISE_REVERSION + self.rng.gauss(0, GAP_NOISE_SIGMA_M * dynamics)
        rider.lateral_noise += -rider.lateral_noise * NOISE_REVERSION + self.rng.gauss(0, LATERAL_NOISE_SIGMA * dynamics)

    def _update_rider(self, rider, pacer_distance, grade, tick_seconds, world_time):
        # Approach the target slot with limited relative speed (looks like "moving up in the group")
        target_gap = self._target_gap(rider, grade)
        target_lateral = self.slots[rider.slot][1] + rider.lateral_jitter
        max_gap_step = MAX_GAP_CHANGE_M_PER_S * tick_seconds
        max_lateral_step = MAX_LATERAL_CHANGE_PER_S * tick_seconds
        rider.gap += clamp((target_gap - rider.gap) * GAP_EASING, -max_gap_step, max_gap_step)
        rider.lateral += clamp((target_lateral - rider.lateral) * LATERAL_EASING, -max_lateral_step, max_lateral_step)
        self._update_noise(rider)

        total_gap = max(0.3, rider.gap + rider.gap_noise)
        gap_change = 0.0 if rider.previous_total_gap is None else total_gap - rider.previous_total_gap
        rider.previous_total_gap = total_gap

        index, fraction = self._locate(pacer_distance - total_gap)
        state = self._interpolated_state(index, fraction)
        state.id = rider.id
        state.watchingRiderId = rider.id
        state.justWatching = False
        state.groupId = 0
        state.worldTime = world_time
        lateral_offset = clamp(rider.lateral + rider.lateral_noise, -MAX_LATERAL_OFFSET, MAX_LATERAL_OFFSET)
        state.roadPosition = round(clamp(state.roadPosition + lateral_offset, ROAD_POSITION_MIN, ROAD_POSITION_MAX))

        route_speed = state.speed / MM_PER_HOUR_PER_M_PER_S
        rider_speed = max(0.0, route_speed - gap_change / tick_seconds)
        state.speed = round(rider_speed * MM_PER_HOUR_PER_M_PER_S)
        state.power = self._rider_power(rider, state.power, total_gap, gap_change / tick_seconds, route_speed, grade)
        state.cadenceUHz = round(self._rider_cadence(rider, state.power, grade) * MICRO_HZ_PER_RPM)
        state.heartrate = round(self._rider_heart_rate(rider, state.power))

        ghost = udp_node_msgs_pb2.Ghost()
        ghost.player_id = rider.id
        ghost.states.append(state)
        rider.route = ghost  # atomic swap: the UDP thread never sees a half-written state

    def _rider_power(self, rider, pacer_power, total_gap, gap_change_per_second, speed, grade):
        if pacer_power <= 0:
            return 0  # descent: everybody coasts
        is_in_wind = total_gap < float(self.config['row_gap']) * 0.6
        draft = 1.0 if is_in_wind else float(self.config['draft'])
        climb_factor = clamp(grade / FULL_CLIMB_GRADE, 0.0, 1.0)
        draft += (1.0 - draft) * climb_factor  # drafting barely helps on climbs
        moving_up = max(0.0, -gap_change_per_second) / max(speed, 1.0)
        effort = 1 + moving_up * MOVING_UP_EFFORT_FACTOR
        pacer_wkg = pacer_power / self.pacer_weight_kg
        noise = 1 + self.rng.gauss(0, POWER_NOISE_SIGMA)
        return max(0, round(pacer_wkg * rider.weight_kg * draft * effort * noise))

    def _rider_cadence(self, rider, power, grade):
        if power <= 0:
            return 0
        intensity = min(1.5, power / max(rider.ftp_watts, 1))
        cadence = rider.cadence_rpm * (0.95 + 0.1 * intensity) + self.rng.gauss(0, 1.5)
        if grade > FULL_CLIMB_GRADE:
            cadence -= STEEP_CLIMB_CADENCE_DROP_RPM
        return max(0.0, cadence)

    def _rider_heart_rate(self, rider, power):
        intensity = min(1.2, power / max(rider.ftp_watts, 1))
        reserve = rider.hr_max - rider.hr_rest
        target = rider.hr_rest + reserve * (HEART_RATE_IDLE_FRACTION + (1 - HEART_RATE_IDLE_FRACTION) * 0.85 * intensity)
        rider.heart_rate += (min(target, rider.hr_max) - rider.heart_rate) * HEART_RATE_EASING
        return rider.heart_rate


class PelotonManager:
    """Loads pelotons from storage/peloton.txt, updates them on every tick of the
    RoboPacers thread and handles the .peloton chat command."""

    def __init__(self, storage_dir, pace_partners, names_provider, game_dictionary, world_time,
                 publish_followers, forget_profiles=None, logger=None):
        self.config_file = os.path.join(storage_dir, CONFIG_FILE_NAME)
        self.pace_partners = pace_partners
        self.names_provider = names_provider
        self.game_dictionary = game_dictionary
        self.world_time = world_time
        self.publish_followers = publish_followers  # callback receiving the dict id -> PelotonRider
        self.forget_profiles = forget_profiles or (lambda ids: None)
        self.logger = logger or logging.getLogger('peloton')
        self.lock = threading.RLock()
        self.pelotons = []
        self.followers = {}
        self.names_pool = None
        self.config_mtime = None
        self.reload_requested = False
        self.next_config_check = 0

    # ---------- configuration ----------

    def _read_config(self):
        if not os.path.isfile(self.config_file):
            return {'pelotons': []}
        with open(self.config_file, encoding='utf-8') as f:
            config = json.load(f)
        if not isinstance(config.get('pelotons'), list):
            raise ValueError('"pelotons" must be a list')
        return config

    def _write_config(self, config):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        self.logger.info('💾 [Peloton] config saved to %s' % self.config_file)

    def _find_pacer_id(self, pacer_reference):
        """Accepts the RoboPacer folder name or its player ID."""
        if isinstance(pacer_reference, int) or str(pacer_reference).isdigit():
            pacer_id = int(pacer_reference)
            return pacer_id if pacer_id in self.pace_partners else None
        for pacer_id, pacer in self.pace_partners.items():
            if str(getattr(pacer, 'folder', '')).lower() == str(pacer_reference).lower():
                return pacer_id
        return None

    def _pacer_reference(self, pacer_id):
        return getattr(self.pace_partners[pacer_id], 'folder', None) or pacer_id

    def _config_mtime(self):
        try:
            return os.path.getmtime(self.config_file)
        except OSError:
            return None

    def load(self):
        """(Re)builds all pelotons. If the config is invalid the current ones are kept."""
        started = time.perf_counter()
        try:
            config = self._read_config()
        except Exception as exc:
            self.logger.error('❌ [Peloton] load - invalid %s: %s' % (self.config_file, repr(exc)))
            self.config_mtime = self._config_mtime()
            return
        if self.names_pool is None:
            self.names_pool = list(self.names_provider())
        # The index (and therefore the bot IDs) depends on the RoboPacer, not on the
        # config order: removing a peloton does not change the IDs of the others.
        pacer_indexes = {pacer_id: i for i, pacer_id in enumerate(sorted(self.pace_partners.keys())[:MAX_PELOTONS])}
        pelotons = []
        for entry in config['pelotons']:
            peloton = self._build_peloton(pacer_indexes, entry)
            if peloton is None:
                continue
            if any(p.pacer_id == peloton.pacer_id for p in pelotons):
                self.logger.warning('⚠️ [Peloton] load - duplicated entry for pacer %s ignored' % peloton.pacer_id)
                continue
            pelotons.append(peloton)
        followers = {rider.id: rider for peloton in pelotons for rider in peloton.riders}
        with self.lock:
            # first tick before publishing, so no bot is left without a state
            for peloton in pelotons:
                peloton.update(1.0)
            old_ids = set(self.followers.keys())
            self.pelotons = pelotons
            self.followers = followers
            self.publish_followers(followers)
            self.forget_profiles(old_ids)
        self.config_mtime = self._config_mtime()
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.logger.info('✅ [Peloton] load - %d peloton(s), %d follower bot(s) in %.0f ms' % (len(pelotons), len(followers), elapsed_ms))

    def _build_peloton(self, pacer_indexes, entry):
        if not isinstance(entry, dict) or entry.get('enabled', True) is False:
            return None
        pacer_id = self._find_pacer_id(entry.get('pacer', ''))
        if pacer_id is None or pacer_id not in pacer_indexes:
            self.logger.warning('⚠️ [Peloton] load - RoboPacer "%s" not found in storage/robopacers' % entry.get('pacer'))
            return None
        config = dict(DEFAULT_PELOTON_CONFIG)
        config.update(entry)
        try:
            peloton = Peloton(pacer_indexes[pacer_id], pacer_id, self.pace_partners[pacer_id], config, self.names_pool, self.game_dictionary, self.world_time)
        except Exception as exc:
            self.logger.error('❌ [Peloton] load - could not build peloton for "%s": %s' % (entry.get('pacer'), repr(exc)))
            return None
        self.logger.info('🔄 [Peloton] load - %s + %d bots' % (self.pace_partners[pacer_id].profile.last_name or pacer_id, len(peloton.riders)))
        return peloton

    def request_reload(self):
        self.reload_requested = True

    def _reload_if_needed(self):
        now = time.monotonic()
        if not self.reload_requested and now < self.next_config_check:
            return
        self.next_config_check = now + CONFIG_CHECK_INTERVAL_SECONDS
        if self.reload_requested or self._config_mtime() != self.config_mtime:
            self.reload_requested = False
            self.load()

    # ---------- tick ----------

    def tick(self, tick_seconds=1.0):
        """Called from the RoboPacers thread right after the pacers advance."""
        self._reload_if_needed()
        with self.lock:
            for peloton in self.pelotons:
                try:
                    peloton.update(tick_seconds)
                except Exception as exc:
                    self.logger.error('❌ [Peloton] tick - pacer %s: %s' % (peloton.pacer_id, repr(exc)))

    # ---------- chat ----------

    def _nearest_pacer_id(self, state):
        if state.watchingRiderId in self.pace_partners:
            return state.watchingRiderId
        best_id, best_distance = None, None
        for pacer_id, pacer in self.pace_partners.items():
            pacer_state = pacer.route.states[pacer.position]
            if course_of(pacer_state) != course_of(state):
                continue
            distance = math.hypot(pacer_state.x - state.x, pacer_state.z - state.z)
            if best_distance is None or distance < best_distance:
                best_id, best_distance = pacer_id, distance
        return best_id

    def chat_command(self, state, arguments):
        """.peloton           -> size of the nearest RoboPacer's peloton
           .peloton <n>       -> creates/updates the peloton with n bots (saved to peloton.txt)
           .peloton off       -> removes that RoboPacer's peloton"""
        pacer_id = self._nearest_pacer_id(state)
        if pacer_id is None:
            return 'No RoboPacer on this course'
        pacer_name = self.pace_partners[pacer_id].profile.last_name or str(pacer_id)
        try:
            config = self._read_config()
        except Exception as exc:
            self.logger.error('❌ [Peloton] chat_command - invalid config: %s' % repr(exc))
            return 'peloton.txt is invalid, check the server log'
        entries = config['pelotons']
        entry = next((e for e in entries if isinstance(e, dict) and self._find_pacer_id(e.get('pacer', '')) == pacer_id), None)
        arguments = arguments.strip().lower()
        if not arguments:
            return '%s: %d bots' % (pacer_name, entry.get('bots', 0) if entry else 0)
        if arguments == 'off':
            if entry:
                entries.remove(entry)
                self._write_config(config)
                self.load()
            return 'Peloton removed from %s' % pacer_name
        if not arguments.isdigit():
            return 'Usage: .peloton <bots> | .peloton off'
        bots = clamp(int(arguments), 0, MAX_BOTS_PER_PELOTON)
        if entry is None:
            entry = {'pacer': self._pacer_reference(pacer_id)}
            entries.append(entry)
        entry['bots'] = bots
        self._write_config(config)
        self.load()
        self.logger.info('📨 [Peloton] chat_command - %s now has %d bots' % (pacer_name, bots))
        return 'Peloton of %d bots following %s' % (bots, pacer_name)
