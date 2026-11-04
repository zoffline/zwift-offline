"""Hand signals of the solo blob riders (elbow flick, ride on, wave, nice, toast, bell).

A gesture is a WorldAttribute of type WAT_B_ACT. Measured on a real client (logs/zoffline.log, "[Gesture]"):
  * payload = 16 bytes, little endian: [player id (uint64), UserBikeAction (uint32), 1 (uint32)]  (NOT a protobuf
    BikeAction). The performer's id is the first 8 bytes: with the real server the client puts its own player id
    there (observed through a pass-through capture of one's own session); zoffline's single player has id 1.
  * the performer's position goes in x / y_altitude / z as well (centimetres, like PlayerState), importance 1000.
So a bot gestures when we send that packet with the bot's own id and position.
"""
import struct
import time

import udp_node_msgs_pb2
from google.protobuf.message import DecodeError

UBA = udp_node_msgs_pb2.UserBikeAction
ELBOW, WAVE, RIDE_ON, HAMMER, NICE, BRING_IT, TOAST, BELL = (UBA.UBA_ELBOW, UBA.UBA_WAVE, UBA.UBA_RIDEON, UBA.UBA_HAMMER,
                                                             UBA.UBA_NICE, UBA.UBA_BRING_IT, UBA.UBA_TOAST, UBA.UBA_BELL)
ACTION_WORDS = {'elbow': ELBOW, 'wave': WAVE, 'rideon': RIDE_ON, 'nice': NICE, 'bringit': BRING_IT, 'toast': TOAST,
                'bell': BELL, 'hammer': HAMMER}
PAYLOAD_FORMAT = '<QII'          # performer id, UserBikeAction, 1
PAYLOAD_LEN = struct.calcsize(PAYLOAD_FORMAT)
GESTURE_IMPORTANCE = 1000
GESTURE_EXPIRE_MS = 60000          # what the relay gives the gestures of real riders

# --- when riders signal (every chance is "sometimes", never every time; `gesture_chance` in the config scales them all) ---
ELBOW_WHEN_PEELING_OFF = 0.6       # the front rider that is about to give up his place (of the 1-3 that peel off) flicks his elbow
TOAST_AFTER_TURN = 0.3             # the rider that has just finished his turn and reached the back says "I'm toast"
NICE_AFTER_YOUR_TURN = 0.6         # you rode at the front for a while and the group takes over: one rider says "Nice"
BELL_WHEN_COMING_THROUGH = 0.35    # the rider that comes through and takes the front rings his bell
BELL_WHEN_PASSING_YOU = 0.2        # a rider that moves up past you from behind rings his bell
YOUR_TURN_SECONDS = 40.0           # you count as "riding at the front" after this long with nobody ahead of you
MIN_SPACING_S = 5.0                # no two gestures of the group closer together than this
RIDER_COOLDOWN_S = 12.0            # the same rider does not gesture again for this long
TOAST_ONCE_PER_TURN_S = 10.0       # of the riders that peel off together only the first to reach the back may say it
EVENT_LIFETIME_S = 6.0             # a signal that has to wait for the spacing is dropped after this long
NEARBY_M = 15.0                    # the random ride on comes from a rider this close to you (you can see him)
MIN_SPEED_MS = 2.0                 # nobody signals while the group stands still


def parse_bike_action(payload):
    """(performer id, UserBikeAction) in a WAT_B_ACT payload, or (None, None). A protobuf BikeAction (no id) is accepted too."""
    if len(payload) == PAYLOAD_LEN:
        player_id, action, tail = struct.unpack(PAYLOAD_FORMAT, payload)
        if tail == 1:
            return player_id, action
    bike_action = udp_node_msgs_pb2.BikeAction()
    try:
        bike_action.ParseFromString(payload)
    except DecodeError:
        return None, None
    return (0, bike_action.action) if bike_action.HasField('action') else (None, None)


def gesture_update(action, state, world_time, rider_id):
    """The serialized WorldAttribute that makes rider `rider_id`, at `state`, perform `action`."""
    update = udp_node_msgs_pb2.WorldAttribute()
    update.server_realm = udp_node_msgs_pb2.ZofflineConstants.RealmID
    update.wa_type = udp_node_msgs_pb2.WA_TYPE.WAT_B_ACT
    update.payload = struct.pack(PAYLOAD_FORMAT, int(rider_id), int(action), 1)
    update.x = int(state.x)
    update.y_altitude = int(state.y_altitude)
    update.z = int(state.z)
    update.world_time_expire = int(world_time) + GESTURE_EXPIRE_MS
    update.importance = GESTURE_IMPORTANCE
    update.wa_f12 = 1
    update.timestamp = int(time.time() * 1000000)
    return update.SerializeToString()


