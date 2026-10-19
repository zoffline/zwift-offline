# Scheduled Intervals workout on game home

## Reference

The response contract was supplied by a contributor in
https://github.com/zoffline/zwift-offline/pull/544#issuecomment-6257306924.
`tests/fixtures/planned_workout_reference.json` preserves those response keys
with synthetic names, identifiers, dates, URL and workout metrics.

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
- All four endpoints use the existing authentication decorators and look
  up only the current player's workout. Multiplayer requires session/JWT
  authentication; single-player keeps its existing selected anonymous profile.
  Another player's workout
  ID is not an authorization token. Responses use `private, no-store`.

The card's `entityId`, schedule's `workoutId` and summary's `workoutId` match.
The card's `sourceId` matches `scheduleId`. Separate deterministic UUIDs are
scoped to player/provider/event; the schedule ID also includes the local planned
day. A manifest GUID or zfile row ID is not reused as a workout UUID.

`workoutUri` and `workoutAssetUrl` point to the authenticated local API asset
route, rather than the reference's online CDN file. Card, definition and asset
must still be tested together in the native Android client, particularly whether
its asset downloader supplies the game session/Bearer token for this API URL.
No unauthenticated CDN download route has been introduced.

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
previous empty-array response. `carousels/for-you` remains unchanged: the
reference confirms it contains built-in workouts/pace partners, not this card.

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
state, provider/sport handling and read-only GET behavior. The previous expected
failures have been replaced by positive contract checks.

Native Android display/launch verification is still pending. This PR remains a
draft for that test; the production deployment is not changed by the PR update.
