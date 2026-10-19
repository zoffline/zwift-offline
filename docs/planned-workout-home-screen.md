# Scheduled Intervals workout on game home

## Reference

The response contract was supplied by a contributor in
https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6257306924.
`tests/fixtures/planned_workout_reference.json` preserves those response keys
with synthetic names, identifiers, dates, URL and workout metrics.
The subsequent native-client findings are documented in
https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6269590334:
the Windows CDN downloader sends no login cookie, and returning an object for
`carousels/for-you` allows the scheduled workout to appear there. This does not
establish that the separate Next Up card works.

The automatic Android import is separate (#543). This change reads the existing
selected provider, metadata and ZWO file; home-screen GETs do not synchronize,
change providers, write state or create another copy of the workout.

## API behavior

- `GET /api/workout/schedule/list` returns one schedule for the currently synced,
  today's cycling workout from the selected Intervals.icu provider.
- `GET /api/head-unit-bff/game-home` returns the reference `nextUp` card, using
  `source=SCHEDULED` and `provider=intervalsicu`.
- `GET /api/workout/workouts/{workoutId}` returns the matching workout summary.
- `GET /api/workout/workouts/{workoutId}/file.zwo` serves the original file bytes.
- `GET /tp-workouts/intervalsicu/{workoutId}.zwo` serves those same bytes under
  the CDN path used by the online reference, with a signed `token` query value.
- The four API endpoints use the existing authentication decorators and look
  up only the current player's workout. Multiplayer requires session/JWT;
  single-player keeps its existing selected anonymous profile.
- The CDN endpoint requires a valid signed URL instead of a session cookie.
  A workout UUID alone cannot authorize a download. File responses use
  `private, no-store`.
- `GET /api/head-unit-bff/carousels/for-you` returns `{}`, matching the shape
  found necessary in the contributor's native-client test.

The card's `entityId`, schedule's `workoutId` and summary's `workoutId` match.
The card's `sourceId` matches `scheduleId`. Separate deterministic UUIDs are
scoped to player/provider/event; the schedule ID also includes the local planned
day. A manifest GUID or zfile row ID is not reused as a workout UUID.

`workoutUri` and `workoutAssetUrl` now use the reference's URL structure:
`https://cdn.zwift.com/tp-workouts/intervalsicu/{workoutId}.zwo?token=...`.
The normal zoffline DNS redirect for `cdn.zwift.com` must point to this server.
The prior session/Bearer-protected API download remains available. The CDN
downloader needs no game cookie: its URL grants access to exactly one player's
current workout bytes until the end of the advertised local-day window. The
server signs the player ID, workout ID, expiry and SHA-256 using its existing
secret key and a purpose-specific salt. Changed bytes, removed metadata,
provider changes and stale planned dates revoke the old grant. A session for
another player cannot issue a grant for someone else's workout, but anyone who
possesses a still-valid signed URL can download its one file.

The URL is therefore private. CDN query values are redacted from the existing
zoffline access logger. Do not publish signed URLs in screenshots or captures.
Missing, malformed, modified or expired signatures return 403 without a login
redirect. The native client still needs to be tested for preserving the query
value and completing the download. Signing uses itsdangerous, already present
as a Flask dependency; no additional dependency is introduced.

## Date, provider and file handling

Only today's local planned date is advertised, consistent with the existing
Intervals importer, which selects one workout from today. Local midnight and
next midnight determine availability; daylight-saving changes produce 23/25-hour
windows correctly. If only an offset/UTC `start_date` exists, convert it to the
server's local day. The server's local timezone must match the existing import
configuration.

Missing/cleared metadata, stale/future dates, missing/unreadable/invalid files,
unsafe filenames and symlinks produce no card. Clearing metadata through the
existing completed-activity path therefore removes the card. TrainingPeaks,
manual library workouts and running workouts are outside this initial scope.
An explicit non-cycling `sport` query produces no cycling card.

Without a matching workout, the schedule and game-home endpoints retain the
previous empty-array response. `carousels/for-you` now returns an empty object;
the later native-client test identified this response shape as necessary for
the scheduled-workout fallback, although the captured online carousel itself
contained built-in workouts/pace partners.

## Summary values

Name/description come from existing metadata or the ZWO. Duration and the six
power-zone time percentages are derived from the ZWO, including intervals and
linear ramps. Free-ride/unknown power has no invented power distribution.
Difficulty is taken from the file when available, otherwise zero/unrated.
Planned `icu_training_load` is retained on the next Intervals sync and used for
`stressPoints`; legacy/missing load uses zero/unknown rather than a fitness
estimate. Existing metadata remains readable; resync obtains the added source
fields. Workout targets and content are not rewritten.

## Validation

```sh
python tests/test_planned_workouts.py
python tests/test_planned_workout_home_screen.py
```

The first suite uses only the standard library. The integration suite uses the
normal project dependencies, a real Flask test client, synthetic profiles and
temporary storage. It needs no network or production data. It checks the supplied
reference structure, original workout selection, linked definition/download,
stable IDs, session and Bearer authentication, single-player mode, player isolation, missing/stale
state, provider/sport handling and read-only GET behavior. CDN cases include
cookie-free signed download, expiry boundaries, changed-content revocation,
modified tokens, profile/workout scope, log redaction and unsigned denial.
The previous expected
failures have been replaced by positive contract checks.

The first private native Android 1.122.0 test with the API-style asset URL failed
to display the home card, although the workout selector worked and the client
received non-empty home/schedule responses. No native request for the asset was
observed. The contributor later confirmed the missing-cookie failure on Windows
and the required object response for the For You carousel. The signed CDN URL
and object response address those findings. Native Android display/launch and
query-token compatibility remain unverified. The PR stays Draft. Passing server
tests do not establish native-client compatibility.