class GestureDirector:
    """Decides when which rider of the group gives a hand signal, from what the group is doing:
      elbow   a rider peels off the front (1-3 do at once) and gives his place up
      toast   a rider that finished his turn has reached the back
      nice    after you rode at the front for a while and the group takes over
      bell    a rider comes through and takes the front / moves up past you
      ride on a random rider, every `gesture_interval` seconds on average"""

    def __init__(self, rng, now):
        self.rng = rng
        self.next_random = now
        self.last_any = 0.0
        self.cooldown_until = {}      # rider id -> monotonic time
        self.seen = {}                # rider id -> (pull_phase, dropping, behind you) of the previous step
        self.front_since = None       # since when nobody has been riding ahead of you
        self.queue = []               # [expires, rider, action]
        self.last_toast = -1e9

    def reset(self, now, interval):
        self.cooldown_until.clear()
        self.seen.clear()
        self.queue = []
        self.front_since = None
        self.next_random = now + self._wait(interval)

    def _wait(self, interval):
        return max(5.0, interval * self.rng.uniform(0.6, 1.4))

    def _ready(self, rider, now):
        return self.cooldown_until.get(rider.id, 0.0) <= now

    def _maybe(self, chance, scale):
        return self.rng.random() < min(1.0, chance * scale)

    def _detect(self, now, riders, scale):
        """Queue the signals the riders' moves since the last step call for."""
        previous_seen, self.seen = self.seen, {}
        peeling = [r for r in riders if r.dropping and not previous_seen.get(r.id, (r.pull_phase, r.dropping, r.gap > 0))[1]]
        for rider in riders:
            self.seen[rider.id] = (rider.pull_phase, rider.dropping, rider.gap > 0)
        for rider in riders:
            phase, dropping, behind = previous_seen.get(rider.id, (rider.pull_phase, rider.dropping, rider.gap > 0))
            if phase == 'approach' and rider.pull_phase == 'pull' and self._maybe(BELL_WHEN_COMING_THROUGH, scale):
                self.queue.append([now + EVENT_LIFETIME_S, rider, BELL])
            elif behind and rider.gap < 0 and not rider.pull_phase and self._maybe(BELL_WHEN_PASSING_YOU, scale):
                self.queue.append([now + EVENT_LIFETIME_S, rider, BELL])
            if dropping and not rider.dropping and now - self.last_toast > TOAST_ONCE_PER_TURN_S:
                self.last_toast = now          # the first rider back from a turn gets the chance, the others do not
                if self._maybe(TOAST_AFTER_TURN, scale):
                    self.queue.append([now + EVENT_LIFETIME_S, rider, TOAST])
        if peeling and self._maybe(ELBOW_WHEN_PEELING_OFF, scale):
            self.queue.append([now + EVENT_LIFETIME_S, min(peeling, key=lambda r: r.gap), ELBOW])   # the front one of them

    def _track_your_turn(self, now, riders, scale):
        nobody_ahead = not any(r.gap < 0 for r in riders)
        if nobody_ahead:
            if self.front_since is None:
                self.front_since = now
        elif self.front_since is not None:
            led_long_enough = now - self.front_since >= YOUR_TURN_SECONDS
            self.front_since = None
            if led_long_enough and self._maybe(NICE_AFTER_YOUR_TURN, scale):
                self.queue.append([now + EVENT_LIFETIME_S, min(riders, key=lambda r: r.gap), NICE])   # the one that comes through first

    def step(self, now, riders, interval, speed_ms, chance=1.0):
        """[(rider, action)] to perform now (at most one)."""
        if not riders:
            return []
        self._detect(now, riders, chance)
        self._track_your_turn(now, riders, chance)
        self.queue = [e for e in self.queue if e[0] > now]
        if speed_ms < MIN_SPEED_MS or now - self.last_any < MIN_SPACING_S:
            return []
        for entry in self.queue:
            _, rider, action = entry
            if self._ready(rider, now):
                self.queue.remove(entry)
                return self._chosen(rider, action, now)
        if interval <= 0 or now < self.next_random:
            return []
        self.next_random = now + self._wait(interval)
        near = [r for r in riders if abs(r.gap) <= NEARBY_M and self._ready(r, now)]
        return self._chosen(self.rng.choice(near), RIDE_ON, now) if near else []

    def _chosen(self, rider, action, now):
        self.cooldown_until[rider.id] = now + RIDER_COOLDOWN_S
        self.last_any = now
        return [(rider, action)]
