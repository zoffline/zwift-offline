# Solo blob: settings in `storage/solo_blob.txt`

The file is JSON (it may span several lines). Missing keys fall back to the defaults in `DEFAULT_CONFIG` in `solo_blob.py`. The file is reloaded after a `.blob` command; after editing it by hand, restart the server.

In-game chat commands: `.blob <n>` (turn on, n riders, max 30), `.blob new`, `.blob off`, `.blob record` (toggles recording), `.blob hammer|toast|attack|lead`. The commands only change `enabled`, `player_id`, `riders` and `record`; the rest of the file is left alone.

The "Default" column holds the settings that were verified visually as the best looking.

## How the blob works

The blob is a group of simulated riders that rides around you. Riders in front of you keep their place along the road, riders behind you follow your recorded path, and the group rotates (riders take turns at the front) when `rotate` is on. Your own position, speed and road position come from the game, so the group follows you on flats, climbs and descents.

### Two layouts: rows and scatter

`scatter` selects how the riders behind you are arranged:

| | Row layout (`scatter: false`) | Scatter layout (`scatter: true`, default) |
|---|---|---|
| Looks like | Staggered rows, a tidy grid | An irregular, natural bunch spread over the road (blue-noise placement) |
| Width | `columns` abreast (0 = automatic, 2-5) | `scatter_width` meters wide |
| Length | Rows `row_gap` apart, kept within `tail_gap` behind you | Riders at least `scatter_gap` apart along the road, up to `max_drop` behind you |
| Sideways pitch | Exactly `lateral_spacing` | At least `max(0.9, 1.15 * keep_apart, scatter_side, lateral_spacing)` |
| Riders in front | Formations built from `lead_gap`, `lead_lateral`, `lead_spread` | Placed by the same scatter pattern, squeezed into `max_lead` meters |

Settings that apply only to one layout:

- **Row only:** `columns`, `row_gap`, `tail_gap`, `ragged_rows`. With `scatter: true` they are ignored.
- **Scatter only:** `scatter_width`, `scatter_gap`, `scatter_side`, `scatter_beside`.
- **Both layouts:** everything else (rotation, gestures, wander, keep_apart, road limits, ...). `lateral_spacing` works in both, see the FAQ at the end.

### Recommended starting point

Use the defaults (scatter layout) and change one thing at a time:

1. Set `riders` (more riders = a longer group; 24 riders are about 19 m long, 30 riders about 24 m).
2. If the group looks too loose or too tight sideways, change `scatter_width`; for the length along the road change `scatter_gap`.
3. If riders overlap, raise `keep_apart` / `keep_apart_long`. If the group looks too spread out, lower them or `scatter_side`.
4. Leave `road_limits` on `"auto"` (and `road_half_width` above 0): the blob then knows the invisible wall next to the centre line and the edge of each road by itself and slides the group sideways when you ride close to them. Only if you set `road_limits` to `"off"` do you tune `road_half_width`, `road_axis_limit` and `road_axis_side` by hand.
5. Restart the server and judge the result in the game.

### Dependencies between options

- `lateral_via` must be `"both"` for the sideways spread to show in the game at full width. With `"xz"` the game flattens the group to about 40% of its width.
- `road_axis_limit` and `road_axis_side` do nothing unless `road_half_width` > 0 and `road_limits` is `"off"`; with `"auto"` (default) the side comes from your direction of travel.
- `keep_apart` = 0 switches off the collision avoidance, so riders can ride through each other. The scatter layout also reads `keep_apart` and `keep_apart_long` to choose its minimum spacing, so changing them changes the layout itself.
- `wander_*` are ignored for the riders in front of you and, along the road, for the first row on your wheel. A drift that would put a rider on top of another one is cancelled.
- `rotate: false` stops riders taking the front on their own (gestures still work). `pull_interval` sets how often the front rotates; `turn_interval` is a separate timer for your own turn at the front.
- `full_range: true` lets the number of riders in front range from none to all; `lead_spread` limits how much it changes at once, `max_lead` limits how far ahead they sit.
- `latency_comp` shifts the whole group along the road; it matters at speed (descents), not for the layout.

## General

| Key | Default | Description |
|---|---|---|
| `enabled` | `false` | Turns on the group of riders around you. |
| `player_id` | `1` | The player the group rides around (only in the file, not in the defaults dictionary). |
| `riders` | `8` | Number of riders (1-30). More riders make a longer group. |
| `only_kitted` | `true` | Draws only riders from `bot.txt` that have a team kit (the others would ride in a random kit). |
| `record` | `false` | Records the ride to `storage/solo_blob_record.jsonl` (analyse it with `scripts/analyze_blob_record.py`). |
| `diag_interval` | `5` | Seconds between diagnostic log lines (0 = off). |
| `latency_comp` | `0` | Seconds your packets are old when sent; the group rides that much further ahead of the last packet. `"auto"` = use the measured `packet_lag` from the diag log line. Matters most at speed (descents). |

## Group layout

| Key | Default | Description |
|---|---|---|
| `scatter` | `true` | `true` = riders behind you are scattered over the width of the road (blue-noise layout), `false` = they sit in rows. With `true`, `columns` and `tail_gap` are ignored. |
| `scatter_width` | `3.8` | Meters: how wide the scattered group may spread. |
| `scatter_gap` | `1.75` | Meters along the road between riders of the same lane. |
| `scatter_side` | `1.3` | Meters: riders level with each other are at least this far apart sideways (closer sideways means further apart along the road). |
| `scatter_beside` | `1.2` | Meters sideways at which a scattered rider may ride right beside you. |
| `lateral_spacing` | `0.95` | Meters between riders side to side. Row layout: the exact column pitch. Scatter layout: only a lower bound for the sideways distance of riders level with each other, which is `max(0.9, 1.15 * keep_apart, scatter_side, lateral_spacing)`. With the current defaults `scatter_side` (1.3) is the largest, so this value has no effect until it exceeds 1.3. |
| `row_gap` | `1.8` | Meters between rows (row layout; a bike is about 1.8 m long). |
| `tail_gap` | `4.0` | The group tries to stay within this many meters behind you (row layout). |
| `columns` | `0` | Maximum group width in the row layout (0 = automatic). |
| `ragged_rows` | `false` | `true` = rows behind you differ in width, spacing and stagger. |
| `max_drop` | `30` | Maximum meters behind you a rider can sit. |

## Riders in front

| Key | Default | Description |
|---|---|---|
| `lead_gap` | `1.6` | Meters a lead rider sits in front of you. |
| `lead_lateral` | `0.8` | Meters the lead riders sit to the side of you (alternating sides). |
| `max_lead` | `8` | Meters: the whole group in front is squeezed into this distance ahead of you. |
| `lead_spread` | `1` | The number of riders in front changes by up to this many at once (0 = fixed). |
| `full_range` | `false` | `true` = anything from nobody in front (you lead) to everybody in front (you are last). |
| `formation_interval` | `45` | Average seconds between changes in the formation in front of you. |

## Turns and rotations

| Key | Default | Description |
|---|---|---|
| `rotate` | `true` | `false` = nobody takes the front on their own (gestures still work). |
| `pull_interval` | `60` | Average seconds between front rotations. |
| `pull_duration` | `18` | Seconds a pull lasts. |
| `pass_time` | `18` | Seconds an overtaking rider needs to get past the leader. |
| `rotation_rate` | `0.7` | m/s the riders move up or back when the line rotates. |
| `shuffle_interval` | `25` | Average seconds between position changes. |
| `turn_interval` | `1200` | Every this many seconds YOU take a turn at the front (0 = never). |

## Gestures (F-keys in game)

| Key | Default | Description |
|---|---|---|
| `hammer_time` | `180` | Seconds the HAMMER gesture (F4) drives a hard pace. |
| `toast_time` | `120` | Seconds the TOAST gesture (F7) makes everyone ease off. |
| `lead_time` | `120` | Seconds the BELL gesture (F8) keeps you at the front. The `attack` gesture (F1) means "come and pass me". |

## Motion and climbs

| Key | Default | Description |
|---|---|---|
| `climb_stretch` | `1.0` | How much the group stretches on climbs (only riders behind you stretch). |
| `wander_gap` | `0.3` | Meters: riders behind you drift randomly this far along the road around their slot (0 = off, 0.6-0.9 looks like a real peloton). |
| `wander_lateral` | `0.15` | Meters: the same sideways (0 = off, 0.25-0.35 is plenty). |
| `wander_time` | `7` | Seconds a drift takes to change direction (higher = slower, calmer). |
| `bot_gestures` | `true` | The riders give hand signals, never every time: **elbow flick** from the front rider of the 1-3 that peel off the front and give up their place (60%); **"I'm toast"** from the first of them that has reached the back (30%); **"Nice"** from the rider that comes through first after you rode at the front for 40+ s (60%); **bike bell** from a rider that comes through and takes the front (35%) or moves up past you (20%); and a random **Ride On** every `gesture_interval` s. A gesture is a `WAT_B_ACT` packet with the rider's position (see `blob_gestures.py`). |
| `gesture_interval` | `75` | Average seconds between two random "Ride On" gestures from a rider within 15 m of you (`0` = none). A rider gestures at most every 12 s, the group at most every 5 s. Test one right now with the chat command `.blob bot <elbow\|wave\|rideon\|nice\|bringit\|toast\|bell\|hammer>`: the rider nearest to you does it. |
| `gesture_chance` | `1.0` | Scales the chances of all the other signals above (`0` = none, `2` = twice as often). |

## Keeping riders apart

| Key | Default | Description |
|---|---|---|
| `keep_apart` | `0.85` | Meters of sideways clearance riders behind you keep from each other (0 = off). Nobody rides through anybody: they go around or wait. A sidestep never goes past the road edge or axis; the rider goes the other way or waits instead. |
| `keep_apart_long` | `1.75` | Meters along the road between the centres of two riders. Together with `keep_apart` it forms an ellipse around each rider. |

A rider blocked for more than 5 s is let through, so a rotation can never deadlock.

## Road, edges and axis

| Key | Default | Description |
|---|---|---|
| `road_half_width` | `3.0` | Meters: half the width of the drivable road around its centre (0 = the whole road logic is off). With `road_limits` `"auto"` it is only the on/off switch (anything above 0 = on; roads that are not in the table use at least 4.4 m). With `road_limits` `"off"` it is the real half width: when you ride near an edge the whole group slides sideways (at most 0.5 m/s), and every single rider is also clamped to the road. 3.0 fits a narrow bridge. |
| `road_limits` | `"auto"` | `"auto"`: the side of the road you may use depends on your direction of travel (forward = the `+` side of `roadPosition`, the other way = the `-` side; in the left-traffic worlds London, Yorkshire, Makuri and Scotland it is the other way round, `peloton.LEFT_TRAFFIC_COURSES`). The invisible wall next to the centre line and the outer edge come from real recorded rides (`data/road_limits.json` = `[inner, outer]` in metres per road and direction, rebuilt with `python3 scripts/gen_road_limits.py`; add `--xml <dir with worldN/road.xml>` to fill roads without recorded rides from the game's road widths, outer ≈ 0.77 × half the road width; the same run writes `data/road_width_profile.json`, how the width changes along ~10 roads with bridges / narrow stretches, which scales the outer edge by where you are on the road); `inner` is not always 0 (London: about 1.6 m). Roads that are not in the table use defaults (wall 1.0 m, edge 4.4 m). Wherever you ride yourself on a road widens these limits for the rest of the session, because you steer to the wall and to the edge on your own. `"off"`: the fixed zone of the two options below. |
| `max_road_shift` | `4.0` | (only with `road_limits` `"auto"`) Meters: the most the whole group may slide sideways off you to stay on the road. Ride in the middle and the shift is 0; ride at an edge or next to the wall and the group slides just far enough that its outermost rider is in line with you and the rest sits further in. `0` = never slide: the group is squeezed on that side instead (riders end up on top of each other). |
| `road_axis_limit` | `1.5` | (only with `road_limits` `"off"`) Meters from the road centre (`roadPosition` 10,000,000) to the road axis (the centre line). The group keeps this distance minus 0.25 m from it, because a rider beyond the axis is pulled back to the edge by the game (an "invisible wall"). 0 = no axis; that side ends at `road_half_width` like the other. |
| `road_axis_side` | `-1` | (only with `road_limits` `"off"`) Which side of the road centre the axis is on: `-1` = lower `roadPosition`, `+1` = higher `roadPosition`. If riders still veer towards the axis, flip the sign. |

## How the sideways offset reaches the game

| Key | Default | Description |
|---|---|---|
| `lateral_via` | `"both"` | `"xz"` = world position only (the game flattens a wide group to about 40% of its width), `"both"` = world position and `roadPosition` (recommended), `"road"` = `roadPosition` only. |
| `lateral_scale` | `1.0` | Multiplies every sideways offset on the way out (a last resort if the game still shows the group narrower than it is). |

## Example

```json
{
 "enabled": true,
 "player_id": 1,
 "riders": 24,
 "only_kitted": true,
 "lateral_via": "both",
 "road_half_width": 3.0,
 "road_limits": "auto",
 "max_road_shift": 4.0,
 "scatter": true,
 "scatter_width": 3.8,
 "keep_apart": 0.85,
 "keep_apart_long": 1.75
}
```

## FAQ

### Does `lateral_spacing` work when `scatter` is on?

Yes, but only as a lower bound, and with the default settings it has no effect.

- **Row layout (`scatter: false`):** `lateral_spacing` is the exact sideways pitch between riders in a row.
- **Scatter layout (`scatter: true`):** the minimum sideways distance between two riders level with each other is

  `max(0.9, 1.15 * keep_apart, scatter_side, lateral_spacing)`

  With the defaults this is `max(0.9, 0.98, 1.3, 0.95) = 1.3`, so `scatter_side` wins and `lateral_spacing: 0.95` changes nothing. It only starts to matter once it exceeds the other terms (above 1.3 here).

To change the sideways spread in scatter mode, tune `scatter_side`, `scatter_width` and `keep_apart` instead.
